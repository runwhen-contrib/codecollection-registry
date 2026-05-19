"""
Mirror introspection + admin trigger API.

    GET  /api/v1/mirror/destinations
    GET  /api/v1/mirror/jobs?status=...
    GET  /api/v1/mirror/jobs/{id}
    POST /api/v1/mirror/destinations/{name}/sync                            (admin)
    POST /api/v1/mirror/destinations/{name}/codecollections/{slug}/sync     (admin)

POST endpoints enqueue jobs synchronously and return the count; the
scheduler's mirror-drain phase consumes them on its next interval (or
the operator can also call POST /api/v1/mirror/drain to drain
immediately — useful in dev).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_config
from app.db import db_session
from app.models import CodeCollection, Destination, MirrorJob, MirrorTarget
from app.schemas.mirror import (
    DestinationSummary,
    MirrorJobDetail,
    MirrorJobView,
    MirrorJobsResponse,
    MirrorTriggerResponse,
)
from app.security import require_admin
from app.services.mirror import drain_mirror_jobs, enqueue_mirror_jobs

router = APIRouter(prefix="/api/v1/mirror", tags=["mirror"])


# ---------------------------------------------------------------------------
# read endpoints
# ---------------------------------------------------------------------------
@router.get("/destinations", response_model=list[DestinationSummary])
def list_destinations(db: Session = Depends(db_session)) -> list[DestinationSummary]:
    cfg = get_config()
    out: list[DestinationSummary] = []
    for dest_cfg in cfg.destinations:
        row = db.execute(
            select(Destination).where(Destination.name == dest_cfg.name)
        ).scalar_one_or_none()
        mirrored_count = 0
        if row is not None:
            mirrored_count = (
                db.execute(
                    select(func.count(MirrorTarget.id)).where(
                        MirrorTarget.destination_id == row.id
                    )
                ).scalar_one()
                or 0
            )
        tracked = dest_cfg.mirror.codecollections or ["*"]
        out.append(
            DestinationSummary(
                name=dest_cfg.name,
                type=dest_cfg.type,
                enabled=(row.enabled if row else True),
                base_url=dest_cfg.base_url,
                repo_key=dest_cfg.repo_key,
                path_prefix=dest_cfg.path_prefix,
                enable_xray_scan=dest_cfg.enable_xray_scan,
                last_synced=(row.last_synced if row else None),
                last_sync_error=(row.last_sync_error if row else None),
                tracked_codecollections=tracked,
                mirrored_tag_count=int(mirrored_count),
            )
        )
    return out


@router.get("/jobs", response_model=MirrorJobsResponse)
def list_jobs(
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(pending|running|done|failed)$",
    ),
    destination: Optional[str] = Query(None),
    cc_slug: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(db_session),
) -> MirrorJobsResponse:
    stmt = select(MirrorJob)
    count_stmt = select(func.count(MirrorJob.id))
    if status_filter:
        stmt = stmt.where(MirrorJob.status == status_filter)
        count_stmt = count_stmt.where(MirrorJob.status == status_filter)
    if destination:
        dest_row = db.execute(
            select(Destination).where(Destination.name == destination)
        ).scalar_one_or_none()
        if dest_row is None:
            raise HTTPException(404, detail=f"unknown destination: {destination}")
        stmt = stmt.where(MirrorJob.destination_id == dest_row.id)
        count_stmt = count_stmt.where(MirrorJob.destination_id == dest_row.id)
    if cc_slug:
        cc_row = db.execute(
            select(CodeCollection).where(CodeCollection.slug == cc_slug)
        ).scalar_one_or_none()
        if cc_row is None:
            raise HTTPException(404, detail=f"unknown codecollection: {cc_slug}")
        stmt = stmt.where(MirrorJob.cc_id == cc_row.id)
        count_stmt = count_stmt.where(MirrorJob.cc_id == cc_row.id)
    total = int(db.execute(count_stmt).scalar_one() or 0)
    jobs = db.execute(
        stmt.order_by(MirrorJob.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()

    items: list[MirrorJobView] = []
    for j in jobs:
        cc_row = db.get(CodeCollection, j.cc_id)
        dest_row = db.get(Destination, j.destination_id)
        items.append(
            MirrorJobView(
                id=j.id,
                cc_slug=(cc_row.slug if cc_row else "?"),
                destination=(dest_row.name if dest_row else "?"),
                source_image_ref=j.source_image_ref,
                target_image_ref=j.target_image_ref,
                status=j.status,
                attempts=j.attempts,
                max_attempts=j.max_attempts,
                last_error=j.last_error,
                created_at=j.created_at,
                started_at=j.started_at,
                finished_at=j.finished_at,
            )
        )
    return MirrorJobsResponse(total=total, items=items)


@router.get("/jobs/{job_id}", response_model=MirrorJobDetail)
def get_job(job_id: int, db: Session = Depends(db_session)) -> MirrorJobDetail:
    j = db.get(MirrorJob, job_id)
    if j is None:
        raise HTTPException(404, detail=f"unknown mirror job: {job_id}")
    cc_row = db.get(CodeCollection, j.cc_id)
    dest_row = db.get(Destination, j.destination_id)
    return MirrorJobDetail(
        id=j.id,
        cc_slug=(cc_row.slug if cc_row else "?"),
        destination=(dest_row.name if dest_row else "?"),
        source_image_ref=j.source_image_ref,
        target_image_ref=j.target_image_ref,
        status=j.status,
        attempts=j.attempts,
        max_attempts=j.max_attempts,
        last_error=j.last_error,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
        log_text=j.log_text,
    )


# ---------------------------------------------------------------------------
# admin (mutating) endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/destinations/{name}/sync",
    response_model=MirrorTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def trigger_destination_sync(name: str) -> MirrorTriggerResponse:
    """Enqueue mirror jobs for every CC tracked by this destination."""
    cfg = get_config()
    if cfg.destination_by_name(name) is None:
        raise HTTPException(404, detail=f"unknown destination: {name}")
    summary = enqueue_mirror_jobs(cfg, only_destination=name)
    return MirrorTriggerResponse(
        destination=name,
        codecollection_slug=None,
        jobs_enqueued=summary.get("jobs_enqueued", 0),
        refs_already_mirrored=summary.get("refs_already_mirrored", 0),
        detail="enqueued; the mirror-drain phase will run them on the next interval",
    )


@router.post(
    "/destinations/{name}/codecollections/{slug}/sync",
    response_model=MirrorTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def trigger_codecollection_sync(name: str, slug: str) -> MirrorTriggerResponse:
    cfg = get_config()
    if cfg.destination_by_name(name) is None:
        raise HTTPException(404, detail=f"unknown destination: {name}")
    summary = enqueue_mirror_jobs(cfg, only_destination=name, only_slug=slug)
    return MirrorTriggerResponse(
        destination=name,
        codecollection_slug=slug,
        jobs_enqueued=summary.get("jobs_enqueued", 0),
        refs_already_mirrored=summary.get("refs_already_mirrored", 0),
        detail="enqueued; the mirror-drain phase will run them on the next interval",
    )


@router.post(
    "/drain",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin)],
)
def trigger_drain(
    workers: Optional[int] = Query(None, ge=1, le=32),
) -> dict:
    """Drain pending mirror jobs synchronously. Useful in dev / one-shot
    air-gap mirror runs; the scheduler also drains on its own interval."""
    return drain_mirror_jobs(workers=workers)
