"""
Image-tag sync tasks.

Periodically reads `codecollections.yaml`, asks each CC's configured
`ImageSource` for every known build, and upserts `CodeCollectionVersion`
rows so PAPI (and any other consumer) can resolve refs to concrete image
tags without ever talking to a git server or running a CRD reconciler.

Design notes:

  - This task is the single writer for image metadata in the catalog. It
    is intentionally idempotent: re-running it converges the DB onto
    whatever the OCI registry reports, including marking gone-from-registry
    versions inactive.
  - It does NOT push to any registry. The registry remains the source of
    truth for whether an image exists.
  - It runs on a regular celery-beat schedule (see schedules.yaml) and is
    also exposed manually via the admin/task UI for on-demand refreshes.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import yaml

from app.core.database import SessionLocal
from app.models import CodeCollection
from app.models.version import CodeCollectionVersion
from app.sources import DiscoveredImageRef, get_source
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _load_codecollections_yaml() -> list[dict]:
    """Locate codecollections.yaml in the same order other tasks do."""
    candidate_paths = [
        "/app/codecollections.yaml",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "..",
            "codecollections.yaml",
        ),
        "/workspaces/codecollection-registry/codecollections.yaml",
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            return data.get("codecollections", []) or []
    logger.error("codecollections.yaml not found in any known location")
    return []


@celery_app.task(bind=True, name="app.tasks.image_sync_tasks.sync_image_tags_task")
def sync_image_tags_task(self):
    """
    For every CC with an `image_source` configured, discover its image
    refs and upsert one CodeCollectionVersion row per ref.
    """
    logger.info("Starting sync_image_tags_task %s", self.request.id)

    collections = _load_codecollections_yaml()
    summary = {
        "collections_processed": 0,
        "refs_upserted": 0,
        "refs_deactivated": 0,
        "errors": [],
    }

    db = SessionLocal()
    try:
        for cc_yaml in collections:
            source_name = cc_yaml.get("image_source")
            if not source_name:
                continue  # CC opted out of image tracking

            slug = cc_yaml.get("slug")
            if not slug:
                logger.warning("Skipping CC without slug: %s", cc_yaml)
                continue

            cc_row = (
                db.query(CodeCollection)
                .filter(CodeCollection.slug == slug)
                .first()
            )
            if not cc_row:
                # Image sync runs after collection sync, so a missing row
                # almost always means the YAML edit hasn't reached the DB
                # yet — bail rather than create a half-formed row.
                logger.warning(
                    "Skipping image sync for %s: collection not yet in DB", slug
                )
                continue

            source = get_source(source_name)
            if source is None:
                summary["errors"].append(
                    {"slug": slug, "error": f"unknown image_source {source_name!r}"}
                )
                continue

            try:
                refs = source.discover_refs(cc_yaml)
                latest_tag = source.resolve_latest(cc_yaml, refs)
                stable_tag = source.resolve_stable(cc_yaml, refs)
            except Exception as exc:  # pragma: no cover - logged for ops
                logger.exception("source %s failed for %s", source_name, slug)
                summary["errors"].append({"slug": slug, "error": str(exc)})
                continue

            upserted, deactivated = _upsert_versions(
                db,
                cc_row,
                cc_yaml.get("image_registry"),
                refs,
                latest_tag,
                stable_tag,
            )
            db.commit()
            summary["collections_processed"] += 1
            summary["refs_upserted"] += upserted
            summary["refs_deactivated"] += deactivated

        logger.info("sync_image_tags_task finished: %s", summary)
        return {"status": "success", **summary}
    finally:
        db.close()


def _upsert_versions(
    db,
    cc_row: CodeCollection,
    image_registry: Optional[str],
    refs: list[DiscoveredImageRef],
    latest_tag: Optional[str],
    stable_tag: Optional[str],
) -> tuple[int, int]:
    """
    Mirror the discovered refs onto codecollection_versions.

    Strategy:
      - Each (cc, ref) maps to a CodeCollectionVersion keyed by version_name=ref.
      - Versions that exist in the DB but no longer appear in the source are
        marked is_active=False (we keep the row for history rather than
        deleting it — PAPI may still reference a now-gone image).
      - `is_latest` is set ONLY on the latest-tag row; `is_prerelease` is
        flipped off the stable row.
    """
    upserted = 0
    deactivated = 0
    now = datetime.utcnow()

    refs_by_name = {r.ref: r for r in refs}

    existing_versions = (
        db.query(CodeCollectionVersion)
        .filter(CodeCollectionVersion.codecollection_id == cc_row.id)
        .all()
    )
    existing_by_name = {v.version_name: v for v in existing_versions}

    # Deactivate rows that no longer appear in the source.
    for name, row in existing_by_name.items():
        if name not in refs_by_name and row.is_active:
            row.is_active = False
            row.updated_at = now
            deactivated += 1

    # Upsert each discovered ref.
    for name, ref in refs_by_name.items():
        is_latest_row = (latest_tag is not None and ref.image_tag == latest_tag)
        is_stable_row = (stable_tag is not None and ref.image_tag == stable_tag)
        row = existing_by_name.get(name)
        if row is None:
            row = CodeCollectionVersion(
                codecollection_id=cc_row.id,
                version_name=name,
                git_ref=name,
                display_name=name,
                version_type=ref.ref_type,
            )
            db.add(row)

        row.image_registry = image_registry
        row.image_tag = ref.image_tag
        row.image_digest = ref.image_digest
        row.commit_hash = ref.commit
        row.rt_revision = ref.rt_revision
        row.image_built_at = ref.built_at
        row.is_active = True
        row.is_latest = is_latest_row
        # Treat anything that isn't the stable pointer (and isn't semver) as a prerelease.
        row.is_prerelease = not (is_stable_row or ref.ref_type == "tag")
        row.synced_at = now
        row.updated_at = now
        upserted += 1

    return upserted, deactivated
