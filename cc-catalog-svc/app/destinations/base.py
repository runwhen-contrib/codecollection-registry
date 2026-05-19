"""
ImageDestination ABC and the default `crane copy`-backed push().

The destination contract is intentionally three methods:

    target_ref(dest_cfg, cc, ref) -> str
        Compose the destination image reference.

    exists(dest_cfg, target_ref) -> bool
        HEAD the destination manifest to keep the mirror engine idempotent.

    push(dest_cfg, source_ref, target_ref) -> MirrorResult
        Copy source -> target. Default implementation shells out to
        `crane copy`; plugins override only if they need bespoke behavior
        (signing, scan triggers, RBAC pre-flight, etc.).

Auth concerns are deliberately pushed into the plugin (every registry's
auth model is different). The base class provides a `crane_env()` helper
that plugins fill in to set DOCKER_CONFIG / REGISTRY_AUTH_FILE for the
subprocess.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


# Where the `crane` binary lives in the Docker image. Override in tests
# by monkey-patching `CRANE_BINARY`.
CRANE_BINARY = shutil.which("crane") or "/usr/local/bin/crane"


@dataclass
class MirrorResult:
    """Outcome of a single mirror push."""

    success: bool
    target_digest: Optional[str] = None  # sha256:... if we could discover it
    log_text: str = ""                   # captured stdout/stderr tail
    error: Optional[str] = None          # short human summary on failure


class ImageDestination(ABC):
    """Abstract destination of mirrored CodeCollection images."""

    name: str  # plugin identifier registered in DESTINATION_REGISTRY

    @abstractmethod
    def target_ref(
        self, dest_cfg: dict, cc: dict, image_tag: str
    ) -> str:
        """Return the fully-qualified destination ref for an image."""
        ...

    @abstractmethod
    def exists(self, dest_cfg: dict, target_ref: str) -> bool:
        """Return True if `target_ref` already resolves on the destination.

        Used by the mirror engine to skip already-mirrored work. A False
        return drives `push()`; a raised exception aborts the job (the
        scheduler logs it and retries on the next mirror poll).
        """
        ...

    def crane_env(self, dest_cfg: dict) -> dict:
        """Extra env vars for `crane`. Default: nothing.

        Plugins set DOCKER_CONFIG / REGISTRY_AUTH_FILE / similar here so
        crane picks up auth without us having to pass tokens on argv
        (which leaks via `ps`).
        """
        return {}

    def push(
        self,
        dest_cfg: dict,
        source_ref: str,
        target_ref: str,
        *,
        timeout: int = 600,
    ) -> MirrorResult:
        """Default impl: `crane copy <source> <target>`.

        Designed to be safe to override. Most destinations only need to
        provide auth via `crane_env()` and never touch this method.
        """
        return run_crane_copy(
            source_ref,
            target_ref,
            env_extra=self.crane_env(dest_cfg),
            timeout=timeout,
        )


# ---------------------------------------------------------------------------
# crane subprocess helper. Importable for tests; the JFrog plugin uses
# the default `push()` which in turn calls this.
# ---------------------------------------------------------------------------
def run_crane_copy(
    source_ref: str,
    target_ref: str,
    *,
    env_extra: Optional[dict] = None,
    timeout: int = 600,
) -> MirrorResult:
    """Shell out to `crane copy <source> <target>`.

    `crane copy` is digest-preserving: if the source is multi-arch, the
    destination ends up as the same manifest list, not a flattened
    single-arch image. That matters for codecollection images that ship
    amd64+arm64.

    On success we additionally call `crane digest <target>` to record
    the destination digest in MirrorResult. This is best-effort — a
    successful copy without a recoverable digest is still considered
    a success.
    """
    if not CRANE_BINARY or not shutil.which(CRANE_BINARY):
        return MirrorResult(
            success=False,
            error=f"crane binary not found at {CRANE_BINARY!r}; install it in the image",
        )

    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    cmd = [CRANE_BINARY, "copy", source_ref, target_ref]
    logger.info("crane copy %s -> %s", source_ref, target_ref)
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return MirrorResult(
            success=False,
            log_text=(exc.stderr or "") + "\n[timeout]",
            error=f"crane copy timed out after {timeout}s",
        )
    except Exception as exc:
        return MirrorResult(success=False, error=f"crane copy crashed: {exc!r}")

    log = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    log_tail = log[-4000:]  # keep DB rows bounded

    if proc.returncode != 0:
        return MirrorResult(
            success=False,
            log_text=log_tail,
            error=f"crane copy exited {proc.returncode}",
        )

    # Best-effort digest discovery.
    target_digest: Optional[str] = None
    try:
        digest_proc = subprocess.run(
            [CRANE_BINARY, "digest", target_ref],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if digest_proc.returncode == 0:
            out = (digest_proc.stdout or "").strip()
            if out.startswith("sha256:"):
                target_digest = out
    except Exception:  # pragma: no cover - digest is informational
        logger.debug("crane digest lookup failed", exc_info=True)

    return MirrorResult(success=True, target_digest=target_digest, log_text=log_tail)
