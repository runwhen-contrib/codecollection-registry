"""Tests for git mirror sync + catalog git_url rewrite."""

from __future__ import annotations

import os
import subprocess
import threading

import pytest
import yaml

from app.config import (
    AppConfig,
    GitServiceConfig,
    load_config,
)
from app import config as config_mod
from app.models import CodeCollection
from app.services.git_mirror import (
    public_git_url,
    repos_to_sync,
    resolve_git_url_for_catalog,
    run_git_sync,
)
from app.git_http import repo_bare_path, repo_exists
from fastapi.testclient import TestClient


@pytest.fixture
def git_enabled_config(tmp_path, engine) -> AppConfig:
    git_dir = tmp_path / "git"
    git_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "git": {
                    "enabled": True,
                    "data_dir": str(git_dir),
                    "public_base_url": "https://catalog.example.com/git",
                },
                "sources": [
                    {
                        "name": "test",
                        "type": "oci",
                        "codecollections": [
                            {
                                "slug": "demo-cc",
                                "git_url": "https://github.com/example/demo-cc",
                                "image_registry": "ghcr.io/example/demo-cc",
                            }
                        ],
                    }
                ],
            }
        )
    )
    cfg = load_config(str(config_path))
    config_mod._CONFIG_CACHE = cfg
    return cfg


@pytest.fixture
def git_client(engine, git_enabled_config, monkeypatch):
    monkeypatch.setenv("CC_CATALOG_DISABLE_SCHEDULER", "1")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_public_git_url():
    cfg = GitServiceConfig(
        enabled=True,
        public_base_url="https://catalog.example.com/git/",
    )
    assert public_git_url("demo-cc", cfg) == "https://catalog.example.com/git/demo-cc.git"


def test_repos_to_sync_all_with_git_url(git_enabled_config):
    pairs = repos_to_sync(git_enabled_config)
    assert pairs == [("demo-cc", "https://github.com/example/demo-cc")]


def test_repos_to_sync_respects_explicit_list(git_enabled_config):
    git_enabled_config.git.codecollections = ["demo-cc"]
    assert repos_to_sync(git_enabled_config) == [("demo-cc", "https://github.com/example/demo-cc")]


def test_resolve_git_url_falls_back_without_mirror(git_enabled_config, db_session):
    cc = CodeCollection(
        slug="demo-cc",
        git_url="https://github.com/example/demo-cc",
    )
    db_session.add(cc)
    db_session.commit()
    assert resolve_git_url_for_catalog(cc, git_enabled_config) == (
        "https://github.com/example/demo-cc"
    )


