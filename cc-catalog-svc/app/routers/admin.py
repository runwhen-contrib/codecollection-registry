"""
Tiny admin endpoints that don't fit cleanly in catalog/mirror routers.

    POST /api/v1/admin/reload-config      (admin) — re-read config.yaml
    POST /api/v1/admin/sync-catalog       (admin) — run a catalog poll now
    POST /api/v1/admin/sync-git           (admin) — fetch upstream git mirrors now

The mirror admin endpoints live on the mirror router because they're
mirror-specific.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.config import reload_config
from app.security import require_admin
from app.services.catalog_poll import run_catalog_poll
from app.services.git_mirror import run_git_sync

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post(
    "/reload-config",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin)],
)
def admin_reload_config() -> dict:
    cfg = reload_config()
    return {
        "status": "ok",
        "sources": len(cfg.sources),
        "destinations": len(cfg.destinations),
        "codecollections": sum(len(s.codecollections) for s in cfg.sources),
    }


@router.post(
    "/sync-catalog",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin)],
)
def admin_sync_catalog() -> dict:
    return run_catalog_poll()


@router.post(
    "/sync-git",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin)],
)
def admin_sync_git() -> dict:
    return run_git_sync(force=True)
