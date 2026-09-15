"""End-to-end-ish tests: drive a fake source into the DB, then assert
the catalog HTTP endpoints expose it correctly.

We don't need real OCI infra — we register a tiny in-process source
plugin and point a config at it.
"""

from __future__ import annotations

import base64
from datetime import datetime

import httpx
import pytest
import respx
import yaml

from app import config as config_mod
from app.config import (
    AppConfig,
    CodeCollectionConfig,
    SchedulerConfig,
    SourceConfig,
    StorageConfig,
)
from app.services.catalog_poll import run_catalog_poll
from app.sources.base import DiscoveredImageRef, ImageSource
from app.sources import registry as src_registry


class FakeSource(ImageSource):
    """In-memory source that yields a fixed ref set."""

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
        ]

    def resolve_latest(self, cc, refs):
        return "main-c1a2b3d-e4f5a6b"

    def resolve_stable(self, cc, refs):
        return "v1.2.0-aabbccd-e4f5a6b"


@pytest.fixture
def fake_source_registered(monkeypatch):
    src = FakeSource()
    monkeypatch.setitem(src_registry.SOURCE_REGISTRY, src.name, src)
    return src


@pytest.fixture
def cfg_with_fake_cc(engine, fake_source_registered):
    cfg = AppConfig(
        storage=StorageConfig(),
        scheduler=SchedulerConfig(),
        sources=[
            SourceConfig(
                name="fake-src",
                type="fake",
                codecollections=[
                    CodeCollectionConfig(
                        slug="rw-cli-codecollection",
                        name="RunWhen CLI CodeCollection",
                        git_url="https://github.com/runwhen-contrib/rw-cli-codecollection",
                        image_registry="ghcr.io/runwhen-contrib/rw-cli-codecollection",
                    )
                ],
            )
        ],
    )
    config_mod._CONFIG_CACHE = cfg
    return cfg


def test_catalog_poll_upserts_cc_and_refs(cfg_with_fake_cc, db_session):
    summary = run_catalog_poll(cfg_with_fake_cc)
    assert summary["collections_processed"] == 1
    assert summary["refs_upserted"] == 2
    assert summary["errors"] == []

    from app.models import CodeCollection, ImageRef
    from sqlalchemy import select

    cc = db_session.execute(
        select(CodeCollection).where(CodeCollection.slug == "rw-cli-codecollection")
    ).scalar_one()
    refs = db_session.execute(select(ImageRef).where(ImageRef.cc_id == cc.id)).scalars().all()
    assert {r.ref_name for r in refs} == {"main", "v1.2.0"}
    assert any(r.is_latest for r in refs if r.ref_name == "main")
    assert any(r.is_stable for r in refs if r.ref_name == "v1.2.0")