def test_resolve_git_url_uses_public_mirror_when_present(git_enabled_config, db_session, tmp_path):
    bare = repo_bare_path(git_enabled_config.git.data_dir, "demo-cc")
    os.makedirs(bare, exist_ok=True)
    with open(os.path.join(bare, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    cc = CodeCollection(
        slug="demo-cc",
        git_url="https://github.com/example/demo-cc",
    )
    db_session.add(cc)
    db_session.commit()

    assert resolve_git_url_for_catalog(cc, git_enabled_config) == (
        "https://catalog.example.com/git/demo-cc.git"
    )


def test_run_git_sync_skips_when_runtime_sync_disabled(git_enabled_config, monkeypatch):
    git_enabled_config.git.runtime_sync = False
    config_mod._CONFIG_CACHE = git_enabled_config

    def fail_git(*args, **kwargs):
        raise AssertionError("git should not run when runtime_sync is false")

    monkeypatch.setattr("app.services.git_mirror.sync_one_repo", fail_git)
    summary = run_git_sync(git_enabled_config)
    assert summary["skipped"]
    assert summary["repos_processed"] == 0


def test_run_git_sync_force_alone_does_not_bypass_air_gap(
    git_enabled_config, db_session, monkeypatch
):
    """``force=True`` must NOT bypass runtime_sync=False on its own.

    The admin endpoint defaults to allow_runtime_sync=False so a stray
    click in an air-gap deployment can't egress to github.com.
    """
    git_enabled_config.git.runtime_sync = False
    config_mod._CONFIG_CACHE = git_enabled_config

    def fail_git(*args, **kwargs):
        raise AssertionError("git must not run when runtime_sync is false")

    monkeypatch.setattr("app.services.git_mirror.sync_one_repo", fail_git)
    summary = run_git_sync(git_enabled_config, force=True)
    assert "skipped" in summary
    assert summary["repos_processed"] == 0


def test_run_git_sync_allow_runtime_sync_overrides_air_gap(
    git_enabled_config, db_session, monkeypatch
):
    git_enabled_config.git.runtime_sync = False
    config_mod._CONFIG_CACHE = git_enabled_config

    monkeypatch.setattr(
        "app.services.git_mirror.sync_one_repo",
        lambda slug, url, git_cfg: "deadbeef",
    )
    summary = run_git_sync(
        git_enabled_config, force=True, allow_runtime_sync=True
    )
    assert summary["repos_updated"] == 1
    assert "skipped" not in summary


def test_run_git_sync_clone_and_update(git_enabled_config, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, auth, *, timeout):
        calls.append(cmd)
        if cmd[:2] == ["clone", "--mirror"]:
            dest = cmd[3]
            os.makedirs(dest, exist_ok=True)
            os.makedirs(os.path.join(dest, "objects"), exist_ok=True)
            with open(os.path.join(dest, "HEAD"), "w") as f:
                f.write("ref: refs/heads/main\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:3] == ["-C", cmd[1], "remote"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["--git-dir", cmd[1]]:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc1234\n", stderr="")
        raise AssertionError(f"unexpected git args: {cmd}")

    monkeypatch.setattr("app.services.git_mirror._run_git", fake_run)
    # ``sync_one_repo`` calls subprocess.run directly to peek at the
    # existing origin URL before deciding to fetch; stub it to a no-op
    # that reports the current upstream so no set-url is issued.
    def fake_remote_geturl(cmd, **kwargs):
        if cmd[:5] == ["git", "--git-dir", cmd[2], "remote", "get-url"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout="https://github.com/example/demo-cc\n", stderr=""
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.git_mirror.subprocess.run", fake_remote_geturl)

    summary = run_git_sync(git_enabled_config)
    assert summary["repos_processed"] == 1
    assert summary["repos_updated"] == 1
    assert summary["errors"] == []
    assert repo_exists(git_enabled_config.git.data_dir, "demo-cc")

    summary2 = run_git_sync(git_enabled_config)
    assert summary2["repos_updated"] == 1
    assert any(
        cmd[:3] == ["-C", repo_bare_path(git_enabled_config.git.data_dir, "demo-cc"), "remote"]
        for cmd in calls[1:]
    )


def test_git_api_disabled_returns_404(client):
    resp = client.get("/api/v1/git/repos")
    assert resp.status_code == 404


def test_git_api_lists_repos(git_enabled_config, git_client):
    bare = repo_bare_path(git_enabled_config.git.data_dir, "demo-cc")
    os.makedirs(bare, exist_ok=True)
    with open(os.path.join(bare, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    resp = git_client.get("/api/v1/git/repos")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["slug"] == "demo-cc"
    assert body[0]["present"] is True
    assert body[0]["public_url"] == "https://catalog.example.com/git/demo-cc.git"


def test_admin_sync_git(git_enabled_config, client, monkeypatch):
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "enabled": True,
            "repos_processed": 0,
            "repos_updated": 0,
            "errors": [],
        }

    monkeypatch.setattr("app.routers.admin.run_git_sync", fake_run)
    resp = client.post(
        "/api/v1/admin/sync-git",
        headers={"Authorization": "Bearer admin-test-token"},
    )
    assert resp.status_code == 200
    # Default: force=True, allow_runtime_sync=False (air-gap safe).
    assert captured == {"force": True, "allow_runtime_sync": False}


def test_admin_sync_git_allow_runtime_sync_flag(git_enabled_config, client, monkeypatch):
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"enabled": True, "repos_processed": 0, "repos_updated": 0, "errors": []}

    monkeypatch.setattr("app.routers.admin.run_git_sync", fake_run)
    resp = client.post(
        "/api/v1/admin/sync-git?allow_runtime_sync=true",
        headers={"Authorization": "Bearer admin-test-token"},
    )
    assert resp.status_code == 200
    assert captured == {"force": True, "allow_runtime_sync": True}


# ---------------------------------------------------------------------------
# Bugbot regressions
# ---------------------------------------------------------------------------
def test_sync_one_repo_recovers_from_incomplete_bare_clone(
    git_enabled_config, monkeypatch
):
    """A bare dir without HEAD must be removed and re-cloned."""
    from app.services import git_mirror

    dest = repo_bare_path(git_enabled_config.git.data_dir, "demo-cc")
    os.makedirs(dest, exist_ok=True)
    # No HEAD, no objects — looks like an interrupted clone.

    cloned: list[list[str]] = []

    def fake_run(cmd, auth, *, timeout):
        cloned.append(cmd)
        if cmd[:2] == ["clone", "--mirror"]:
            clone_dest = cmd[3]
            os.makedirs(clone_dest, exist_ok=True)
            os.makedirs(os.path.join(clone_dest, "objects"), exist_ok=True)
            with open(os.path.join(clone_dest, "HEAD"), "w") as f:
                f.write("ref: refs/heads/main\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="abc1234\n", stderr="")

    monkeypatch.setattr(git_mirror, "_run_git", fake_run)
    head = git_mirror.sync_one_repo(
        "demo-cc",
        "https://github.com/example/demo-cc",
        git_enabled_config.git,
    )
    assert head == "abc1234"
    # First git invocation after the cleanup must be a fresh clone, not
    # a `remote update` against the junked directory.
    assert cloned[0][:2] == ["clone", "--mirror"]


def test_sync_one_repo_resets_origin_when_upstream_changes(
    git_enabled_config, monkeypatch
):
    """Existing mirror whose origin no longer matches config gets reset."""
    from app.services import git_mirror

    dest = repo_bare_path(git_enabled_config.git.data_dir, "demo-cc")
    os.makedirs(os.path.join(dest, "objects"), exist_ok=True)
    with open(os.path.join(dest, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    # Stub subprocess.run so we observe set-url being issued.
    issued: list[list[str]] = []

    def fake_run(cmd, check=False, capture_output=False, text=False, timeout=None, env=None):
        issued.append(cmd)
        if cmd[:4] == ["git", "--git-dir", dest, "remote"] and cmd[4] == "get-url":
            return subprocess.CompletedProcess(cmd, 0, stdout="https://old.example.com/x\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(git_mirror.subprocess, "run", fake_run)
    monkeypatch.setattr(
        git_mirror,
        "_run_git",
        lambda cmd, auth, *, timeout: subprocess.CompletedProcess(
            cmd, 0, stdout="abc1234\n", stderr=""
        ),
    )

    head = git_mirror.sync_one_repo(
        "demo-cc",
        "https://github.com/example/demo-cc",
        git_enabled_config.git,
    )
    assert head == "abc1234"
    assert any(
        cmd[:5] == ["git", "--git-dir", dest, "remote", "set-url"]
        and cmd[6] == "https://github.com/example/demo-cc"
        for cmd in issued
    )


def test_run_git_sync_lock_prevents_overlap(git_enabled_config, monkeypatch):
    """Second concurrent run_git_sync must skip rather than race the first."""
    from app.services import git_mirror

    holding = threading.Event()
    release = threading.Event()

    def slow_sync(slug, url, git_cfg):
        holding.set()
        release.wait(timeout=5)
        return "abc1234"

    monkeypatch.setattr(git_mirror, "sync_one_repo", slow_sync)

    first_result: dict = {}
    second_result: dict = {}

    def run_first():
        first_result.update(git_mirror.run_git_sync(git_enabled_config))

    t1 = threading.Thread(target=run_first)
    t1.start()
    assert holding.wait(timeout=5)
    second_result.update(git_mirror.run_git_sync(git_enabled_config))
    release.set()
    t1.join(timeout=5)

    assert second_result.get("skipped") == "another git sync is already running"
    assert first_result["repos_updated"] == 1


def test_populate_baked_head_commits_backfills_from_disk(
    git_enabled_config, db_session, monkeypatch
):
    """Build-time baked mirrors should surface a head_commit even with runtime_sync=False."""
    from app.services import git_mirror

    bare = repo_bare_path(git_enabled_config.git.data_dir, "demo-cc")
    os.makedirs(bare, exist_ok=True)
    with open(os.path.join(bare, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")

    monkeypatch.setattr(
        git_mirror, "_head_commit_from_disk", lambda path: "feedface"
    )
    touched = git_mirror.populate_baked_head_commits(git_enabled_config)
    assert touched == 1

    statuses = git_mirror.list_repo_status(git_enabled_config)
    assert any(
        s.slug == "demo-cc" and s.head_commit == "feedface" for s in statuses
    )


def test_init_db_adds_missing_git_columns(tmp_path, monkeypatch):
    """Upgrade path: pre-existing codecollections table gains git_* columns."""
    from sqlalchemy import create_engine, text

    db_url = f"sqlite:///{tmp_path}/upgrade.db"
    monkeypatch.setenv("CC_CATALOG_DB_URL", db_url)
    from app.config import get_settings
    from app import db as db_mod

    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None

    eng = create_engine(db_url, future=True)
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE codecollections ("
                "id INTEGER PRIMARY KEY, slug VARCHAR(200) UNIQUE NOT NULL)"
            )
        )
    eng.dispose()

    db_mod.init_db()
    eng2 = create_engine(db_url, future=True)
    with eng2.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(codecollections)"))}
    eng2.dispose()
    for col in ("git_head_commit", "git_last_synced", "git_last_sync_error"):
        assert col in cols, f"upgrade did not add {col}"
