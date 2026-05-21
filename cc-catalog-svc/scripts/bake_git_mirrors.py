#!/usr/bin/env python3
"""Bake bare git mirrors into the container image at build time.

CI has outbound access; the running air-gapped container does not.
This script is invoked from the Dockerfile git-bake stage.
"""
from __future__ import annotations

import argparse
import sys

from app.config import AppConfig, load_config
from app.services.git_mirror import sync_one_repo


def repos_to_bake(cfg: AppConfig) -> list[tuple[str, str]]:
    """Return ``(slug, upstream_url)`` pairs for image bake.

    Unlike ``repos_to_sync``, this does not require ``git.enabled`` — the bake
    manifest only lists sources and is never used at runtime.
    """
    explicit = cfg.git.codecollections if cfg.git.codecollections else None
    pairs: list[tuple[str, str]] = []
    for slug, cc in cfg.all_codecollections().items():
        if explicit is not None and slug not in explicit:
            continue
        if cc.git_url:
            pairs.append((slug, cc.git_url))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone bare git mirrors for image bake")
    parser.add_argument(
        "--config",
        required=True,
        help="YAML config listing CodeCollection git_url values to mirror",
    )
    parser.add_argument(
        "--dest",
        required=True,
        help="Output directory for bare repos (<slug>.git)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    git_cfg = cfg.git.model_copy(update={"data_dir": args.dest})
    pairs = repos_to_bake(cfg)
    if not pairs:
        print(
            "bake_git_mirrors: no codecollections with git_url in bake config",
            file=sys.stderr,
        )
        return 1

    errors: list[str] = []
    for slug, upstream_url in pairs:
        print(f"bake_git_mirrors: mirroring {slug} <- {upstream_url}", flush=True)
        try:
            head = sync_one_repo(slug, upstream_url, git_cfg)
            print(f"bake_git_mirrors: {slug} @ {head[:12]}", flush=True)
        except Exception as exc:
            errors.append(f"{slug}: {exc}")
            print(f"bake_git_mirrors: FAILED {slug}: {exc}", file=sys.stderr, flush=True)

    if errors:
        print(f"bake_git_mirrors: {len(errors)} repo(s) failed", file=sys.stderr)
        return 1
    print(f"bake_git_mirrors: baked {len(pairs)} repo(s) to {args.dest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
