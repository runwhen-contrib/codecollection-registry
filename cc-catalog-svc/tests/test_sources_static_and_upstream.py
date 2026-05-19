"""Tests for the static and upstream source plugins."""
from __future__ import annotations

import json

import httpx
import respx

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
