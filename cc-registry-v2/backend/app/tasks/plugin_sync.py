"""
Persistence helpers for V13 plugin skills.

`plugin_parser.py` turns `plugins/<plugin>/skills/<skill>` into a plain dict.
This module wires those dicts onto the `Codebundle` ORM object and owns the
repository-clone cache so that a monorepo such as `runwhen-plugins` (six
collections, one remote) is cloned exactly once per sync run instead of once
per collection.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tasks.plugin_parser import (
    DEFAULT_GIT_REF,
    parse_plugin_directory,
    parse_plugin_from_files,
)

logger = logging.getLogger(__name__)


def clone_repository_cached(
    git_url: str,
    git_ref: Optional[str],
    tmp_dir: str,
    cache: Dict[Tuple[str, str], Optional[str]],
) -> Optional[str]:
    """Clone `(git_url, git_ref)` once into `tmp_dir`, returning its path.

    The cache is keyed by `(git_url, git_ref)` so a plug-in monorepo shared by
    several registry collections is fetched a single time. Returns None when
    the clone fails; the error is logged and callers skip that collection.
    """
    ref = git_ref or "main"
    key = (git_url, ref)
    if key in cache:
        return cache[key]

    from git import Repo

    repo_path = Path(tmp_dir) / f"repo-{abs(hash(key))}"
    try:
        logger.info(f"Cloning {git_url} (ref={ref}) to {repo_path}")
        Repo.clone_from(git_url, str(repo_path), branch=ref)
        cache[key] = str(repo_path)
        return str(repo_path)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to clone {git_url} (ref={ref}): {exc}")
        cache[key] = None
        return None


def resolve_plugin_dir(
    repo_path: str,
    collection_slug: str,
    plugin_path: Optional[str] = None,
) -> Optional[Path]:
    """Locate a V13 plugin directory inside a cloned repository.

    Order: explicit `plugin_path` from `codecollections.yaml`, then
    `plugins/<collection slug>`, then a repo that *is* the plugin
    (`plugin.yaml` at the root).
    """
    repo = Path(repo_path)
    candidates: List[Path] = []
    if plugin_path:
        candidates.append(repo / plugin_path)
    candidates.append(repo / "plugins" / collection_slug)
    candidates.append(repo)

    for candidate in candidates:
        # `skills/` is optional: the `misc` plugin is a placeholder with only
        # plugin.yaml until its first skill lands.
        if (candidate / "plugin.yaml").exists():
            return candidate
    return None


def parse_collection_plugin(
    repo_path: str,
    collection_slug: str,
    git_url: Optional[str] = None,
    git_ref: Optional[str] = None,
    plugin_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Parse the plugin that belongs to `collection_slug` (None if absent)."""
    plugin_dir = resolve_plugin_dir(repo_path, collection_slug, plugin_path)
    if not plugin_dir:
        return None
    return parse_plugin_directory(
        plugin_dir,
        repo_root=Path(repo_path),
        git_url=git_url,
        git_ref=git_ref or DEFAULT_GIT_REF,
    )


