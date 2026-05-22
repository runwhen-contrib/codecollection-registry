"""End-to-end-ish tests: drive a fake source into the DB, then assert
the catalog HTTP endpoints expose it correctly.

We don't need real OCI infra — we register a tiny in-process source
plugin and point a config at it.
"""
from __future__ import annotations

from datetime import datetime

import pytest

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
    refs = db_session.execute(
        select(ImageRef).where(ImageRef.cc_id == cc.id)
    ).scalars().all()
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
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?ref=main"
    )
    assert resp.status_code == 200
    assert resp.json()["image_tag"] == "main-c1a2b3d-e4f5a6b"


def test_catalog_api_resolve_requires_exactly_one(client, cfg_with_fake_cc):
    run_catalog_poll(cfg_with_fake_cc)
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/resolve"
    )
    assert resp.status_code == 400
    resp = client.get(
        "/api/v1/catalog/codecollections/rw-cli-codecollection/"
        "resolve?pointer=latest&ref=main"
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
