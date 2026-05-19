"""
ImageSource abstract base + DiscoveredImageRef value object.

Contract-compatible with cc-registry-v2/backend/app/sources/base.py — by
intent. Anyone who has written a custom source for the registry can copy
the file over (subclass shape and field names are identical) and drop
it in here as a CC_CATALOG_EXTRA_SOURCES entry.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DiscoveredImageRef:
    """One concrete image build a source has found for a CodeCollection."""

    ref: str                              # git ref (branch/tag name)
    ref_type: str                         # "branch" | "tag" | "release"
    commit: str                           # full sha of the cc commit
    rt_revision: str                      # full sha of the runtime
    image_tag: str                        # concrete OCI tag
    image_digest: Optional[str] = None    # sha256:... when available
    built_at: Optional[datetime] = None
    extra: dict = field(default_factory=dict)


class ImageSource(ABC):
    """Abstract source of CodeCollection image metadata.

    Implementations MUST be safe to call repeatedly from a scheduler
    (no global mutable state, raise on network/auth errors so the
    catalog poll task records them rather than silently dropping the
    sync).
    """

    name: str  # unique key registered in SOURCE_REGISTRY (e.g. "oci")

    @abstractmethod
    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]:
        """Return every image build currently known for this CC.

        `cc` is the raw mapping from config.yaml (slug, image_registry,
        etc.) so sources can read any source-specific fields without a
        separate config layer.
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
