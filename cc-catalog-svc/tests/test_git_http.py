"""Integration tests for git smart HTTP serving."""

from __future__ import annotations

import io
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


# ---------------------------------------------------------------------------
# Foreign-owned baked mirrors (OpenShift arbitrary-uid) — see
# _git_http_backend_environ. GIT_TEST_ASSUME_DIFFERENT_OWNER is git's own knob
# for forcing the ownership check to fail, so these run as any user.
# ---------------------------------------------------------------------------
def test_info_refs_serves_repo_owned_by_another_user(tmp_path, monkeypatch):
    """A mirror owned by a different uid must still clone.

    Release images bake mirrors as uid 1000; OpenShift's restricted SCC runs
    the pod as an arbitrary uid. Without a scoped safe.directory, git refuses
    with "detected dubious ownership" and http-backend answers Status: 500.
    """
    bare = repo_bare_path(str(tmp_path), "demo-cc")
    _init_bare_repo(bare)
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(tmp_path))))

    with TestClient(api) as client:
        resp = client.get(
            "/git/demo-cc.git/info/refs",
            params={"service": "git-upload-pack"},
            headers={"Accept": "*/*"},
        )

    assert resp.status_code == 200, resp.content[:500]
    assert resp.headers["content-type"].startswith("application/x-git-upload-pack-advertisement")
    assert b"refs/heads/" in resp.content
    assert b"dubious ownership" not in resp.content


def test_safe_directory_is_scoped_to_the_served_repo(tmp_path):
    """safe.directory names one repo path, not data_dir and not '*'."""
    from app.git_http.server import _git_http_backend_environ

    served = repo_bare_path(str(tmp_path), "demo-cc")
    env = _git_http_backend_environ(str(tmp_path), {}, safe_directory=served)

    count = int(env["GIT_CONFIG_COUNT"])
    pairs = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}
    assert pairs["safe.directory"] == served
    assert pairs["safe.directory"] not in ("*", str(tmp_path))


def test_operator_supplied_git_config_is_preserved(tmp_path, monkeypatch):
    """Appending must not clobber GIT_CONFIG_* already set on the container.

    Operators set these as the out-of-band workaround; silently dropping them
    on upgrade would regress whatever else they configured.
    """
    from app.git_http.server import _git_http_backend_environ

    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "http.postBuffer")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "524288000")

    served = repo_bare_path(str(tmp_path), "demo-cc")
    env = _git_http_backend_environ(str(tmp_path), {}, safe_directory=served)

    count = int(env["GIT_CONFIG_COUNT"])
    assert count == 2
    pairs = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}
    assert pairs["http.postBuffer"] == "524288000"
    assert pairs["safe.directory"] == served


def test_backend_stderr_logged_even_when_exit_code_is_zero(caplog):
    """http-backend dies via CGI Status: 5xx and exits 0 — must still log.

    This is the regression that hid the 500: the old guard returned early on
    rc == 0, so the only copy of git's message went to the response body.
    """
    import logging
    import subprocess as sp

    from app.git_http.server import _log_proc_stderr

    proc = sp.Popen(["printf", "%s", ""], stdout=sp.PIPE, stderr=sp.PIPE)
    proc.wait()
    proc.stderr = io.BytesIO(b"fatal: detected dubious ownership in repository at '/x.git'")

    with caplog.at_level(logging.WARNING, logger="app.git_http.server"):
        _log_proc_stderr(proc, "/git/x.git/info/refs", "500 Internal Server Error")

    assert proc.returncode == 0
    assert "dubious ownership" in caplog.text
    assert "status=500 Internal Server Error" in caplog.text


def test_healthy_request_does_not_warn(caplog):
    """Quiet on success: empty stderr + 200 must produce no WARNING."""
    import logging
    import subprocess as sp

    from app.git_http.server import _log_proc_stderr

    proc = sp.Popen(["printf", "%s", ""], stdout=sp.PIPE, stderr=sp.PIPE)
    proc.wait()
    proc.stderr = io.BytesIO(b"")

    with caplog.at_level(logging.WARNING, logger="app.git_http.server"):
        _log_proc_stderr(proc, "/git/x.git/info/refs", "200 OK")

    assert caplog.text == ""


def test_safe_directory_resolves_symlinked_data_dir(tmp_path):
    """A symlinked data_dir must still produce a matching safe.directory.

    git compares safe.directory against the RESOLVED gitdir, so an
    unresolved path would silently fail to match and still 500. Deployments
    where data_dir traverses a symlink are the realistic case.
    """
    from app.git_http.server import _git_http_backend_environ

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)

    bare = repo_bare_path(str(link), "demo-cc")
    _init_bare_repo(bare)

    env = _git_http_backend_environ(str(link), {}, safe_directory=bare)
    count = int(env["GIT_CONFIG_COUNT"])
    pairs = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(count)}

    assert pairs["safe.directory"] == os.path.realpath(bare)
    assert pairs["safe.directory"] == str(real.resolve() / "demo-cc.git")


def test_clone_succeeds_through_symlinked_data_dir_when_foreign_owned(tmp_path, monkeypatch):
    """End-to-end: symlinked data_dir + foreign ownership must still serve."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    _init_bare_repo(repo_bare_path(str(link), "demo-cc"))
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")

    api = FastAPI()
    api.mount("/git", WSGIMiddleware(make_git_wsgi_app(str(link))))

    with TestClient(api) as client:
        resp = client.get(
            "/git/demo-cc.git/info/refs",
            params={"service": "git-upload-pack"},
            headers={"Accept": "*/*"},
        )

    assert resp.status_code == 200, resp.content[:500]
    assert b"refs/heads/" in resp.content