def parse_collection_plugin_from_files(
    collection_slug: str,
    files: Dict[str, str],
    git_url: Optional[str] = None,
    git_ref: Optional[str] = None,
    plugin_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Parse a plugin from stored `relative path -> content` files.

    Returns None when the files do not contain a V13 plugin.
    """
    plugin_slug = (
        Path(plugin_path).name if plugin_path else collection_slug
    )
    has_plugin_yaml = any(
        path.endswith("/plugin.yaml") and "skills/" not in path for path in files
    ) or f"plugins/{collection_slug}/plugin.yaml" in files
    has_skill_files = any(
        f"plugins/{plugin_slug}/skills/" in path for path in files
    )
    if not has_plugin_yaml and not has_skill_files:
        return None
    return parse_plugin_from_files(
        plugin_slug,
        files,
        git_url=git_url,
        git_ref=git_ref or DEFAULT_GIT_REF,
    )


def _apply_skill_to_codebundle(codebundle, parsed: Dict[str, Any]) -> None:
    """Copy every parsed skill field onto a `Codebundle` row."""
    codebundle.name = parsed.get("name") or parsed.get("slug")
    codebundle.slug = parsed["slug"]
    codebundle.display_name = parsed.get("display_name") or codebundle.slug
    codebundle.description = parsed.get("description", "")
    codebundle.doc = parsed.get("doc", "")
    codebundle.readme = parsed.get("readme", "")
    codebundle.author = parsed.get("author", "")
    codebundle.support_tags = parsed.get("support_tags", [])
    codebundle.categories = parsed.get("categories", [])
    codebundle.tasks = parsed.get("tasks", [])
    codebundle.slis = parsed.get("slis", [])
    codebundle.task_count = parsed.get("task_count", len(codebundle.tasks or []))
    codebundle.sli_count = parsed.get("sli_count", 0)
    codebundle.user_variables = parsed.get("user_variables", [])
    codebundle.access_level = parsed.get("access_level", "unknown")
    codebundle.minimum_iam_requirements = parsed.get("minimum_iam_requirements", [])
    codebundle.data_classifications = parsed.get("data_classifications", {})
    codebundle.has_genrules = parsed.get("has_genrules", False)
    codebundle.is_discoverable = parsed.get("is_discoverable", False)
    codebundle.discovery_platform = parsed.get("discovery_platform")
    codebundle.discovery_resource_types = parsed.get("discovery_resource_types", [])
    codebundle.discovery_match_patterns = parsed.get("discovery_match_patterns", [])
    codebundle.discovery_output_items = parsed.get("discovery_output_items", [])
    codebundle.discovery_level_of_detail = parsed.get("discovery_level_of_detail")
    codebundle.discovery_templates = parsed.get("discovery_templates", [])
    codebundle.runbook_path = parsed.get("runbook_path")
    codebundle.sli_path = None
    codebundle.meta_path = parsed.get("meta_path")
    codebundle.runbook_source_url = parsed.get("runbook_source_url")
    codebundle.ai_enhanced_description = parsed.get("ai_enhanced_description")
    codebundle.ai_enhanced_metadata = parsed.get("ai_enhanced_metadata", {})
    codebundle.enhancement_status = parsed.get("enhancement_status", "completed")
    codebundle.is_active = True


def upsert_skill_codebundle(
    db,
    collection,
    parsed: Dict[str, Any],
    git_updated_at: Optional[datetime] = None,
) -> str:
    """Create or update the `Codebundle` for one parsed skill.

    Returns "created" or "updated".
    """
    from app.models import Codebundle

    existing = db.query(Codebundle).filter(
        Codebundle.slug == parsed["slug"],
        Codebundle.codecollection_id == collection.id,
    ).first()

    if existing:
        _apply_skill_to_codebundle(existing, parsed)
        if git_updated_at:
            existing.git_updated_at = git_updated_at
        return "updated"

    codebundle = Codebundle(
        codecollection_id=collection.id,
        is_active=True,
        git_updated_at=git_updated_at,
    )
    _apply_skill_to_codebundle(codebundle, parsed)
    db.add(codebundle)
    return "created"


def deactivate_stale_codebundles(db, collection, active_slugs: List[str]) -> int:
    """Mark codebundles in `collection` that no longer exist on disk inactive."""
    from app.models import Codebundle

    query = db.query(Codebundle).filter(
        Codebundle.codecollection_id == collection.id,
        Codebundle.is_active == True,  # noqa: E712 - SQLAlchemy comparison
    )
    if active_slugs:
        query = query.filter(Codebundle.slug.notin_(active_slugs))

    stale = query.all()
    for codebundle in stale:
        codebundle.is_active = False
    if stale:
        logger.info(
            f"[{collection.slug}] deactivated {len(stale)} stale codebundle(s)"
        )
    return len(stale)


def sync_plugin_collection(
    db,
    collection,
    repo_path: str,
    plugin_parsed: Dict[str, Any],
    git_updated_at: Optional[datetime] = None,
) -> Tuple[int, int, int]:
    """Upsert every skill of a parsed plugin and deactivate removed skills.

    Returns `(created, updated, deactivated)`.
    """
    created = updated = 0
    active_slugs: List[str] = []

    for skill in plugin_parsed.get("skills", []):
        try:
            outcome = upsert_skill_codebundle(db, collection, skill, git_updated_at)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[{collection.slug}] failed to upsert skill "
                         f"{skill.get('slug')}: {exc}")
            continue
        active_slugs.append(skill["slug"])
        if outcome == "created":
            created += 1
        else:
            updated += 1

    deactivated = deactivate_stale_codebundles(db, collection, active_slugs)
    return created, updated, deactivated