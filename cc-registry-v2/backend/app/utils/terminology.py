"""Display-label helpers for backend response copy.

Phase 1 of the cosmetic naming convention realignment (2026) renames the
user-facing surface to align with industry-standard automation + agentic
vocabulary, while leaving every internal identifier (DB columns, JSON
``type`` enum values, MCP tool function names, API paths, class names)
byte-identical to the previous schema.

Mapping (internal -> display):
    Task        -> Tool
    CodeBundle  -> Skill
    SLI         -> Monitor    (scheduled, continuous, numeric output)
    TaskSet     -> Runbook    (on-demand, event-triggered, findings)
    CodeCollection -> Plugin

Lifecycle distinction:
    - A **Skill** is the registry-side, parameterised package (formerly
      "CodeBundle"). Vars and secrets are unresolved placeholders.
    - A **Plugin** groups Skills with their platform integration (resource
      types, facets, credentials) and is backed by a git repository
      (formerly "CodeCollection").

The backend continues to emit ``type: "TaskSet" | "SLI" | "CodeBundle"`` on
``/api/v1/registry/tasks`` for backward compatibility. This module is used
where the backend itself composes human-readable text (chat replies,
OpenAPI descriptions, prompt context blocks) and needs to render the new
display vocabulary.
"""

from typing import Literal

InternalType = Literal["TaskSet", "SLI", "CodeBundle"]

TYPE_LABELS: dict[str, dict[str, str]] = {
    "TaskSet": {"singular": "Runbook", "plural": "Runbooks"},
    "SLI": {"singular": "Monitor", "plural": "Monitors"},
    "CodeBundle": {"singular": "Skill", "plural": "Skills"},
}

CONCEPTS: dict[str, dict[str, str]] = {
    "TASK": {"singular": "Tool", "plural": "Tools"},
    "CODEBUNDLE": {"singular": "Skill", "plural": "Skills"},
    # Runtime instantiation of a Skill inside a workspace.
    "SKILL": {"singular": "Skill", "plural": "Skills"},
    "CODECOLLECTION": {"singular": "Plugin", "plural": "Plugins"},
    "SLI": {"singular": "Monitor", "plural": "Monitors"},
    "TASKSET": {"singular": "Runbook", "plural": "Runbooks"},
}

VOCABULARY_BLOCK = """\
RunWhen registry vocabulary (2026):
- Tool: an invocable unit (formerly "Task").
- Skill: a reusable, parameterised package of Tools that lives in a
  Plugin in the registry (formerly "CodeBundle"). Has placeholder vars and
  unresolved secrets.
- Plugin: a git-repo-level grouping of Skills and their platform
  integration (formerly "CodeCollection").
- Monitor: a Tool that runs on a schedule, continuously, in the background
  and emits a numeric 0-1 health value (formerly "SLI").
- Runbook: a Tool that runs on demand in response to an event or request
  and emits structured findings with next-steps (formerly "TaskSet").

Users may use either vocabulary interchangeably. Internal JSON `type`
values returned by the API remain "TaskSet", "SLI", and "CodeBundle" for
backward compatibility with existing integrations.
"""


def label_for_type(type_value: str, plural: bool = False) -> str:
    """Resolve a display label for an internal ``type`` value."""
    if type_value in TYPE_LABELS:
        return TYPE_LABELS[type_value]["plural" if plural else "singular"]
    return type_value


def label_with_count(type_value: str, count: int) -> str:
    """Return a count-friendly label like ``"Runbook (3)"``."""
    label = label_for_type(type_value, plural=count != 1)
    return f"{label} ({count})"
