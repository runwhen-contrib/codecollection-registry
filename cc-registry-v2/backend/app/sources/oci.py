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
newest by ``built_at`` (manifest creation time fetched lazily — see the
tiebreak enrichment below). Lexicographic on ``image_tag`` only acts as
a last-resort tiebreak when we couldn't get a real timestamp.

`stable` resolution: prefer the highest semver-looking ref (`v\\d+...`) if
one exists; otherwise fall back to `latest`.

Why the built_at fetch matters: the canonical tag's ``cc_sha7`` prefix is
hex. ``main-1xxxxxx-...`` sorts ASCII-before ``main-dxxxxxx-...`` even
when the ``1xxxxxx`` push happened weeks later. Without an actual
timestamp the catalog would happily keep reporting a stale tag as
``latest`` — and JFrog-fronted catalogs (which cache /v2/.../tags/list)
amplify the staleness window.

NOTE: this source intentionally treats the registry as the source of
truth. It never mutates the registry; the cc-registry-v2 catalog is a
read-only mirror that powers PAPI lookups.
"""
from __future__ import annotations

import dataclasses
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

        # Shared session so the bearer dance, manifest GETs, and
        # config-blob fetches reuse the same TCP connection / token.
        with requests.Session() as session:
            tags = self._list_tags(session, host, repo)

            discovered: list[DiscoveredImageRef] = []
            for tag in tags:
                ref = self._parse_tag(tag)
                if ref is None:
                    continue
                discovered.append(ref)

            # When multiple canonical tags share a ref (e.g. two builds
            # of `main`) we MUST pick the newer one. Lex sort on
            # image_tag is wrong: cc_sha7 is hex, so `main-1...` sorts
            # before `main-d...` even when the `1...` push happened
            # later. Fetch the real build timestamp from the registry
            # so the existing (built_at, image_tag) sort picks the
            # right tag. We only enrich tags that actually compete —
            # single-tag-per-ref polls do zero extra HTTP work.
            discovered = self._enrich_built_at_for_tiebreaks(
                session, host, repo, discovered
            )

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

    def _list_tags(
        self,
        session: requests.Session,
        host: str,
        repo: str,
    ) -> list[str]:
        """Walk the v2 tags endpoint with Link-header pagination."""
        url = f"https://{host}/v2/{repo}/tags/list"
        params: dict = {"n": 200}
        all_tags: list[str] = []
        for _ in range(self.max_pages):
            resp = self._get_with_token(session, host, repo, url, params)
            resp.raise_for_status()
            payload = resp.json()
            all_tags.extend(payload.get("tags") or [])
            link = resp.headers.get("Link") or ""
            next_url = self._parse_next_link(link, host)
            if not next_url:
                break
            url, params = next_url, {}
        return all_tags

    def _get_with_token(
        self,
        session: requests.Session,
        host: str,
        repo: str,
        url: str,
        params: dict,
        accept: Optional[str] = None,
    ):
        """
        Some public registries (GHCR, Docker Hub) require an anonymous
        bearer token even for public reads. Handle the 401 -> token ->
        retry dance once.

        Pass ``accept`` to negotiate manifest content-types. The header
        is forwarded to the realm-retry leg so the bearer-token request
        doesn't return a different manifest type than the first call.
        """
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept
        resp = session.get(url, params=params, timeout=self.timeout, headers=headers)
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
        token_resp = session.get(realm, params=token_params, timeout=self.timeout)
        token_resp.raise_for_status()
        token = token_resp.json().get("token") or token_resp.json().get("access_token")
        if not token:
            return resp
        retry_headers = {"Authorization": f"Bearer {token}"}
        if accept:
            retry_headers["Accept"] = accept
        return session.get(
            url,
            params=params,
            timeout=self.timeout,
            headers=retry_headers,
        )

    # ------------------------------------------------------------------
    # tiebreak enrichment
    # ------------------------------------------------------------------
    def _enrich_built_at_for_tiebreaks(
        self,
        session: requests.Session,
        host: str,
        repo: str,
        refs: list[DiscoveredImageRef],
    ) -> list[DiscoveredImageRef]:
        """Set ``built_at`` on refs whose ``ref`` is shared by >1 image_tag.

        We only fetch manifests for the ambiguous subset because:
          - each enriched tag is up to two registry round-trips, and
          - when a ref has exactly one tag there's nothing to tiebreak.

        Failures are best-effort: one broken tag must not poison the
        whole sync, so any exception just leaves built_at=None and the
        downstream sort falls back to lex-on-image_tag.
        """
        by_ref: dict[str, list[DiscoveredImageRef]] = {}
        for r in refs:
            by_ref.setdefault(r.ref, []).append(r)
        ambiguous_tags = {
            r.image_tag
            for group in by_ref.values()
            if len(group) > 1
            for r in group
        }
        if not ambiguous_tags:
            return refs

        built_at_by_tag: dict[str, datetime] = {}
        for tag in ambiguous_tags:
            built_at = self._fetch_built_at_for_tag(session, host, repo, tag)
            if built_at is not None:
                built_at_by_tag[tag] = built_at

        if not built_at_by_tag:
            return refs

        return [
            dataclasses.replace(r, built_at=built_at_by_tag[r.image_tag])
            if r.image_tag in built_at_by_tag
            else r
            for r in refs
        ]

    def _fetch_built_at_for_tag(
        self,
        session: requests.Session,
        host: str,
        repo: str,
        tag: str,
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
        notably JFrog Artifactory's docker-remote setup — set
        ``Last-Modified`` to the local CACHE freshness time, not the
        upstream build time. That means whichever tag the sync happens
        to GET first or last would win the tiebreak based on
        cache-warmup order, completely unrelated to which image is
        actually newer. The OCI spec does not require ``Last-Modified``
        either, so taking the extra HTTP hop to ``config.digest`` is the
        only universally correct path.

        Returns None on any failure so the caller can fall back to its
        lex-only ordering rather than crash the sync.
        """
        manifest_url = f"https://{host}/v2/{repo}/manifests/{tag}"
        try:
            resp = self._get_with_token(
                session, host, repo, manifest_url, params={},
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
            return self._fetch_created_from_manifest(
                session, host, repo, manifest
            )
        except Exception:
            logger.debug(
                "oci source: failed to fetch built_at for %s:%s",
                repo,
                tag,
                exc_info=True,
            )
            return None

    def _fetch_created_from_manifest(
        self,
        session: requests.Session,
        host: str,
        repo: str,
        manifest: dict,
    ) -> Optional[datetime]:
        """Resolve a manifest doc to its config-blob ``created`` timestamp.

        Handles both single-platform manifests (``config.digest`` is on
        the top-level) and image indices / manifest lists (descend into
        the first child manifest — all platforms of a multi-arch build
        share the same buildkit timestamp).
        """
        config_digest: Optional[str] = None
        child_manifests = manifest.get("manifests")
        if child_manifests:
            child_digest = (child_manifests[0] or {}).get("digest")
            if not child_digest:
                return None
            child_url = f"https://{host}/v2/{repo}/manifests/{child_digest}"
            child_resp = self._get_with_token(
                session, host, repo, child_url, params={},
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
        blob_resp = self._get_with_token(
            session, host, repo, blob_url, params={}
        )
        if blob_resp.status_code != 200:
            return None
        created = blob_resp.json().get("created")
        if not created:
            return None
        # OCI uses RFC 3339; normalize "Z" for fromisoformat (<3.11).
        if created.endswith("Z"):
            created = created[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(created)
        except ValueError:
            return None

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
