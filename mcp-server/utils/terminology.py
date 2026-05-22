"""Display-label helpers for MCP server output text.

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
    - A **Skill** is the runtime instantiation of a Skill Template inside
      a workspace, with vars/secrets materialised against real infra.
      The registry only stores Skill Templates; Skills only exist at
      runtime in a workspace. "Skill" is used colloquially as an umbrella
      term in user-facing copy (e.g. "All Skills" page titles).

The MCP server consumes the registry's REST API and renders markdown for
LLM consumers. The REST API still returns ``type: "TaskSet" | "SLI" |
"CodeBundle"`` verbatim; this module is what translates those values to
their new display labels in returned markdown.
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
    # inside a workspace). Used colloquially as an umbrella term in page titles.
    "SKILL": {"singular": "Skill", "plural": "Skills"},
    "CODECOLLECTION": {"singular": "CodeCollection", "plural": "CodeCollections"},
    "SLI": {"singular": "Monitor", "plural": "Monitors"},
    "TASKSET": {"singular": "Runbook", "plural": "Runbooks"},
}


def label_for_type(type_value: str, plural: bool = False) -> str:
    """Resolve a display label for an internal ``type`` value.

    Returns the raw input unchanged if the type is unknown, so debugging
    unexpected enum values stays straightforward.
    """
    if type_value in TYPE_LABELS:
        return TYPE_LABELS[type_value]["plural" if plural else "singular"]
    return type_value


def label_with_count(type_value: str, count: int) -> str:
    """Return a count-friendly label like ``"Runbook (3)"``.

    Pluralises automatically when ``count`` is not 1.
    """
    label = label_for_type(type_value, plural=count != 1)
    return f"{label} ({count})"
