"""
ImageSource abstract base + DiscoveredImageRef value object.

The image-sync task drives sources in three phases:

    refs   = source.discover_refs(cc)
    latest = source.resolve_latest(cc, refs)
    stable = source.resolve_stable(cc, refs)

`discover_refs` is the only mandatory remote call; the resolvers should be
pure functions over the discovered list so they're easy to unit test.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DiscoveredImageRef:
    """
    One concrete image build that a source has found for a CodeCollection.

    A "ref" maps 1:1 to an OCI image tag we will track in the catalog. For
    example a CC built from `main` at commit `c1a2b3d…` against a runtime
    at `e4f5a6b…` produces a single `DiscoveredImageRef`:

        ref          = "main"
        ref_type     = "branch"
        commit       = "c1a2b3d…"
        rt_revision  = "e4f5a6b…"
        image_tag    = "main-c1a2b3d-e4f5a6b"
    """
    ref: str                           # git ref this build represents (branch/tag name)
    ref_type: str                      # "branch" | "tag" | "release"
    commit: str                        # full sha of the codecollection commit
    rt_revision: str                   # full sha of the runtime used at build time
    image_tag: str                     # concrete OCI tag (pullable)
    image_digest: Optional[str] = None # sha256:... when available from manifest
    built_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)  # source-specific overflow (free form)


class ImageSource(ABC):
    """
    Abstract source of CodeCollection image metadata.

    Subclasses must be safe to call on a schedule from a Celery worker:
    no global mutable state, network errors should raise rather than
    swallow so the sync task can record them.
    """

    name: str  # unique key registered in SOURCE_REGISTRY (e.g. "oci")

    @abstractmethod
    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]:
        """
        Return every image build currently known for this CodeCollection.

        `cc` is the raw mapping from `codecollections.yaml` (slug, git_url,
        image_registry, image_source, etc.) so a source can read any
        source-specific fields it needs without a separate config layer.
        """
        ...

    @abstractmethod
    def resolve_latest(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        """Return the image_tag that should be considered `latest`, or None."""
        ...

    @abstractmethod
    def resolve_stable(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        """Return the image_tag that should be considered `stable`, or None."""
        ...
