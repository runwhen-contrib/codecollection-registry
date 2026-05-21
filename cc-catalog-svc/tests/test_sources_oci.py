"""
OCISource unit tests.

We exercise the tag parser directly (pure function, no I/O) and use
respx to fake the GHCR token + tags endpoints for the discovery path.
"""
from __future__ import annotations

from datetime import datetime, timezone

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


@respx.mock
def test_discover_refs_enriches_built_at_on_tiebreak():
    """When two canonical tags share a ref, fetch built_at to break the tie.

    This is the bug seen in air-gap deployments behind JFrog: the newer
    ``main-10792f4-6e4bc81`` push was being beaten by the older
    ``main-de76dd0-71dfdc4`` because ``d`` > ``1`` in ASCII. With built_at
    enrichment (sourced from manifest config blob `created`), the actually-
    newer build wins regardless of tag lex order.
    """
    src = OCISource()
    repo_path = "stewartshea/rw-cli-codecollection"
    cc = {
        "slug": "ss-rw-cli-codecollection",
        "image_registry": f"jfrog.example.com/{repo_path}",
    }

    respx.get(f"https://jfrog.example.com/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": repo_path,
                "tags": [
                    "latest",
                    "main",
                    "main-10792f4-6e4bc81",  # newer push (per config.created)
                    "main-de76dd0-71dfdc4",  # older push, but ASCII-larger
                ],
            },
        )
    )

    # Older tag → older config.created.
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/manifests/main-de76dd0-71dfdc4").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:old-cfg"}})
    )
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/blobs/sha256:old-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-12T10:00:00Z"})
    )

    # Newer tag → newer config.created.
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/manifests/main-10792f4-6e4bc81").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:new-cfg"}})
    )
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/blobs/sha256:new-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-21T17:00:00Z"})
    )

    refs = src.discover_refs(cc)
    by_tag = {r.image_tag: r for r in refs}
    assert by_tag["main-10792f4-6e4bc81"].built_at is not None
    assert by_tag["main-de76dd0-71dfdc4"].built_at is not None
    assert (
        by_tag["main-10792f4-6e4bc81"].built_at
        > by_tag["main-de76dd0-71dfdc4"].built_at
    )

    # The enriched built_at flips resolve_latest's decision from the
    # ASCII-largest tag to the actually-newest one.
    latest = src.resolve_latest({"default_ref": "main"}, refs)
    assert latest == "main-10792f4-6e4bc81"


@respx.mock
def test_discover_refs_ignores_misleading_last_modified_from_jfrog():
    """Regression: never trust the Last-Modified header.

    JFrog Artifactory's docker-remote setup proxies an upstream
    registry but sets ``Last-Modified`` to JFrog's local cache mtime
    — i.e. when JFrog last refreshed the manifest from upstream. After
    a cache flush, whichever tag the poll happens to GET first or last
    ends up with the freshest cache-mtime regardless of which image
    was actually built more recently. Production hit exactly this:
    the user cleared JFrog's cache, the catalog re-polled, and the
    OLDER ``main-de76dd0-71dfdc4`` ended up with a more recent
    ``Last-Modified`` than the NEWER ``main-10792f4-6e4bc81`` (because
    cc-catalog-svc happened to GET de76dd0's manifest a few hundred
    millis later in the loop). The OCI source must ignore that header
    entirely and read ``config.created`` instead.
    """
    src = OCISource()
    repo_path = "stewartshea/rw-cli-codecollection"
    cc = {
        "slug": "ss-rw-cli-codecollection",
        "image_registry": f"jfrog.example.com/{repo_path}",
    }

    respx.get(f"https://jfrog.example.com/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": repo_path,
                "tags": [
                    "main-10792f4-6e4bc81",  # actually newer
                    "main-de76dd0-71dfdc4",  # actually older
                ],
            },
        )
    )

    # The OLDER image, but JFrog cached it most recently → newer LM.
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/manifests/main-de76dd0-71dfdc4").mock(
        return_value=httpx.Response(
            200,
            headers={"Last-Modified": "Thu, 21 May 2026 18:26:19 GMT"},
            json={"config": {"digest": "sha256:older-build-cfg"}},
        )
    )
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/blobs/sha256:older-build-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-12T10:00:00Z"})
    )

    # The NEWER image, cached slightly earlier → older LM.
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/manifests/main-10792f4-6e4bc81").mock(
        return_value=httpx.Response(
            200,
            headers={"Last-Modified": "Thu, 21 May 2026 18:26:18 GMT"},
            json={"config": {"digest": "sha256:newer-build-cfg"}},
        )
    )
    respx.get(f"https://jfrog.example.com/v2/{repo_path}/blobs/sha256:newer-build-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-21T17:00:00Z"})
    )

    refs = src.discover_refs(cc)
    by_tag = {r.image_tag: r for r in refs}
    # build times reflect actual build, NOT Last-Modified
    assert by_tag["main-10792f4-6e4bc81"].built_at > by_tag["main-de76dd0-71dfdc4"].built_at

    # And resolve_latest picks the actually-newer build despite the
    # Last-Modified misdirection.
    latest = src.resolve_latest({"default_ref": "main"}, refs)
    assert latest == "main-10792f4-6e4bc81"


