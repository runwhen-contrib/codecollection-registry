"""Git mirror status API (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_config
from app.services.git_mirror import list_repo_status

router = APIRouter(prefix="/api/v1/git", tags=["git"])


def _require_git_enabled() -> None:
    if not get_config().git.enabled:
        raise HTTPException(status_code=404, detail="git mirror service is disabled")


@router.get("/repos")
def list_git_repos() -> list[dict]:
    _require_git_enabled()
    return [
        {
            "slug": s.slug,
            "upstream_url": s.upstream_url,
            "public_url": s.public_url,
            "present": s.present,
            "head_commit": s.head_commit,
            "last_synced": s.last_synced,
            "last_sync_error": s.last_sync_error,
        }
        for s in list_repo_status()
    ]


@router.get("/repos/{slug}")
def get_git_repo(slug: str) -> dict:
    _require_git_enabled()
    for s in list_repo_status():
        if s.slug == slug:
            return {
                "slug": s.slug,
                "upstream_url": s.upstream_url,
                "public_url": s.public_url,
                "local_path": s.local_path,
                "present": s.present,
                "head_commit": s.head_commit,
                "last_synced": s.last_synced,
                "last_sync_error": s.last_sync_error,
            }
    raise HTTPException(status_code=404, detail=f"unknown git repo: {slug}")
