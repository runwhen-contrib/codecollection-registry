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
    assert len(pairs) == 6


def test_git_auth_args_uses_github_basic_token(monkeypatch):
    from app.config import GitAuth
    from app.services import git_mirror as gm

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    args = gm._git_auth_args(GitAuth(token_env="GITHUB_TOKEN"))
    assert len(args) == 2
    assert args[0] == "-c"
    assert args[1].startswith("http.extraHeader=Authorization: Basic ")
    assert "Bearer" not in args[1]
