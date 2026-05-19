"""
OCISource unit tests.

We exercise the tag parser directly (pure function, no I/O) and use
respx to fake the GHCR token + tags endpoints for the discovery path.
"""
from __future__ import annotations

import httpx
import respx

from app.sources.oci import OCISource


def test_parse_tag_matches_schema():
    src = OCISource()
    parsed = src._parse_tag("main-c1a2b3d-e4f5a6b")
    assert parsed is not None
    assert parsed.ref == "main"
    assert parsed.commit == "c1a2b3d"
    assert parsed.rt_revision == "e4f5a6b"


def test_parse_tag_handles_pr_ref_with_hyphens():
    src = OCISource()
    parsed = src._parse_tag("pr-42-9988aab-e4f5a6b")
    assert parsed is not None
    assert parsed.ref == "pr-42"
    assert parsed.commit == "9988aab"


def test_parse_tag_rejects_non_schema_tags():
    src = OCISource()
    assert src._parse_tag("latest") is None
    assert src._parse_tag("main-only") is None
    assert src._parse_tag("1.2.3") is None


def test_resolve_latest_picks_default_ref():
    src = OCISource()
    refs = [
        src._parse_tag("main-aaaaaaa-bbbbbbb"),
        src._parse_tag("main-cccccccc-bbbbbbb"),
        src._parse_tag("feature-x-deadbee-bbbbbbb"),
    ]
    refs = [r for r in refs if r is not None]
    latest = src.resolve_latest({"default_ref": "main"}, refs)
    # Lexicographic fallback within `main`: "cccccccc" sorts after "aaaaaaa"
    assert latest == "main-cccccccc-bbbbbbb"


def test_resolve_stable_prefers_semver():
    src = OCISource()
    refs = [
        src._parse_tag("main-aaaaaaa-bbbbbbb"),
        src._parse_tag("v1.0.0-deadbee-bbbbbbb"),
        src._parse_tag("v1.2.0-deadbee-bbbbbbb"),
        src._parse_tag("v1.1.5-deadbee-bbbbbbb"),
    ]
    refs = [r for r in refs if r is not None]
    stable = src.resolve_stable({"default_ref": "main"}, refs)
    assert stable == "v1.2.0-deadbee-bbbbbbb"


def test_resolve_stable_falls_back_to_latest_when_no_semver():
    src = OCISource()
    refs = [
        src._parse_tag("main-aaaaaaa-bbbbbbb"),
    ]
    refs = [r for r in refs if r is not None]
    stable = src.resolve_stable({"default_ref": "main"}, refs)
    assert stable == "main-aaaaaaa-bbbbbbb"


@respx.mock
def test_discover_refs_against_mocked_ghcr():
    src = OCISource()
    cc = {
        "slug": "rw-cli-codecollection",
        "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
    }

    respx.get(
        "https://ghcr.io/v2/runwhen-contrib/rw-cli-codecollection/tags/list"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "runwhen-contrib/rw-cli-codecollection",
                "tags": [
                    "latest",
                    "main",
                    "main-c1a2b3d-e4f5a6b",
                    "v1.2.0-aabbccd-e4f5a6b",
                    "pr-42-9988aab-e4f5a6b",
                ],
            },
        )
    )

    refs = src.discover_refs(cc)
    parsed_refs = {r.ref for r in refs}
    assert "main" in parsed_refs
    assert "v1.2.0" in parsed_refs
    assert "pr-42" in parsed_refs
    # The two non-schema tags are silently dropped.
    assert len(refs) == 3


@respx.mock
def test_discover_refs_handles_anonymous_bearer_dance():
    """Simulate GHCR's 401 -> token -> retry response cycle."""
    src = OCISource()
    cc = {
        "slug": "rw-cli-codecollection",
        "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
    }

    list_url = "https://ghcr.io/v2/runwhen-contrib/rw-cli-codecollection/tags/list"
    route = respx.get(list_url)
    # First call: 401 with WWW-Authenticate
    route.side_effect = [
        httpx.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    'Bearer realm="https://ghcr.io/token",'
                    'service="ghcr.io",'
                    'scope="repository:runwhen-contrib/rw-cli-codecollection:pull"'
                ),
            },
        ),
        httpx.Response(
            200,
            json={"tags": ["main-c1a2b3d-e4f5a6b"]},
        ),
    ]
    respx.get("https://ghcr.io/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )

    refs = src.discover_refs(cc)
    assert len(refs) == 1
    assert refs[0].ref == "main"
