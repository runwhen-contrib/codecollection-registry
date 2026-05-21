"""Tests for build-time git mirror bake."""

from __future__ import annotations

from pathlib import Path

from app.config import load_config
from scripts.bake_git_mirrors import repos_to_bake


def test_repos_to_bake_reads_codecollections_without_runtime_git_enabled():
    cfg_path = Path(__file__).resolve().parents[1] / "config-examples" / "config.bake.yaml"
    cfg = load_config(str(cfg_path))
    assert cfg.git.enabled is True
    pairs = repos_to_bake(cfg)
    slugs = {slug for slug, _ in pairs}
    assert "rw-cli-codecollection" in slugs
    assert "ss-cli-codecollection" in slugs
    assert len(pairs) == 7