@respx.mock
def test_discover_refs_skips_enrichment_when_no_tiebreak():
    """With one tag per ref the enrichment must hit zero manifest endpoints.

    Otherwise every poll across many CCs becomes O(tags) extra HTTP calls.
    respx in strict mode would raise if we accidentally GET a manifest
    here, which would make this test fail.
    """
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
                "tags": [
                    "main-c1a2b3d-e4f5a6b",
                    "v1.2.0-aabbccd-e4f5a6b",
                    "pr-42-9988aab-e4f5a6b",
                ],
            },
        )
    )

    refs = src.discover_refs(cc)
    assert len(refs) == 3
    # built_at stays None for everyone — no enrichment triggered.
    assert all(r.built_at is None for r in refs)


@respx.mock
def test_discover_refs_falls_back_to_config_blob_created():
    """When Last-Modified is missing (GHCR), descend into manifest -> config blob."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-cli-codecollection"
    cc = {
        "slug": "rw-cli-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "tags": [
                    "main-aaaaaaa-bbbbbbb",
                    "main-1111111-bbbbbbb",
                ],
            },
        )
    )

    # Single-platform manifest with config.digest pointing at a blob.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-aaaaaaa-bbbbbbb").mock(
        return_value=httpx.Response(
            200,
            json={"config": {"digest": "sha256:older"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-1111111-bbbbbbb").mock(
        return_value=httpx.Response(
            200,
            json={"config": {"digest": "sha256:newer"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:older").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-12T10:00:00Z"})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:newer").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-21T17:00:00Z"})
    )

    refs = src.discover_refs(cc)
    by_tag = {r.image_tag: r for r in refs}
    assert by_tag["main-1111111-bbbbbbb"].built_at == datetime(
        2026, 5, 21, 17, 0, 0, tzinfo=timezone.utc
    )
    assert by_tag["main-aaaaaaa-bbbbbbb"].built_at == datetime(
        2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc
    )


@respx.mock
def test_discover_refs_handles_manifest_index_for_multiarch():
    """OCI image indices have no top-level config; descend into a child manifest."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-cli-codecollection"
    cc = {
        "slug": "rw-cli-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "tags": [
                    "main-aaaaaaa-bbbbbbb",
                    "main-1111111-bbbbbbb",
                ],
            },
        )
    )

    # Both tags are multi-arch indices.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-aaaaaaa-bbbbbbb").mock(
        return_value=httpx.Response(
            200,
            json={"manifests": [{"digest": "sha256:older-amd64"}]},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-1111111-bbbbbbb").mock(
        return_value=httpx.Response(
            200,
            json={"manifests": [{"digest": "sha256:newer-amd64"}]},
        )
    )
    # Child platform manifests carry config.digest.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:older-amd64").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:older-cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:newer-amd64").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:newer-cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:older-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-12T10:00:00Z"})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:newer-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-21T17:00:00Z"})
    )

    refs = src.discover_refs(cc)
    latest = src.resolve_latest({"default_ref": "main"}, refs)
    assert latest == "main-1111111-bbbbbbb"


@respx.mock
def test_discover_refs_enrichment_tolerates_per_tag_failure():
    """One broken tag's manifest must not poison the entire poll."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-cli-codecollection"
    cc = {
        "slug": "rw-cli-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "tags": [
                    "main-aaaaaaa-bbbbbbb",
                    "main-1111111-bbbbbbb",
                ],
            },
        )
    )
    # One returns 500 (broken). The other still gets a timestamp.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-aaaaaaa-bbbbbbb").mock(
        return_value=httpx.Response(500)
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main-1111111-bbbbbbb").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:ok-cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:ok-cfg").mock(
        return_value=httpx.Response(200, json={"created": "2026-05-21T17:00:00Z"})
    )

    refs = src.discover_refs(cc)
    by_tag = {r.image_tag: r for r in refs}
    assert by_tag["main-aaaaaaa-bbbbbbb"].built_at is None
    assert by_tag["main-1111111-bbbbbbb"].built_at is not None

    # resolve_latest still produces the right answer: the only ref with
    # a known built_at outranks the bare-image_tag fallback (epoch_min).
    latest = src.resolve_latest({"default_ref": "main"}, refs)
    assert latest == "main-1111111-bbbbbbb"
