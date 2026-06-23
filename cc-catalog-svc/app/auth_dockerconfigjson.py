"""
Resolve HTTP Basic credentials from a Docker config.json file.

Why this exists
---------------
The catalog talks to OCI registries via httpx (``app/sources/oci.py``)
and to git remotes via ``git`` subprocesses (``app/services/git_mirror.py``).
Neither honors the Docker keychain natively the way ``crane`` does on
the destination side. Operators running on Kubernetes already have a
``kubernetes.io/dockerconfigjson`` Secret for kubelet image pulls, and
they reasonably expect the catalog to reuse that one credential for
its upstream tag-list / git-clone calls instead of maintaining a
parallel Opaque Secret.

This module provides a small, host-aware lookup against a Docker
config.json file. Both ``SourceAuth`` and ``GitAuth`` accept a new
``dockerconfigjson_env`` field (env var name holding the file path),
and resolve credentials through here at request time.

Format reference
----------------
Standard ``$HOME/.docker/config.json`` schema:

    {
      "auths": {
        "artifactory.example.com": {
          "auth": "<base64 of user:password>"
        },
        "ghcr.io": {
          "username": "u",
          "password": "p"
        }
      }
    }

Both encodings are accepted; ``auth`` wins when both are present
(matches Docker CLI behavior).
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def resolve_basic_pair(file_path: str, target_host: str) -> Optional[tuple[str, str]]:
    """Return ``(username, password)`` for ``target_host`` or ``None``.

    Resolution:

    1. Open and JSON-parse ``file_path``. Any I/O / parse error logs a
       warning and returns ``None`` so the caller can fall back to
       anonymous instead of crashing the poll.
    2. Look up ``auths[target_host]``. **Exact match only** for now;
       wildcard / fallback ``*`` entries are not implemented because
       K8s ``dockerconfigjson`` Secrets in practice carry one host
       per Secret (one Secret per upstream registry).
    3. Within the entry, prefer the base64 ``auth`` field. Fall back
       to explicit ``username`` + ``password``. Both encodings ship in
       the wild — Docker CLI writes ``auth``, ``docker-credential-*``
       helpers and some operators write the split form.
    4. A malformed entry (``auth`` not base64, or ``auth`` decoded
       without a single ``:`` separator) is logged and treated as a
       miss so the caller falls back rather than blowing up.

    Caller convention
    -----------------
    A ``None`` return is normal and is **not** an error indicator — it
    just means "no creds for this host." Callers should warn (once) if
    they were configured to use this auth mode and got a miss for a
    host they expected to find.
    """
    if not file_path:
        return None
    if not os.path.exists(file_path):
        logger.warning(
            "dockerconfigjson: configured path %s does not exist; treating as no creds",
            file_path,
        )
        return None

    try:
        with open(file_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "dockerconfigjson: could not read/parse %s (%s); treating as no creds",
            file_path,
            exc,
        )
        return None

    auths = (data or {}).get("auths") or {}
    if not isinstance(auths, dict):
        logger.warning(
            "dockerconfigjson: %s has non-dict 'auths' key; treating as no creds",
            file_path,
        )
        return None

    entry = auths.get(target_host)
    if not isinstance(entry, dict):
        # Normal miss — log at debug so noisy on-purpose configs (one
        # source per host) don't spam logs.
        logger.debug(
            "dockerconfigjson: %s has no entry for host %s",
            file_path,
            target_host,
        )
        return None

    encoded = entry.get("auth")
    if isinstance(encoded, str) and encoded:
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning(
                "dockerconfigjson: %s host %s has malformed 'auth' field (%s); "
                "treating as no creds",
                file_path,
                target_host,
                exc,
            )
            return None
        if ":" not in decoded:
            logger.warning(
                "dockerconfigjson: %s host %s 'auth' decoded without ':' separator; "
                "treating as no creds",
                file_path,
                target_host,
            )
            return None
        user, _, pwd = decoded.partition(":")
        if user and pwd:
            return user, pwd
        logger.warning(
            "dockerconfigjson: %s host %s 'auth' decoded with empty user/password; "
            "treating as no creds",
            file_path,
            target_host,
        )
        return None

    user = entry.get("username")
    pwd = entry.get("password")
    if isinstance(user, str) and isinstance(pwd, str) and user and pwd:
        return user, pwd

    logger.debug(
        "dockerconfigjson: %s host %s entry has neither valid 'auth' nor "
        "username/password pair; treating as no creds",
        file_path,
        target_host,
    )
    return None


def resolve_basic_pair_from_env(env_var_name: str, target_host: str) -> Optional[tuple[str, str]]:
    """Convenience wrapper: env var holds the file path.

    Matches the schema convention used elsewhere (``token_env``,
    ``user_env``, ``pass_env``, ``docker_config_env`` on the JFrog
    destination): the YAML stores the env-var **name**, not the value,
    so the catalog config is safe to commit and the deployment
    controls where the Secret is projected.

    Returns ``None`` when the env var is unset / empty (treated the
    same as "no creds configured").
    """
    if not env_var_name:
        return None
    file_path = os.environ.get(env_var_name, "")
    if not file_path:
        logger.debug(
            "dockerconfigjson: env var %s is unset/empty; no creds",
            env_var_name,
        )
        return None
    return resolve_basic_pair(file_path, target_host)
