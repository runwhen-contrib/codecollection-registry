"""
Capability discovery unit tests.

Pure tag-classification logic is exercised directly (no I/O); the manifest
label + auth-dance paths use respx to fake the GHCR surface, matching the
style of tests/test_sources_oci.py.
"""

from __future__ import annotations

import base64

import httpx
import respx
import yaml

from app.sources.capability import (
    _select_capability_refs,
    discover_capabilities,
)
from app.sources.oci import OCISource


def _manifest_label(capability: str, version: str) -> str:
    text = yaml.safe_dump({"capability": capability, "version": version})
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# tag classification (pure)
# ---------------------------------------------------------------------------
def test_select_capability_refs_branch_alias_pr_and_latest_excluded():
    raw = {"main", "main-287377c", "latest", "pr-42", "pr-42-abcdef1", "random"}
    assert _select_capability_refs(raw) == [("main", "branch")]


def test_select_capability_refs_requires_hex_companion():
    # "release-notes" has no <ref>-<7..40 hex> companion tag, so it's not a
    # branch alias even though it superficially looks hyphenated.
    raw = {"release-notes"}
    assert _select_capability_refs(raw) == []


def test_select_capability_refs_semver_tags():
    raw = {"v1.2.0", "v1.2.0-rc.1", "1.2.3", "v1.2", "not-semver"}
    refs = dict(_select_capability_refs(raw))
    assert refs["v1.2.0"] == "tag"
    assert refs["v1.2.0-rc.1"] == "tag"
    assert refs["1.2.3"] == "tag"
    # v1.2 has no patch component -> not semver, and has no alias companion.
    assert "v1.2" not in refs
    assert "not-semver" not in refs


