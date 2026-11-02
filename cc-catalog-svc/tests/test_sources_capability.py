"""
Capability discovery unit tests.

Pure tag-classification logic is exercised directly (no I/O); the manifest
label + auth-dance paths use respx to fake the GHCR surface, matching the
style of tests/test_sources_oci.py.
"""

from __future__ import annotations

import base64
import json

import httpx
import respx
import yaml

from app.sources.capability import (
    _pending_alias_refs,
    _select_capability_refs,
    discover_capabilities,
)
from app.sources.oci import OCISource


def _manifest_label(capability: str, version: str) -> str:
    text = yaml.safe_dump({"capability": capability, "version": version})
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _schemas_label(obj) -> str:
    return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("ascii")


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


def test_select_capability_refs_version_named_branch_is_not_a_release():
    # Branch `1.2.3` pushes both `1.2.3` and its canonical `1.2.3-287377c`.
    raw = {"1.2.3", "1.2.3-287377c", "v2.0.0"}
    refs = dict(_select_capability_refs(raw))
    assert refs["1.2.3"] == "branch"
    assert "1.2.3-287377c" not in refs
    assert refs["v2.0.0"] == "tag"


# ---------------------------------------------------------------------------
# alias-tag race bridge (pure)
# ---------------------------------------------------------------------------
def test_pending_alias_refs_keeps_known_alias_missing_its_companion():
    # "main" has no "main-<sha>" companion yet, but we've resolved it before.
    raw = {"main", "v1.0.0"}
    assert _pending_alias_refs(raw, known_refs=frozenset({"main"})) == {"main"}


def test_pending_alias_refs_skips_unknown_tag_missing_a_companion():
    # Never resolved before -> not bridged, same as today.
    raw = {"main"}
    assert _pending_alias_refs(raw, known_refs=frozenset()) == frozenset()


def test_pending_alias_refs_ignores_alias_that_already_has_its_companion():
    # "main" is already selected via its companion, so it's not "pending".
    raw = {"main", "main-287377c"}
    assert _pending_alias_refs(raw, known_refs=frozenset({"main"})) == frozenset()


def test_pending_alias_refs_excludes_latest_pr_and_semver():
    raw = {"latest", "pr-42", "v1.0.0"}
    known = frozenset({"latest", "pr-42", "v1.0.0"})
    assert _pending_alias_refs(raw, known_refs=known) == frozenset()


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


# ---------------------------------------------------------------------------
# required `capability` / `version` manifest fields
# ---------------------------------------------------------------------------
@respx.mock
def test_discover_capabilities_skips_ref_missing_capability_field():
    """A manifest with no `capability` key is invalid, not merely unresolved:
    it's skipped, but the ref stays in `listed_refs` so it isn't pruned."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }
    bad_label = base64.b64encode(yaml.safe_dump({"version": "0.2.0"}).encode()).decode()

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
            json={"config": {"Labels": {"com.runwhen.capability.manifest.v1": bad_label}}},
        )
    )

    discovery = discover_capabilities(src, cc)
    assert discovery.capabilities == []
    assert discovery.listed_refs == {"main"}


@respx.mock
def test_discover_capabilities_skips_ref_missing_version_field():
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }
    bad_label = base64.b64encode(yaml.safe_dump({"capability": "rw-checks"}).encode()).decode()

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
            json={"config": {"Labels": {"com.runwhen.capability.manifest.v1": bad_label}}},
        )
    )

    discovery = discover_capabilities(src, cc)
    assert discovery.capabilities == []
    assert discovery.listed_refs == {"main"}


# ---------------------------------------------------------------------------
# schemas label (optional; a bad value never invalidates the ref)
# ---------------------------------------------------------------------------
@respx.mock
def test_discover_capabilities_reads_valid_schemas_label():
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }
    schemas_obj = {"schemas/k8s_object.json": {"type": "object"}}

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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
                        "com.runwhen.capability.schemas.v1": _schemas_label(schemas_obj),
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert json.loads(caps[0].schemas_text) == schemas_obj


@respx.mock
def test_discover_capabilities_schemas_text_none_when_label_absent():
    """The schemas label is optional: no label at all is not a warning-worthy
    condition, just schemas_text = None with the ref kept normally."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].schemas_text is None


@respx.mock
def test_discover_capabilities_schemas_label_bad_base64_keeps_ref(caplog):
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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
                        "com.runwhen.capability.schemas.v1": "not-valid-base64!!!",
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].capability == "rw-checks"  # the manifest is still valid
    assert caps[0].schemas_text is None
    assert "schemas label" in caplog.text


@respx.mock
def test_discover_capabilities_schemas_label_bad_json_keeps_ref(caplog):
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }
    bad_json_label = base64.b64encode(b"not json at all").decode("ascii")

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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
                        "com.runwhen.capability.schemas.v1": bad_json_label,
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].schemas_text is None
    assert "schemas label" in caplog.text


@respx.mock
def test_discover_capabilities_schemas_label_json_array_keeps_ref(caplog):
    """A JSON array decodes fine but isn't the required object shape."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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
                        "com.runwhen.capability.schemas.v1": _schemas_label(
                            ["schemas/k8s_object.json"]
                        ),
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].schemas_text is None
    assert "schemas label" in caplog.text


@respx.mock
def test_discover_capabilities_schemas_label_non_object_value_keeps_ref(caplog):
    """Every value must itself be a JSON object (a schema document)."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["v1.0.0"]})
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
                        "com.runwhen.capability.schemas.v1": _schemas_label(
                            {"schemas/k8s_object.json": "not-an-object"}
                        ),
                    }
                }
            },
        )
    )

    caps = discover_capabilities(src, cc).capabilities
    assert len(caps) == 1
    assert caps[0].schemas_text is None
    assert "schemas label" in caplog.text


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


# ---------------------------------------------------------------------------
# alias-tag race: companion tag not (yet) pushed
# ---------------------------------------------------------------------------
@respx.mock
def test_discover_capabilities_keeps_known_alias_without_its_companion():
    """`main`'s `main-<sha>` companion hasn't landed this poll. We've resolved
    `main` before (`known_refs`), so it's kept listed (not pruned) and never
    re-fetched -- no manifest route is mocked for it, so respx would raise if
    the code tried."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "v1.0.0"]})
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

    discovery = discover_capabilities(src, cc, known_refs=frozenset({"main"}))
    assert [c.ref for c in discovery.capabilities] == ["v1.0.0"]
    assert discovery.listed_refs == {"main", "v1.0.0"}


@respx.mock
def test_discover_capabilities_drops_unknown_alias_without_its_companion():
    """Same setup, but `main` has never resolved before -- it's dropped from
    the listing exactly as it was before this fix."""
    src = OCISource()
    repo_path = "runwhen-contrib/rw-checks-codecollection"
    cc = {
        "slug": "rw-checks-codecollection",
        "image_registry": f"ghcr.io/{repo_path}",
    }

    respx.get(f"https://ghcr.io/v2/{repo_path}/tags/list").mock(
        return_value=httpx.Response(200, json={"tags": ["main", "v1.0.0"]})
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

    discovery = discover_capabilities(src, cc)  # known_refs defaults to empty
    assert [c.ref for c in discovery.capabilities] == ["v1.0.0"]
    assert discovery.listed_refs == {"v1.0.0"}
