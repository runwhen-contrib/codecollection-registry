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
import dataclasses
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.auth_dockerconfigjson import resolve_basic_pair_from_env
from app.sources.base import DiscoveredImageRef, ImageSource

logger = logging.getLogger(__name__)


TAG_PATTERN = re.compile(r"^(?P<ref>.+?)-(?P<cc_sha>[0-9a-f]{7,40})-(?P<rt_sha>[0-9a-f]{7,40})$")
SEMVER_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?")

# Accept headers we send when fetching an OCI manifest. Order matters: the
# registry returns the first content-type it supports, so we list OCI types
# before Docker ones. Without an explicit Accept the registry MAY return a
# legacy v1 manifest, which has no `config.digest` field we can follow.
_MANIFEST_ACCEPT = ",".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


class OCISource(ImageSource):
    name = "oci"

    # Match crane / go-containerregistry. GHCR tag listing breaks when n=200:
    # Link headers can carry n=0 and pagination loops over the same page.
    TAGS_PAGE_SIZE = 1000

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

        # Single httpx.Client so the bearer dance, manifest GETs, and
        # config-blob fetches reuse the same TCP connection / token.
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            tags = self._list_tags(client, host, repo, auth_header=auth_header, auth_mode=auth_mode)
            raw_set = set(tags)
            default_ref = cc.get("default_ref", "main")

            # Resolve moving pointers (`main`, `latest`, `pr-N`, …) up front.
            # The build workflow stamps OCI labels on every image so we can
            # derive the canonical tag from a single pointer manifest — no
            # digest scan across thousands of historical `main-*` builds.
            pointer_resolved: dict[str, DiscoveredImageRef] = {}
            for pointer in self._pointer_tags_for_ref(default_ref, raw_set, default_ref):
                winner = self._resolve_via_pointer(
                    client,
                    host,
                    repo,
                    pointer,
                    default_ref,
                    raw_set,
                    auth_header,
                    auth_mode,
                )
                if winner is not None:
                    pointer_resolved[default_ref] = winner
                    break

            discovered: list[DiscoveredImageRef] = []
            for tag in tags:
                parsed = self._parse_tag(tag)
                if parsed is None:
                    continue
                if parsed.ref in pointer_resolved:
                    continue
                discovered.append(parsed)

            discovered.extend(pointer_resolved.values())

            discovered = self._collapse_via_pointer_tags(
                client,
                host,
                repo,
                tags,
                discovered,
                cc,
                auth_header,
                auth_mode,
                pointer_resolved=pointer_resolved,
            )

            discovered = self._enrich_built_at_for_tiebreaks(
                client, host, repo, discovered, auth_header, auth_mode
            )

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

    @classmethod
    def _resolve_auth_header(cls, cc: dict) -> tuple[Optional[str], str]:
        """Build the Authorization header for outbound requests.

        Returns ``(header_value, mode)`` where ``mode`` is one of:

        * ``"bearer"``    — explicit Bearer token in token_env
        * ``"basic"``     — explicit Basic from user_env + pass_env
                            OR from a dockerconfigjson lookup
        * ``"anonymous"`` — no creds; caller will fall back to the
                            bearer-realm dance for public-GHCR-style reads

        Reads ``cc["_source_auth"]`` which the catalog poll layer
        synthesizes from ``SourceConfig.auth``. The mode is returned
        separately so the caller knows whether a subsequent 401 is a
        real auth failure (explicit) or a signal to start the dance
        (anonymous).

        dockerconfigjson note
        ---------------------
        When ``dockerconfigjson_env`` is set, the catalog opens the
        Docker config.json file pointed at by that env var and looks
        up the source's ``image_registry`` host in the file's ``auths``
        map. A hit returns Basic (treated identically to explicit
        ``user_env``+``pass_env`` from this point on — including the
        bearer-realm dance behavior). A miss falls back to anonymous
        — so a Secret that doesn't cover the target host degrades
        gracefully against public registries instead of hard-failing.
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

        dockerconfigjson_env = auth.get("dockerconfigjson_env")
        if dockerconfigjson_env:
            registry_url = cc.get("image_registry")
            if not registry_url:
                logger.warning(
                    "oci source: %s requested dockerconfigjson_env=%s but cc has no "
                    "image_registry to look up; falling back to anonymous",
                    slug,
                    dockerconfigjson_env,
                )
                return None, "anonymous"
            try:
                host, _ = cls._split_registry_url(registry_url)
            except ValueError:
                logger.warning(
                    "oci source: %s image_registry=%r could not be parsed; "
                    "dockerconfigjson lookup skipped, falling back to anonymous",
                    slug,
                    registry_url,
                )
                return None, "anonymous"
            pair = resolve_basic_pair_from_env(dockerconfigjson_env, host)
            if pair is not None:
                user, pwd = pair
                creds = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
                return f"Basic {creds}", "basic"
            logger.warning(
                "oci source: %s dockerconfigjson_env=%s yielded no creds for host %s; "
                "falling back to anonymous",
                slug,
                dockerconfigjson_env,
                host,
            )

        return None, "anonymous"

    def _list_tags(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        auth_header: Optional[str] = None,
        auth_mode: str = "anonymous",
    ) -> list[str]:
        """Walk /v2/<repo>/tags/list with Link-header pagination."""
        url = f"https://{host}/v2/{repo}/tags/list"
        params: dict = {"n": self.TAGS_PAGE_SIZE}
        all_tags: list[str] = []
        seen: set[str] = set()
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
            page_tags = payload.get("tags") or []
            new_tags = [tag for tag in page_tags if tag not in seen]
            if page_tags and not new_tags:
                break
            seen.update(new_tags)
            all_tags.extend(new_tags)
            link = resp.headers.get("Link") or ""
            next_url = self._parse_next_link(link, host)
            if not next_url:
                break
            url, params = self._next_tags_page_request(next_url)
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
        accept: Optional[str] = None,
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
        headers: dict[str, str] = {}
        if auth_header:
            headers["Authorization"] = auth_header
        if accept:
            headers["Accept"] = accept
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
        retry_headers = {"Authorization": f"Bearer {token}"}
        if accept:
            retry_headers["Accept"] = accept
        return client.get(url, params=params, headers=retry_headers)

    # ------------------------------------------------------------------
    # moving-pointer collapse (latest / branch aliases)
    # ------------------------------------------------------------------
    @staticmethod
    def _pointer_tags_for_ref(
        ref: str, raw_set: set[str], default_ref: str = "main"
    ) -> list[str]:
        """Moving aliases the build workflow publishes for ``ref``.

        Branch aliases (``:main``) are tried before ``:latest``. The build
        workflow updates ``:main`` on every main build (push or dispatch),
        while ``:latest`` is only repointed on push — so ``:latest`` can lag.
        """
        pointers: list[str] = []
        if ref in raw_set:
            pointers.append(ref)
        if ref == default_ref and "latest" in raw_set:
            pointers.append("latest")
        return pointers

    def _resolve_via_pointer(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        pointer_tag: str,
        ref_name: str,
        raw_set: set[str],
        auth_header: Optional[str],
        auth_mode: str,
        candidate_tags: Optional[list[str]] = None,
    ) -> Optional[DiscoveredImageRef]:
        """Map a moving pointer to its canonical tag in O(1) registry calls.

        Prefers OCI config labels (``io.runwhen.codecollection.commit``,
        ``io.runwhen.runtime.commit``) baked in by the build workflow. Falls
        back to a digest compare only when labels are missing (older images).
        """
        canonical_tag, built_at = self._canonical_tag_from_pointer_labels(
            client,
            host,
            repo,
            pointer_tag,
            ref_name,
            auth_header,
            auth_mode,
        )
        if canonical_tag:
            parsed = self._parse_tag(canonical_tag)
            if parsed is not None and parsed.ref == ref_name:
                if built_at is not None:
                    parsed = dataclasses.replace(parsed, built_at=built_at)
                logger.info(
                    "oci source: resolved %s via %s labels -> %s",
                    ref_name,
                    pointer_tag,
                    canonical_tag,
                )
                return parsed

        if not candidate_tags:
            return None

        pointer_digest = self._manifest_digest(
            client, host, repo, pointer_tag, auth_header, auth_mode
        )
        if not pointer_digest:
            return None
        for tag in candidate_tags:
            parsed = self._parse_tag(tag)
            if parsed is None or parsed.ref != ref_name:
                continue
            cand_digest = self._manifest_digest(
                client, host, repo, tag, auth_header, auth_mode
            )
            if cand_digest == pointer_digest:
                if built_at is not None:
                    parsed = dataclasses.replace(parsed, built_at=built_at)
                return parsed
        return None

    def _canonical_tag_from_pointer_labels(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        pointer_tag: str,
        ref_name: str,
        auth_header: Optional[str],
        auth_mode: str,
    ) -> tuple[Optional[str], Optional[datetime]]:
        """Read build labels from a pointer manifest and derive canonical tag."""
        manifest_url = f"https://{host}/v2/{repo}/manifests/{pointer_tag}"
        try:
            resp = self._get_with_auth(
                client,
                host,
                repo,
                manifest_url,
                params={},
                auth_header=auth_header,
                auth_mode=auth_mode,
                accept=_MANIFEST_ACCEPT,
            )
            if resp.status_code != 200:
                return None, None
            manifest = resp.json()
            blob = self._fetch_config_blob_from_manifest(
                client, host, repo, manifest, auth_header, auth_mode
            )
            if blob is None:
                return None, None
            built_at = self._parse_created_timestamp(blob.get("created"))
            labels = (blob.get("config") or {}).get("Labels") or {}
            cc_sha = labels.get("io.runwhen.codecollection.commit") or labels.get(
                "org.opencontainers.image.revision"
            )
            rt_sha = labels.get("io.runwhen.runtime.commit")
            if not cc_sha or not rt_sha:
                return None, built_at
            canonical = f"{ref_name}-{cc_sha[:7]}-{rt_sha[:7]}"
            return canonical, built_at
        except Exception:
            logger.debug(
                "oci source: failed to read labels from pointer %s:%s",
                repo,
                pointer_tag,
                exc_info=True,
            )
            return None, None

    def _collapse_via_pointer_tags(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        raw_tags: list[str],
        refs: list[DiscoveredImageRef],
        cc: dict,
        auth_header: Optional[str],
        auth_mode: str,
        pointer_resolved: Optional[dict[str, DiscoveredImageRef]] = None,
    ) -> list[DiscoveredImageRef]:
        """Keep one canonical tag per ref using registry pointer aliases."""
        raw_set = set(raw_tags)
        default_ref = cc.get("default_ref", "main")
        already_resolved = pointer_resolved or {}
        by_ref: dict[str, list[DiscoveredImageRef]] = {}
        for r in refs:
            by_ref.setdefault(r.ref, []).append(r)

        collapsed: list[DiscoveredImageRef] = []
        for ref, group in by_ref.items():
            if ref in already_resolved:
                collapsed.append(already_resolved[ref])
                continue
            if len(group) == 1:
                collapsed.append(group[0])
                continue

            winner: Optional[DiscoveredImageRef] = None
            group_tags = [r.image_tag for r in group]
            for pointer in self._pointer_tags_for_ref(ref, raw_set, default_ref):
                winner = self._resolve_via_pointer(
                    client,
                    host,
                    repo,
                    pointer,
                    ref,
                    raw_set,
                    auth_header,
                    auth_mode,
                    candidate_tags=group_tags,
                )
                if winner is not None:
                    break

            if winner is None:
                collapsed.extend(group)
            else:
                collapsed.append(winner)

        return collapsed

    def _manifest_digest(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        tag: str,
        auth_header: Optional[str],
        auth_mode: str,
    ) -> Optional[str]:
        """Best-effort manifest digest for an OCI tag (one GET, no blob fetch)."""
        manifest_url = f"https://{host}/v2/{repo}/manifests/{tag}"
        try:
            resp = self._get_with_auth(
                client,
                host,
                repo,
                manifest_url,
                params={},
                auth_header=auth_header,
                auth_mode=auth_mode,
                accept=_MANIFEST_ACCEPT,
            )
            if resp.status_code != 200:
                return None
            digest = resp.headers.get("Docker-Content-Digest")
            if digest:
                return digest
            manifest = resp.json()
            child_manifests = manifest.get("manifests")
            if child_manifests:
                return (child_manifests[0] or {}).get("digest")
            return None
        except Exception:
            logger.debug(
                "oci source: failed to fetch digest for %s:%s",
                repo,
                tag,
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # tiebreak enrichment
    # ------------------------------------------------------------------
    def _enrich_built_at_for_tiebreaks(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        refs: list[DiscoveredImageRef],
        auth_header: Optional[str],
        auth_mode: str,
    ) -> list[DiscoveredImageRef]:
        """Set ``built_at`` on refs whose ``ref`` is shared by >1 image_tag.

        We only fetch manifests for the ambiguous subset because:
          - each enriched tag is up to two registry round-trips, and
          - when a ref has exactly one tag, there's nothing to tiebreak.

        Failures are best-effort: a single broken tag must not poison the
        whole poll, so any exception just leaves built_at=None and the
        downstream sort falls back to lex-on-image_tag.
        """
        by_ref: dict[str, list[DiscoveredImageRef]] = {}
        for r in refs:
            by_ref.setdefault(r.ref, []).append(r)
        ambiguous_tags = {r.image_tag for group in by_ref.values() if len(group) > 1 for r in group}
        if not ambiguous_tags:
            return refs

        built_at_by_tag: dict[str, datetime] = {}
        for tag in ambiguous_tags:
            built_at = self._fetch_built_at_for_tag(client, host, repo, tag, auth_header, auth_mode)
            if built_at is not None:
                built_at_by_tag[tag] = built_at

        if not built_at_by_tag:
            return refs

        return [
            (
                dataclasses.replace(r, built_at=built_at_by_tag[r.image_tag])
                if r.image_tag in built_at_by_tag
                else r
            )
            for r in refs
        ]

    def _fetch_built_at_for_tag(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        tag: str,
        auth_header: Optional[str],
        auth_mode: str,
    ) -> Optional[datetime]:
        """Return the build timestamp of an OCI image, best-effort.

        Strategy: GET ``/v2/<repo>/manifests/<tag>`` with Accept headers,
        descend into the manifest's ``config.digest`` blob (or, for OCI
        image indices, the first child platform manifest's config blob),
        and read its ``created`` field. That field is always populated by
        buildkit / docker buildx and is the only OCI-spec'd source of
        truth for when the image was actually built.

        We deliberately do NOT use the ``Last-Modified`` HTTP header,
        even though many registries set it. Caching proxies — most
        notably JFrog Artifactory's docker-remote setup which is the
        whole reason this code exists — set ``Last-Modified`` to the
        local CACHE freshness time, not the upstream build time. That
        means whichever tag the poll happens to GET first or last would
        win the tiebreak based on cache-warmup order, completely
        unrelated to which image is actually newer. The OCI spec does
        not require ``Last-Modified`` either, so taking the extra HTTP
        hop to ``config.digest`` is the only universally correct path.

        Returns None on any failure so the caller can fall back to its
        lex-only ordering rather than crash the poll.
        """
        manifest_url = f"https://{host}/v2/{repo}/manifests/{tag}"
        try:
            resp = self._get_with_auth(
                client,
                host,
                repo,
                manifest_url,
                params={},
                auth_header=auth_header,
                auth_mode=auth_mode,
                accept=_MANIFEST_ACCEPT,
            )
            if resp.status_code != 200:
                logger.debug(
                    "oci source: manifest GET %s:%s returned %s",
                    repo,
                    tag,
                    resp.status_code,
                )
                return None

            manifest = resp.json()
            blob = self._fetch_config_blob_from_manifest(
                client, host, repo, manifest, auth_header, auth_mode
            )
            if blob is None:
                return None
            return self._parse_created_timestamp(blob.get("created"))
        except Exception:
            logger.debug(
                "oci source: failed to fetch built_at for %s:%s",
                repo,
                tag,
                exc_info=True,
            )
            return None

    def _fetch_config_blob_from_manifest(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        manifest: dict,
        auth_header: Optional[str],
        auth_mode: str,
    ) -> Optional[dict]:
        """Return the image config blob JSON for a manifest document."""
        config_digest: Optional[str] = None
        child_manifests = manifest.get("manifests")
        if child_manifests:
            child_digest = (child_manifests[0] or {}).get("digest")
            if not child_digest:
                return None
            child_url = f"https://{host}/v2/{repo}/manifests/{child_digest}"
            child_resp = self._get_with_auth(
                client,
                host,
                repo,
                child_url,
                params={},
                auth_header=auth_header,
                auth_mode=auth_mode,
                accept=_MANIFEST_ACCEPT,
            )
            if child_resp.status_code != 200:
                return None
            config_digest = (child_resp.json().get("config") or {}).get("digest")
        else:
            config_digest = (manifest.get("config") or {}).get("digest")

        if not config_digest:
            return None

        blob_url = f"https://{host}/v2/{repo}/blobs/{config_digest}"
        blob_resp = self._get_with_auth(
            client,
            host,
            repo,
            blob_url,
            params={},
            auth_header=auth_header,
            auth_mode=auth_mode,
        )
        if blob_resp.status_code != 200:
            return None
        return blob_resp.json()

    @staticmethod
    def _parse_created_timestamp(created: Optional[str]) -> Optional[datetime]:
        if not created:
            return None
        if created.endswith("Z"):
            created = created[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(created)
        except ValueError:
            return None

    def _fetch_created_from_manifest(
        self,
        client: httpx.Client,
        host: str,
        repo: str,
        manifest: dict,
        auth_header: Optional[str],
        auth_mode: str,
    ) -> Optional[datetime]:
        """Resolve a manifest doc to its config-blob ``created`` timestamp."""
        blob = self._fetch_config_blob_from_manifest(
            client, host, repo, manifest, auth_header, auth_mode
        )
        if blob is None:
            return None
        return self._parse_created_timestamp(blob.get("created"))

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

    @classmethod
    def _next_tags_page_request(cls, next_url: str) -> tuple[str, dict]:
        """Turn a registry ``Link: ... rel=next`` URL into the next GET.

        GHCR has been observed to emit ``n=0`` on subsequent pages when the
        initial request used ``n=200``, which makes pagination loop forever.
        We always send our own ``n=TAGS_PAGE_SIZE`` and carry forward only
        the ``last`` cursor — matching crane / go-containerregistry.
        """
        parsed = urlparse(next_url)
        query = parse_qs(parsed.query)
        params: dict = {"n": cls.TAGS_PAGE_SIZE}
        last_values = query.get("last") or []
        if last_values:
            params["last"] = last_values[0]
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return base_url, params

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
