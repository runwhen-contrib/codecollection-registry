"""
PAPI-facing CodeCollection catalog API.

These endpoints intentionally bypass the `visibility = 'public'` filter
that protects the registry website: PAPI needs to see hidden CCs so it
can still resolve their image refs for workspaces that use them.

Surface area:

    GET /api/v1/catalog/codecollections
    GET /api/v1/catalog/codecollections/{slug}
    GET /api/v1/catalog/codecollections/{slug}/refs
    GET /api/v1/catalog/codecollections/{slug}/refs/{ref}
    GET /api/v1/catalog/codecollections/{slug}/resolve?pointer=latest|stable
    GET /api/v1/catalog/codecollections/{slug}/resolve?ref=<git_ref>

Everything is read-only. Writes happen only through the image-sync
Celery task — there is no public write API and no auth needed.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CodeCollection
from app.models.version import CodeCollectionVersion
from app.schemas.cc_catalog import (
    CatalogEntry,
    CatalogEntryDetail,
    ImageRef,
    ResolveResponse,
)

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _to_image_ref(v: CodeCollectionVersion) -> ImageRef:
    return ImageRef(
        ref=v.version_name,
        ref_type=v.version_type or "branch",
        image_registry=v.image_registry,
        image_tag=v.image_tag,
        image_digest=v.image_digest,
        commit_hash=v.commit_hash,
        rt_revision=v.rt_revision,
        image_built_at=v.image_built_at,
        is_latest=bool(v.is_latest),
        is_prerelease=bool(v.is_prerelease),
        is_active=bool(v.is_active),
        synced_at=v.synced_at,
    )


def _entry_pointers(versions: list[CodeCollectionVersion]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Pull (latest_tag, stable_tag, image_registry) out of a CC's versions.

    `stable` is re-derived here from version_type=='tag' rows because the
    schema does not (yet) track `is_stable` on CodeCollectionVersion —
    cc-catalog-svc's ImageRef does. The comparison is apples-to-apples
    (version_name vs version_name), never mixed against image_tag — that
    would compare "v1.2.0" against "v1.2.0-aabbccd-e4f5a6b" and let the
    suffix flip the result.

    Caveat: the comparison is still lexicographic, so multi-digit semver
    components ("v10.0.0" vs "v9.0.0") will still mis-sort. The cleaner
    fix is to add `is_stable` to the model and set it in the sync task
    using the source plugin's semver-aware resolver (cc-catalog-svc
    already does this).
    """
    latest_tag: Optional[str] = None
    stable_tag: Optional[str] = None
    stable_version_name: Optional[str] = None
    image_registry: Optional[str] = None
    for v in versions:
        if v.image_registry and not image_registry:
            image_registry = v.image_registry
        if v.is_latest and v.image_tag:
            latest_tag = v.image_tag
        if (
            v.image_tag
            and v.version_type == "tag"
            and (stable_version_name is None or v.version_name > stable_version_name)
        ):
            stable_tag = v.image_tag
            stable_version_name = v.version_name
    # Fall back to `latest` if no semver tag is present.
    return latest_tag, (stable_tag or latest_tag), image_registry


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
    db: Session = Depends(get_db),
) -> list[CatalogEntry]:
    """List every CodeCollection PAPI may need to resolve."""
    q = db.query(CodeCollection).filter(CodeCollection.is_active.is_(True))
    if visibility:
        q = q.filter(CodeCollection.visibility == visibility)
    collections = q.order_by(CodeCollection.slug).all()

    entries: list[CatalogEntry] = []
    for cc in collections:
        versions = [v for v in cc.versions if v.is_active]
        if only_with_image and not any(v.image_tag for v in versions):
            continue
        latest_tag, stable_tag, image_registry = _entry_pointers(versions)
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
def get_catalog_entry(slug: str, db: Session = Depends(get_db)) -> CatalogEntryDetail:
    cc = (
        db.query(CodeCollection)
        .filter(CodeCollection.slug == slug, CodeCollection.is_active.is_(True))
        .first()
    )
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")
    versions = [v for v in cc.versions if v.is_active and v.image_tag]
    latest_tag, stable_tag, image_registry = _entry_pointers(versions)
    return CatalogEntryDetail(
        slug=cc.slug,
        name=cc.name,
        git_url=cc.git_url,
        visibility=cc.visibility or "public",
        latest_image_tag=latest_tag,
        stable_image_tag=stable_tag,
        image_registry=image_registry,
        last_synced=cc.last_synced,
        refs=[_to_image_ref(v) for v in versions],
    )


@router.get("/codecollections/{slug}/refs", response_model=list[ImageRef])
def list_refs(
    slug: str,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[ImageRef]:
    cc = (
        db.query(CodeCollection)
        .filter(CodeCollection.slug == slug, CodeCollection.is_active.is_(True))
        .first()
    )
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")
    versions = list(cc.versions)
    if not include_inactive:
        versions = [v for v in versions if v.is_active]
    versions = [v for v in versions if v.image_tag]
    return [_to_image_ref(v) for v in versions]


@router.get("/codecollections/{slug}/refs/{ref}", response_model=ImageRef)
def get_ref(slug: str, ref: str, db: Session = Depends(get_db)) -> ImageRef:
    row = (
        db.query(CodeCollectionVersion)
        .join(CodeCollection, CodeCollectionVersion.codecollection_id == CodeCollection.id)
        .filter(
            CodeCollection.slug == slug,
            CodeCollection.is_active.is_(True),
            CodeCollectionVersion.version_name == ref,
        )
        .first()
    )
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
    db: Session = Depends(get_db),
) -> ResolveResponse:
    """
    Resolve a pointer or git ref to a concrete OCI image tag. Exactly one of
    `pointer` or `ref` must be supplied. This is the endpoint PAPI calls
    on the workspace reconcile path.
    """
    if bool(pointer) == bool(ref):
        raise HTTPException(
            status_code=400,
            detail="exactly one of 'pointer' or 'ref' must be provided",
        )

    cc = (
        db.query(CodeCollection)
        .filter(CodeCollection.slug == slug, CodeCollection.is_active.is_(True))
        .first()
    )
    if cc is None:
        raise HTTPException(status_code=404, detail=f"unknown codecollection: {slug}")

    versions = [v for v in cc.versions if v.is_active and v.image_tag]
    if not versions:
        raise HTTPException(status_code=404, detail=f"no images tracked for {slug}")

    selected: Optional[CodeCollectionVersion] = None
    if pointer == "latest":
        latest_tag, _, _ = _entry_pointers(versions)
        selected = next((v for v in versions if v.image_tag == latest_tag), None)
        requested = "latest"
    elif pointer == "stable":
        _, stable_tag, _ = _entry_pointers(versions)
        selected = next((v for v in versions if v.image_tag == stable_tag), None)
        requested = "stable"
    else:
        selected = next((v for v in versions if v.version_name == ref), None)
        requested = ref or ""

    if selected is None:
        raise HTTPException(
            status_code=404,
            detail=f"could not resolve {requested!r} for {slug}",
        )

    return ResolveResponse(
        slug=slug,
        requested=requested,
        image_tag=selected.image_tag,
        image_registry=selected.image_registry,
        image_digest=selected.image_digest,
        commit_hash=selected.commit_hash,
        rt_revision=selected.rt_revision,
    )
