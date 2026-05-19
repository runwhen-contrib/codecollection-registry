"""
Catalog read helpers (shared by routers and the mirror enqueue logic).

The pointer-resolution math mirrors cc-registry-v2's `cc_catalog.py`
`_entry_pointers` exactly so PAPI sees the same `latest_image_tag` /
`stable_image_tag` semantics from either service.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CodeCollection, ImageRef


def get_cc_by_slug(db: Session, slug: str) -> Optional[CodeCollection]:
    stmt = select(CodeCollection).where(CodeCollection.slug == slug)
    return db.execute(stmt).scalar_one_or_none()


def active_refs(db: Session, cc_id: int) -> list[ImageRef]:
    stmt = (
        select(ImageRef)
        .where(ImageRef.cc_id == cc_id, ImageRef.is_active.is_(True))
        .order_by(ImageRef.ref_name)
    )
    return list(db.execute(stmt).scalars().all())


def entry_pointers(
    refs: list[ImageRef],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Pull (latest_tag, stable_tag, image_registry) out of a CC's refs.

    Matches cc-registry-v2's logic:
      - latest = the single ref flagged is_latest by the sync task
      - stable = highest semver-looking tag (by version_type=='tag'),
                 falling back to latest if none exists.
    """
    latest_tag: Optional[str] = None
    stable_tag: Optional[str] = None
    image_registry: Optional[str] = None
    for r in refs:
        if r.image_registry and not image_registry:
            image_registry = r.image_registry
        if r.is_latest and r.image_tag:
            latest_tag = r.image_tag
        if (
            r.image_tag
            and r.ref_type == "tag"
            and (stable_tag is None or r.ref_name > stable_tag)
        ):
            stable_tag = r.image_tag
    return latest_tag, (stable_tag or latest_tag), image_registry


def find_ref_by_name(
    db: Session, cc_id: int, ref_name: str
) -> Optional[ImageRef]:
    stmt = select(ImageRef).where(
        ImageRef.cc_id == cc_id, ImageRef.ref_name == ref_name
    )
    return db.execute(stmt).scalar_one_or_none()
