"""
JFrog Artifactory destination plugin.

Artifactory exposes a vanilla OCI Distribution v2 endpoint per Docker
repository, so `crane copy` works without modification. This plugin's
job is therefore narrowly scoped:

  1. Compose the destination ref (`{base_url_host}/{repo_key}/{path_prefix?}/{cc_slug}:{tag}`).
  2. Provide auth to crane via a per-job DOCKER_CONFIG (so we never put
     tokens on argv or pollute the global Docker config).
  3. Implement an `exists()` check that HEADs the Artifactory manifest
     endpoint so the mirror engine can short-circuit already-mirrored
     tags.
  4. Optionally kick a JFrog Xray scan after a successful push.

Auth options (set in `destinations[].auth` in config.yaml). Set EXACTLY
ONE of:

  - ``token_env: JFROG_ACCESS_TOKEN``  — bearer access token (preferred)
  - ``user_env: JFROG_USER`` + ``pass_env: JFROG_PASS``
                                       — HTTP Basic (LDAP user, or user +
                                         access-token-as-password)
  - ``docker_config_env: JFROG_DOCKER_CONFIG``
                                       — path to a docker config.json
                                         (use when an external tool
                                         already manages the file, e.g.
                                         a k8s pull secret mounted in)

If nothing is set, ``crane`` runs anonymously and the destination must
allow anonymous push (rare).

Precedence when multiple slots are populated is enforced at config-load
time by ``JFrogAuth``'s validator: misconfigurations fail fast.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import tempfile
from typing import Iterator, Optional
from urllib.parse import urlparse

import httpx

from app.destinations.base import ImageDestination, MirrorResult, run_crane_copy

logger = logging.getLogger(__name__)


class JFrogDestination(ImageDestination):
    name = "jfrog"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def target_ref(self, dest_cfg: dict, cc: dict, image_tag: str) -> str:
        host = self._host(dest_cfg)
        repo_key = dest_cfg["repo_key"]
        prefix = (dest_cfg.get("path_prefix") or "").strip("/")
        slug = cc["slug"]

        parts = [host, repo_key]
        if prefix:
            parts.append(prefix)
        parts.append(slug)
        path = "/".join(parts)
        return f"{path}:{image_tag}"

    def exists(self, dest_cfg: dict, target_ref: str) -> bool:
        """HEAD the Artifactory manifest for `target_ref`.

        Returns True only on a 200. 404 -> False (needs push). Anything
        else is raised so the scheduler logs it and retries — silently
        treating a 5xx as "needs push" would cause endless re-pushes
        against an unhealthy Artifactory.
        """
        host, repo_key, path_in_repo, tag = _split_target_ref(target_ref, dest_cfg)
        url = (
            f"https://{host}/artifactory/api/docker/{repo_key}/v2/"
            f"{path_in_repo}/manifests/{tag}"
        )
        headers = {"Accept": "application/vnd.oci.image.manifest.v1+json"}
        auth = self._http_auth(dest_cfg)
        with httpx.Client(timeout=10.0) as client:
            resp = client.head(url, headers=headers, auth=auth)
        if resp.status_code == 200:
            return True
        if resp.status_code in (401, 403):
            raise PermissionError(
                f"JFrog destination {dest_cfg.get('name')!r} cannot read "
                f"{url}: HTTP {resp.status_code}. Check token scope."
            )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return False  # unreachable but keeps mypy happy

    def push(
        self,
        dest_cfg: dict,
        source_ref: str,
        target_ref: str,
        *,
        timeout: int = 600,
    ) -> MirrorResult:
        """Wrap the default crane-based push with a temporary
        DOCKER_CONFIG synthesized from the JFrog token, then optionally
        trigger an Xray scan.
        """
        with self._with_crane_auth(dest_cfg) as env_extra:
            result = run_crane_copy(
                source_ref,
                target_ref,
                env_extra=env_extra,
                timeout=timeout,
            )

        if result.success and dest_cfg.get("enable_xray_scan"):
            try:
                self._trigger_xray_scan(dest_cfg, target_ref)
            except Exception as exc:  # don't fail the mirror on a scan-trigger blip
                logger.warning("JFrog Xray scan trigger failed for %s: %r", target_ref, exc)
                result.log_text = (result.log_text or "") + (
                    f"\n[xray scan trigger failed: {exc!r}]"
                )

        return result

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _host(dest_cfg: dict) -> str:
        """`https://acme.jfrog.io` -> `acme.jfrog.io`."""
        base = dest_cfg.get("base_url") or ""
        parsed = urlparse(base)
        return parsed.netloc or parsed.path or base

    @contextlib.contextmanager
    def _with_crane_auth(self, dest_cfg: dict) -> Iterator[dict]:
        """Yield env extras for `crane` with Artifactory auth wired up.

        We use a per-call temporary docker config (one file, deleted on
        exit) and point crane at it via DOCKER_CONFIG. This is the only
        env var crane / go-containerregistry honors for auth.

        Auth resolution order (see module docstring):
          1. ``docker_config_env`` — reuse an existing config.json
          2. ``token_env``         — Bearer access token (encoded as ``_:<token>``)
          3. ``user_env``+``pass_env`` — HTTP Basic (encoded as ``<user>:<pass>``)
          4. Anonymous fallback

        Note: ``JFrogAuth``'s validator enforces "exactly one mode" at
        config-load time, so in practice only one branch fires.

        Why not just CRI_CONFIG / a global config? Because two destinations
        on the same Artifactory host with different scoped tokens would
        collide, and because dropping the file once we're done keeps the
        token out of the container's writable layer.
        """
        auth_cfg = dest_cfg.get("auth") or {}
        docker_config_env = auth_cfg.get("docker_config_env")
        token_env = auth_cfg.get("token_env")
        user_env = auth_cfg.get("user_env")
        pass_env = auth_cfg.get("pass_env")

        host = self._host(dest_cfg)

        # 1. Pre-existing docker config wins — operator has full control.
        if docker_config_env:
            path = os.environ.get(docker_config_env, "")
            if path and os.path.exists(path):
                yield {"DOCKER_CONFIG": os.path.dirname(path)}
                return
            logger.warning(
                "jfrog destination %s: docker_config_env=%s points at missing file; "
                "falling back to other auth modes",
                dest_cfg.get("name"),
                docker_config_env,
            )

        # 2/3. Resolve a (user, secret) pair from token_env OR basic creds.
        auth_pair = self._resolve_basic_pair(dest_cfg, token_env, user_env, pass_env)

        if auth_pair is None:
            # No usable auth at all — let crane try anonymously. Will
            # surface a meaningful 401 from the registry on push.
            yield {}
            return

        # Synthesize a docker config.json. crane reads /<dir>/config.json
        # so we write to <tmpdir>/config.json and point DOCKER_CONFIG at
        # the directory.
        user, secret = auth_pair
        cred = base64.b64encode(f"{user}:{secret}".encode("utf-8")).decode("ascii")
        config = {
            "auths": {
                host: {"auth": cred},
            }
        }
        with tempfile.TemporaryDirectory(prefix="cc-catalog-jfrog-") as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as fp:
                json.dump(config, fp)
            os.chmod(config_path, 0o600)
            yield {"DOCKER_CONFIG": tmpdir}

    @staticmethod
    def _resolve_basic_pair(
        dest_cfg: dict,
        token_env: Optional[str],
        user_env: Optional[str],
        pass_env: Optional[str],
    ) -> Optional[tuple[str, str]]:
        """Collapse token/basic config into a single ``(user, secret)``.

        - ``token_env``  -> ``("_", <token>)``  (Artifactory convention)
        - ``user_env``+``pass_env`` -> ``(<user>, <pass>)``
        - anything missing in env -> ``None`` with a warning
        """
        name = dest_cfg.get("name")
        if token_env:
            token = os.environ.get(token_env)
            if token:
                # Artifactory's Docker subsystem accepts `_:<token>` as
                # equivalent to a Bearer header.
                return ("_", token)
            logger.warning(
                "jfrog destination %s: token_env=%s is empty",
                name,
                token_env,
            )
            return None

        if user_env and pass_env:
            user = os.environ.get(user_env)
            pwd = os.environ.get(pass_env)
            if user and pwd:
                return (user, pwd)
            logger.warning(
                "jfrog destination %s: user_env=%s pass_env=%s one/both empty",
                name,
                user_env,
                pass_env,
            )
            return None

        return None

    @classmethod
    def _http_auth(cls, dest_cfg: dict) -> Optional[tuple[str, str]]:
        """httpx-style basic auth tuple for the manifest HEAD / Xray POST.

        Picks the same credential the crane subprocess would use:
        token_env (mapped to ``_:<token>``) or user_env+pass_env.
        ``docker_config_env`` is intentionally not honored here — it's
        a crane-only convenience; reading and parsing the file in
        application code would duplicate crane's logic.
        """
        auth_cfg = dest_cfg.get("auth") or {}
        return cls._resolve_basic_pair(
            dest_cfg,
            auth_cfg.get("token_env"),
            auth_cfg.get("user_env"),
            auth_cfg.get("pass_env"),
        )

    def _trigger_xray_scan(self, dest_cfg: dict, target_ref: str) -> None:
        """POST to Xray's `scanArtifact` for the just-pushed manifest.

        Best-effort: a 200 is success, anything else logs and is
        swallowed by the caller. Xray scan triggers are eventually
        consistent — Artifactory may take a while to register that the
        artifact exists before Xray can pick it up.
        """
        host, repo_key, path_in_repo, tag = _split_target_ref(target_ref, dest_cfg)
        # Xray identifies artifacts by their Artifactory path.
        artifact_path = (
            f"{repo_key}/{path_in_repo}/manifest.json"  # tag-level manifest path
            if not tag
            else f"{repo_key}/{path_in_repo}/{tag}/manifest.json"
        )
        url = f"https://{host}/xray/api/v1/scanArtifact"
        auth = self._http_auth(dest_cfg)
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                json={"componentID": f"docker://{artifact_path}"},
                auth=auth,
            )
            resp.raise_for_status()


def _split_target_ref(target_ref: str, dest_cfg: dict) -> tuple[str, str, str, str]:
    """Decompose `acme.jfrog.io/runwhen-virtual/codecollections/foo:tag`
    into (host, repo_key, path_in_repo, tag).

    We could re-derive these from dest_cfg + cc, but doing the math
    against the actual `target_ref` keeps the exists()/scan logic in
    sync with whatever `target_ref()` produced.
    """
    if ":" not in target_ref:
        raise ValueError(f"target_ref must include a tag: {target_ref!r}")
    repo_part, _, tag = target_ref.rpartition(":")

    host, _, rest = repo_part.partition("/")
    if not rest:
        raise ValueError(f"target_ref missing repo path: {target_ref!r}")

    repo_key = dest_cfg.get("repo_key")
    if not repo_key:
        raise ValueError("destination is missing repo_key")
    if not rest.startswith(f"{repo_key}/") and rest != repo_key:
        raise ValueError(
            f"target_ref {target_ref!r} does not start with " f"configured repo_key {repo_key!r}"
        )
    path_in_repo = rest[len(repo_key) + 1 :] if rest != repo_key else ""
    return host, repo_key, path_in_repo, tag
