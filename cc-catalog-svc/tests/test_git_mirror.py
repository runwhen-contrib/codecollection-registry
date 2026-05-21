"""Tests for git mirror sync + catalog git_url rewrite."""

from __future__ import annotations

import os
import subprocess

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


def test_run_git_sync_clone_and_update(git_enabled_config, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, auth, *, timeout):
        calls.append(cmd)
        if cmd[:2] == ["clone", "--mirror"]:
            dest = cmd[3]
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "HEAD"), "w") as f:
                f.write("ref: refs/heads/main\n")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:3] == ["-C", cmd[1], "remote"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["--git-dir", cmd[1]]:
            return subprocess.CompletedProcess(cmd, 0, stdout="abc1234\n", stderr="")
        raise AssertionError(f"unexpected git args: {cmd}")

    monkeypatch.setattr("app.services.git_mirror._run_git", fake_run)

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
    monkeypatch.setattr(
        "app.routers.admin.run_git_sync",
        lambda: {"enabled": True, "repos_processed": 0, "repos_updated": 0, "errors": []},
    )
    resp = client.post(
        "/api/v1/admin/sync-git",
        headers={"Authorization": "Bearer admin-test-token"},
    )
    assert resp.status_code == 200
