"""
Upstream-catalog source.

Reads `/api/v1/catalog/codecollections/{slug}/refs` from another catalog
(this service, or cc-registry-v2 itself) and re-publishes the rows
verbatim. Lets a customer's self-hosted instance ride on RunWhen's
public catalog rather than polling GHCR themselves.

Source-specific config (set via `options.upstream_url` on the source
block in config.yaml, or per-CC `upstream_url`):

    sources:
      - name: runwhen-public
        type: upstream
        options:
          upstream_url: https://registry.runwhen.com
        codecollections:
          - slug: rw-cli-codecollection
          - slug: rw-public-codecollection

The plugin trusts the upstream's `is_latest` and `is_prerelease` flags,
falling back to the same logic the OCI source uses if the upstream is
old enough that those fields aren't populated.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.sources.base import DiscoveredImageRef, ImageSource

logger = logging.getLogger(__name__)


class UpstreamCatalogSource(ImageSource):
    name = "upstream"

    # The source instance is shared across CCs in one poll cycle, so the
    # upstream URL can come either from the source's `options` block or
    # per-CC. Per-CC wins.
    def __init__(self, default_upstream_url: Optional[str] = None, timeout: float = 15.0):
        self.default_upstream_url = default_upstream_url
        self.timeout = timeout

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]:
        upstream_url = self._resolve_upstream(cc)
        if not upstream_url:
            logger.warning(
                "upstream source skipping %s: no upstream_url configured",
                cc.get("slug"),
            )
            return []

        slug = cc.get("slug")
        url = (
            f"{upstream_url.rstrip('/')}/api/v1/catalog/codecollections/{slug}/refs"
        )
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                logger.info(
                    "upstream source: %s not found on %s (skipping)", slug, upstream_url
                )
                return []
            resp.raise_for_status()
            payload = resp.json()

        refs: list[DiscoveredImageRef] = []
        for row in payload:
            built_at = self._parse_iso(row.get("image_built_at"))
            refs.append(
                DiscoveredImageRef(
                    ref=row.get("ref") or "",
                    ref_type=row.get("ref_type") or "branch",
                    commit=row.get("commit_hash") or "",
                    rt_revision=row.get("rt_revision") or "",
                    image_tag=row.get("image_tag") or "",
                    image_digest=row.get("image_digest"),
                    built_at=built_at,
                    extra={"_upstream_is_latest": bool(row.get("is_latest"))},
                )
            )
        logger.info(
            "upstream source: %s -> %d refs from %s",
            slug, len(refs), upstream_url,
        )
        return refs

    def resolve_latest(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        # Prefer the upstream's `is_latest` flag — they already ran the
        # math (which may include manifest dates we can't see).
        flagged = [r for r in refs if r.extra.get("_upstream_is_latest")]
        if flagged:
            return flagged[0].image_tag

        default_ref = cc.get("default_ref", "main")
        candidates = [r for r in refs if r.ref == default_ref]
        if not candidates:
            return None
        # built_at from `_parse_iso` is timezone-aware; the fallback for
        # rows that lack it must match or Python raises TypeError when the
        # sort compares an aware datetime to a naive one. Mirrors the
        # pattern used in app.sources.oci.
        epoch_min = datetime.min.replace(tzinfo=timezone.utc)
        candidates.sort(
            key=lambda r: (r.built_at or epoch_min, r.image_tag)
        )
        return candidates[-1].image_tag

    def resolve_stable(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        # The upstream catalog's `/refs` doesn't currently expose a
        # `is_stable` flag, so we re-derive: highest semver-looking ref.
        from app.sources.oci import SEMVER_TAG  # avoid circular import at module load
        semver_refs = [r for r in refs if SEMVER_TAG.match(r.ref)]
        if not semver_refs:
            return self.resolve_latest(cc, refs)
        from app.sources.oci import OCISource
        semver_refs.sort(key=lambda r: OCISource._semver_key(r.ref))
        return semver_refs[-1].image_tag

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _resolve_upstream(self, cc: dict) -> Optional[str]:
        return cc.get("upstream_url") or self.default_upstream_url

    @staticmethod
    def _parse_iso(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
