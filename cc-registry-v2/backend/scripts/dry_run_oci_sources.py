#!/usr/bin/env python3
"""
Dry-run the image-sync pipeline against the live registries listed in
codecollections.yaml — without a database, Celery, or the FastAPI app.

For every CodeCollection that has `image_source` configured, this script:

  1. Loads the configured `ImageSource` from `app.sources` (oci, static, ...).
  2. Calls `source.discover_refs(cc)` to fetch the full tag list and parse
     it into the catalog's `DiscoveredImageRef` shape.
  3. Calls `source.resolve_latest(cc, refs)` and `source.resolve_stable(cc, refs)`
     so you can see what the catalog would expose as the canonical pointers.

It prints a per-CC summary and (with `--verbose`) every parsed ref. It is
purely read-only — no DB writes, no Celery dispatch, no side effects.

Usage:

  # Default: read ../../codecollections.yaml relative to this file
  python scripts/dry_run_oci_sources.py

  # Point at a specific config (useful for testing draft changes)
  python scripts/dry_run_oci_sources.py --config /path/to/codecollections.yaml

  # Filter by slug
  python scripts/dry_run_oci_sources.py --only rw-cli-codecollection

  # Filter by source type
  python scripts/dry_run_oci_sources.py --source oci

  # Show every parsed ref, not just the summary
  python scripts/dry_run_oci_sources.py --verbose

Exit codes:
  0 = every configured CC discovered at least one ref successfully
  1 = one or more sources errored (network / auth / parse)
  2 = one or more sources returned zero refs (likely a tag-schema mismatch)

The last case is the one we care about most before flipping image_source
from unset -> "oci" in production: it usually means the registry has tags
but they don't match `<sanitized-ref>-<cc_sha7>-<rt_sha7>`. Re-run with
`--verbose` to see which tags were rejected.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

# Make `app.sources` importable when this script is invoked directly.
# Layout: cc-registry-v2/backend/scripts/dry_run_oci_sources.py
#         cc-registry-v2/backend/app/sources/...
HERE = Path(__file__).resolve()
BACKEND_DIR = HERE.parent.parent  # cc-registry-v2/backend
sys.path.insert(0, str(BACKEND_DIR))

import yaml  # noqa: E402  (after sys.path tweak)

from app.sources import DiscoveredImageRef, get_source  # noqa: E402

logger = logging.getLogger("dry_run_oci_sources")


# ---------------------------------------------------------------------------
# config loading
# ---------------------------------------------------------------------------


def _default_config_path() -> Path:
    """
    Resolve codecollections.yaml the same way the Celery tasks do, but
    starting from this file's location instead of `/app/...`.

    Search order (first hit wins):
      1. Explicit env var CC_REGISTRY_YAML
      2. <repo-root>/codecollections.yaml         (devcontainer / local checkout)
      3. /app/codecollections.yaml                (running inside the backend image)
      4. /workspaces/codecollection-registry/codecollections.yaml
    """
    env = os.environ.get("CC_REGISTRY_YAML")
    if env:
        return Path(env)

    repo_root = BACKEND_DIR.parent.parent  # cc-registry-v2/.. = repo root
    candidates = [
        repo_root / "codecollections.yaml",
        Path("/app/codecollections.yaml"),
        Path("/workspaces/codecollection-registry/codecollections.yaml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to the first candidate even if it doesn't exist; the caller
    # will hit a clearer error from yaml.safe_load.
    return candidates[0]


def _load_codecollections(config_path: Path) -> list[dict]:
    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("codecollections", []) or []


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def _fmt_ref(r: DiscoveredImageRef) -> str:
    built = r.built_at.isoformat() if r.built_at else "-"
    return (
        f"  • {r.image_tag:<60s}  ref={r.ref!r:<14s} "
        f"type={r.ref_type:<7s} cc={r.commit[:7]} rt={r.rt_revision[:7]} built={built}"
    )


def _print_cc_result(
    cc: dict,
    refs: list[DiscoveredImageRef],
    latest: Optional[str],
    stable: Optional[str],
    verbose: bool,
) -> None:
    slug = cc.get("slug", "<unknown>")
    source = cc.get("image_source")
    registry = cc.get("image_registry", "-")
    default_ref = cc.get("default_ref", "main")

    by_type = Counter(r.ref_type for r in refs)
    type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())) or "-"

    print(f"  source={source}  registry={registry}  default_ref={default_ref}")
    print(f"  discovered={len(refs)} refs  ({type_summary})")
    print(f"  latest -> {latest or '(none)'}")
    print(f"  stable -> {stable or '(none)'}")
    if verbose and refs:
        print("  ----")
        # Sort by ref then tag for readability
        for r in sorted(refs, key=lambda r: (r.ref, r.image_tag)):
            print(_fmt_ref(r))
    if not refs:
        print(
            "  WARN: source returned 0 refs — likely a tag-schema mismatch. "
            "Re-run with --verbose against a less restrictive parser, or "
            "inspect the registry directly:"
        )
        if registry and registry != "-":
            host, _, repo = registry.partition("/")
            print(f"    curl -s https://{host}/v2/{repo}/tags/list?n=20 | jq .")
    print()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to codecollections.yaml (default: auto-discover)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated list of CC slugs to include (default: all configured)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help='Only run CCs whose image_source matches (e.g. "oci", "static")',
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="List every parsed ref"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress per-source INFO logs"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config_path = args.config or _default_config_path()
    if not config_path.exists():
        print(f"ERROR: codecollections.yaml not found at {config_path}", file=sys.stderr)
        return 1
    print(f"# Using config: {config_path}\n")

    all_ccs = _load_codecollections(config_path)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        all_ccs = [c for c in all_ccs if c.get("slug") in wanted]
    if args.source:
        all_ccs = [c for c in all_ccs if c.get("image_source") == args.source]

    configured = [c for c in all_ccs if c.get("image_source")]
    unconfigured = [c for c in all_ccs if not c.get("image_source")]

    if unconfigured and not args.source:
        print(
            f"# Skipping {len(unconfigured)} CC(s) without image_source: "
            + ", ".join(sorted(c.get("slug", "?") for c in unconfigured))
            + "\n"
        )

    if not configured:
        print("# No CodeCollections matched the filters; nothing to dry-run.")
        return 0

    errors: list[str] = []
    empty: list[str] = []

    for cc in configured:
        slug = cc.get("slug", "<unknown>")
        source_name = cc.get("image_source")
        print(f"== {slug} ==")

        source = get_source(source_name)
        if source is None:
            msg = f"unknown image_source '{source_name}' for {slug}"
            print(f"  ERROR: {msg}\n")
            errors.append(msg)
            continue

        try:
            refs = source.discover_refs(cc)
            latest = source.resolve_latest(cc, refs)
            stable = source.resolve_stable(cc, refs)
        except Exception as e:  # noqa: BLE001 - we want to keep going
            msg = f"{slug}: {type(e).__name__}: {e}"
            print(f"  ERROR: {msg}\n")
            errors.append(msg)
            continue

        _print_cc_result(cc, refs, latest, stable, verbose=args.verbose)
        if not refs:
            empty.append(slug)

    # ---------------- summary ----------------
    print("=" * 70)
    print(f"Summary: {len(configured)} CC(s) dry-run, "
          f"{len(errors)} error(s), {len(empty)} returned zero refs.")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
    if empty:
        print("\nZero-ref CCs (likely tag-schema mismatch):")
        for s in empty:
            print(f"  - {s}")

    if errors:
        return 1
    if empty:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
