"""Integration tests for git smart HTTP serving."""

from __future__ import annotations

import os
import subprocess
import tempfile

import pytest
from a2wsgi import WSGIMiddleware
from dulwich.repo import NotGitRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.git_http import make_git_wsgi_app, repo_bare_path


def _init_bare_repo(path: str) -> None:
    with tempfile.TemporaryDirectory() as workdir:
        subprocess.run(["git", "init"], cwd=workdir, check=True, capture_output=True)
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=workdir,
            check=True,
            capture_output=True,
            env=env,
        )
        subprocess.run(
            ["git", "clone", "--bare", workdir, path],
            check=True,
            capture_output=True,
        )


def test_dulwich_backend_uses_leading_slash_repo_paths(tmp_path):
    """HTTPGitApplication resolves repos at ``/<slug>.git``, not ``<slug>.git``."""
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    app = make_git_wsgi_app(str(tmp_path))
    repo = app.backend.open_repository("/demo-cc.git")
    assert repo is not None
    assert repo.head() is not None

    with pytest.raises(NotGitRepository):
        app.backend.open_repository("demo-cc.git")

    with pytest.raises(NotGitRepository):
        app.backend.open_repository("/missing.git")


def test_info_refs_via_a2wsgi_mount(tmp_path):
    """Dulwich streams refs via WSGI write(); a2wsgi must expose that callback."""
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(tmp_path))))

    with TestClient(api) as client:
        resp = client.get(
            "/git/demo-cc.git/info/refs",
            params={"service": "git-upload-pack"},
            headers={"Accept": "*/*"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-git-upload-pack-advertisement")
    assert b"# service=git-upload-pack" in resp.content
    assert b"refs/heads/" in resp.content
