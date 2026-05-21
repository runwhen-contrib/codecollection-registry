"""
Git smart HTTP via dulwich.

Mirrored bare repos live at ``<data_dir>/<slug>.git``. This module maps
them to a WSGI app suitable for mounting under FastAPI (e.g. ``/git``).

Consumers clone with::

    git clone https://<host>/git/<slug>.git
"""

from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)


def repo_bare_path(data_dir: str, slug: str) -> str:
    return os.path.join(data_dir, f"{slug}.git")


def repo_exists(data_dir: str, slug: str) -> bool:
    path = repo_bare_path(data_dir, slug)
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD"))


def _discover_repos(data_dir: str) -> dict[str, "Repo"]:
    """Map Dulwich URL prefixes (``/<slug>.git``) to open Repo handles."""
    from dulwich.repo import Repo

    repos: dict[str, Repo] = {}
    if not os.path.isdir(data_dir):
        return repos
    for name in sorted(os.listdir(data_dir)):
        if not name.endswith(".git"):
            continue
        path = os.path.join(data_dir, name)
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "HEAD")):
            slug = name[:-4]  # strip .git
            # HTTPGitApplication resolves repos via url_prefix() → "/<slug>.git"
            repos[f"/{slug}.git"] = Repo(path)
    return repos


def make_git_wsgi_app(data_dir: str) -> Callable:
    """Build a WSGI app that serves bare repos under ``data_dir``."""
    from dulwich.server import DictBackend
    from dulwich.web import make_wsgi_chain

    repos = _discover_repos(data_dir)
    logger.info("git HTTP: serving %d repo(s) from %s", len(repos), data_dir)
    backend = DictBackend(repos)
    # make_wsgi_chain wraps HTTPGitApplication with GunzipFilter (git clients
    # gzip upload-pack POST bodies) and LimitedInputFilter (Content-Length).
    return make_wsgi_chain(backend)
