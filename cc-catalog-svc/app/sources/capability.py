"""
Capability image discovery.

A `kind: capability` CodeCollection entry (see `app.config.CodeCollectionConfig`)
is a different pipeline from the Robot `TAG_PATTERN` scheme in `app.sources.oci`:
each platform image carries its capability manifest as a config-blob label
instead of an OCI ref -> two-sha tag mapping. This module composes
`OCISource`'s auth + tag-listing + manifest-GET helpers (never duplicating
the bearer-realm dance or pagination logic) and adds the capability-specific
tag classification and label decoding described in the design's Contract 2.

Only `type: oci` sources are supported — capability discovery needs the raw
OCI Distribution v2 surface (`OCISource._get_with_auth`, `_list_tags`,
`_resolve_auth_header`) that other source plugins (`static`, `upstream`)
don't expose.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import logging
import re
from typing import Optional

import httpx
import yaml

from app.sources.oci import _MANIFEST_ACCEPT, OCISource

logger = logging.getLogger(__name__)


# The label the C1 build workflow stamps on every platform's image config,
# holding the base64 of the capability's manifest.yaml verbatim.
CAPABILITY_MANIFEST_LABEL = "com.runwhen.capability.manifest.v1"

# A branch alias tag T is detected by the existence of a companion
# T-<7..40 hex> tag (the same convention the Robot pipeline stamps, minus
# the second `rt_sha` component). This is intentionally a different, looser
# pattern than oci.TAG_PATTERN (which requires two sha components).
_ALIAS_SUFFIX = re.compile(r"^(?P<ref>.+)-(?P<sha>[0-9a-f]{7,40})$")

# Full-match semver, unlike oci.SEMVER_TAG (a prefix match used to classify
# already-parsed Robot refs). Capability tags are literal tag names, so we
# require the whole tag to be a semver string.
CAPABILITY_SEMVER_TAG = re.compile(r"^v?\d+\.\d+\.\d+([-+].*)?$")


@dataclasses.dataclass(frozen=True)
class DiscoveredCapability:
    """One capability image build found for a `kind: capability` entry."""

    capability: Optional[str]
    version: Optional[str]
    ref: str
    ref_type: str  # "branch" | "tag"
    commit_hash: Optional[str]
    image_tag: str
    image_digest: str
    image: str
    manifest_text: str


@dataclasses.dataclass(frozen=True)
class CapabilityDiscovery:
    """Result of one `discover_capabilities` call.

    `listed_refs` is every ref the tag listing selected, whether or not it
    resolved. The poll layer prunes only rows whose ref dropped out of
    `listed_refs`, so a ref that is still tagged but failed to resolve this
    poll (a 429/5xx/timeout on its manifest or blob) keeps its last good
    row instead of being deleted.
    """

    listed_refs: frozenset[str]
    capabilities: list[DiscoveredCapability]


def discover_capabilities(source: OCISource, cc: dict) -> CapabilityDiscovery:
    """Discover every capability ref for one `kind: capability` CC entry.

    `source` must be the configured `OCISource` instance for the entry's
    source (same one the catalog poll layer already built for the Robot
    path) — we reuse its auth resolution, tag listing, and 401-dance GET
    rather than reimplementing any of it.
    """
    registry_url = cc.get("image_registry")
    slug = cc.get("slug")
    if not registry_url:
        logger.warning(
            "capability source skipping %s: no image_registry configured",
            slug,
        )
        return CapabilityDiscovery(listed_refs=frozenset(), capabilities=[])

    host, repo = source._split_registry_url(registry_url)
    auth_header, auth_mode = source._resolve_auth_header(cc)

    with httpx.Client(timeout=source.timeout, follow_redirects=True) as client:
        tags = source._list_tags(client, host, repo, auth_header=auth_header, auth_mode=auth_mode)
        refs = _select_capability_refs(set(tags))

        discovered: list[DiscoveredCapability] = []
        for ref, ref_type in refs:
            # Any failure resolving one ref skips just that ref — it must
            # never raise and poison the rest of the entry's listing.
            try:
                cap = _discover_one_ref(
                    source,
                    client,
                    host,
                    repo,
                    registry_url,
                    ref,
                    ref_type,
                    auth_header,
                    auth_mode,
                    slug,
                )
            except Exception:
                logger.warning(
                    "capability source: %s failed to resolve ref %s; skipping",
                    slug,
                    ref,
                    exc_info=True,
                )
                cap = None
            if cap is not None:
                discovered.append(cap)

    logger.info(
        "capability source: %s -> %d tags, %d capability ref(s) discovered",
        slug,
        len(tags),
        len(discovered),
    )
    return CapabilityDiscovery(
        listed_refs=frozenset(ref for ref, _ in refs),
        capabilities=discovered,
    )


# ---------------------------------------------------------------------------
# tag classification
# ---------------------------------------------------------------------------
def _select_capability_refs(raw_tags: set[str]) -> list[tuple[str, str]]:
    """Return `(ref, ref_type)` pairs per Contract 2's ref rules.

    - Every branch alias tag T (a tag T for which some `T-<7..40 hex>` tag
      exists) whose name does not start with `pr-`. `latest` is never one,
      even if a `latest-<sha>` tag happened to exist.
    - Every semver tag (full match), regardless of a `pr-` prefix — the
      `pr-` exclusion only applies to the branch-alias rule.
    """
    alias_bases = {m.group("ref") for t in raw_tags if (m := _ALIAS_SUFFIX.match(t)) is not None}

    refs: dict[str, str] = {}
    for t in raw_tags:
        if t == "latest":
            continue
        if CAPABILITY_SEMVER_TAG.match(t):
            refs[t] = "tag"
            continue
        if t.startswith("pr-"):
            continue
        if t in alias_bases:
            refs[t] = "branch"

    return sorted(refs.items())


# ---------------------------------------------------------------------------
# per-ref manifest + label resolution
# ---------------------------------------------------------------------------
def _discover_one_ref(
    source: OCISource,
    client: httpx.Client,
    host: str,
    repo: str,
    image_registry: str,
    ref: str,
    ref_type: str,
    auth_header: Optional[str],
    auth_mode: str,
    slug: Optional[str],
) -> Optional[DiscoveredCapability]:
    """Resolve one ref to a `DiscoveredCapability`, or None + a warning log.

    Expected gaps (non-200 responses, missing label, undecodable label,
    unparseable YAML) return None here; unexpected errors (transport
    failures, non-JSON bodies) raise and are skipped by the caller.
    """
    manifest_url = f"https://{host}/v2/{repo}/manifests/{ref}"
    resp = source._get_with_auth(
        client,
        host,
        repo,
        manifest_url,
        params={},
        auth_header=auth_header,
        auth_mode=auth_mode,
        accept=_MANIFEST_ACCEPT,
    )
    if resp.status_code != 200:
        logger.warning(
            "capability source: %s manifest GET for ref %s returned %s",
            slug,
            ref,
            resp.status_code,
        )
        return None

    # The top-level digest (the index digest for multi-arch). A registry
    # that omits Docker-Content-Digest still served these exact bytes, and a
    # manifest's digest is by definition the sha256 of them — never fall back
    # to a child digest, which would pin one platform's image.
    image_digest = (
        resp.headers.get("Docker-Content-Digest")
        or f"sha256:{hashlib.sha256(resp.content).hexdigest()}"
    )
    manifest = resp.json()
    child_manifests = manifest.get("manifests")

    if child_manifests:
        child = _select_linux_amd64_child(child_manifests)
        child_digest = (child or {}).get("digest")
        if not child_digest:
            logger.warning(
                "capability source: %s ref %s multi-arch index has no usable child digest",
                slug,
                ref,
            )
            return None
        child_resp = source._get_with_auth(
            client,
            host,
            repo,
            f"https://{host}/v2/{repo}/manifests/{child_digest}",
            params={},
            auth_header=auth_header,
            auth_mode=auth_mode,
            accept=_MANIFEST_ACCEPT,
        )
        if child_resp.status_code != 200:
            logger.warning(
                "capability source: %s ref %s child manifest GET returned %s",
                slug,
                ref,
                child_resp.status_code,
            )
            return None
        config_digest = (child_resp.json().get("config") or {}).get("digest")
    else:
        config_digest = (manifest.get("config") or {}).get("digest")

    if not config_digest:
        logger.warning(
            "capability source: %s ref %s is missing its config digest",
            slug,
            ref,
        )
        return None

    blob_resp = source._get_with_auth(
        client,
        host,
        repo,
        f"https://{host}/v2/{repo}/blobs/{config_digest}",
        params={},
        auth_header=auth_header,
        auth_mode=auth_mode,
    )
    if blob_resp.status_code != 200:
        logger.warning(
            "capability source: %s ref %s config blob GET returned %s",
            slug,
            ref,
            blob_resp.status_code,
        )
        return None
    labels = (blob_resp.json().get("config") or {}).get("Labels") or {}

    manifest_label = labels.get(CAPABILITY_MANIFEST_LABEL)
    if not manifest_label:
        logger.warning(
            "capability source: %s ref %s has no %s label; skipping",
            slug,
            ref,
            CAPABILITY_MANIFEST_LABEL,
        )
        return None
    try:
        manifest_text = base64.b64decode(manifest_label, validate=True).decode("utf-8")
    except Exception:
        logger.warning(
            "capability source: %s ref %s manifest label is not valid base64; skipping",
            slug,
            ref,
        )
        return None
    try:
        parsed = yaml.safe_load(manifest_text)
    except yaml.YAMLError:
        logger.warning(
            "capability source: %s ref %s manifest label is not parseable YAML; skipping",
            slug,
            ref,
        )
        return None
    if not isinstance(parsed, dict):
        logger.warning(
            "capability source: %s ref %s manifest YAML did not parse to a mapping; skipping",
            slug,
            ref,
        )
        return None

    commit_full = labels.get("io.runwhen.codecollection.commit")
    commit_hash = commit_full[:7] if commit_full else None

    image_tag = ref if ref_type == "tag" else (f"{ref}-{commit_hash}" if commit_hash else ref)

    return DiscoveredCapability(
        capability=parsed.get("capability"),
        version=parsed.get("version"),
        ref=ref,
        ref_type=ref_type,
        commit_hash=commit_hash,
        image_tag=image_tag,
        image_digest=image_digest,
        image=f"{image_registry}@{image_digest}",
        manifest_text=manifest_text,
    )


def _select_linux_amd64_child(child_manifests: list[dict]) -> Optional[dict]:
    """Prefer the linux/amd64 child; fall back to the first child."""
    for m in child_manifests:
        platform = (m or {}).get("platform") or {}
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            return m
    return child_manifests[0] if child_manifests else None
