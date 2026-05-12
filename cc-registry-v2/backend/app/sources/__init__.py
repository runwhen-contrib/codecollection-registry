"""
Image source plugin system.

Each `ImageSource` implementation knows how to discover the set of built
image refs for a given CodeCollection and pick the `latest` / `stable`
pointers. Built-in sources:

  - oci     – polls an OCI Distribution v2 registry (GHCR, GAR, Quay, ECR, ...)
  - static  – reads a hand-curated JSON file (useful for vendored / signed-off images)

Add a new source by writing a class that satisfies `ImageSource` and
registering it in `SOURCE_REGISTRY` (see `registry.py`).
"""
from .base import ImageSource, DiscoveredImageRef
from .registry import SOURCE_REGISTRY, get_source

__all__ = ["ImageSource", "DiscoveredImageRef", "SOURCE_REGISTRY", "get_source"]