# ---------------------------------------------------------------------------
# end-to-end discovery against a mocked registry
# ---------------------------------------------------------------------------
@respx.mock
def test_discover_capabilities_reads_label_from_amd64_child_with_arm64_first():
    """Multi-arch index lists arm64 first; the label must come from amd64."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "main-287377c", "latest"]})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:indexdigest"},
            json={
                "manifests": [
                    {
                        "digest": "sha256:arm64digest",
                        "platform": {"architecture": "arm64", "os": "linux"},
                    },
                    {
                        "digest": "sha256:amd64digest",
                        "platform": {"architecture": "amd64", "os": "linux"},
                    },
                ]
            },
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:amd64digest").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:amd64cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:amd64cfg").mock(
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
    # No route mocked for the arm64 child manifest -- respx raises if the
    # code ever fetches it, which is exactly the regression this guards.

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    cap = caps[0]
    assert cap.capability == "rw-checks"
    assert cap.version == "0.2.0"
    assert cap.ref == "main"
    assert cap.ref_type == "branch"
    assert cap.commit_hash == "287377c"
    assert cap.image_tag == "main-287377c"
    assert cap.image_digest == "sha256:indexdigest"
    assert cap.image == f"ghcr.io/{repo_path}@sha256:indexdigest"
    assert yaml.safe_load(cap.manifest_text) == {"capability": "rw-checks", "version": "0.2.0"}


@respx.mock
def test_discover_capabilities_falls_back_to_first_child_without_amd64():
    src = OCISource()
    repo_path = "runwhen-contrib/rw-worktree-codecollection"
    cc = {
        "slug": "rw-worktree-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/v1.0.0").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:indexdigest"},
            json={
                "manifests": [
                    {
                        "digest": "sha256:onlychilddigest",
                        "platform": {"architecture": "arm64", "os": "linux"},
                    },
                ]
            },
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:onlychilddigest").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:onlycfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:onlycfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label(
                            "rw-worktree", "1.0.0"
                        ),
                        "io.runwhen.codecollection.commit": "deadbee",
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    cap = caps[0]
    assert cap.ref == "v1.0.0"
    assert cap.ref_type == "tag"
    assert cap.image_tag == "v1.0.0"  # semver refs keep the tag verbatim


@respx.mock
def test_discover_capabilities_skips_ref_with_missing_label_without_failing_entry():
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "main-287377c", "v1.0.0"]})
    )
    # "main" has no label at all.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:mainindex"},
            json={"config": {"digest": "sha256:maincfg"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:maincfg").mock(
        return_value=httpx.Response(200, json={"config": {"Labels": {}}})
    )
    # "v1.0.0" has a well-formed label.
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/v1.0.0").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:v1index"},
            json={"config": {"digest": "sha256:v1cfg"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:v1cfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label("rw-checks", "1.0.0"),
                        "io.runwhen.codecollection.commit": "cafebee",
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].ref == "v1.0.0"


@respx.mock
def test_discover_capabilities_skips_ref_with_undecodable_label():
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "main-287377c"]})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:mainindex"},
            json={"config": {"digest": "sha256:maincfg"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:maincfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": "not-valid-base64!!!",
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert caps == []


@respx.mock
def test_discover_capabilities_handles_anonymous_bearer_dance():
    """The bearer-realm 401 dance must still work on the capability path."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    list_url = f"https://ghcr.io/v2/{repo_path}/tags/list"
    route = respx.get(list_url)
    route.side_effect = [
        httpx.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    'Bearer realm="https://ghcr.io/token",'
                    'service="ghcr.io",'
                    f'scope="repository:{repo_path}:pull"'
                ),
            },
        ),
        httpx.Response(200, json={"tags": ["v1.0.0"]}),
    ]
    respx.get("https://ghcr.io/token").mock(return_value=httpx.Response(200, json={"token": "tok"}))
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/v1.0.0").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:v1index"},
            json={"config": {"digest": "sha256:v1cfg"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:v1cfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label("rw-checks", "1.0.0"),
                        "io.runwhen.codecollection.commit": "cafebee",
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].ref == "v1.0.0"


def test_discover_capabilities_skips_when_no_image_registry():
    src = OCISource()
    assert discover_capabilities(src, {"slug": "no-registry"}).capabilities == []


@respx.mock
def test_discover_capabilities_hashes_body_when_digest_header_absent():
    """Without Docker-Content-Digest the image digest is the sha256 of the
    index body, never a child (single-platform) digest."""
    import hashlib
    import json

    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }
    index_body = json.dumps(
        {
            "manifests": [
                {
                    "digest": "sha256:arm64digest",
                    "platform": {"architecture": "arm64", "os": "linux"},
                },
                {
                    "digest": "sha256:amd64digest",
                    "platform": {"architecture": "amd64", "os": "linux"},
                },
            ]
        }
    ).encode("utf-8")

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/v1.0.0").mock(
        return_value=httpx.Response(200, content=index_body)
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:amd64digest").mock(
        return_value=httpx.Response(200, json={"config": {"digest": "sha256:amd64cfg"}})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:amd64cfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label("rw-checks", "1.0.0"),
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    expected = f"sha256:{hashlib.sha256(index_body).hexdigest()}"
    assert caps[0].image_digest == expected
    assert caps[0].image == f"ghcr.io/{repo_path}@{expected}"


@respx.mock
def test_discover_capabilities_skips_ref_whose_child_fetch_raises():
    """A transport error on one ref's child manifest skips only that ref, and
    the ref is still reported as listed so the poll layer won't prune it."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "main-287377c", "v1.0.0"]})
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/main").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:mainindex"},
            json={
                "manifests": [
                    {
                        "digest": "sha256:mainamd64",
                        "platform": {"architecture": "amd64", "os": "linux"},
                    },
                ]
            },
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/sha256:mainamd64").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/manifests/v1.0.0").mock(
        return_value=httpx.Response(
            200,
            headers={"Docker-Content-Digest": "sha256:v1index"},
            json={"config": {"digest": "sha256:v1cfg"}},
        )
    )
    respx.get(f"https://ghcr.io/v2/{repo_path}/blobs/sha256:v1cfg").mock(
        return_value=httpx.Response(
            200,
            json={
                "config": {
                    "Labels": {
                        "com.runwhen.capability.manifest.v1": _manifest_label("rw-checks", "1.0.0"),
                    }
                }
            },
        )
    )

    discovery = discover_capabilities(src, cc)
    assert [c.ref for c in discovery.capabilities] == ["v1.0.0"]
    assert discovery.listed_refs == {"main", "v1.0.0"}
