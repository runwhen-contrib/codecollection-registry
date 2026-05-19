"""
OCI Distribution v2 image source.

Ported from cc-registry-v2/backend/app/sources/oci.py with three small
differences:

  - Uses httpx instead of requests so we keep one HTTP client across the
    whole service (httpx is already a dep via FastAPI/test fixtures).
  - Reads source-level auth (`token_env` OR `user_env`+`pass_env`) from
    a synthetic ``_source_auth`` key injected by the catalog poll layer.
    Supports anonymous, Bearer, and HTTP Basic against any OCI registry
    (GHCR, JFrog, Artifactory, Harbor, GAR, ECR, Quay).
  - When credentials are explicit, sends them up-front and skips the
    anonymous-bearer-realm dance on 401 (a 401 against explicit creds is
    a real auth error and shouldn't be papered over by re-authing).

Tag schema (identical to the registry):

    <ref>-<cc_sha[:7,40]>-<rt_sha[:7,40]>

Tags that don't match the schema are silently ignored — that lets
floating tags like `latest`, `main`, `<date>` coexist on the same repo
without confusing the catalog.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.sources.base import DiscoveredImageRef, ImageSource

logger = logging.getLogger(__name__)


TAG_PATTERN = re.compile(r"^(?P<ref>.+?)-(?P<cc_sha>[0-9a-f]{7,40})-(?P<rt_sha>[0-9a-f]{7,40})$")
SEMVER_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?")


class OCISource(ImageSource):
    name = "oci"

    def __init__(self, timeout: float = 10.0, max_pages: int = 50):
        # Defensive caps. A misbehaving registry shouldn't be able to
        # hang the scheduler thread or page forever.
        self.timeout = timeout
        self.max_pages = max_pages

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]:
        registry_url = cc.get("image_registry")
        if not registry_url:
            logger.warning(
                "oci source skipping %s: no image_registry configured",
                cc.get("slug"),
            )
            return []

        host, repo = self._split_registry_url(registry_url)
        auth_header, auth_mode = self._resolve_auth_header(cc)
        tags = self._list_tags(host, repo, auth_header=auth_header, auth_mode=auth_mode)

        discovered: list[DiscoveredImageRef] = []
        for tag in tags:
            parsed = self._parse_tag(tag)
            if parsed is None:
                continue
            discovered.append(parsed)
        logger.info(
            "oci source: %s -> %d tags, %d matched build schema",
            cc.get("slug"),
            len(tags),
            len(discovered),
        )
        return discovered

    def resolve_latest(self, cc: dict, refs: list[DiscoveredImageRef]) -> Optional[str]:
        default_ref = cc.get("default_ref", "main")
        candidates = [r for r in refs if r.ref == default_ref]
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: (
                r.built_at or datetime.min.replace(tzinfo=timezone.utc),
                r.image_tag,
            )
        )
        return candidates[-1].image_tag

    def resolve_stable(self, cc: dict, refs: list[DiscoveredImageRef]) -> Optional[str]:
        semver_refs = [r for r in refs if SEMVER_TAG.match(r.ref)]
        if semver_refs:
            semver_refs.sort(key=lambda r: self._semver_key(r.ref))
            return semver_refs[-1].image_tag
        return self.resolve_latest(cc, refs)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _split_registry_url(url: str) -> tuple[str, str]:
        """`ghcr.io/runwhen-contrib/foo` -> (`ghcr.io`, `runwhen-contrib/foo`)."""
        url = url.strip().rstrip("/")
        if "/" not in url:
            raise ValueError(f"image_registry must include a repo path: {url}")
        host, _, repo = url.partition("/")
        return host, repo

    @staticmethod
    def _resolve_auth_header(cc: dict) -> tuple[Optional[str], str]:
        """Build the Authorization header for outbound requests.

        Returns ``(header_value, mode)`` where ``mode`` is one of:

        * ``"bearer"``    — explicit Bearer token in token_env
        * ``"basic"``     — explicit Basic from user_env + pass_env
        * ``"anonymous"`` — no creds; caller will fall back to the
                            bearer-realm dance for public-GHCR-style reads

        Reads ``cc["_source_auth"]`` which the catalog poll layer
        synthesizes from ``SourceConfig.auth``. The mode is returned
        separately so the caller knows whether a subsequent 401 is a
        real auth failure (explicit) or a signal to start the dance
        (anonymous).
        """
        auth = cc.get("_source_auth") or {}
        slug = cc.get("slug")

        token_env = auth.get("token_env")
        if token_env:
            token = os.environ.get(token_env)
            if token:
                return f"Bearer {token}", "bearer"
            logger.warning(
                "oci source: %s requested token_env=%s but env var is empty",
                slug,
                token_env,
            )

        user_env = auth.get("user_env")
        pass_env = auth.get("pass_env")
        if user_env and pass_env:
            user = os.environ.get(user_env)
            pwd = os.environ.get(pass_env)
            if user and pwd:
                creds = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
                return f"Basic {creds}", "basic"
            logger.warning(
                "oci source: %s requested user_env=%s pass_env=%s but one/both are empty",
                slug,
                user_env,
                pass_env,
            )

        return None, "anonymous"

    def _list_tags(
        self,
        host: str,
        repo: str,
        auth_header: Optional[str] = None,
        auth_mode: str = "anonymous",
    ) -> list[str]:
        """Walk /v2/<repo>/tags/list with Link-header pagination."""
        url = f"https://{host}/v2/{repo}/tags/list"
        params: dict = {"n": 200}
        all_tags: list[str] = []
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for _ in range(self.max_pages):
                resp = self._get_with_auth(
                    client,
                    host,
                    repo,
                    url,
                    params,
                    auth_header=auth_header,
                    auth_mode=auth_mode,
                )
                resp.raise_for_status()
                payload = resp.json()
                all_tags.extend(payload.get("tags") or [])
                link = resp.headers.get("Link") or ""
                next_url = self._parse_next_link(link, host)
                if not next_url:
                    break
                url, params = next_url, {}
        return all_tags

    def _get_with_auth(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        url: str,
        params: dict,
        auth_header: Optional[str] = None,
        auth_mode: str = "anonymous",
    ) -> httpx.Response:
        """Send the request with whatever auth we have; on 401 with a
        Bearer-realm WWW-Authenticate header, do the realm-token dance
        — but only when it could actually succeed for our auth mode:

        ============  ============================  ====================================
        auth_mode     first request                 behaviour on 401 + Bearer realm
        ============  ============================  ====================================
        anonymous     no Authorization header       dance anonymously (public GHCR pattern)
        basic         Authorization: Basic <b64>    dance with the SAME Basic header on
                                                    the realm endpoint, then retry with
                                                    the minted Bearer token (JFrog /
                                                    Docker Hub / Quay / Artifactory)
        bearer        Authorization: Bearer <tok>   surface the 401 — a pre-minted token
                                                    can't be re-minted, so 401 means
                                                    "wrong/expired/under-scoped token"
        ============  ============================  ====================================

        Why exchange Basic for a Bearer instead of just sending Basic on
        the data plane? Many OCI registries (notably JFrog Artifactory's
        canonical `/v2/<repo>/...` path, Docker Hub, Quay) refuse Basic
        directly there and only accept it at the token endpoint to mint
        a scoped Bearer. JFrog's REST shim at
        `/artifactory/api/docker/<repo>/v2/...` does take Basic directly,
        but we use the canonical OCI path so we have to dance.
        """
        headers = {"Authorization": auth_header} if auth_header else {}
        resp = client.get(url, params=params, headers=headers)
        if resp.status_code != 401:
            return resp

        # Explicit Bearer rejected -> real auth failure, surface it.
        if auth_mode == "bearer":
            return resp

        www_auth = resp.headers.get("WWW-Authenticate", "")
        m = re.search(r'Bearer realm="([^"]+)"', www_auth)
        realm = m.group(1) if m else None
        if not realm:
            # Registry isn't asking for the realm dance — nothing we
            # can do; return the original 401 for the caller to raise.
            return resp
        service_match = re.search(r'service="([^"]+)"', www_auth)
        token_params = {"scope": f"repository:{repo}:pull"}
        if service_match:
            token_params["service"] = service_match.group(1)

        # Forward Basic credentials (if any) to the token endpoint.
        # Anonymous registries (public GHCR) mint a scoped token without
        # auth; private ones (JFrog, etc.) require Basic here.
        token_headers = {"Authorization": auth_header} if auth_mode == "basic" else {}
        token_resp = client.get(realm, params=token_params, headers=token_headers)
        token_resp.raise_for_status()
        token = token_resp.json().get("token") or token_resp.json().get("access_token")
        if not token:
            return resp
        return client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )

    @staticmethod
    def _parse_next_link(link_header: str, host: str) -> Optional[str]:
        # Link: </v2/.../tags/list?last=foo&n=200>; rel="next"
        m = re.search(r'<([^>]+)>;\s*rel="next"', link_header or "")
        if not m:
            return None
        path = m.group(1)
        if path.startswith("http"):
            return path
        return f"https://{host}{path}"

    @staticmethod
    def _parse_tag(tag: str) -> Optional[DiscoveredImageRef]:
        m = TAG_PATTERN.match(tag)
        if not m:
            return None
        ref = m.group("ref")
        return DiscoveredImageRef(
            ref=ref,
            ref_type=_classify_ref(ref),
            commit=m.group("cc_sha"),
            rt_revision=m.group("rt_sha"),
            image_tag=tag,
        )

    @staticmethod
    def _semver_key(ref: str) -> tuple:
        ref = ref.lstrip("v")
        parts = re.split(r"[.\-+]", ref)
        key: list = []
        for p in parts:
            if p.isdigit():
                key.append((0, int(p)))
            else:
                key.append((1, p))
        return tuple(key)


def _classify_ref(ref: str) -> str:
    if ref.startswith("pr-"):
        return "branch"
    if SEMVER_TAG.match(ref):
        return "tag"
    return "branch"
