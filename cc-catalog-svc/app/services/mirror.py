"""
Mirror engine.

Two phases, both driven by the scheduler on their own intervals:

  1. enqueue_mirror_jobs(): compute the delta of refs to mirror for each
     configured destination and insert one MirrorJob per `(cc, dest,
     ref)` that isn't already mirrored or already in-flight.

  2. drain_mirror_jobs(): pull pending jobs, call destination.push() in a
     bounded thread pool, write results to MirrorTarget / MirrorJob.

Splitting enqueue from drain means an admin can trigger an enqueue
manually (POST /api/v1/mirror/destinations/{name}/sync) and the work
continues to flow even if the request goroutine is gone.

All destination interactions go through the plugin contract — this
module never reaches into JFrog-specific APIs.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.config import AppConfig, DestinationConfig, MirrorFilter, get_config
from app.db import session_scope
from app.destinations import get_destination
from app.destinations.base import ImageDestination, MirrorResult
from app.models import (
    CodeCollection,
    Destination,
    ImageRef,
    MirrorJob,
    MirrorTarget,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Naive UTC timestamp (matches the DateTime columns); avoids the
    Python 3.12 deprecation of `datetime.utcnow()`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


SEMVER_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?")


# ---------------------------------------------------------------------------
# Destination row sync (configure DB rows from config.yaml)
# ---------------------------------------------------------------------------
def sync_destination_rows(cfg: Optional[AppConfig] = None) -> dict[str, Destination]:
    """Upsert one Destination row per configured destination.

    Returns name -> Destination so callers can reference IDs.
    """
    cfg = cfg or get_config()
    out: dict[str, Destination] = {}
    with session_scope() as db:
        for dest_cfg in cfg.destinations:
            row = db.execute(
                select(Destination).where(Destination.name == dest_cfg.name)
            ).scalar_one_or_none()
            if row is None:
                row = Destination(name=dest_cfg.name, type=dest_cfg.type)
                db.add(row)
            row.type = dest_cfg.type
            row.enabled = True
            # config_json captures everything except secrets (auth fields
            # only refer to env-var NAMES; the values stay in env).
            row.config_json = dest_cfg.model_dump(mode="json")
            db.flush()
            db.refresh(row)
            out[row.name] = row
    return out


# ---------------------------------------------------------------------------
# Phase 1: enqueue
# ---------------------------------------------------------------------------
def enqueue_mirror_jobs(
    cfg: Optional[AppConfig] = None,
    *,
    only_destination: Optional[str] = None,
    only_slug: Optional[str] = None,
) -> dict:
    """Compute the mirror delta and create MirrorJob rows.

    `only_destination` / `only_slug` narrow the scope when an admin
    triggered a targeted resync; the periodic scheduler call passes both
    as None to enqueue everything.
    """
    cfg = cfg or get_config()
    dests = sync_destination_rows(cfg)

    summary = {
        "destinations_processed": 0,
        "jobs_enqueued": 0,
        "refs_already_mirrored": 0,
        "errors": [],
    }

    for dest_cfg in cfg.destinations:
        if only_destination and dest_cfg.name != only_destination:
            continue

        dest_row = dests.get(dest_cfg.name)
        if dest_row is None:
            summary["errors"].append(
                {"destination": dest_cfg.name, "error": "destination row not created"}
            )
            continue
        plugin = get_destination(dest_cfg.type)
        if plugin is None:
            summary["errors"].append(
                {"destination": dest_cfg.name, "error": f"unknown destination type {dest_cfg.type!r}"}
            )
            continue

        try:
            enqueued, already = _enqueue_for_destination(
                cfg, dest_cfg, dest_row, plugin, only_slug=only_slug,
            )
        except Exception as exc:
            logger.exception("enqueue failed for destination %s", dest_cfg.name)
            summary["errors"].append(
                {"destination": dest_cfg.name, "error": str(exc)}
            )
            continue

        summary["destinations_processed"] += 1
        summary["jobs_enqueued"] += enqueued
        summary["refs_already_mirrored"] += already

    logger.info("mirror enqueue complete: %s", summary)
    return summary


def _enqueue_for_destination(
    cfg: AppConfig,
    dest_cfg: DestinationConfig,
    dest_row: Destination,
    plugin: ImageDestination,
    *,
    only_slug: Optional[str] = None,
) -> tuple[int, int]:
    enqueued = 0
    already = 0

    cc_filter = dest_cfg.mirror.codecollections or ["*"]
    all_ccs = cfg.all_codecollections()

    with session_scope() as db:
        for slug, cc_cfg in all_ccs.items():
            if only_slug and slug != only_slug:
                continue
            if "*" not in cc_filter and slug not in cc_filter:
                continue

            cc_row = db.execute(
                select(CodeCollection).where(CodeCollection.slug == slug)
            ).scalar_one_or_none()
            if cc_row is None:
                continue  # not yet catalogued

            refs = db.execute(
                select(ImageRef).where(
                    and_(
                        ImageRef.cc_id == cc_row.id,
                        ImageRef.is_active.is_(True),
                    )
                )
            ).scalars().all()
            if not refs:
                continue

            selected_refs = _filter_refs_for_mirror(refs, dest_cfg.mirror)
            for ref in selected_refs:
                source_image_ref = _compose_source_ref(ref)
                target_image_ref = plugin.target_ref(
                    dest_cfg.model_dump(mode="json"),
                    cc_cfg.model_dump(),
                    ref.image_tag,
                )

                # Skip if already mirrored.
                already_done = db.execute(
                    select(MirrorTarget).where(
                        and_(
                            MirrorTarget.cc_id == cc_row.id,
                            MirrorTarget.destination_id == dest_row.id,
                            MirrorTarget.source_image_tag == ref.image_tag,
                        )
                    )
                ).scalar_one_or_none()
                if already_done is not None:
                    already += 1
                    continue

                # Skip if there's already a non-terminal job for this work.
                in_flight = db.execute(
                    select(MirrorJob).where(
                        and_(
                            MirrorJob.cc_id == cc_row.id,
                            MirrorJob.destination_id == dest_row.id,
                            MirrorJob.target_image_ref == target_image_ref,
                            MirrorJob.status.in_(("pending", "running")),
                        )
                    )
                ).scalar_one_or_none()
                if in_flight is not None:
                    continue

                db.add(
                    MirrorJob(
                        cc_id=cc_row.id,
                        destination_id=dest_row.id,
                        source_image_ref=source_image_ref,
                        target_image_ref=target_image_ref,
                        status="pending",
                    )
                )
                enqueued += 1

    return enqueued, already


def _filter_refs_for_mirror(
    refs: list[ImageRef], filt: MirrorFilter
) -> list[ImageRef]:
    """Apply MirrorFilter against the list of active refs for one CC.

    Pointer selection is implicit: if a ref is currently `is_latest` /
    `is_stable` AND the filter includes that pointer, the ref qualifies.
    Branch / semver / PR rules apply independently.
    """
    selected: list[ImageRef] = []
    pointer_set = set(filt.include_pointers)
    branch_set = set(filt.include_branches or [])

    for r in refs:
        keep = False
        if r.is_latest and "latest" in pointer_set:
            keep = True
        if r.is_stable and "stable" in pointer_set:
            keep = True
        if r.ref_name in branch_set:
            keep = True
        if filt.include_semver_tags and r.ref_type == "tag" and SEMVER_TAG.match(r.ref_name):
            keep = True
        if filt.include_pr_refs and r.ref_name.startswith("pr-"):
            keep = True
        if keep:
            selected.append(r)
    return selected


def _compose_source_ref(ref: ImageRef) -> str:
    """`ghcr.io/runwhen-contrib/foo:tag` (digest-pin when we can)."""
    base = ref.image_registry or ""
    if ref.image_digest:
        return f"{base}@{ref.image_digest}"
    return f"{base}:{ref.image_tag}"


# ---------------------------------------------------------------------------
# Phase 2: drain
# ---------------------------------------------------------------------------
def drain_mirror_jobs(
    cfg: Optional[AppConfig] = None,
    *,
    batch_size: Optional[int] = None,
    workers: Optional[int] = None,
    per_job_timeout: Optional[int] = None,
) -> dict:
    """Run pending mirror jobs through their destination plugins.

    We pull a batch, mark them `running`, then push in a thread pool.
    Each job's outcome (success -> MirrorTarget upsert, failure ->
    MirrorJob bumped + retried next pass) is its own transaction so
    one failing job can't poison a whole batch.
    """
    cfg = cfg or get_config()
    sched = cfg.scheduler
    workers = workers or sched.mirror_workers
    per_job_timeout = per_job_timeout or sched.per_job_timeout_seconds
    batch_size = batch_size or max(workers * 4, 8)

    summary = {"jobs_run": 0, "jobs_succeeded": 0, "jobs_failed": 0}

    # Pull a batch of pending jobs and flip them to `running` atomically.
    job_ctx_list: list[dict] = []
    with session_scope() as db:
        jobs = (
            db.execute(
                select(MirrorJob)
                .where(MirrorJob.status == "pending")
                .order_by(MirrorJob.created_at)
                .limit(batch_size)
            )
            .scalars()
            .all()
        )
        now = _utcnow()
        for j in jobs:
            j.status = "running"
            j.started_at = now
            j.attempts += 1
            # Snapshot what we need outside the session.
            dest_row = db.get(Destination, j.destination_id)
            cc_row = db.get(CodeCollection, j.cc_id)
            if dest_row is None or cc_row is None:
                j.status = "failed"
                j.last_error = "destination or codecollection row missing"
                j.finished_at = _utcnow()
                continue
            job_ctx_list.append(
                {
                    "job_id": j.id,
                    "cc_id": j.cc_id,
                    "cc_slug": cc_row.slug,
                    "destination_id": j.destination_id,
                    "destination_name": dest_row.name,
                    "destination_type": dest_row.type,
                    "destination_config": dest_row.config_json or {},
                    "source_image_ref": j.source_image_ref,
                    "target_image_ref": j.target_image_ref,
                    # Derive the canonical source tag from the *target* ref:
                    # `source_image_ref` may be digest-pinned (`...@sha256:...`)
                    # when the discovered ref had an image_digest, which would
                    # cause `_tag_from_ref` to extract the digest instead of
                    # the tag name. The natural key on MirrorTarget is the
                    # tag, and `_enqueue_for_destination` looks it up with
                    # `MirrorTarget.source_image_tag == ref.image_tag`, so a
                    # digest stored here would never match → infinite re-
                    # enqueue. `target_image_ref` is always tag-based (every
                    # destination plugin constructs it from `image_tag`).
                    # Derive the canonical source tag from the *target* ref:
                    # `source_image_ref` may be digest-pinned (`...@sha256:...`)
                    # when the discovered ref had an image_digest, which would
                    # cause `_tag_from_ref` to extract the digest instead of
                    # the tag name. The natural key on MirrorTarget is the
                    # tag, and `_enqueue_for_destination` looks it up with
                    # `MirrorTarget.source_image_tag == ref.image_tag`, so a
                    # digest stored here would never match → infinite re-
                    # enqueue. `target_image_ref` is always tag-based (every
                    # destination plugin constructs it from `image_tag`).
                    "source_image_tag": _tag_from_ref(j.target_image_ref),
                    "max_attempts": j.max_attempts,
                    "current_attempt": j.attempts,
                }
            )

    if not job_ctx_list:
        return summary

    # Drain in a thread pool. Each `_run_one_job` opens its own DB session
    # so workers don't share state.
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mirror") as pool:
        futures = [
            pool.submit(_run_one_job, ctx, per_job_timeout) for ctx in job_ctx_list
        ]
        for fut in as_completed(futures):
            outcome = fut.result()
            summary["jobs_run"] += 1
            if outcome:
                summary["jobs_succeeded"] += 1
            else:
                summary["jobs_failed"] += 1

    return summary


def _run_one_job(ctx: dict, timeout: int) -> bool:
    """Execute a single mirror job. Returns True on success.

    `ctx` is threaded into every `_finish_job` call (both success and
    failure) so the destination's `last_sync_error` / `last_synced` rows
    stay accurate. Skipping `ctx` on failure makes the error-state update
    in `_finish_job` silently dead code.
    """
    plugin = get_destination(ctx["destination_type"])
    if plugin is None:
        _finish_job(
            ctx["job_id"],
            success=False,
            error=f"unknown destination type {ctx['destination_type']!r}",
            ctx=ctx,
        )
        return False

    # exists() guard: if the tag is already present on the destination
    # (e.g. someone pushed it manually), record a MirrorTarget and skip
    # the copy. This makes manual operator workflows compose cleanly.
    try:
        if plugin.exists(ctx["destination_config"], ctx["target_image_ref"]):
            _finish_job(
                ctx["job_id"],
                success=True,
                target_digest=None,
                log_text="[skip: already exists on destination]",
                ctx=ctx,
            )
            return True
    except Exception as exc:
        # Treat exists()-time failures as job failures (visible to
        # operators) rather than silently flipping to push.
        _finish_job(
            ctx["job_id"],
            success=False,
            error=f"destination exists() failed: {exc!r}",
            ctx=ctx,
        )
        return False

    result: MirrorResult = plugin.push(
        ctx["destination_config"],
        ctx["source_image_ref"],
        ctx["target_image_ref"],
        timeout=timeout,
    )

    if result.success:
        _finish_job(
            ctx["job_id"],
            success=True,
            target_digest=result.target_digest,
            log_text=result.log_text,
            ctx=ctx,
        )
        return True

    _finish_job(
        ctx["job_id"],
        success=False,
        log_text=result.log_text,
        error=result.error,
        ctx=ctx,
    )
    return False


def _finish_job(
    job_id: int,
    *,
    success: bool,
    target_digest: Optional[str] = None,
    log_text: str = "",
    error: Optional[str] = None,
    ctx: Optional[dict] = None,
) -> None:
    """Update the MirrorJob row and, on success, upsert MirrorTarget."""
    with session_scope() as db:
        job = db.get(MirrorJob, job_id)
        if job is None:
            logger.warning("MirrorJob %s vanished mid-run", job_id)
            return
        job.finished_at = _utcnow()
        job.log_text = log_text or job.log_text
        job.last_error = error
        if success:
            job.status = "done"
            if ctx is not None:
                _upsert_mirror_target(
                    db,
                    cc_id=ctx["cc_id"],
                    destination_id=ctx["destination_id"],
                    source_image_tag=ctx["source_image_tag"],
                    target_image_ref=ctx["target_image_ref"],
                    target_digest=target_digest,
                )
                dest_row = db.get(Destination, ctx["destination_id"])
                if dest_row is not None:
                    dest_row.last_synced = _utcnow()
                    dest_row.last_sync_error = None
        else:
            # Retry up to max_attempts, then mark `failed` and leave for
            # operator inspection.
            if job.attempts < job.max_attempts:
                job.status = "pending"
            else:
                job.status = "failed"
                if ctx is not None:
                    dest_row = db.get(Destination, ctx["destination_id"])
                    if dest_row is not None:
                        dest_row.last_sync_error = (error or "")[:2000]


def _upsert_mirror_target(
    db: Session,
    *,
    cc_id: int,
    destination_id: int,
    source_image_tag: str,
    target_image_ref: str,
    target_digest: Optional[str],
) -> None:
    existing = db.execute(
        select(MirrorTarget).where(
            and_(
                MirrorTarget.cc_id == cc_id,
                MirrorTarget.destination_id == destination_id,
                MirrorTarget.source_image_tag == source_image_tag,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            MirrorTarget(
                cc_id=cc_id,
                destination_id=destination_id,
                source_image_tag=source_image_tag,
                target_image_ref=target_image_ref,
                target_digest=target_digest,
            )
        )
    else:
        existing.target_image_ref = target_image_ref
        existing.target_digest = target_digest
        existing.mirrored_at = _utcnow()


def _tag_from_ref(image_ref: str) -> str:
    """`ghcr.io/.../foo:main-abc-def` -> `main-abc-def`.

    Falls back to the original string when a digest-pinned ref is used.
    """
    if "@" in image_ref:
        # digest pin: tag is unrecoverable from the ref alone; use the
        # digest's short form as a stand-in so the MirrorTarget natural
        # key still functions.
        return image_ref.rsplit("@", 1)[-1]
    if ":" in image_ref:
        return image_ref.rsplit(":", 1)[-1]
    return image_ref
