"""Mirror engine tests.

We stub the JFrog plugin's exists() + push() so the engine runs without
crane or Artifactory. The point is to verify the enqueue -> drain ->
MirrorTarget flow, retry semantics, and the resolve(?destination=)
extension.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app import config as config_mod
from app.config import (
    AppConfig,
    CodeCollectionConfig,
    DestinationConfig,
    JFrogAuth,
    MirrorFilter,
    SchedulerConfig,
    SourceConfig,
)
from app.destinations import registry as dest_registry
from app.destinations.base import ImageDestination, MirrorResult
from app.services.catalog_poll import run_catalog_poll
from app.services.mirror import (
    drain_mirror_jobs,
    enqueue_mirror_jobs,
    sync_destination_rows,
)
from app.sources import registry as src_registry
from app.sources.base import DiscoveredImageRef, ImageSource


class FakeSource(ImageSource):
    name = "fake"

    def discover_refs(self, cc):
        return [
            DiscoveredImageRef(
                ref="main",
                ref_type="branch",
                commit="c1a2b3d",
                rt_revision="e4f5a6b",
                image_tag="main-c1a2b3d-e4f5a6b",
                built_at=datetime(2026, 5, 12, 10, 0, 0),
            ),
            DiscoveredImageRef(
                ref="v1.2.0",
                ref_type="tag",
                commit="aabbccd",
                rt_revision="e4f5a6b",
                image_tag="v1.2.0-aabbccd-e4f5a6b",
                built_at=datetime(2026, 5, 11, 10, 0, 0),
            ),
            DiscoveredImageRef(
                ref="pr-99",
                ref_type="branch",
                commit="9988aab",
                rt_revision="e4f5a6b",
                image_tag="pr-99-9988aab-e4f5a6b",
                built_at=datetime(2026, 5, 10, 10, 0, 0),
            ),
        ]

    def resolve_latest(self, cc, refs):
        return "main-c1a2b3d-e4f5a6b"

    def resolve_stable(self, cc, refs):
        return "v1.2.0-aabbccd-e4f5a6b"


class FakeJFrog(ImageDestination):
    """In-memory JFrog stand-in. Tracks every push call so tests can
    assert which images flowed through."""

    name = "jfrog"

    def __init__(self):
        self._exists: dict[str, bool] = {}
        self.push_calls: list[tuple[str, str]] = []
        self.fail_next: int = 0  # number of upcoming push() calls to fail

    def target_ref(self, dest_cfg, cc, image_tag):
        host = dest_cfg["base_url"].replace("https://", "")
        return f"{host}/{dest_cfg['repo_key']}/{cc['slug']}:{image_tag}"

    def exists(self, dest_cfg, target_ref):
        return self._exists.get(target_ref, False)

    def push(self, dest_cfg, source_ref, target_ref, *, timeout=600):
        self.push_calls.append((source_ref, target_ref))
        if self.fail_next > 0:
            self.fail_next -= 1
            return MirrorResult(success=False, error="simulated push failure")
        self._exists[target_ref] = True
        return MirrorResult(success=True, target_digest="sha256:deadbeef")


@pytest.fixture
def fake_plugins(monkeypatch):
    src = FakeSource()
    dst = FakeJFrog()
    monkeypatch.setitem(src_registry.SOURCE_REGISTRY, src.name, src)
    monkeypatch.setitem(dest_registry.DESTINATION_REGISTRY, dst.name, dst)
    return src, dst


@pytest.fixture
def cfg_for_mirror(engine, fake_plugins):
    cfg = AppConfig(
        scheduler=SchedulerConfig(mirror_workers=1, per_job_timeout_seconds=10),
        sources=[
            SourceConfig(
                name="fake-src",
                type="fake",
                codecollections=[
                    CodeCollectionConfig(
                        slug="rw-cli-codecollection",
                        name="rw-cli",
                        image_registry="ghcr.io/runwhen-contrib/rw-cli-codecollection",
                    )
                ],
            )
        ],
        destinations=[
            DestinationConfig(
                name="acme-jfrog",
                type="jfrog",
                base_url="https://acme.jfrog.io",
                repo_key="runwhen-virtual",
                auth=JFrogAuth(token_env="JFROG_NOT_REAL"),
                mirror=MirrorFilter(
                    codecollections=["*"],
                    include_pointers=["latest", "stable"],
                    include_branches=[],
                    include_semver_tags=False,
                    include_pr_refs=False,
                ),
            )
        ],
    )
    config_mod._CONFIG_CACHE = cfg
    return cfg


def test_enqueue_creates_one_job_per_eligible_ref(cfg_for_mirror, fake_plugins):
    _src, _dst = fake_plugins
    run_catalog_poll(cfg_for_mirror)
    summary = enqueue_mirror_jobs(cfg_for_mirror)
    # latest + stable pointers -> 2 jobs; pr-99 excluded; v1.2.0 also semver
    # but include_semver_tags=False, so the only path it qualifies under is
    # `is_stable=True` (via include_pointers=['stable']). Total = 2.
    assert summary["jobs_enqueued"] == 2


def test_drain_pushes_and_records_mirror_targets(cfg_for_mirror, fake_plugins):
    _src, dst = fake_plugins
    run_catalog_poll(cfg_for_mirror)
    enqueue_mirror_jobs(cfg_for_mirror)
    drain_summary = drain_mirror_jobs(cfg_for_mirror)
    assert drain_summary["jobs_succeeded"] == 2
    assert drain_summary["jobs_failed"] == 0
    assert len(dst.push_calls) == 2

    # Second enqueue should be a no-op now that mirror_targets exists.
    summary = enqueue_mirror_jobs(cfg_for_mirror)
    assert summary["jobs_enqueued"] == 0
    assert summary["refs_already_mirrored"] >= 2


def test_drain_retries_failed_jobs_until_max_attempts(cfg_for_mirror, fake_plugins):
    _src, dst = fake_plugins
    run_catalog_poll(cfg_for_mirror)
    enqueue_mirror_jobs(cfg_for_mirror)

    # Fail the next 3 pushes -> default max_attempts is 3, so each job
    # should end up `failed` after that many tries.
    dst.fail_next = 100

    for _ in range(5):  # plenty of drains
        drain_mirror_jobs(cfg_for_mirror)

    from app.models import Destination, MirrorJob
    from sqlalchemy import select
    from app.db import session_scope

    with session_scope() as s:
        statuses = [r.status for r in s.execute(select(MirrorJob)).scalars().all()]
        # Regression: when a job exhausts max_attempts, _finish_job must
        # stamp Destination.last_sync_error. If the failure-path call to
        # _finish_job skips `ctx`, that update silently becomes dead code
        # and operators lose visibility into permanent failures.
        dest = s.execute(
            select(Destination).where(Destination.name == "acme-jfrog")
        ).scalar_one()
        assert dest.last_sync_error is not None
        assert "simulated push failure" in (dest.last_sync_error or "")
    assert all(st == "failed" for st in statuses)


def test_drain_skips_when_destination_says_exists(cfg_for_mirror, fake_plugins):
    _src, dst = fake_plugins
    run_catalog_poll(cfg_for_mirror)
    enqueue_mirror_jobs(cfg_for_mirror)
    # Pre-populate exists() so the engine takes the skip path.
    dst._exists["acme.jfrog.io/runwhen-virtual/rw-cli-codecollection:main-c1a2b3d-e4f5a6b"] = True
    dst._exists["acme.jfrog.io/runwhen-virtual/rw-cli-codecollection:v1.2.0-aabbccd-e4f5a6b"] = True
    drain_summary = drain_mirror_jobs(cfg_for_mirror)
    assert drain_summary["jobs_succeeded"] == 2
    assert dst.push_calls == []  # exists() short-circuited push


def test_resolve_with_destination_returns_target_ref(client, cfg_for_mirror, fake_plugins):
    run_catalog_poll(cfg_for_mirror)
    sync_destination_rows(cfg_for_mirror)
    enqueue_mirror_jobs(cfg_for_mirror)
    drain_mirror_jobs(cfg_for_mirror)

    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/"
        "resolve?pointer=latest&destination=acme-jfrog"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["destination"] == "acme-jfrog"
    assert body["target_image_ref"] == (
        "acme.jfrog.io/runwhen-virtual/rw-cli-codecollection:main-c1a2b3d-e4f5a6b"
    )
    assert body["target_digest"] == "sha256:deadbeef"
    # source ref still present
    assert body["image_tag"] == "main-c1a2b3d-e4f5a6b"


def test_resolve_with_unknown_destination_returns_404(client, cfg_for_mirror):
    run_catalog_poll(cfg_for_mirror)
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/"
        "resolve?pointer=latest&destination=not-configured"
    )
    assert resp.status_code == 404


def test_mirror_destinations_endpoint(client, cfg_for_mirror):
    sync_destination_rows(cfg_for_mirror)
    resp = client.get("/api/v1/mirror/destinations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "acme-jfrog"
    assert body[0]["type"] == "jfrog"


def test_admin_trigger_requires_token(client, cfg_for_mirror):
    sync_destination_rows(cfg_for_mirror)
    # no Authorization header
    resp = client.post("/api/v1/mirror/destinations/acme-jfrog/sync")
    assert resp.status_code == 401
    # wrong token
    resp = client.post(
        "/api/v1/mirror/destinations/acme-jfrog/sync",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 403


def test_admin_trigger_with_token_enqueues(client, cfg_for_mirror):
    run_catalog_poll(cfg_for_mirror)
    sync_destination_rows(cfg_for_mirror)
    resp = client.post(
        "/api/v1/mirror/destinations/acme-jfrog/sync",
        headers={"Authorization": "Bearer admin-test-token"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["destination"] == "acme-jfrog"
    assert body["jobs_enqueued"] == 2
