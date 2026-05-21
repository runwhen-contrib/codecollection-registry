"""
Git repository mirror sync.

When ``git.enabled`` is set in config.yaml, this service maintains bare
mirror clones of each configured CodeCollection's ``git_url`` under
``git.data_dir``. The mirrors are served read-only via git smart HTTP
(see ``app/git_http``).

Upstream fetch uses the optional ``git.auth`` block (PAT via ``token_env`` or
HTTP Basic) so private GitHub repos can be mirrored during the brief
window when outbound access is available.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.config import AppConfig, GitAuth, GitServiceConfig, get_config
from app.db import session_scope
from app.git_http import repo_bare_path, repo_exists
from app.models import CodeCollection

logger = logging.getLogger(__name__)


@dataclass
class GitRepoStatus:
    slug: str
    upstream_url: str
    local_path: str
    public_url: Optional[str]
    head_commit: Optional[str]
    last_synced: Optional[datetime]
    last_sync_error: Optional[str]
    present: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def public_git_url(slug: str, git_cfg: GitServiceConfig) -> Optional[str]:
    if not git_cfg.enabled or not git_cfg.public_base_url:
        return None
    return f"{git_cfg.public_base_url.rstrip('/')}/{slug}.git"


def resolve_git_url_for_catalog(
    cc: CodeCollection,
    cfg: Optional[AppConfig] = None,
) -> Optional[str]:
    """Return the git URL platform consumers should clone from.

    When git mirroring is enabled and the local bare repo exists, return
    the configured ``public_base_url`` clone URL. Otherwise fall back to
    the upstream URL stored on the CC row.
    """
    app_cfg = cfg or get_config()
    git_cfg = app_cfg.git
    if git_cfg.enabled and git_cfg.public_base_url and repo_exists(git_cfg.data_dir, cc.slug):
        return public_git_url(cc.slug, git_cfg)
    return cc.git_url


def repos_to_sync(cfg: AppConfig) -> list[tuple[str, str]]:
    """Return ``(slug, upstream_url)`` pairs to mirror."""
    git_cfg = cfg.git
    if not git_cfg.enabled:
        return []

    if git_cfg.codecollections:
        pairs: list[tuple[str, str]] = []
        all_cc = cfg.all_codecollections()
        for slug in git_cfg.codecollections:
            cc = all_cc.get(slug)
            if cc is None:
                logger.warning("git mirror: unknown slug %r in git.codecollections", slug)
                continue
            if not cc.git_url:
                logger.warning("git mirror: slug %r has no git_url", slug)
                continue
            pairs.append((slug, cc.git_url))
        return pairs

    return [(slug, cc.git_url) for slug, cc in cfg.all_codecollections().items() if cc.git_url]


def list_repo_status(cfg: Optional[AppConfig] = None) -> list[GitRepoStatus]:
    app_cfg = cfg or get_config()
    git_cfg = app_cfg.git
    statuses: list[GitRepoStatus] = []

    with session_scope() as db:
        rows = {r.slug: r for r in db.execute(select(CodeCollection)).scalars().all()}

    for slug, upstream in repos_to_sync(app_cfg):
        row = rows.get(slug)
        local_path = repo_bare_path(git_cfg.data_dir, slug)
        statuses.append(
            GitRepoStatus(
                slug=slug,
                upstream_url=upstream,
                local_path=local_path,
                public_url=public_git_url(slug, git_cfg),
                head_commit=getattr(row, "git_head_commit", None) if row else None,
                last_synced=getattr(row, "git_last_synced", None) if row else None,
                last_sync_error=getattr(row, "git_last_sync_error", None) if row else None,
                present=repo_exists(git_cfg.data_dir, slug),
            )
        )
    return statuses


def run_git_sync(config: Optional[AppConfig] = None, *, force: bool = False) -> dict:
    """Fetch/update every configured git mirror.

    When ``git.runtime_sync`` is false (air-gap), this is a no-op unless
    ``force=True`` (admin manual sync).
    """
    cfg = config or get_config()
    git_cfg = cfg.git
    summary = {
        "enabled": git_cfg.enabled,
        "runtime_sync": git_cfg.runtime_sync,
        "repos_processed": 0,
        "repos_updated": 0,
        "errors": [],
    }
    if not git_cfg.enabled:
        return summary
    if not git_cfg.runtime_sync and not force:
        summary["skipped"] = "runtime_sync disabled (using build-time baked mirrors)"
        return summary

    os.makedirs(git_cfg.data_dir, exist_ok=True)

    for slug, upstream_url in repos_to_sync(cfg):
        summary["repos_processed"] += 1
        try:
            head = sync_one_repo(slug, upstream_url, git_cfg)
            _record_git_sync_success(slug, head)
            summary["repos_updated"] += 1
        except Exception as exc:
            logger.exception("git mirror sync failed for %s", slug)
            summary["errors"].append({"slug": slug, "error": str(exc)})
            _record_git_sync_error(slug, str(exc))

    logger.info("git mirror sync complete: %s", summary)
    return summary


def sync_one_repo(slug: str, upstream_url: str, git_cfg: GitServiceConfig) -> str:
    """Clone or update one bare mirror. Returns HEAD commit hash."""
    dest = repo_bare_path(git_cfg.data_dir, slug)
    os.makedirs(git_cfg.data_dir, exist_ok=True)

    if not os.path.isdir(dest):
        _run_git(
            ["clone", "--mirror", upstream_url, dest],
            git_cfg.auth,
            timeout=git_cfg.clone_timeout_seconds,
        )
    else:
        _run_git(
            ["-C", dest, "remote", "update", "--prune"],
            git_cfg.auth,
            timeout=git_cfg.fetch_timeout_seconds,
        )

    head = _run_git(
        ["--git-dir", dest, "rev-parse", "HEAD"],
        git_cfg.auth,
        timeout=30,
    ).stdout.strip()
    if not head:
        raise RuntimeError(f"mirror at {dest} has no HEAD after sync")
    return head


def _git_auth_args(auth: GitAuth) -> list[str]:
    args: list[str] = []
    token = os.environ.get(auth.token_env, "") if auth.token_env else ""
    if token:
        # GitHub git HTTPS expects Basic x-access-token, not Bearer (API-only).
        args.extend(
            [
                "-c",
                f"http.extraHeader=Authorization: Basic {_basic_auth('x-access-token', token)}",
            ]
        )
        return args

    user = os.environ.get(auth.user_env, "") if auth.user_env else ""
    password = os.environ.get(auth.pass_env, "") if auth.pass_env else ""
    if user and password:
        args.extend(["-c", f"http.extraHeader=Authorization: Basic {_basic_auth(user, password)}"])
    return args


def _basic_auth(user: str, password: str) -> str:
    import base64

    raw = f"{user}:{password}".encode()
    return base64.b64encode(raw).decode("ascii")


def _run_git(
    args: list[str],
    auth: GitAuth,
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *_git_auth_args(auth), *args]
    # Never log the full command — auth args may embed secrets indirectly.
    logger.debug("running git %s", " ".join(args))
    proc = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
        },
    )
    return proc


def _record_git_sync_success(slug: str, head_commit: str) -> None:
    with session_scope() as db:
        row = db.execute(
            select(CodeCollection).where(CodeCollection.slug == slug)
        ).scalar_one_or_none()
        if row is None:
            row = CodeCollection(slug=slug)
            db.add(row)
        row.git_head_commit = head_commit
        row.git_last_synced = _utcnow()
        row.git_last_sync_error = None


def _record_git_sync_error(slug: str, error: str) -> None:
    with session_scope() as db:
        row = db.execute(
            select(CodeCollection).where(CodeCollection.slug == slug)
        ).scalar_one_or_none()
        if row is None:
            row = CodeCollection(slug=slug)
            db.add(row)
        row.git_last_sync_error = error[:4000]
