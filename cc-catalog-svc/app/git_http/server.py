"""
Git smart HTTP via ``git http-backend``.

Mirrored bare repos live at ``<data_dir>/<slug>.git``. This module maps
them to a WSGI app suitable for mounting under FastAPI (e.g. ``/git``).

We delegate to the native ``git http-backend`` CGI rather than Dulwich
so clients can use shallow fetch (``--depth=N --tags``), which the
platform's gitget relies on. Each request spawns ``git http-backend``,
which reads ``GIT_PROJECT_ROOT`` directly from disk — so mirrors created
or refreshed after process start are served immediately, no restart
needed.

Consumers clone with::

    git clone https://<host>/git/<slug>.git

Security notes:
  * Slugs are validated against ``_VALID_SLUG_RE`` before being joined
    onto ``data_dir``. This blocks ``..`` segments, slashes, and other
    path-escape tricks.
  * When ``allowed_slugs`` is supplied, only those repos are served.
    Any other ``*.git`` directory under ``data_dir`` returns 404. This
    keeps leftover or operator-staged mirrors from being unintentionally
    exposed over unauthenticated HTTP.
  * Response bytes from ``git http-backend`` are streamed to the client
    via the WSGI ``write`` callback in 64 KiB chunks; we never buffer
    a full packfile in memory.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Callable, Iterable, Optional

logger = logging.getLogger(__name__)

# Slugs are stable CodeCollection identifiers. Anchored, ascii-only, and
# no path separators / dots so we can join straight onto ``data_dir``
# without worrying about traversal.
_VALID_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")

# Chunk size for streaming the CGI response body back over WSGI. 64 KiB
# matches what git's own smart-HTTP server uses.
_STREAM_CHUNK_BYTES = 64 * 1024

# Only ``info/refs`` and the two smart-HTTP service endpoints reach the
# git CGI. Anything else returns 404 so we don't accidentally expose
# raw refs / loose objects under unauthenticated HTTP.
#
# ``.git`` is optional in the URL path. GitHub/GitLab accept clone URLs
# with or without the suffix; platform consumers (sobow gitget) often
# normalize to the bare form before ``git ls-remote``. Bare repos on disk
# are still ``<slug>.git`` — we rewrite PATH_INFO before http-backend.
_PATH_RE = re.compile(
    r"^/(?P<slug>[A-Za-z0-9][A-Za-z0-9._-]{0,199})(?:\.git)?"
    r"(?P<rest>/info/refs|/git-upload-pack|/git-receive-pack|/HEAD)$"
)


def _canonical_path_info(slug: str, rest: str) -> str:
    """Return PATH_INFO with ``<slug>.git`` for ``git http-backend``."""
    return f"/{slug}.git{rest}"


def is_valid_slug(slug: str) -> bool:
    """Return True if ``slug`` is safe to join onto ``data_dir``."""
    return bool(slug) and bool(_VALID_SLUG_RE.match(slug))


def repo_bare_path(data_dir: str, slug: str) -> str:
    """Return the on-disk path for ``<slug>.git`` under ``data_dir``.

    Raises ``ValueError`` if ``slug`` contains characters that could
    escape ``data_dir`` (path separators, ``..`` segments, etc.).
    """
    if not is_valid_slug(slug):
        raise ValueError(f"invalid git mirror slug: {slug!r}")
    return os.path.join(data_dir, f"{slug}.git")


def repo_exists(data_dir: str, slug: str) -> bool:
    """True if ``<data_dir>/<slug>.git`` looks like a usable bare repo."""
    if not is_valid_slug(slug):
        return False
    path = repo_bare_path(data_dir, slug)
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD"))


def list_bare_repo_slugs(data_dir: str) -> list[str]:
    """Return sorted slugs for bare repos under ``data_dir``.

    Quietly skips entries with invalid slug syntax so operator-staged
    directories with funny names can't poison the listing.
    """
    if not os.path.isdir(data_dir):
        return []
    slugs: list[str] = []
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".git"):
            continue
        slug = name[:-4]
        if not is_valid_slug(slug):
            logger.warning("git HTTP: skipping invalid slug %r under %s", slug, data_dir)
            continue
        path = os.path.join(data_dir, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD")):
            slugs.append(slug)
    return slugs


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


def _stream_body(stdout, write: Callable[[bytes], None]) -> None:
    """Pump stdout chunks straight to the WSGI ``write`` callback."""
    while True:
        chunk = stdout.read(_STREAM_CHUNK_BYTES)
        if not chunk:
            return
        write(chunk)


def _read_cgi_header(stdout) -> tuple[bytes, bytes]:
    """Read until the CGI header/body separator. Returns (headers, leftover)."""
    buf = bytearray()
    while True:
        chunk = stdout.read(1)
        if not chunk:
            return bytes(buf), b""
        buf.extend(chunk)
        for sep in (b"\r\n\r\n", b"\n\n"):
            idx = buf.find(sep)
            if idx != -1:
                return bytes(buf[:idx]), bytes(buf[idx + len(sep) :])


def make_git_wsgi_app(
    data_dir: str,
    *,
    allowed_slugs: Optional[Iterable[str]] = None,
) -> Callable:
    """Build a WSGI app that serves bare repos under ``data_dir``.

    Args:
        data_dir: Directory containing ``<slug>.git`` bare repos.
        allowed_slugs: If provided, only these slugs are served (404 for
            anything else under ``data_dir``). Pass ``None`` to serve
            every valid slug discovered on disk — typically only useful
            for local dev / tests.
    """
    allowed: Optional[frozenset[str]]
    if allowed_slugs is None:
        allowed = None
    else:
        allowed = frozenset(s for s in allowed_slugs if is_valid_slug(s))

    if allowed is None:
        logger.info(
            "git HTTP: serving %d repo(s) from %s via git http-backend (UNRESTRICTED)",
            len(list_bare_repo_slugs(data_dir)),
            data_dir,
        )
    else:
        logger.info(
            "git HTTP: serving %d allowed slug(s) from %s via git http-backend",
            len(allowed),
            data_dir,
        )

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "")
        match = _PATH_RE.match(path)
        if not match:
            return _send_not_found(start_response, "not a smart git HTTP path")

        slug = match.group("slug")
        if slug.endswith(".git"):
            slug = slug[:-4]
        if not is_valid_slug(slug):
            return _send_not_found(start_response, "not a smart git HTTP path")

        if allowed is not None and slug not in allowed:
            logger.info("git HTTP: 404 for unallowed slug %r", slug)
            return _send_not_found(start_response, "unknown git mirror")

        if not repo_exists(data_dir, slug):
            return _send_not_found(start_response, "git mirror not found on disk")

        # git http-backend expects PATH_INFO like /{slug}.git/info/refs.
        backend_environ = dict(environ)
        backend_environ["PATH_INFO"] = _canonical_path_info(slug, match.group("rest"))
        cmd_env = _git_http_backend_environ(data_dir, backend_environ)
        body_in = b""
        if environ.get("REQUEST_METHOD") in ("POST", "PUT", "PATCH"):
            body_in = environ["wsgi.input"].read()
            if body_in:
                cmd_env["CONTENT_LENGTH"] = str(len(body_in))

        try:
            proc = subprocess.Popen(  # noqa: S603 - git is trusted CGI
                ["git", "http-backend"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cmd_env,
            )
        except FileNotFoundError:
            logger.exception("git binary not found")
            start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
            return [b"git http-backend unavailable: git binary not found"]

        try:
            if body_in:
                proc.stdin.write(body_in)
            proc.stdin.close()

            header_block, leftover = _read_cgi_header(proc.stdout)
            if not header_block:
                stderr = proc.stderr.read()
                proc.wait()
                logger.error(
                    "git http-backend produced no output (rc=%s path=%s): %s",
                    proc.returncode,
                    path,
                    stderr.decode("utf-8", errors="replace")[:2000],
                )
                start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
                return [stderr or b"git http-backend failed"]

            status, headers, _ = _parse_cgi_response(header_block + b"\r\n\r\n")
            write = start_response(status, headers)
            if write:
                if leftover:
                    write(leftover)
                _stream_body(proc.stdout, write)
                proc.wait()
                _log_proc_stderr(proc, path)
                return []

            # Fallback path: caller's WSGI stack didn't return a ``write``
            # callable. Buffer the body (size is bounded by what a single
            # client requested anyway).
            body_chunks: list[bytes] = [leftover] if leftover else []
            while True:
                chunk = proc.stdout.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                body_chunks.append(chunk)
            proc.wait()
            _log_proc_stderr(proc, path)
            return body_chunks
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    return app


def _send_not_found(start_response, message: str) -> list[bytes]:
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [message.encode("utf-8")]


def _log_proc_stderr(proc: subprocess.Popen, path: str) -> None:
    if proc.returncode == 0:
        return
    try:
        stderr = proc.stderr.read() if proc.stderr else b""
    except Exception:  # pragma: no cover - best-effort logging
        return
    if stderr:
        logger.warning(
            "git http-backend exited rc=%s for %s: %s",
            proc.returncode,
            path,
            stderr.decode("utf-8", errors="replace")[:2000],
        )
