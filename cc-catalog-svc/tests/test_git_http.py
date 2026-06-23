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
from app.git_http.server import is_valid_slug, list_bare_repo_slugs


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


def _mount_test_server(tmp_path: str) -> tuple[FastAPI, int]:
    import socket

    import uvicorn

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(tmp_path)))

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(api, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)
    return api, port


def test_bare_repos_discovered_by_slug(tmp_path):
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    slugs = list_bare_repo_slugs(str(tmp_path))
    assert slugs == ["demo-cc"]

    head = subprocess.run(
        ["git", "--git-dir", bare, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head

    assert callable(make_git_wsgi_app(str(tmp_path)))


def test_info_refs_via_a2wsgi_mount(tmp_path):
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


def test_info_refs_without_dot_git_suffix(tmp_path):
    """Platform gitget calls ls-remote with URLs that omit the ``.git`` suffix."""
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(tmp_path))))

    with TestClient(api) as client:
        resp = client.get(
            "/git/demo-cc/info/refs",
            params={"service": "git-upload-pack"},
            headers={"Accept": "*/*"},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-git-upload-pack-advertisement")
    assert b"refs/heads/" in resp.content


@pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")
def test_ls_remote_without_dot_git_suffix(tmp_path):
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    _, port = _mount_test_server(str(tmp_path))
    result = subprocess.run(
        [
            "git",
            "ls-remote",
            "--heads",
            "--tags",
            f"http://127.0.0.1:{port}/git/demo-cc",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "refs/heads/" in result.stdout


@pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")
def test_git_clone_via_a2wsgi_mount(tmp_path):
    bare = repo_bare_path(str(tmp_path), "many-branches")
    _init_bare_repo_many_branches(bare)

    _, port = _mount_test_server(str(tmp_path))
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
    assert result.returncode == 0, result.stderr
    assert (dest / ".git").is_dir()


def test_repo_bare_path_rejects_traversal(tmp_path):
    """Slug must not be allowed to escape data_dir via .. or path separators."""
    for bad in (
        "../etc",
        "..",
        "foo/bar",
        "foo\\bar",
        ".hidden",
        "",
        " spaces ",
    ):
        with pytest.raises(ValueError):
            repo_bare_path(str(tmp_path), bad)


def test_is_valid_slug():
    assert is_valid_slug("demo-cc")
    assert is_valid_slug("rw_cli.codecollection-001")
    assert not is_valid_slug("../etc")
    assert not is_valid_slug("foo/bar")
    assert not is_valid_slug("")
    assert not is_valid_slug(".hidden")


def test_app_404s_for_path_traversal_attempts(tmp_path):
    """Unmatched / suspicious paths return 404 (not 500, no shell-out)."""
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(tmp_path))))
    with TestClient(api) as client:
        for bad in (
            "/git/../etc/passwd",
            "/git/demo-cc.git/../../etc/passwd",
            "/git/demo-cc.git/objects/pack/pack-xxx.idx",
            "/git/demo-cc.git/config",
            "/git/demo-cc.git/HEAD/../etc",
        ):
            resp = client.get(bad)
            assert resp.status_code in (404, 400), f"{bad} returned {resp.status_code}"


def test_allowed_slugs_filters_unknown_repos(tmp_path):
    """Repos on disk but not in allowed_slugs must be 404, not served."""
    _init_bare_repo(repo_bare_path(str(tmp_path), "allowed-cc"))
    _init_bare_repo(repo_bare_path(str(tmp_path), "leftover-cc"))

    api = FastAPI()
    api.mount(
        "/git",
        WSGIMiddleware(
            make_git_wsgi_app(str(tmp_path), allowed_slugs={"allowed-cc"})
        ),
    )
    with TestClient(api) as client:
        ok = client.get(
            "/git/allowed-cc.git/info/refs",
            params={"service": "git-upload-pack"},
        )
        denied = client.get(
            "/git/leftover-cc.git/info/refs",
            params={"service": "git-upload-pack"},
        )
    assert ok.status_code == 200
    assert denied.status_code == 404


@pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")
def test_shallow_fetch_depth2_tags_via_a2wsgi_mount(tmp_path):
    """Platform gitget uses ``fetch(depth=2, tags=True)`` — must not crash server."""
    bare = repo_bare_path(str(tmp_path), "many-branches")
    _init_bare_repo_many_branches(bare)

    _, port = _mount_test_server(str(tmp_path))
    repo = tmp_path / "work"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "remote",
            "add",
            "origin",
            f"http://127.0.0.1:{port}/git/many-branches.git",
        ],
        cwd=repo,
        check=True,
    )
    result = subprocess.run(
        ["git", "fetch", "-v", "--depth=2", "--tags", "--", "origin"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
