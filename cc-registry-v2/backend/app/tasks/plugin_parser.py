"""
V13 Plugins parser — `runwhen-plugins` (branch `v13/plugins-m4`).

The legacy registry parses Robot Framework CodeCollections
(`codebundles/<bundle>/runbook.robot`).  V13 replaces those with *plugins*
that ship *skills*:

    plugins/
      <plugin>/
        plugin.yaml                  # name, version, description, requires
        integration/integration.yaml # platform, title, docs, credentialTypes ...
        skills/
          <skill>/
            SKILL.md                 # YAML frontmatter + Markdown body
            tasks.yaml               # runtime, defaults, settings, tasks[]

A skill is what the registry calls a "Skill Template" (`Codebundle` in the
database).  Each skill maps 1:1 onto one `codebundles` row; each entry in
`tasks.yaml` maps onto one Tool inside it (`tasks` JSON column).

This module only *parses and shapes* data.  Persistence lives in
`registry_tasks.py` / `admin.py`.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

DEFAULT_GIT_REF = "v13/plugins-m4"

# Platform display names keyed by the integration `platform` value (or plugin slug).
_PLATFORM_DISPLAY_NAMES = {
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "misc": "Misc",
}

# Data classification labels mirror the ones used for legacy Robot CodeBundles.
_DATA_TAG_LABELS = {
    "data:config": "Configuration data",
    "data:logs-regexp": "Filtered logs",
    "data:logs-bulk": "General/unfiltered logs",
    "data:logs-stacktrace": "Stacktrace logs",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _create_display_name(name: str) -> str:
    """Turn `k8s-workload-health` / `pg_locks` into `K8s Workload Health`."""
    display_words: List[str] = []
    for word in re.split(r"[-_]", name or ""):
        if not word:
            continue
        # Words with digits (`k8s`, `v13`) are abbreviations: keep them intact.
        if re.search(r"\d", word):
            display_words.append(word[0].upper() + word[1:] if word[0].isalpha() else word)
            continue
        camel_words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", word)
        if camel_words:
            display_words.extend([w.capitalize() for w in camel_words])
        else:
            display_words.append(word.capitalize())
    return " ".join(display_words) or name


def _read_yaml(path: Path) -> Dict[str, Any]:
    """Read a YAML file, returning {} on any problem (never raises)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 - parsing is best-effort
        logger.warning(f"Failed to read YAML {path}: {exc}")
        return {}


def _first_paragraph(body: str) -> str:
    """First non-heading, non-empty paragraph of a Markdown body."""
    paragraph: List[str] = []
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            if paragraph:
                break
            continue
        if not line:
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# 1. SKILL.md
# ---------------------------------------------------------------------------
def parse_skill_md(content: str) -> Tuple[Dict[str, Any], str]:
    """Split a `SKILL.md` into (YAML frontmatter dict, Markdown body).

    Frontmatter is delimited by a leading `---` line and the next `---` line.
    Anything malformed degrades gracefully to ({}, whole content).
    """
    if not content:
        return {}, ""
    text = content.lstrip("\ufeff")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in ("---", "..."):
            end_index = idx
            break
    if end_index is None:
        return {}, text

    frontmatter_text = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1:])
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Invalid SKILL.md frontmatter: {exc}")
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    return frontmatter, body


