"""
PAPI-facing CodeCollection catalog API.

Surface area (identical to cc-registry-v2's `cc_catalog.py`, plus the
`?destination=` extension on /resolve):

    GET /api/v1/catalog/codecollections
    GET /api/v1/catalog/codecollections/{slug}
    GET /api/v1/catalog/codecollections/{slug}/refs
    GET /api/v1/catalog/codecollections/{slug}/refs/{ref}
    GET /api/v1/catalog/codecollections/{slug}/resolve?pointer=latest|stable
    GET /api/v1/catalog/codecollections/{slug}/resolve?ref=<git_ref>
    GET /api/v1/catalog/codecollections/{slug}/resolve?...&destination=<dest_name>

`?destination=` returns the mirrored destination ref (e.g. JFrog) when
one exists; omit it and the response is the source ref, matching the
registry's behavior exactly.

All endpoints are read-only and unauthenticated by design.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.config import get_config
from app.db import db_session
from app.models import CodeCollection, Destination, ImageRef, MirrorTarget
from app.schemas.catalog import (
    CatalogEntry,
    CatalogEntryDetail,
    ImageRef as ImageRefSchema,
    ResolveResponse,
)
from app.services.catalog import (
    active_refs,
    entry_pointers,
    find_ref_by_name,
    get_cc_by_slug,
)

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _to_image_ref(r: ImageRef) -> ImageRefSchema:
    return ImageRefSchema(
        ref=r.ref_name,
        ref_type=r.ref_type or "branch",
        image_registry=r.image_registry,
        image_tag=r.image_tag,
        image_digest=r.image_digest,
        commit_hash=r.commit_hash,
        rt_revision=r.rt_revision,
        image_built_at=r.image_built_at,
        is_latest=bool(r.is_latest),
        is_prerelease=bool(r.is_prerelease),
        is_active=bool(r.is_active),
        synced_at=r.synced_at,
    )


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.get("/codecollections", response_model=list[CatalogEntry])
def list_catalog(
    visibility: Optional[str] = Query(
        None,
        description="Filter by visibility ('public' | 'hidden'). Omit to see all.",
    ),
    only_with_image: bool = Query(
        True,
        description="If true (default), only return CCs that have at least one tracked image.",
    ),
    db: Session = Depends(db_session),
) -> list[CatalogEntry]:
    stmt = select(CodeCollection)
    if visibility:
        stmt = stmt.where(CodeCollection.visibility == visibility)
    stmt = stmt.order_by(CodeCollection.slug)
    collections = db.execute(stmt).scalars().all()

    entries: list[CatalogEntry] = []
    for cc in collections:
        refs = active_refs(db, cc.id)
        if only_with_image and not any(r.image_tag for r in refs):
            continue
        latest_tag, stable_tag, image_registry = entry_pointers(refs)
        entries.append(
            CatalogEntry(
                slug=cc.slug,
                name=cc.name,
                git_url=cc.git_url,
                visibility=cc.visibility or "public",
                latest_image_tag=latest_tag,
                stable_image_tag=stable_tag,
                image_registry=image_registry,
                last_synced=cc.last_synced,
            )
        )
    return entries


@router.get("/codecollections/{slug}", response_model=CatalogEntryDetail)
def get_catalog_entry(slug: str, db: Session = Depends(db_session)) -> CatalogEntryDetail:
    cc = get_cc_by_slug(db, slug)
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")
    refs = [r for r in active_refs(db, cc.id) if r.image_tag]
    latest_tag, stable_tag, image_registry = entry_pointers(refs)
    return CatalogEntryDetail(
        slug=cc.slug,
        name=cc.name,
        git_url=cc.git_url,
        visibility=cc.visibility or "public",
        latest_image_tag=latest_tag,
        stable_image_tag=stable_tag,
        image_registry=image_registry,
        last_synced=cc.last_synced,
        refs=[_to_image_ref(r) for r in refs],
    )


@router.get("/codecollections/{slug}/refs", response_model=list[ImageRefSchema])
def list_refs(
    slug: str,
    include_inactive: bool = Query(False),
    db: Session = Depends(db_session),
) -> list[ImageRefSchema]:
    cc = get_cc_by_slug(db, slug)
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")
    stmt = select(ImageRef).where(ImageRef.cc_id == cc.id)
    if not include_inactive:
        stmt = stmt.where(ImageRef.is_active.is_(True))
    refs = [r for r in db.execute(stmt).scalars().all() if r.image_tag]
    return [_to_image_ref(r) for r in refs]


@router.get("/codecollections/{slug}/refs/{ref}", response_model=ImageRefSchema)
def get_ref(slug: str, ref: str, db: Session = Depends(db_session)) -> ImageRefSchema:
    cc = get_cc_by_slug(db, slug)
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")
    row = find_ref_by_name(db, cc.id, ref)
    if row is None or not row.image_tag:
        raise HTTPException(
            status_code=404, detail=f"no image for {slug}@{ref}"
        )
    return _to_image_ref(row)


@router.get("/codecollections/{slug}/resolve", response_model=ResolveResponse)
def resolve_image(
    slug: str,
    pointer: Optional[str] = Query(
        None, pattern="^(latest|stable)$",
        description="Resolve a named pointer ('latest' or 'stable').",
    ),
    ref: Optional[str] = Query(
        None, description="Resolve a specific git ref name (branch/tag)."
    ),
    destination: Optional[str] = Query(
        None,
        description=(
            "Optional destination name. When provided and the image has been "
            "mirrored, the response includes target_image_ref/target_digest for "
            "the destination registry instead of just the source ref."
        ),
    ),
    db: Session = Depends(db_session),
) -> ResolveResponse:
    if bool(pointer) == bool(ref):
        raise HTTPException(
            status_code=400,
            detail="exactly one of 'pointer' or 'ref' must be provided",
        )

    cc = get_cc_by_slug(db, slug)
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")

    refs = [r for r in active_refs(db, cc.id) if r.image_tag]
    if not refs:
        raise HTTPException(status_code=404, detail=f"no images tracked for {slug}")

    selected: Optional[ImageRef] = None
    requested: str
    if pointer == "latest":
        latest_tag, _, _ = entry_pointers(refs)
        selected = next((r for r in refs if r.image_tag == latest_tag), None)
        requested = "latest"
    elif pointer == "stable":
        _, stable_tag, _ = entry_pointers(refs)
        selected = next((r for r in refs if r.image_tag == stable_tag), None)
        requested = "stable"
    else:
        selected = next((r for r in refs if r.ref_name == ref), None)
        requested = ref or ""

    if selected is None:
        raise HTTPException(
            status_code=404,
            detail=f"could not resolve {requested!r} for {slug}",
        )

    response = ResolveResponse(
        slug=slug,
        requested=requested,
        image_tag=selected.image_tag,
        image_registry=selected.image_registry,
        image_digest=selected.image_digest,
        commit_hash=selected.commit_hash,
        rt_revision=selected.rt_revision,
    )

    if destination:
        _attach_destination(db, response, cc.id, selected, destination)

    return response


def _attach_destination(
    db: Session,
    response: ResolveResponse,
    cc_id: int,
    selected: ImageRef,
    dest_name: str,
) -> None:
    """Populate the destination-related fields on a ResolveResponse.

    A missing destination row (or one that hasn't mirrored this tag yet)
    is NOT a 404 — the response still carries the source ref. We surface
    the gap through `destination=<name>` + `target_image_ref=None` so
    callers can fall back to the source.
    """
    dest_cfg = get_config().destination_by_name(dest_name)
    if dest_cfg is None:
        raise HTTPException(
            status_code=404, detail=f"unknown destination: {dest_name}"
        )

    dest_row = db.execute(
        select(Destination).where(Destination.name == dest_name)
    ).scalar_one_or_none()
    response.destination = dest_name
    if dest_row is None:
        return  # configured but not yet synced into DB rows

    target = db.execute(
        select(MirrorTarget).where(
            and_(
                MirrorTarget.cc_id == cc_id,
                MirrorTarget.destination_id == dest_row.id,
                MirrorTarget.source_image_tag == selected.image_tag,
            )
        )
    ).scalar_one_or_none()
    if target is None:
        return  # not yet mirrored; caller can use source ref

    response.target_image_ref = target.target_image_ref
    response.target_digest = target.target_digest
