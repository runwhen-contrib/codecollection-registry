"""
Git smart HTTP via ``git http-backend``.

Mirrored bare repos live at ``<data_dir>/<slug>.git``. This module maps
them to a WSGI app suitable for mounting under FastAPI (e.g. ``/git``).

We delegate to the native ``git http-backend`` CGI rather than Dulwich so
clients can use shallow fetch (``--depth=N --tags``), which platform
gitget relies on.

Consumers clone with::

    git clone https://<host>/git/<slug>.git
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Callable

logger = logging.getLogger(__name__)


def repo_bare_path(data_dir: str, slug: str) -> str:
    return os.path.join(data_dir, f"{slug}.git")


def repo_exists(data_dir: str, slug: str) -> bool:
    path = repo_bare_path(data_dir, slug)
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD"))


def list_bare_repo_slugs(data_dir: str) -> list[str]:
    """Return sorted slugs for bare repos under ``data_dir``."""
    if not os.path.isdir(data_dir):
        return []
    slugs: list[str] = []
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".git"):
            continue
        path = os.path.join(data_dir, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD")):
            slugs.append(name[:-4])
    return slugs


def _discover_repos(data_dir: str) -> dict[str, str]:
    """Map URL prefixes (``/<slug>.git``) to on-disk bare repo paths."""
    return {
        f"/{slug}.git": repo_bare_path(data_dir, slug)
        for slug in list_bare_repo_slugs(data_dir)
    }


def _parse_cgi_response(raw: bytes) -> tuple[str, list[tuple[str, str]], bytes]:
    """Split ``git http-backend`` CGI stdout into status, headers, body."""
    sep = raw.find(b"\r\n\r\n")
    sep_len = 4
    if sep == -1:
        sep = raw.find(b"\n\n")
        sep_len = 2
    if sep == -1:
        return "500 Internal Server Error", [("Content-Type", "text/plain")], raw

    header_block = raw[:sep].decode("latin-1")
    body = raw[sep + sep_len :]
    status = "200 OK"
    headers: list[tuple[str, str]] = []
    for line in header_block.splitlines():
        if not line.strip():
            continue
        if line.lower().startswith("status:"):
            status = line.split(":", 1)[1].strip()
        elif ":" in line:
            name, value = line.split(":", 1)
            headers.append((name.strip(), value.strip()))
    return status, headers, body


def _git_http_backend_environ(data_dir: str, environ: dict) -> dict[str, str]:
    """Build CGI environment for ``git http-backend`` from a WSGI environ."""
    cmd_env = os.environ.copy()
    cmd_env["GIT_HTTP_EXPORT_ALL"] = "1"
    cmd_env["GIT_PROJECT_ROOT"] = data_dir
    cmd_env["REQUEST_METHOD"] = environ.get("REQUEST_METHOD", "GET")
    cmd_env["PATH_INFO"] = environ.get("PATH_INFO", "")
    cmd_env["QUERY_STRING"] = environ.get("QUERY_STRING", "")
    cmd_env["SERVER_NAME"] = environ.get("SERVER_NAME", "localhost")
    cmd_env["SERVER_PORT"] = str(environ.get("SERVER_PORT", "80"))
    cmd_env["SERVER_PROTOCOL"] = environ.get("SERVER_PROTOCOL", "HTTP/1.1")

    for key, value in environ.items():
        if key.startswith("HTTP_") or key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            cmd_env[key] = value
    return cmd_env


def make_git_wsgi_app(data_dir: str) -> Callable:
    """Build a WSGI app that serves bare repos under ``data_dir``."""
    repos = _discover_repos(data_dir)
    logger.info("git HTTP: serving %d repo(s) from %s via git http-backend", len(repos), data_dir)

    def app(environ, start_response):
        cmd_env = _git_http_backend_environ(data_dir, environ)

        body_in = b""
        if environ.get("REQUEST_METHOD") in ("POST", "PUT", "PATCH"):
            body_in = environ["wsgi.input"].read()
            if body_in:
                cmd_env["CONTENT_LENGTH"] = str(len(body_in))

        try:
            proc = subprocess.run(
                ["git", "http-backend"],
                input=body_in,
                capture_output=True,
                env=cmd_env,
                check=False,
            )
        except FileNotFoundError:
            logger.exception("git binary not found")
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"git http-backend unavailable: git binary not found"]

        if proc.returncode != 0 and not proc.stdout:
            logger.error(
                "git http-backend failed (rc=%s path=%s): %s",
                proc.returncode,
                environ.get("PATH_INFO"),
                proc.stderr.decode("utf-8", errors="replace")[:2000],
            )
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [proc.stderr or b"git http-backend failed"]

        status, headers, body = _parse_cgi_response(proc.stdout)
        write = start_response(status, headers)
        if write:
            if body:
                write(body)
            return []
        return [body]

    return app
