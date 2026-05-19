"""
Catalog poll: iterate every configured CC, ask its source for refs, upsert.

Ported in shape from cc-registry-v2's `sync_image_tags_task` but driven
by `config.yaml` instead of a DB-of-CCs and adapted to our slightly
different model (we don't have a `version_name` vs `git_ref` split).

The function is idempotent and safe to call concurrently with reads;
writes use a single transaction per CC so a failing source doesn't poison
the others.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.config import AppConfig, CodeCollectionConfig, SourceConfig, get_config
from app.db import session_scope
from app.models import CodeCollection, ImageRef
from app.sources import DiscoveredImageRef
from app.sources.registry import configure_source_from_options

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Naive UTC clock used for all timestamp columns.

    SQLite (default) and Postgres both store the DateTime column as a
    naive timestamp at the chosen offset; we standardize on UTC. We
    avoid `datetime.utcnow()` (deprecated in 3.12) by stripping tzinfo
    after constructing a tz-aware now().
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_catalog_poll(config: Optional[AppConfig] = None) -> dict:
    """Discover refs for every configured CC; upsert into the DB.

    Returns a summary dict (counts + per-CC errors) suitable for surfacing
    in the admin manual-sync response.
    """
    cfg = config or get_config()
    summary = {
        "collections_processed": 0,
        "refs_upserted": 0,
        "refs_deactivated": 0,
        "errors": [],
    }

    for src_cfg in cfg.sources:
        source = configure_source_from_options(src_cfg.type, src_cfg.options)
        if source is None:
            err = f"unknown source type {src_cfg.type!r} (source={src_cfg.name!r})"
            logger.warning(err)
            summary["errors"].append({"source": src_cfg.name, "error": err})
            continue

        for cc_cfg in src_cfg.codecollections:
            try:
                upserted, deactivated = _sync_one_cc(src_cfg, source, cc_cfg)
            except Exception as exc:
                logger.exception(
                    "catalog poll: source %s failed for %s",
                    src_cfg.name,
                    cc_cfg.slug,
                )
                summary["errors"].append(
                    {
                        "source": src_cfg.name,
                        "slug": cc_cfg.slug,
                        "error": str(exc),
                    }
                )
                _record_cc_error(cc_cfg.slug, str(exc))
                continue

            summary["collections_processed"] += 1
            summary["refs_upserted"] += upserted
            summary["refs_deactivated"] += deactivated

    logger.info("catalog poll complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _sync_one_cc(
    src_cfg: SourceConfig,
    source,
    cc_cfg: CodeCollectionConfig,
) -> tuple[int, int]:
    """Sync a single CC. Returns (upserted_refs, deactivated_refs)."""
    cc_dict = cc_cfg.model_dump()  # what the source plugins expect
    # Merge source-level options so plugins like `upstream` that take a
    # per-source default URL still see it on the per-CC dict.
    for k, v in (src_cfg.options or {}).items():
        cc_dict.setdefault(k, v)
    # Source-level auth is read by plugins via this synthetic key (the
    # leading underscore signals it's injected by the caller, not from
    # config.yaml's CC entry). Today only `oci` consumes it.
    cc_dict["_source_auth"] = src_cfg.auth.model_dump()

    refs = source.discover_refs(cc_dict)
    latest_tag = source.resolve_latest(cc_dict, refs)
    stable_tag = source.resolve_stable(cc_dict, refs)

    with session_scope() as db:
        cc_row = _upsert_cc(db, cc_cfg, src_cfg.name)
        upserted, deactivated = _upsert_refs(
            db,
            cc_row,
            cc_cfg.image_registry,
            refs,
            latest_tag,
            stable_tag,
        )
        cc_row.last_synced = _utcnow()
        cc_row.last_sync_error = None
    return upserted, deactivated


def _upsert_cc(
    db,
    cc_cfg: CodeCollectionConfig,
    source_name: str,
) -> CodeCollection:
    row = db.execute(
        select(CodeCollection).where(CodeCollection.slug == cc_cfg.slug)
    ).scalar_one_or_none()
    if row is None:
        row = CodeCollection(slug=cc_cfg.slug)
        db.add(row)
    row.name = cc_cfg.name or row.name or cc_cfg.slug
    row.git_url = cc_cfg.git_url or row.git_url
    row.image_registry = cc_cfg.image_registry or row.image_registry
    row.default_ref = cc_cfg.default_ref
    row.visibility = cc_cfg.visibility
    row.source_name = source_name
    db.flush()
    return row


def _upsert_refs(
    db,
    cc_row: CodeCollection,
    image_registry: Optional[str],
    refs: list[DiscoveredImageRef],
    latest_tag: Optional[str],
    stable_tag: Optional[str],
) -> tuple[int, int]:
    """Mirror the discovered refs onto image_refs.

    Strategy is identical to cc-registry-v2's `_upsert_versions`:
      - Each (cc, ref) maps to one image_refs row keyed by ref_name.
      - Rows that exist in the DB but no longer appear in the source
        are flipped is_active=False (we keep history so consumers of
        a previously-resolved ref still get a sane error).
      - is_latest set ONLY on the latest-tag row; is_prerelease flipped
        off the stable row.
    """
    now = _utcnow()
    refs_by_name = {r.ref: r for r in refs}

    existing = db.execute(select(ImageRef).where(ImageRef.cc_id == cc_row.id)).scalars().all()
    existing_by_name = {v.ref_name: v for v in existing}

    upserted = 0
    deactivated = 0

    for name, row in existing_by_name.items():
        if name not in refs_by_name and row.is_active:
            row.is_active = False
            row.updated_at = now
            deactivated += 1

    for name, ref in refs_by_name.items():
        is_latest_row = latest_tag is not None and ref.image_tag == latest_tag
        is_stable_row = stable_tag is not None and ref.image_tag == stable_tag
        row = existing_by_name.get(name)
        if row is None:
            row = ImageRef(
                cc_id=cc_row.id,
                ref_name=name,
                ref_type=ref.ref_type,
            )
            db.add(row)

        row.ref_type = ref.ref_type
        row.image_registry = image_registry
        row.image_tag = ref.image_tag
        row.image_digest = ref.image_digest
        row.commit_hash = ref.commit
        row.rt_revision = ref.rt_revision
        row.image_built_at = ref.built_at
        row.is_active = True
        row.is_latest = is_latest_row
        row.is_stable = is_stable_row
        # Anything that isn't the stable pointer and isn't a semver tag
        # is considered a prerelease (matches the registry's heuristic).
        row.is_prerelease = not (is_stable_row or ref.ref_type == "tag")
        row.synced_at = now
        row.updated_at = now
        upserted += 1

    return upserted, deactivated


def _record_cc_error(slug: str, error: str) -> None:
    """Stamp the CC row's `last_sync_error` so operators can see why a
    sync failed without having to scrape logs."""
    try:
        with session_scope() as db:
            row = db.execute(
                select(CodeCollection).where(CodeCollection.slug == slug)
            ).scalar_one_or_none()
            if row is not None:
                row.last_sync_error = error[:2000]
    except Exception:
        logger.exception("failed to record last_sync_error for %s", slug)
