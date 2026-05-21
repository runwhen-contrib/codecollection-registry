"""Integration tests for git smart HTTP serving."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time

import pytest
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.git_http import make_git_wsgi_app, repo_bare_path
from app.git_http.server import _discover_repos


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


def _init_bare_repo_many_branches(path: str, *, branches: int = 40) -> None:
    """Bare repo large enough that git gzip-compresses upload-pack POST bodies."""
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
        for i in range(branches):
            subprocess.run(
                ["git", "branch", f"branch-{i}"],
                cwd=workdir,
                check=True,
                capture_output=True,
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

    repos = _discover_repos(str(tmp_path))
    assert "/demo-cc.git" in repos
    assert repos["/demo-cc.git"].head() is not None

    # WSGI chain is buildable (GunzipFilter + LimitedInputFilter wrapper).
    assert callable(make_git_wsgi_app(str(tmp_path)))


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


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git binary required",
)
def test_git_clone_gzip_upload_pack_via_a2wsgi_mount(tmp_path):
    """Git gzip-compresses upload-pack POST bodies; GunzipFilter must be enabled."""
    import socket

    import uvicorn

    bare = repo_bare_path(str(tmp_path), "many-branches")
    _init_bare_repo_many_branches(bare)

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(tmp_path))))

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(api, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)

    dest = tmp_path / "clone"
    result = subprocess.run(
        [
            "git",
            "clone",
            f"http://127.0.0.1:{port}/git/many-branches.git",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    server.should_exit = True
    thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    assert (dest / ".git").is_dir()