# ---------------------------------------------------------------------------
# 2. Permissions
# ---------------------------------------------------------------------------
def format_permission_entry(perm: Dict[str, Any]) -> str:
    """Render a `tasks.yaml` permission object as a human-readable string.

    Kubernetes RBAC  -> ``apps: deployments, statefulsets [get]``
    AWS / Azure      -> ``lambda:ListFunctions``, ``.../read (subscription)``
    GCP              -> ``cloudfunctions.functions.get``
    PostgreSQL       -> ``role: pg_read_all_stats`` / ``EXECUTE on pg_x``
    """
    if not isinstance(perm, dict):
        return str(perm)

    api_groups = perm.get("apiGroups")
    resources = perm.get("resources")
    verbs = perm.get("verbs")
    if api_groups is not None or resources is not None or verbs is not None:
        groups = api_groups if isinstance(api_groups, list) else [api_groups]
        groups = [("core" if g == "" else str(g)) for g in groups if g is not None]
        res = resources if isinstance(resources, list) else [resources]
        res = [str(r) for r in res if r is not None]
        verb_list = verbs if isinstance(verbs, list) else [verbs]
        verb_list = [str(v) for v in verb_list if v is not None]
        group_str = ", ".join(_dedupe(groups))
        res_str = ", ".join(_dedupe(res))
        verb_str = ", ".join(_dedupe(verb_list))
        head = f"{group_str}: {res_str}" if group_str else res_str
        return f"{head} [{verb_str}]" if verb_str else head

    if perm.get("action"):
        action = str(perm["action"])
        scope = perm.get("scope")
        return f"{action} ({scope})" if scope else action

    if perm.get("permission"):
        return str(perm["permission"])

    if perm.get("role"):
        return f"role: {perm['role']}"

    if perm.get("function"):
        privilege = perm.get("privilege", "EXECUTE")
        return f"{privilege} on {perm['function']}"

    # Fallback: a stable, human-readable rendering of whatever is left.
    simple = {k: v for k, v in perm.items() if isinstance(v, (str, int, float, bool))}
    if simple and len(simple) == len(perm):
        return ", ".join(f"{k}={v}" for k, v in simple.items())
    try:
        return json.dumps(perm, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        return str(perm)


# ---------------------------------------------------------------------------
# 3. Settings + inputs -> registry user_variables
# ---------------------------------------------------------------------------
def _variable_entry(
    name: str,
    spec: Any,
    scope: str,
    task_name: Optional[str] = None,
) -> Dict[str, Any]:
    spec = spec if isinstance(spec, dict) else {}
    return {
        "name": name,
        "type": spec.get("type", "string"),
        "description": spec.get("description", "") or "",
        "default": spec.get("default"),
        "example": spec.get("example", "") or "",
        "pattern": spec.get("pattern", "") or "",
        "scope": scope,
        "task": task_name,
        "required": bool(spec.get("required", False)),
    }


def extract_variables_from_tasks_yaml(tasks_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten skill-level settings and per-task inputs/settings.

    Registry shape (matches the legacy `user_variables` JSON column):
    ``{name, type, description, default, example, pattern, scope, task, required}``
    """
    variables: List[Dict[str, Any]] = []
    if not isinstance(tasks_data, dict):
        return variables

    seen_settings = set()
    skill_settings = tasks_data.get("settings") or {}
    if isinstance(skill_settings, dict):
        for name, spec in skill_settings.items():
            variables.append(_variable_entry(str(name), spec, "setting"))
            seen_settings.add(str(name))

    for task in tasks_data.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        task_name = task.get("name")

        for name, spec in (task.get("settings") or {}).items() if isinstance(task.get("settings"), dict) else []:
            key = str(name)
            if key in seen_settings:
                continue
            variables.append(_variable_entry(key, spec, "setting", task_name))

        for name, spec in (task.get("inputs") or {}).items() if isinstance(task.get("inputs"), dict) else []:
            variables.append(_variable_entry(str(name), spec, "input", task_name))

    return variables


# ---------------------------------------------------------------------------
# 4. Data classification
# ---------------------------------------------------------------------------
def _classify_data(tags: List[str], output_keys: List[str]) -> Dict[str, Any]:
    """Summarize what data the skill's tools consume/produce.

    Mirrors the legacy `data_classifications` column:
    ``{ "data:config": {"label": ..., "count": N}, ... }``
    """
    haystack = {t.lower() for t in tags} | {k.lower() for k in output_keys}
    classifications: Dict[str, Any] = {}

    def _add(tag: str, count: int) -> None:
        classifications[tag] = {
            "label": _DATA_TAG_LABELS[tag],
            "count": max(1, count),
        }

    if haystack & {"logs", "log", "logs-regexp", "error-patterns", "stacktrace"}:
        _add("data:logs-regexp", 1)
    if haystack & {"logs-bulk", "recent-logs"}:
        _add("data:logs-bulk", 1)
    if haystack & {"stacktrace", "traceback"}:
        _add("data:logs-stacktrace", 1)
    if haystack & {"config", "configuration", "settings", "configmap", "configmaps"}:
        _add("data:config", 1)

    return classifications


# ---------------------------------------------------------------------------
# 5. Single skill
# ---------------------------------------------------------------------------
def parse_plugin_skill_directory(
    skill_dir: Path,
    plugin_slug: str,
    repo_root: Path = None,
    plugin_meta: Dict[str, Any] = None,
    integration_meta: Dict[str, Any] = None,
    git_url: str = None,
    git_ref: str = DEFAULT_GIT_REF,
) -> Optional[Dict[str, Any]]:
    """Parse one `plugins/<plugin>/skills/<skill>` directory.

    Returns a dict shaped for `Codebundle` creation/update, or None when the
    directory has neither `SKILL.md` nor `tasks.yaml`.
    """
    skill_dir = Path(skill_dir)

    skill_md_path = skill_dir / "SKILL.md"
    tasks_yaml_path = skill_dir / "tasks.yaml"
    has_skill_md = skill_md_path.exists()
    has_tasks = tasks_yaml_path.exists()
    if not has_skill_md and not has_tasks:
        return None

    skill_md_content = ""
    if has_skill_md:
        try:
            skill_md_content = skill_md_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to read {skill_md_path}: {exc}")
            skill_md_content = ""

    tasks_content = ""
    if has_tasks:
        try:
            tasks_content = tasks_yaml_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to read {tasks_yaml_path}: {exc}")
            tasks_content = ""

    return parse_plugin_skill_content(
        skill_slug=skill_dir.name,
        skill_md_content=skill_md_content,
        tasks_yaml_content=tasks_content,
        plugin_slug=plugin_slug,
        plugin_meta=plugin_meta,
        integration_meta=integration_meta,
        git_url=git_url,
        git_ref=git_ref,
    )


def parse_plugin_skill_content(
    skill_slug: str,
    skill_md_content: str,
    tasks_yaml_content: str,
    plugin_slug: str,
    plugin_meta: Dict[str, Any] = None,
    integration_meta: Dict[str, Any] = None,
    git_url: str = None,
    git_ref: str = DEFAULT_GIT_REF,
) -> Optional[Dict[str, Any]]:
    """Parse skill content already in memory (`SKILL.md` + `tasks.yaml`).

    Used by the raw-data pipeline, which stores file contents in the database
    rather than keeping a repository checkout around.
    """
    plugin_meta = plugin_meta or {}
    integration_meta = integration_meta or {}

    if not skill_md_content and not tasks_yaml_content:
        return None

    skill_dir_name = skill_slug
    frontmatter, body = parse_skill_md(skill_md_content or "")

    tasks_data: Dict[str, Any] = {}
    if tasks_yaml_content:
        try:
            loaded = yaml.safe_load(tasks_yaml_content)
            tasks_data = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Invalid tasks.yaml for {plugin_slug}/{skill_slug}: {exc}")
            tasks_data = {}

    runwhen_meta = frontmatter.get("runwhen") or {}
    if not isinstance(runwhen_meta, dict):
        runwhen_meta = {}
    applies_to = runwhen_meta.get("appliesTo") or {}
    if isinstance(applies_to, list):
        applies_to_types = [str(t) for t in applies_to]
    else:
        applies_to_types = [str(t) for t in (applies_to.get("types") or [])]
    role = runwhen_meta.get("role")
    frontmatter_tags = [str(t) for t in (runwhen_meta.get("tags") or [])]

    runtime = tasks_data.get("runtime")
    defaults = tasks_data.get("defaults") or {}
    default_timeout = defaults.get("timeout") if isinstance(defaults, dict) else None

    raw_tasks = [t for t in (tasks_data.get("tasks") or []) if isinstance(t, dict)]

    tasks: List[Dict[str, Any]] = []
    all_permissions: List[str] = []
    all_tags: List[str] = list(frontmatter_tags)
    output_keys: List[str] = []
    any_write = False

    for task in raw_tasks:
        task_name = task.get("name")
        if not task_name:
            continue
        task_tags = [str(t) for t in (task.get("tags") or [])]
        all_tags.extend(task_tags)

        outputs = task.get("outputs") or {}
        if isinstance(outputs, dict):
            output_keys.extend(str(k) for k in outputs.keys())
        if isinstance(outputs, list):
            output_keys.extend(str(o) for o in outputs)

        formatted_permissions = [
            format_permission_entry(p) for p in (task.get("permissions") or [])
        ]
        all_permissions.extend(formatted_permissions)

        read_only = task.get("readOnly", True)
        if read_only is False:
            any_write = True

        tasks.append({
            "id": f"{skill_slug}/{task_name}",
            "name": task_name,
            "title": task.get("title") or task_name,
            "doc": task.get("description", "") or "",
            "description": task.get("description", "") or "",
            "tags": task_tags,
            "readOnly": read_only,
            "destructive": bool(task.get("destructive", False)),
            "idempotent": task.get("idempotent"),
            "dryRun": bool(task.get("dryRun", False)),
            "script": task.get("script"),
            "timeout": task.get("timeout") or default_timeout,
            "effects": task.get("effects", []),
            "inputs": task.get("inputs", {}),
            "settings": task.get("settings", {}),
            "outputs": task.get("outputs", {}),
            "permissions": formatted_permissions,
        })

    # Description: SKILL.md frontmatter -> first body paragraph -> tasks.yaml
    description = frontmatter.get("description")
    if isinstance(description, list):
        description = " ".join(str(d) for d in description)
    if not description:
        description = _first_paragraph(body)
    if not description:
        description = tasks_data.get("description", "") or ""
    description = " ".join(str(description).split()) if description else ""

    support_tags = _dedupe(
        [plugin_slug]
        + frontmatter_tags
        + ([str(role)] if role else [])
        + all_tags
    )
    support_tags = [t.upper() for t in support_tags]

    platform_raw = (
        integration_meta.get("platform") if isinstance(integration_meta, dict) else None
    ) or plugin_slug
    discovery_platform = _PLATFORM_DISPLAY_NAMES.get(
        str(platform_raw).lower(), str(platform_raw)
    )

    relative_base = f"plugins/{plugin_slug}/skills/{skill_slug}"
    runbook_source_url = None
    if git_url:
        runbook_source_url = (
            f"{str(git_url).rstrip('/').removesuffix('.git')}/tree/"
            f"{git_ref}/{relative_base}"
        )

    return {
        "name": skill_slug,
        "slug": skill_slug,
        "display_name": _create_display_name(skill_dir_name),
        "description": description,
        "doc": body,
        "readme": skill_md_content,
        "author": "RunWhen",
        "support_tags": support_tags,
        "categories": [str(role)] if role else [],
        "tasks": tasks,
        "slis": [],
        "task_count": len(tasks),
        "sli_count": 0,
        "user_variables": extract_variables_from_tasks_yaml(tasks_data),
        "access_level": "read-write" if any_write else "read-only",
        "minimum_iam_requirements": _dedupe(all_permissions),
        "data_classifications": _classify_data(all_tags, output_keys),
        "has_genrules": bool(applies_to_types),
        "is_discoverable": bool(applies_to_types)
        or any(t.get("name") == "discover" for t in raw_tasks),
        "discovery_platform": discovery_platform,
        "discovery_resource_types": applies_to_types,
        "discovery_match_patterns": [
            {"type": "appliesTo", "pattern": rt} for rt in applies_to_types
        ],
        "discovery_output_items": ["tasks"],
        "discovery_level_of_detail": str(role) if role else None,
        "discovery_templates": [],
        "runbook_path": f"{relative_base}/tasks.yaml",
        "meta_path": f"{relative_base}/SKILL.md",
        "runbook_source_url": runbook_source_url,
        "ai_enhanced_description": description,
        "ai_enhanced_metadata": {
            "runtime": runtime,
            "defaults": defaults,
            "role": role,
            "applies_to": applies_to_types,
            "plugin_version": (plugin_meta or {}).get("version"),
            "integration": integration_meta or None,
        },
        "enhancement_status": "completed",
        "skill_dir": relative_base,
        "plugin_slug": plugin_slug,
    }


# ---------------------------------------------------------------------------
# 6. Whole plugin
# ---------------------------------------------------------------------------
def _safe_yaml_load(content: str) -> Dict[str, Any]:
    if not content:
        return {}
    try:
        loaded = yaml.safe_load(content)
        return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Invalid YAML: {exc}")
        return {}


def parse_plugin_from_files(
    plugin_slug: str,
    files: Dict[str, str],
    git_url: str = None,
    git_ref: str = DEFAULT_GIT_REF,
) -> Dict[str, Any]:
    """Reconstruct a plugin parse from stored `relative path -> content` files.

    The raw-data pipeline keeps file contents in `raw_repository_data` rather
    than a checkout; this builds the same structure `parse_plugin_directory`
    returns without touching disk.
    """
    prefix = f"plugins/{plugin_slug}/"
    plugin_meta = _safe_yaml_load(files.get(f"{prefix}plugin.yaml", ""))
    if not plugin_meta:
        plugin_meta = {"name": plugin_slug}
    integration_content = files.get(f"{prefix}integration/integration.yaml", "")
    integration_meta: Optional[Dict[str, Any]] = (
        _safe_yaml_load(integration_content) if integration_content else None
    )

    skill_files: Dict[str, Dict[str, str]] = {}
    pattern = re.compile(
        rf"^plugins/{re.escape(plugin_slug)}/skills/([^/]+)/(SKILL\.md|tasks\.yaml)$"
    )
    for path, content in files.items():
        match = pattern.match(path)
        if not match:
            continue
        skill_slug, filename = match.group(1), match.group(2)
        skill_files.setdefault(skill_slug, {})[filename] = content or ""

    skills: List[Dict[str, Any]] = []
    errors: List[str] = []
    for skill_slug in sorted(skill_files):
        entry = skill_files[skill_slug]
        try:
            parsed = parse_plugin_skill_content(
                skill_slug=skill_slug,
                skill_md_content=entry.get("SKILL.md", ""),
                tasks_yaml_content=entry.get("tasks.yaml", ""),
                plugin_slug=plugin_slug,
                plugin_meta=plugin_meta,
                integration_meta=integration_meta,
                git_url=git_url,
                git_ref=git_ref,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to parse skill {skill_slug}: {exc}")
            errors.append(f"{skill_slug}: {exc}")
            continue
        if parsed:
            skills.append(parsed)

    return {
        "plugin": plugin_meta,
        "integration": integration_meta,
        "plugin_slug": plugin_slug,
        "plugin_path": f"plugins/{plugin_slug}",
        "skills": skills,
        "errors": errors,
    }


def parse_plugin_directory(
    plugin_dir: Path,
    repo_root: Path = None,
    git_url: str = None,
    git_ref: str = DEFAULT_GIT_REF,
) -> Dict[str, Any]:
    """Parse `plugins/<plugin>/` into plugin metadata plus parsed skills.

    Returns::

        {
          "plugin": {name, version, description, requires, platform, ...},
          "integration": {...} | None,
          "plugin_slug": "kubernetes",
          "skills": [ {...}, ... ],
          "errors": [ "..." ],
        }
    """
    plugin_dir = Path(plugin_dir)
    repo_root = Path(repo_root) if repo_root else plugin_dir.parent.parent
    plugin_slug = plugin_dir.name

    plugin_meta = _read_yaml(plugin_dir / "plugin.yaml")
    if not plugin_meta:
        plugin_meta = {"name": plugin_slug}

    integration_path = plugin_dir / "integration" / "integration.yaml"
    integration_meta: Optional[Dict[str, Any]] = (
        _read_yaml(integration_path) if integration_path.exists() else None
    )

    skills: List[Dict[str, Any]] = []
    errors: List[str] = []

    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            try:
                parsed = parse_plugin_skill_directory(
                    skill_dir,
                    plugin_slug=plugin_slug,
                    repo_root=repo_root,
                    plugin_meta=plugin_meta,
                    integration_meta=integration_meta,
                    git_url=git_url,
                    git_ref=git_ref,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to parse skill {skill_dir}: {exc}")
                errors.append(f"{skill_dir.name}: {exc}")
                continue
            if parsed:
                skills.append(parsed)

    return {
        "plugin": plugin_meta,
        "integration": integration_meta,
        "plugin_slug": plugin_slug,
        "plugin_path": f"plugins/{plugin_slug}",
        "skills": skills,
        "errors": errors,
    }