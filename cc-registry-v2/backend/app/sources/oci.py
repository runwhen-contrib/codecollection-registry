"""
OCI Distribution v2 image source.

Lists every tag in a public OCI repository and shapes each into a
`DiscoveredImageRef`. The expected tag schema matches the one emitted by
the codecollection build workflows in this design:

    <sanitized-ref>-<cc_sha[:7]>-<rt_sha[:7]>

For example:

    main-c1a2b3d-e4f5a6b
    pr-42-9988aabb-e4f5a6b
    v1.2.0-aabbccd-e4f5a6b

`latest` resolution: among tags whose ref-portion is `main`, pick the
newest (by manifest `created` if available, otherwise the lexicographically
last — tags are time-monotonic given the sha suffix).

`stable` resolution: prefer the highest semver-looking ref (`v\\d+...`) if
one exists; otherwise fall back to `latest`.

NOTE: this source intentionally treats the registry as the source of
truth. It never mutates the registry; the cc-registry-v2 catalog is a
read-only mirror that powers PAPI lookups.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from .base import DiscoveredImageRef, ImageSource

logger = logging.getLogger(__name__)


# Tag schema: <ref>-<cc_sha7>-<rt_sha7>. The ref portion may itself contain
# hyphens (e.g. "pr-42"), so we anchor on the two trailing 7-char sha groups.
TAG_PATTERN = re.compile(
    r"^(?P<ref>.+?)-(?P<cc_sha>[0-9a-f]{7,40})-(?P<rt_sha>[0-9a-f]{7,40})$"
)

SEMVER_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?")


class OCISource(ImageSource):
    name = "oci"

    def __init__(self, timeout: float = 10.0, max_pages: int = 50):
        # Defensive caps: a single CC shouldn't paginate forever, and
        # individual HTTP calls shouldn't hang a Celery worker.
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
        tags = self._list_tags(host, repo)

        discovered: list[DiscoveredImageRef] = []
        for tag in tags:
            ref = self._parse_tag(tag)
            if ref is None:
                continue
            discovered.append(ref)
        logger.info(
            "oci source: %s -> %d tags, %d matched build schema",
            cc.get("slug"),
            len(tags),
            len(discovered),
        )
        return discovered

    def resolve_latest(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        # Prefer the newest build of the configured default branch.
        default_ref = cc.get("default_ref", "main")
        candidates = [r for r in refs if r.ref == default_ref]
        if not candidates:
            return None
        candidates.sort(
            key=lambda r: (r.built_at or datetime.min.replace(tzinfo=timezone.utc), r.image_tag)
        )
        return candidates[-1].image_tag

    def resolve_stable(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        # Highest semver-looking ref wins; fall back to latest.
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
        """
        "ghcr.io/runwhen-contrib/rw-cli-codecollection"
            -> ("ghcr.io", "runwhen-contrib/rw-cli-codecollection")
        """
        url = url.strip().rstrip("/")
        if "/" not in url:
            raise ValueError(f"image_registry must include a repo path: {url}")
        host, _, repo = url.partition("/")
        return host, repo

    def _list_tags(self, host: str, repo: str) -> list[str]:
        """Walk the v2 tags endpoint with Link-header pagination."""
        url = f"https://{host}/v2/{repo}/tags/list"
        params = {"n": 200}
        all_tags: list[str] = []
        for _ in range(self.max_pages):
            resp = self._get_with_token(host, repo, url, params)
            resp.raise_for_status()
            payload = resp.json()
            all_tags.extend(payload.get("tags") or [])
            link = resp.headers.get("Link") or ""
            next_url = self._parse_next_link(link, host)
            if not next_url:
                break
            url, params = next_url, {}
        return all_tags

    def _get_with_token(self, host: str, repo: str, url: str, params: dict):
        """
        Some public registries (GHCR, Docker Hub) require an anonymous
        bearer token even for public reads. Handle the 401 -> token ->
        retry dance once.
        """
        resp = requests.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 401:
            return resp

        www_auth = resp.headers.get("WWW-Authenticate", "")
        m = re.search(r'Bearer realm="([^"]+)"', www_auth)
        realm = m.group(1) if m else None
        if not realm:
            return resp  # nothing we can do, let caller raise
        service_match = re.search(r'service="([^"]+)"', www_auth)
        token_params = {
            "scope": f"repository:{repo}:pull",
        }
        if service_match:
            token_params["service"] = service_match.group(1)
        token_resp = requests.get(realm, params=token_params, timeout=self.timeout)
        token_resp.raise_for_status()
        token = token_resp.json().get("token") or token_resp.json().get("access_token")
        if not token:
            return resp
        return requests.get(
            url,
            params=params,
            timeout=self.timeout,
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
        # Cheap semver sort key; non-numeric suffixes sort last.
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
