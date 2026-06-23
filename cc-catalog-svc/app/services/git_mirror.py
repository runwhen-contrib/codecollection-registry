"""
Git repository mirror sync.

When ``git.enabled`` is set in config.yaml, this service maintains bare
mirror clones of each configured CodeCollection's ``git_url`` under
``git.data_dir``. The mirrors are served read-only via git smart HTTP
(see ``app/git_http``).

Upstream fetch uses the optional ``git.auth`` block (PAT via
``token_env`` or HTTP Basic) so private GitHub repos can be mirrored
during the brief window when outbound access is available.

Air-gap mode: when ``runtime_sync`` is false the scheduler never runs
sync, and ``run_git_sync(force=True)`` (admin endpoint) refuses by
default. Operators that need to refresh mirrors from an air-gapped
deployment must pass ``allow_runtime_sync=True`` *and* flip
``git.runtime_sync`` to true via config reload — this is intentional, so
nobody accidentally reaches public github.com from an air-gapped
cluster.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from urllib.parse import urlparse

from app.auth_dockerconfigjson import resolve_basic_pair_from_env
from app.config import AppConfig, GitAuth, GitServiceConfig, get_config
from app.db import session_scope
from app.git_http import (
    is_valid_slug,
    list_bare_repo_slugs,
    repo_bare_path,
    repo_exists,
)
from app.models import CodeCollection

logger = logging.getLogger(__name__)

# Process-wide lock guarding both scheduled and admin-triggered runs.
# Prevents two ``git clone --mirror`` / ``remote update`` invocations
# from hitting the same on-disk bare repo concurrently and corrupting
# packs / refs.
_SYNC_LOCK = threading.Lock()


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
    if not is_valid_slug(slug):
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


def _head_commit_from_disk(bare_path: str) -> Optional[str]:
    """Return the HEAD commit of a bare repo on disk, or None on error."""
    if not os.path.isdir(bare_path):
        return None
    try:
        proc = subprocess.run(
            ["git", "--git-dir", bare_path, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    head = proc.stdout.strip()
    return head or None


def list_repo_status(cfg: Optional[AppConfig] = None) -> list[GitRepoStatus]:
    app_cfg = cfg or get_config()
    git_cfg = app_cfg.git
    statuses: list[GitRepoStatus] = []

    with session_scope() as db:
        rows = {r.slug: r for r in db.execute(select(CodeCollection)).scalars().all()}

    for slug, upstream in repos_to_sync(app_cfg):
        row = rows.get(slug)
        local_path = repo_bare_path(git_cfg.data_dir, slug)
        present = repo_exists(git_cfg.data_dir, slug)
        # Prefer the DB-tracked head_commit (set on the most recent
        # successful runtime sync), but fall back to reading HEAD off
        # disk so build-time baked mirrors still surface a commit even
        # when runtime_sync=False.
        head_commit = getattr(row, "git_head_commit", None) if row else None
        if head_commit is None and present:
            head_commit = _head_commit_from_disk(local_path)
        statuses.append(
            GitRepoStatus(
                slug=slug,
                upstream_url=upstream,
                local_path=local_path,
                public_url=public_git_url(slug, git_cfg),
                head_commit=head_commit,
                last_synced=getattr(row, "git_last_synced", None) if row else None,
                last_sync_error=getattr(row, "git_last_sync_error", None) if row else None,
                present=present,
            )
        )
    return statuses


def run_git_sync(
    config: Optional[AppConfig] = None,
    *,
    force: bool = False,
    allow_runtime_sync: bool = False,
) -> dict:
    """Fetch/update every configured git mirror.

    Args:
        force: bypass the "is anything stale" heuristic and sync now.
            Useful for the admin endpoint. Does NOT bypass
            ``runtime_sync=False`` — see ``allow_runtime_sync``.
        allow_runtime_sync: required for sync to actually reach upstream
            when ``git.runtime_sync`` is false. Defaults to False so an
            air-gapped operator who calls the admin endpoint by mistake
            doesn't trigger outbound git traffic.

    Concurrency: holds a process-wide lock for the whole run, so an
    admin POST that arrives mid-scheduler-tick waits rather than
    racing the scheduler on the same bare repos.
    """
    cfg = config or get_config()
    git_cfg = cfg.git
    summary: dict = {
        "enabled": git_cfg.enabled,
        "runtime_sync": git_cfg.runtime_sync,
        "repos_processed": 0,
        "repos_updated": 0,
        "errors": [],
    }
    if not git_cfg.enabled:
        return summary
    if not git_cfg.runtime_sync and not allow_runtime_sync:
        summary["skipped"] = (
            "runtime_sync disabled (using build-time baked mirrors); "
            "pass allow_runtime_sync=True to override"
        )
        return summary
    # ``force`` is retained for callers that want to bypass a future
    # "is anything stale" check. We don't have one yet, so it's a no-op
    # other than nudging operators that they explicitly asked for it.
    _ = force

    acquired = _SYNC_LOCK.acquire(blocking=False)
    if not acquired:
        summary["skipped"] = "another git sync is already running"
        return summary

    try:
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
    finally:
        _SYNC_LOCK.release()
    return summary


def _is_complete_bare_clone(path: str) -> bool:
    """A bare clone is 'complete' if HEAD exists and has refs."""
    if not os.path.isfile(os.path.join(path, "HEAD")):
        return False
    objects = os.path.join(path, "objects")
    if not os.path.isdir(objects):
        return False
    return True


def _ensure_remote_url(dest: str, upstream_url: str) -> None:
    """Make sure ``origin`` points at ``upstream_url``; reset if not."""
    try:
        proc = subprocess.run(
            ["git", "--git-dir", dest, "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return
    current = proc.stdout.strip()
    if proc.returncode == 0 and current == upstream_url:
        return
    logger.info(
        "git mirror: updating origin url for %s (was %r, now %r)",
        dest,
        current or "<unset>",
        upstream_url,
    )
    subprocess.run(
        ["git", "--git-dir", dest, "remote", "set-url", "origin", upstream_url],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )


def sync_one_repo(slug: str, upstream_url: str, git_cfg: GitServiceConfig) -> str:
    """Clone or update one bare mirror. Returns HEAD commit hash."""
    dest = repo_bare_path(git_cfg.data_dir, slug)
    os.makedirs(git_cfg.data_dir, exist_ok=True)

    # If a previous clone died mid-flight the directory exists but is
    # missing HEAD / objects. Treat as garbage and re-clone, otherwise
    # ``git remote update`` would just keep failing forever.
    if os.path.isdir(dest) and not _is_complete_bare_clone(dest):
        logger.warning(
            "git mirror: %s exists but is not a complete bare clone; removing and re-cloning",
            dest,
        )
        shutil.rmtree(dest, ignore_errors=True)

    if not os.path.isdir(dest):
        _run_git(
            ["clone", "--mirror", upstream_url, dest],
            git_cfg.auth,
            timeout=git_cfg.clone_timeout_seconds,
            upstream_url=upstream_url,
        )
    else:
        # If the configured upstream_url changed since the last clone
        # (e.g. operator updated config.yaml to point at a fork) reset
        # origin so subsequent fetches pull from the right place.
        _ensure_remote_url(dest, upstream_url)
        _run_git(
            ["-C", dest, "remote", "update", "--prune"],
            git_cfg.auth,
            timeout=git_cfg.fetch_timeout_seconds,
            upstream_url=upstream_url,
        )

    # rev-parse is a local op; no upstream_url needed (no network call,
    # so auth is moot and the host lookup would be a no-op).
    head = _run_git(
        ["--git-dir", dest, "rev-parse", "HEAD"],
        git_cfg.auth,
        timeout=30,
    ).stdout.strip()
    if not head:
        raise RuntimeError(f"mirror at {dest} has no HEAD after sync")
    return head


def populate_baked_head_commits(cfg: Optional[AppConfig] = None) -> int:
    """Backfill ``CodeCollection.git_head_commit`` from baked mirrors on disk.

    Called once at startup so ``GET /api/v1/git/repos`` and catalog
    rewrites have accurate HEAD info immediately, even in air-gap
    deployments where ``run_git_sync`` is never invoked.

    Returns the number of rows touched.
    """
    app_cfg = cfg or get_config()
    git_cfg = app_cfg.git
    if not git_cfg.enabled:
        return 0

    on_disk = set(list_bare_repo_slugs(git_cfg.data_dir))
    if not on_disk:
        return 0

    touched = 0
    with session_scope() as db:
        rows_by_slug = {r.slug: r for r in db.execute(select(CodeCollection)).scalars().all()}
        for slug, _ in repos_to_sync(app_cfg):
            if slug not in on_disk:
                continue
            head = _head_commit_from_disk(repo_bare_path(git_cfg.data_dir, slug))
            if not head:
                continue
            row = rows_by_slug.get(slug)
            if row is None:
                row = CodeCollection(slug=slug)
                db.add(row)
            if row.git_head_commit == head:
                continue
            row.git_head_commit = head
            # Don't fake a last_synced timestamp — baked content was
            # synced at build time, not now. ``last_synced`` stays NULL
            # until a real runtime sync fires.
            touched += 1
    if touched:
        logger.info("git mirror: backfilled head_commit for %d baked repo(s)", touched)
    return touched


def _git_auth_args(auth: GitAuth, upstream_url: Optional[str] = None) -> list[str]:
    """Render ``-c http.extraHeader=...`` args for ``git`` to use.

    ``upstream_url`` is only consulted when ``auth.dockerconfigjson_env``
    is set — the catalog needs the host to look up in the file's
    ``auths`` map. For ``token_env`` / ``user_env``+``pass_env`` the URL
    is irrelevant (env-var values apply to every git call equally).
    Callers that don't have a URL (e.g. local ``git rev-parse``) can
    omit it; those operations don't talk to a remote so auth is moot.
    """
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

    if auth.dockerconfigjson_env and upstream_url:
        try:
            host = urlparse(upstream_url).hostname
        except ValueError:
            host = None
        if host:
            pair = resolve_basic_pair_from_env(auth.dockerconfigjson_env, host)
            if pair is not None:
                dc_user, dc_pwd = pair
                args.extend(
                    [
                        "-c",
                        f"http.extraHeader=Authorization: Basic {_basic_auth(dc_user, dc_pwd)}",
                    ]
                )
                return args
            logger.warning(
                "git mirror: dockerconfigjson_env=%s yielded no creds for host %s "
                "(upstream_url=%s); falling back to anonymous",
                auth.dockerconfigjson_env,
                host,
                upstream_url,
            )
        else:
            logger.warning(
                "git mirror: dockerconfigjson_env set but upstream_url=%r has no parseable host; "
                "falling back to anonymous",
                upstream_url,
            )
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
    upstream_url: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *_git_auth_args(auth, upstream_url=upstream_url), *args]
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
