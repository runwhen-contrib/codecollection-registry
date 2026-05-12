"""
Pydantic response models for the PAPI-facing CodeCollection catalog API.

These shapes are part of the contract PAPI (and any other consumer)
depends on. Keep field names stable; add new fields rather than renaming.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImageRef(BaseModel):
    """One built image ref (1:1 with a CodeCollectionVersion row)."""

    ref: str = Field(..., description="Git ref this build represents (branch/tag).")
    ref_type: str = Field(..., description="'branch' | 'tag' | 'release'.")
    image_registry: Optional[str] = Field(
        None, description="OCI repository, e.g. 'ghcr.io/runwhen-contrib/rw-cli-codecollection'."
    )
    image_tag: str = Field(..., description="Concrete OCI tag, pullable verbatim.")
    image_digest: Optional[str] = Field(
        None, description="sha256 digest when available; pin to this for reproducibility."
    )
    commit_hash: Optional[str] = Field(
        None, description="Full codecollection commit sha this image was built from."
    )
    rt_revision: Optional[str] = Field(
        None, description="platform-robot-runtime sha at build time."
    )
    image_built_at: Optional[datetime] = None
    is_latest: bool = False
    is_prerelease: bool = False
    is_active: bool = True
    synced_at: Optional[datetime] = None


class CatalogEntry(BaseModel):
    """A single CodeCollection plus its currently-resolved pointers."""

    slug: str
    name: str
    git_url: str
    visibility: str = Field(
        "public",
        description=(
            "'public' or 'hidden'. PAPI returns both; public-audience surfaces "
            "(website/MCP/AI) filter to public only."
        ),
    )
    latest_image_tag: Optional[str] = None
    stable_image_tag: Optional[str] = None
    image_registry: Optional[str] = None
    last_synced: Optional[datetime] = None


class CatalogEntryDetail(CatalogEntry):
    """Catalog entry with the full set of known refs attached."""

    refs: list[ImageRef] = Field(default_factory=list)


class ResolveResponse(BaseModel):
    """`/resolve` endpoint: ref-or-pointer -> concrete image."""

    slug: str
    requested: str = Field(..., description="The pointer or ref the caller asked for.")
    image_tag: str
    image_registry: Optional[str] = None
    image_digest: Optional[str] = None
    commit_hash: Optional[str] = None
    rt_revision: Optional[str] = None
