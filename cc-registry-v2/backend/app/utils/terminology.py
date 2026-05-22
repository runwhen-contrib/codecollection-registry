"""Display-label helpers for backend response copy.

Phase 1 of the cosmetic naming convention realignment (2026) renames the
user-facing surface to align with industry-standard automation + agentic
vocabulary, while leaving every internal identifier (DB columns, JSON
``type`` enum values, MCP tool function names, API paths, class names)
byte-identical to the previous schema.

Mapping (internal -> display):
    Task        -> Tool
    CodeBundle  -> Skill Template
    SLI         -> Monitor    (scheduled, continuous, numeric output)
    TaskSet     -> Runbook    (on-demand, event-triggered, findings)

Lifecycle distinction:
    - A **Skill Template** is the registry-side, parameterised package
      (formerly "CodeBundle"). Vars and secrets are unresolved placeholders.
    - A **Skill** is the runtime instantiation of a Skill Template inside a
      workspace, with vars/secrets materialised against real infrastructure.
      The registry itself never holds Skills - only Skill Templates - but
      the umbrella word "Skill" is used colloquially in user-facing page
      titles and chat copy (e.g. "All Skills") because it reads naturally
      and aligns with industry usage (Anthropic Agent Skills, etc.).

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
    "CodeBundle": {"singular": "Skill Template", "plural": "Skill Templates"},
}

CONCEPTS: dict[str, dict[str, str]] = {
    "TASK": {"singular": "Tool", "plural": "Tools"},
    "CODEBUNDLE": {"singular": "Skill Template", "plural": "Skill Templates"},
    # Runtime instantiation of a Skill Template (vars/secrets materialised
    # inside a workspace). The registry itself only stores Skill Templates,
    # but "Skill" is the umbrella word used in user-facing page titles.
    "SKILL": {"singular": "Skill", "plural": "Skills"},
    "CODECOLLECTION": {"singular": "CodeCollection", "plural": "CodeCollections"},
    "SLI": {"singular": "Monitor", "plural": "Monitors"},
    "TASKSET": {"singular": "Runbook", "plural": "Runbooks"},
}

VOCABULARY_BLOCK = """\
RunWhen registry vocabulary (2026):
- Tool: an invocable unit (formerly "Task").
- Skill Template: a reusable, parameterised package of Tools that lives
  in the registry (formerly "CodeBundle"). Has placeholder vars and
  unresolved secrets.
- Skill: the RUNTIME instantiation of a Skill Template inside a workspace,
  with vars/secrets materialised against real infrastructure. The registry
  itself only stores Skill Templates; Skills only exist at runtime in a
  workspace. The umbrella word "Skill" is used colloquially in page titles
  and chat copy (e.g. "All Skills").
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