def test_catalog_api_list_returns_entry(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get("/api/v1/catalog/codecollections")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    entry = body[0]
    assert entry["slug"] == "rw-cli-codecollection"
    assert entry["latest_image_tag"] == "main-c1a2b3d-e4f5a6b"
    assert entry["stable_image_tag"] == "v1.2.0-aabbccd-e4f5a6b"


def test_catalog_api_resolve_pointer(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?pointer=stable"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["image_tag"] == "v1.2.0-aabbccd-e4f5a6b"
    assert body["image_registry"] == "ghcr.io/runwhen-contrib/rw-cli-codecollection"


def test_catalog_api_resolve_specific_ref(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get("/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?ref=main")
    assert resp.status_code == 200
    assert resp.json()["image_tag"] == "main-c1a2b3d-e4f5a6b"


def test_catalog_api_resolve_requires_exactly_one(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get("/api/v1/catalog/codecollections/rw-cli-codecollection/resolve")
    assert resp.status_code == 400
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/" "resolve?pointer=latest&ref=main"
    )
    assert resp.status_code == 400


def test_catalog_api_unknown_cc_returns_404(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get("/api/v1/catalog/codecollections/does-not-exist")
    assert resp.status_code == 404


def test_health_endpoints(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_entry_pointers_trusts_is_stable_for_semver_ordering():
    """Regression: `entry_pointers` must trust the sync task's `is_stable`
    flag (computed with proper semver awareness in `_upsert_versions`)
    rather than re-deriving stable with a lexicographic comparison —
    "v10.0.0" < "v9.0.0" lexicographically because '1' < '9'.
    """
    from types import SimpleNamespace
    from app.services.catalog import entry_pointers

    refs = [
        SimpleNamespace(
            ref_name="v9.0.0",
            ref_type="tag",
            image_tag="v9.0.0-aabbccd-e4f5a6b",
            image_registry="ghcr.io/x/y",
            is_latest=False,
            is_stable=False,
        ),
        SimpleNamespace(
            ref_name="v10.0.0",
            ref_type="tag",
            image_tag="v10.0.0-bbccdde-e4f5a6b",
            image_registry="ghcr.io/x/y",
            is_latest=False,
            is_stable=True,  # sync task already picked the right winner
        ),
    ]
    _latest, stable, _reg = entry_pointers(refs)
    assert stable == "v10.0.0-bbccdde-e4f5a6b"


def test_entry_pointers_fallback_never_compares_ref_name_to_image_tag():
    """Regression for the Bugbot finding: when no row has `is_stable` set
    (legacy data or sync hasn't propagated yet), the lexicographic
    fallback must compare ref_name to ref_name — never to image_tag.

    With `ref_name vs image_tag`:
        "v2.0.0" > "v1.2.0-aabbccd-e4f5a6b"  is True ('2' > '1')
    but the previously chosen image_tag's suffix can flip the result in
    pathological inputs. We assert the cleaner apples-to-apples ordering.
    """
    from types import SimpleNamespace
    from app.services.catalog import entry_pointers

    refs = [
        SimpleNamespace(
            ref_name="v1.2.0",
            ref_type="tag",
            image_tag="v1.2.0-aabbccd-e4f5a6b",
            image_registry="ghcr.io/x/y",
            is_latest=False,
            is_stable=False,
        ),
        SimpleNamespace(
            ref_name="v2.0.0",
            ref_type="tag",
            image_tag="v2.0.0-bbccdde-e4f5a6b",
            image_registry="ghcr.io/x/y",
            is_latest=False,
            is_stable=False,
        ),
    ]
    _latest, stable, _reg = entry_pointers(refs)
    assert stable == "v2.0.0-bbccdde-e4f5a6b"


class TiebreakSource(ImageSource):
    """In-memory source that returns two competing tags for ref=main.

    Used to verify ``_upsert_refs`` picks the row with the newer
    ``built_at`` rather than the one with the lexicographically-largest
    ``image_tag``. The older tag's image_tag is intentionally larger in
    ASCII (``main-d...`` > ``main-1...``) — that's the trap the bug fell
    into in production behind JFrog.
    """

    name = "tiebreak"

    def discover_refs(self, cc):
        return [
            DiscoveredImageRef(
                ref="main",
                ref_type="branch",
                commit="de76dd0",
                rt_revision="71dfdc4",
                image_tag="main-de76dd0-71dfdc4",  # lex-larger, older
                built_at=datetime(2026, 5, 12, 10, 0, 0),
            ),
            DiscoveredImageRef(
                ref="main",
                ref_type="branch",
                commit="10792f4",
                rt_revision="6e4bc81",
                image_tag="main-10792f4-6e4bc81",  # lex-smaller, newer
                built_at=datetime(2026, 5, 21, 17, 0, 0),
            ),
        ]

    def resolve_latest(self, cc, refs):
        # Match the OCISource ordering exactly.
        from datetime import timezone

        candidates = [r for r in refs if r.ref == cc.get("default_ref", "main")]
        candidates.sort(
            key=lambda r: (
                r.built_at or datetime.min.replace(tzinfo=timezone.utc),
                r.image_tag,
            )
        )
        return candidates[-1].image_tag if candidates else None

    def resolve_stable(self, cc, refs):
        return None


def test_upsert_refs_picks_newest_by_built_at_not_lex(monkeypatch, db_session):
    """Regression: catalog must not be tricked into keeping the older
    canonical tag just because its cc_sha7 prefix is ASCII-larger.

    Before the fix, the JFrog-fronted catalog kept reporting
    ``main-de76dd0-71dfdc4`` as the ``main`` ref's row even after the
    newer ``main-10792f4-6e4bc81`` showed up in /v2/.../tags/list,
    because ``d`` > ``1`` lexicographically. The fix wires
    ``DiscoveredImageRef.built_at`` into the tiebreak so the surviving
    row matches what ``resolve_latest`` declared.
    """
    src = TiebreakSource()
    monkeypatch.setitem(src_registry.SOURCE_REGISTRY, src.name, src)
    cfg = AppConfig(
        storage=StorageConfig(),
        scheduler=SchedulerConfig(),
        sources=[
            SourceConfig(
                name="tiebreak-src",
                type="tiebreak",
                codecollections=[
                    CodeCollectionConfig(
                        slug="ss-rw-cli-codecollection",
                        name="SheaStewart RW CLI",
                        image_registry="jfrog.example.com/stewartshea/rw-cli-codecollection",
                    )
                ],
            )
        ],
    )
    config_mod._CONFIG_CACHE = cfg

    summary = run_catalog_poll(cfg)
    assert summary["collections_processed"] == 1
    assert summary["errors"] == []

    from app.models import CodeCollection, ImageRef
    from sqlalchemy import select

    cc = db_session.execute(
        select(CodeCollection).where(CodeCollection.slug == "ss-rw-cli-codecollection")
    ).scalar_one()
    main_row = db_session.execute(
        select(ImageRef).where(ImageRef.cc_id == cc.id, ImageRef.ref_name == "main")
    ).scalar_one()
    assert main_row.image_tag == "main-10792f4-6e4bc81"
    assert main_row.commit_hash == "10792f4"
    assert main_row.is_latest is True


def _manifest_label(capability: str, version: str) -> str:
    text = yaml.safe_dump({"capability": capability, "version": version})
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest.fixture
def cfg_mixed_kind(engine) -> AppConfig:
    """One `type: oci` source with a Robot entry and a capability entry."""
    cfg = AppConfig(
        storage=StorageConfig(),
        scheduler=SchedulerConfig(),
        sources=[
            SourceConfig(
                name="ghcr-mixed",
                type="oci",
                codecollections=[
                    CodeCollectionConfig(
                        slug="rw-cli-codecollection",
                        name="RunWhen CLI CodeCollection",
                        git_url="https://github.com/runwhen-contrib/rw-cli-codecollection",
                        image_registry="ghcr.io/runwhen-contrib/rw-cli-codecollection",
                    ),
                    CodeCollectionConfig(
                        slug="rw-checks-codecollection",
                        kind="capability",
                        git_url="https://github.com/runwhen-contrib/rw-checks-codecollection",
                        image_registry="ghcr.io/runwhen-contrib/rw-checks-codecollection",
                    ),
                ],
            )
        ],
    )
    config_mod._CONFIG_CACHE = cfg
    return cfg


@respx.mock
def test_capability_entry_and_robot_entry_in_same_source_dont_leak(client, cfg_mixed_kind):
    """A Robot CC and a capability CC under the *same* oci source both sync,
    and neither shows up on the other's endpoint."""
    robot_repo = "runwhen-contrib/rw-cli-codecollection"
    cap_repo = "runwhen-contrib/rw-checks-codecollection"

    respx.get(f"https://ghcr.io/v2/{robot_repo}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]})
    )
    respx.get(f"https://ghcr.io/v2/{cap_repo}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "main-287377c"]})
    )
    respx.get(f"https://ghcr.io/v2/{cap_repo}/manifests/main").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:indexdigest"},
            json={
                "manifests": [
                    {
                        "digest": "sha256:amd64digest",
                        "platform": {"architecture": "amd64", "os": "linux"},
                    },
                ]
            },
        )
    )
    respx.get(f"https://ghcr.io/v2/{cap_repo}/manifests/sha256:amd64digest").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:amd64cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{cap_repo}/blobs/sha256:amd64cfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label("rw-checks", "0.2.0"),
                        "io.runwhen.codecollection.commit": "287377caaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    }
                }
            },
        )
    )

    summary = run_catalog_poll(cfg_mixed_kind)
    assert summary["errors"] == []
    assert summary["collections_processed"] == 1
    assert summary["refs_upserted"] == 1
    assert summary["capabilities_processed"] == 1
    assert summary["capability_refs_upserted"] == 1

    # Robot listing: only the codecollection-kind slug, never the capability one.
    resp = client.get("/api/v1/catalog/codecollections")
    assert resp.status_code == 200
    assert {e["slug"] for e in resp.json()} == {"rw-cli-codecollection"}

    resp = client.get("/api/v1/catalog/codecollections/rw-checks-codecollection")
    assert resp.status_code == 404

    resp = client.get("/api/v1/catalog/codecollections/rw-cli-codecollection/refs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Capability listing: only the capability-kind slug.
    resp = client.get("/api/v1/catalog/capabilities")
    assert resp.status_code == 200
    caps = resp.json()["capabilities"]
    assert len(caps) == 1
    entry = caps[0]
    assert entry["capability"] == "rw-checks"
    assert entry["version"] == "0.2.0"
    assert entry["codecollection"] == "rw-checks-codecollection"
    assert entry["ref"] == "main"
    assert entry["ref_type"] == "branch"
    assert entry["commit_hash"] == "287377c"
    assert entry["image_tag"] == "main-287377c"
    assert entry["image_digest"] == "sha256:indexdigest"
    assert entry["image"] == f"ghcr.io/{cap_repo}@sha256:indexdigest"
    assert entry["manifest"] == {"capability": "rw-checks", "version": "0.2.0"}
    assert "capability: rw-checks" in entry["manifest_text"]


def test_capabilities_endpoint_filters_by_capability_id(client, db_session):
    from app.services.catalog_poll import _upsert_capability_versions
    from app.sources.capability import DiscoveredCapability

    cap_a = DiscoveredCapability(
        capability="rw-checks",
        version="0.1.0",
        ref="main",
        ref_type="branch",
        commit_hash="aaaaaaa",
        image_tag="main-aaaaaaa",
        image_digest="sha256:aaa",
        image="ghcr.io/runwhen-contrib/rw-checks-codecollection@sha256:aaa",
        manifest_text="capability: rw-checks\nversion: 0.1.0\n",
    )
    cap_b = DiscoveredCapability(
        capability="rw-worktree",
        version="1.0.0",
        ref="v1.0.0",
        ref_type="tag",
        commit_hash="bbbbbbb",
        image_tag="v1.0.0",
        image_digest="sha256:bbb",
        image="ghcr.io/runwhen-contrib/rw-worktree-codecollection@sha256:bbb",
        manifest_text="capability: rw-worktree\nversion: 1.0.0\n",
    )
    _upsert_capability_versions(db_session, "rw-checks-codecollection", [cap_a])
    _upsert_capability_versions(db_session, "rw-worktree-codecollection", [cap_b])
    db_session.commit()

    resp = client.get("/api/v1/catalog/capabilities")
    assert resp.status_code == 200
    assert {c["capability"] for c in resp.json()["capabilities"]} == {
        "rw-checks",
        "rw-worktree",
    }

    resp = client.get("/api/v1/catalog/capabilities?capability=rw-checks")
    assert resp.status_code == 200
    caps = resp.json()["capabilities"]
    assert len(caps) == 1
    assert caps[0]["codecollection"] == "rw-checks-codecollection"


def test_upsert_capability_versions_replaces_and_prunes_stale_refs(db_session):
    """Re-poll replaces existing (slug, ref) rows in place, prunes refs that
    dropped out of a *non-empty* listing, and never wipes rows on an empty
    listing (mirrors _upsert_refs's caution around transient hiccups)."""
    from app.services.catalog_poll import _upsert_capability_versions
    from app.models import CapabilityVersion
    from app.sources.capability import DiscoveredCapability
    from sqlalchemy import select

    cap_main_v1 = DiscoveredCapability(
        capability="rw-checks",
        version="0.1.0",
        ref="main",
        ref_type="branch",
        commit_hash="aaaaaaa",
        image_tag="main-aaaaaaa",
        image_digest="sha256:aaa",
        image="ghcr.io/x/y@sha256:aaa",
        manifest_text="capability: rw-checks\nversion: 0.1.0\n",
    )
    upserted, removed = _upsert_capability_versions(
        db_session, "rw-checks-codecollection", [cap_main_v1]
    )
    db_session.commit()
    assert (upserted, removed) == (1, 0)

    cap_main_v2 = DiscoveredCapability(
        capability="rw-checks",
        version="0.2.0",
        ref="main",
        ref_type="branch",
        commit_hash="bbbbbbb",
        image_tag="main-bbbbbbb",
        image_digest="sha256:bbb",
        image="ghcr.io/x/y@sha256:bbb",
        manifest_text="capability: rw-checks\nversion: 0.2.0\n",
    )
    cap_v1_tag = DiscoveredCapability(
        capability="rw-checks",
        version="1.0.0",
        ref="v1.0.0",
        ref_type="tag",
        commit_hash="ccccccc",
        image_tag="v1.0.0",
        image_digest="sha256:ccc",
        image="ghcr.io/x/y@sha256:ccc",
        manifest_text="capability: rw-checks\nversion: 1.0.0\n",
    )
    upserted, removed = _upsert_capability_versions(
        db_session, "rw-checks-codecollection", [cap_main_v2, cap_v1_tag]
    )
    db_session.commit()
    assert (upserted, removed) == (2, 0)  # "main" replaced in place, "v1.0.0" is new

    rows = (
        db_session.execute(
            select(CapabilityVersion).where(
                CapabilityVersion.codecollection == "rw-checks-codecollection"
            )
        )
        .scalars()
        .all()
    )
    assert {r.ref for r in rows} == {"main", "v1.0.0"}
    main_row = next(r for r in rows if r.ref == "main")
    assert main_row.version == "0.2.0"

    # A non-empty listing that drops "v1.0.0" prunes the stale row.
    upserted, removed = _upsert_capability_versions(
        db_session, "rw-checks-codecollection", [cap_main_v2]
    )
    db_session.commit()
    assert (upserted, removed) == (1, 1)
    rows = (
        db_session.execute(
            select(CapabilityVersion).where(
                CapabilityVersion.codecollection == "rw-checks-codecollection"
            )
        )
        .scalars()
        .all()
    )
    assert {r.ref for r in rows} == {"main"}

    # An empty listing (failed/empty source) never wipes existing rows.
    upserted, removed = _upsert_capability_versions(db_session, "rw-checks-codecollection", [])
    db_session.commit()
    assert (upserted, removed) == (0, 0)
    rows = (
        db_session.execute(
            select(CapabilityVersion).where(
                CapabilityVersion.codecollection == "rw-checks-codecollection"
            )
        )
        .scalars()
        .all()
    )
    assert {r.ref for r in rows} == {"main"}


def test_duplicate_cc_slug_across_sources_fails_loudly():
    cfg = AppConfig(
        sources=[
            SourceConfig(
                name="a",
                type="fake",
                codecollections=[CodeCollectionConfig(slug="foo")],
            ),
            SourceConfig(
                name="b",
                type="fake",
                codecollections=[CodeCollectionConfig(slug="foo")],
            ),
        ],
    )
    import pytest

    with pytest.raises(ValueError, match="Duplicate"):
        cfg.all_codecollections()
