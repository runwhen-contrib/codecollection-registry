"""Tests for the static and upstream source plugins."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import respx

from app.sources.base import DiscoveredImageRef
from app.sources.static import StaticSource
from app.sources.upstream import UpstreamCatalogSource


def test_static_source_reads_pinned_refs(tmp_path):
    payload = {
        "default_ref": "main",
        "stable_ref": "v1.2.0",
        "refs": [
            {
                "ref": "main",
                "ref_type": "branch",
                "commit": "c1a2b3d",
                "rt_revision": "e4f5a6b",
                "image_tag": "main-c1a2b3d-e4f5a6b",
            },
            {
                "ref": "v1.2.0",
                "ref_type": "tag",
                "commit": "aabbccd",
                "rt_revision": "e4f5a6b",
                "image_tag": "v1.2.0-aabbccd-e4f5a6b",
            },
        ],
    }
    path = tmp_path / "refs.json"
    path.write_text(json.dumps(payload))

    src = StaticSource()
    cc = {"slug": "foo", "static_path": str(path)}
    refs = src.discover_refs(cc)
    assert len(refs) == 2
    assert src.resolve_latest(cc, refs) == "main-c1a2b3d-e4f5a6b"
    assert src.resolve_stable(cc, refs) == "v1.2.0-aabbccd-e4f5a6b"


def test_static_source_missing_path_returns_empty():
    src = StaticSource()
    assert src.discover_refs({"slug": "foo"}) == []


@respx.mock
def test_upstream_source_reads_catalog_api():
    src = UpstreamCatalogSource(default_upstream_url="https://registry.example.com")
    cc = {"slug": "rw-cli-codecollection"}

    respx.get(
        "https://registry.example.com/api/v1/catalog/codecollections/rw-cli-codecollection/refs"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "ref": "main",
                    "ref_type": "branch",
                    "image_tag": "main-c1a2b3d-e4f5a6b",
                    "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
                    "commit_hash": "c1a2b3def123",
                    "rt_revision": "e4f5a6b789",
                    "is_latest": True,
                },
                {
                    "ref": "v1.0.0",
                    "ref_type": "tag",
                    "image_tag": "v1.0.0-aabbccd-e4f5a6b",
                    "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
                    "commit_hash": "aabbccd",
                    "rt_revision": "e4f5a6b",
                    "is_latest": False,
                },
            ],
        )
    )

    refs = src.discover_refs(cc)
    assert len(refs) == 2
    latest = src.resolve_latest(cc, refs)
    assert latest == "main-c1a2b3d-e4f5a6b"
    stable = src.resolve_stable(cc, refs)
    assert stable == "v1.0.0-aabbccd-e4f5a6b"


@respx.mock
def test_upstream_source_404_returns_empty():
    src = UpstreamCatalogSource(default_upstream_url="https://registry.example.com")
    respx.get(
        "https://registry.example.com/api/v1/catalog/codecollections/unknown/refs"
    ).mock(return_value=httpx.Response(404))
    refs = src.discover_refs({"slug": "unknown"})
    assert refs == []


def test_upstream_resolve_latest_mixes_aware_and_naive_built_at():
    """Regression: when some candidates have tz-aware `built_at` (from
    `_parse_iso`) and others don't, the fallback sort key must not use a
    naive `datetime.min` — that raises TypeError when Python compares an
    offset-aware with an offset-naive datetime.
    """
    src = UpstreamCatalogSource(default_upstream_url="https://example")
    cc = {"slug": "x", "default_ref": "main"}
    refs = [
        DiscoveredImageRef(
            ref="main",
            ref_type="branch",
            commit="aaa",
            rt_revision="111",
            image_tag="main-aaa-111",
            built_at=None,  # missing -> falls back to epoch
        ),
        DiscoveredImageRef(
            ref="main",
            ref_type="branch",
            commit="bbb",
            rt_revision="222",
            image_tag="main-bbb-222",
            built_at=datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    # Must not raise; the second (aware) ref wins on built_at.
    assert src.resolve_latest(cc, refs) == "main-bbb-222"
