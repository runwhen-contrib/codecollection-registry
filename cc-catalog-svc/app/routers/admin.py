"""
Tiny admin endpoints that don't fit cleanly in catalog/mirror routers.

    POST /api/v1/admin/reload-config      (admin) — re-read config.yaml
    POST /api/v1/admin/sync-catalog       (admin) — run a catalog poll now
    POST /api/v1/admin/sync-git           (admin) — fetch upstream git mirrors now

The mirror admin endpoints live on the mirror router because they're
mirror-specific.

``sync-git`` accepts an ``allow_runtime_sync`` query flag. When
``git.runtime_sync`` is false (air-gap), the endpoint refuses to reach
upstream unless this flag is explicitly true — that prevents an
operator from accidentally bypassing the air-gap with a stray click.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

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
def admin_sync_git(
    allow_runtime_sync: bool = Query(
        False,
        description=(
            "Required to reach upstream when git.runtime_sync is false. "
            "Defaults to false so air-gap deployments don't accidentally "
            "egress to github.com on a stray admin click."
        ),
    ),
) -> dict:
    return run_git_sync(force=True, allow_runtime_sync=allow_runtime_sync)
