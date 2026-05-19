"""
Image source plugin system.

Mirrors the contract used in cc-registry-v2/backend/app/sources/. We do
not import from that package because we don't want a hard runtime
dependency on the registry — but the shape and semantics are identical:

    refs   = source.discover_refs(cc)
    latest = source.resolve_latest(cc, refs)
    stable = source.resolve_stable(cc, refs)

Built-in source types:

  - oci      polls an OCI Distribution v2 registry (GHCR / GAR / ECR / Quay / Harbor / Artifactory)
  - static   reads refs from a JSON file (air-gap / pinning / tests)
  - upstream reads /api/v1/catalog from another catalog (this service or cc-registry-v2)

Custom sources can be added via the CC_CATALOG_EXTRA_SOURCES env var (a
colon-separated list of import paths, each module exposing a top-level
`SOURCE` of type `ImageSource`).
"""
from app.sources.base import DiscoveredImageRef, ImageSource
from app.sources.registry import SOURCE_REGISTRY, get_source

__all__ = ["DiscoveredImageRef", "ImageSource", "SOURCE_REGISTRY", "get_source"]
