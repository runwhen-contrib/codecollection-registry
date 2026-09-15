"""
Catalog API response models.

These shapes match cc-registry-v2's `app/schemas/cc_catalog.py` field-for-field
so PAPI can point at either service without code changes. Keep field
names stable; add new fields rather than renaming.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImageRef(BaseModel):
    """One built image ref (1:1 with an image_refs row)."""

    ref: str = Field(..., description="Git ref this build represents (branch/tag).")
    ref_type: str = Field(..., description="'branch' | 'tag' | 'release'.")
    image_registry: Optional[str] = Field(
        None,
        description="OCI repository, e.g. 'ghcr.io/runwhen-contrib/rw-cli-codecollection'.",
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
    name: Optional[str] = None
    git_url: Optional[str] = None
    visibility: str = Field(
        "public",
        description=(
            "'public' or 'hidden'. PAPI returns both; public-audience surfaces "
            "(website / MCP / AI) should filter to public only."
        ),
    )
    latest_image_tag: Optional[str] = None
    stable_image_tag: Optional[str] = None
    image_registry: Optional[str] = None
    last_synced: Optional[datetime] = None


class CatalogEntryDetail(CatalogEntry):
    """Catalog entry with the full set of known refs attached."""

    refs: list[ImageRef] = Field(default_factory=list)


class CapabilityEntry(BaseModel):
    """One discovered capability image build (1:1 with a capability_versions
    row). Field names/shape are the K1/P1 contract — snake_case, stable."""

    capability: Optional[str] = Field(None, description="Capability id from the parsed manifest.")
    version: Optional[str] = Field(None, description="Capability version from the parsed manifest.")
    codecollection: str = Field(..., description="Slug of the owning `kind: capability` entry.")
    ref: str = Field(..., description="Branch alias or semver tag this build represents.")
    ref_type: str = Field(..., description="'tag' for semver refs, else 'branch'.")
    commit_hash: Optional[str] = Field(
        None, description="First 7 chars of io.runwhen.codecollection.commit."
    )
    image_tag: Optional[str] = Field(
        None, description="'<ref>-<commit_hash>' for branches, the tag itself for semver."
    )
    image_digest: str = Field(
        ..., description="Top-level (index, for multi-arch) digest of the tag."
    )
    image: str = Field(..., description="'<image_registry>@<image_digest>'.")
    manifest_text: str = Field(..., description="The decoded label, verbatim YAML.")
    manifest: Optional[dict] = Field(None, description="manifest_text parsed to JSON.")
    synced_at: Optional[datetime] = None


class CapabilitiesResponse(BaseModel):
    capabilities: list[CapabilityEntry] = Field(default_factory=list)


class ResolveResponse(BaseModel):
    """`/resolve`: ref-or-pointer (-and-optional-destination) -> concrete image."""

    slug: str
    requested: str = Field(..., description="The pointer or ref the caller asked for.")
    image_tag: str
    image_registry: Optional[str] = None
    image_digest: Optional[str] = None
    commit_hash: Optional[str] = None
    rt_revision: Optional[str] = None
    # Populated when ?destination=<name> is provided and a mirror exists.
    destination: Optional[str] = None
    target_image_ref: Optional[str] = Field(
        None,
        description=(
            "Fully-qualified destination ref (e.g. acme.jfrog.io/...:tag). "
            "Present only when resolving against a configured destination."
        ),
    )
    target_digest: Optional[str] = None
