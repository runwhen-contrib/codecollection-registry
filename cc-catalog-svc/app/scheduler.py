"""
In-process scheduler.

APScheduler's BackgroundScheduler runs three periodic jobs:

  catalog-poll  — every cfg.scheduler.catalog_poll_minutes
  mirror-enqueue — every cfg.scheduler.mirror_poll_minutes
  mirror-drain  — every cfg.scheduler.mirror_poll_minutes (offset by 30s
                  so enqueue almost always lands first within an interval)

We deliberately do NOT use Celery here. Replacing a Celery+Redis pair
with one APScheduler in the FastAPI process is the single biggest
contributor to the "self-contained" feel of this service. The trade-off
is no HA — but a customer that needs HA can run two replicas + an
external scheduler later; the task functions themselves are
architecture-agnostic.

The scheduler is wired in via the FastAPI lifespan in `app/main.py`.
"""

from __future__ import annotations

import logging
from typing import Optional

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_config
from app.services.catalog_poll import run_catalog_poll
from app.services.git_mirror import run_git_sync
from app.services.mirror import (
    drain_mirror_jobs,
    enqueue_mirror_jobs,
    sync_destination_rows,
)

logger = logging.getLogger(__name__)


_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler() -> BackgroundScheduler:
    """Start the in-process scheduler. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    cfg = get_config()
    sched = cfg.scheduler

    # Two executors:
    #   default — periodic poll/enqueue tasks (small, fast)
    #   mirror  — drain task, sized to the configured worker count so the
    #             drain itself can fan out without blocking the poll.
    executors = {
        "default": ThreadPoolExecutor(2),
        "mirror": ThreadPoolExecutor(max(sched.mirror_workers, 1)),
    }

    bg = BackgroundScheduler(
        executors=executors,
        job_defaults={"coalesce": True, "max_instances": 1},
        timezone="UTC",
    )

    # Seed destination rows once at startup so the DB matches config.yaml
    # even before the first mirror-enqueue tick.
    try:
        sync_destination_rows(cfg)
    except Exception:
        logger.exception("initial destination row sync failed; will retry")

    bg.add_job(
        run_catalog_poll,
        trigger="interval",
        minutes=sched.catalog_poll_minutes,
        id="catalog-poll",
        name="catalog-poll",
        next_run_time=_now_plus(seconds=5),
    )
    bg.add_job(
        enqueue_mirror_jobs,
        trigger="interval",
        minutes=sched.mirror_poll_minutes,
        id="mirror-enqueue",
        name="mirror-enqueue",
        next_run_time=_now_plus(seconds=15),
    )
    bg.add_job(
        drain_mirror_jobs,
        trigger="interval",
        minutes=sched.mirror_poll_minutes,
        id="mirror-drain",
        name="mirror-drain",
        executor="mirror",
        next_run_time=_now_plus(seconds=45),
    )

    if cfg.git.enabled and cfg.git.runtime_sync:
        bg.add_job(
            run_git_sync,
            trigger="interval",
            minutes=sched.git_sync_minutes,
            id="git-sync",
            name="git-sync",
            next_run_time=_now_plus(seconds=60),
        )

    bg.start()
    _scheduler = bg
    logger.info(
        "scheduler started: catalog_poll=%dm mirror_poll=%dm workers=%d "
        "git_sync=%dm git_runtime_sync=%s",
        sched.catalog_poll_minutes,
        sched.mirror_poll_minutes,
        sched.mirror_workers,
        sched.git_sync_minutes,
        cfg.git.runtime_sync if cfg.git.enabled else "n/a",
    )
    return bg


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    logger.info("stopping scheduler")
    _scheduler.shutdown(wait=False)
    _scheduler = None


def _now_plus(*, seconds: int):
    """A small initial delay so we don't run jobs before the HTTP
    listener is up — keeps the first /readyz probe honest."""
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
