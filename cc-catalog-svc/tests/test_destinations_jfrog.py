"""JFrog destination plugin tests.

We mock httpx for the exists()/Xray paths and monkey-patch the crane
binary subprocess shell for push() so tests run without `crane`
installed.
"""
from __future__ import annotations

import os
import subprocess
from types import SimpleNamespace

import httpx
import pytest
import respx

from app.destinations import base as dest_base
from app.destinations.jfrog import JFrogDestination


@pytest.fixture
def dest_cfg():
    return {
        "name": "acme-jfrog",
        "type": "jfrog",
        "base_url": "https://acme.jfrog.io",
        "repo_key": "runwhen-virtual",
        "path_prefix": "codecollections",
        "auth": {"token_env": "JFROG_TEST_TOKEN"},
        "enable_xray_scan": False,
    }


def test_target_ref_composes_full_path(dest_cfg):
    d = JFrogDestination()
    ref = d.target_ref(
        dest_cfg,
        {"slug": "rw-cli-codecollection"},
        "main-c1a2b3d-e4f5a6b",
    )
    assert ref == (
        "acme.jfrog.io/runwhen-virtual/codecollections/"
        "rw-cli-codecollection:main-c1a2b3d-e4f5a6b"
    )


def test_target_ref_no_prefix():
    d = JFrogDestination()
    cfg = {
        "name": "x",
        "type": "jfrog",
        "base_url": "https://acme.jfrog.io",
        "repo_key": "runwhen-virtual",
    }
    ref = d.target_ref(cfg, {"slug": "rw-cli-codecollection"}, "main-abc-def")
    assert ref == "acme.jfrog.io/runwhen-virtual/rw-cli-codecollection:main-abc-def"


@respx.mock
def test_exists_returns_true_on_200(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "test-token-xyz")
    d = JFrogDestination()
    target = "acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-abc-def"
    respx.head(
        "https://acme.jfrog.io/artifactory/api/docker/runwhen-virtual/v2/"
        "codecollections/rw-cli-codecollection/manifests/main-abc-def"
    ).mock(return_value=httpx.Response(200))
    assert d.exists(dest_cfg, target) is True


@respx.mock
def test_exists_returns_false_on_404(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "test-token-xyz")
    d = JFrogDestination()
    target = "acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-abc-def"
    respx.head(
        "https://acme.jfrog.io/artifactory/api/docker/runwhen-virtual/v2/"
        "codecollections/rw-cli-codecollection/manifests/main-abc-def"
    ).mock(return_value=httpx.Response(404))
    assert d.exists(dest_cfg, target) is False


@respx.mock
def test_exists_raises_on_403(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "test-token-xyz")
    d = JFrogDestination()
    target = "acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-abc-def"
    respx.head(
        "https://acme.jfrog.io/artifactory/api/docker/runwhen-virtual/v2/"
        "codecollections/rw-cli-codecollection/manifests/main-abc-def"
    ).mock(return_value=httpx.Response(403))
    with pytest.raises(PermissionError):
        d.exists(dest_cfg, target)


def test_with_crane_auth_writes_docker_config(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "supersecret")
    d = JFrogDestination()
    with d._with_crane_auth(dest_cfg) as env:
        config_dir = env["DOCKER_CONFIG"]
        config_path = os.path.join(config_dir, "config.json")
        assert os.path.exists(config_path)
        with open(config_path) as fp:
            data = fp.read()
        assert "acme.jfrog.io" in data
        # token should be base64-encoded with `_:` prefix
        assert "auth" in data
    # cleanup happens on context exit; dir should be gone
    assert not os.path.exists(config_path)


def test_push_invokes_crane_copy(dest_cfg, monkeypatch):
    """Patch the crane subprocess call and confirm wiring is correct."""
    monkeypatch.setenv("JFROG_TEST_TOKEN", "tok")
    monkeypatch.setattr(dest_base, "CRANE_BINARY", "/usr/bin/echo")  # shutil.which returns truthy

    # Force shutil.which to return our shim so run_crane_copy doesn't bail.
    monkeypatch.setattr(
        "app.destinations.base.shutil.which",
        lambda name: "/usr/bin/echo" if "echo" in str(name) or "crane" in str(name) else None,
    )

    calls: list[list[str]] = []

    def _fake_run(cmd, env=None, capture_output=False, text=False, timeout=None, check=False):
        calls.append(cmd)
        return SimpleNamespace(
            returncode=0,
            stdout="copied",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    d = JFrogDestination()
    result = d.push(
        dest_cfg,
        "ghcr.io/runwhen-contrib/rw-cli-codecollection:main-abc-def",
        "acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-abc-def",
        timeout=30,
    )
    assert result.success
    # First call is `crane copy <src> <dst>`; second is `crane digest <dst>`.
    assert any(cmd[:2] == ["/usr/bin/echo", "copy"] for cmd in calls)


def test_push_handles_crane_failure(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "tok")
    monkeypatch.setattr(dest_base, "CRANE_BINARY", "/usr/bin/crane")
    monkeypatch.setattr(
        "app.destinations.base.shutil.which",
        lambda _name: "/usr/bin/crane",
    )

    def _fake_run(cmd, env=None, capture_output=False, text=False, timeout=None, check=False):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom: unauthorized")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    d = JFrogDestination()
    result = d.push(
        dest_cfg,
        "ghcr.io/x:y",
        "acme.jfrog.io/runwhen-virtual/codecollections/x:y",
        timeout=30,
    )
    assert not result.success
    assert result.error and "exited 1" in result.error
    assert "unauthorized" in (result.log_text or "")


def test_push_missing_crane_returns_clean_failure(dest_cfg, monkeypatch):
    monkeypatch.setenv("JFROG_TEST_TOKEN", "tok")
    monkeypatch.setattr(dest_base, "CRANE_BINARY", "/nonexistent/crane")
    monkeypatch.setattr(
        "app.destinations.base.shutil.which",
        lambda _name: None,
    )

    d = JFrogDestination()
    result = d.push(
        dest_cfg,
        "ghcr.io/x:y",
        "acme.jfrog.io/runwhen-virtual/codecollections/x:y",
    )
    assert not result.success
    assert "crane binary not found" in (result.error or "")
