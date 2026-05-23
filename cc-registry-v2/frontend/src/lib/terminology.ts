/**
 * Centralised display-label map for the codecollection registry.
 *
 * Phase 1 of the cosmetic naming convention realignment (2026) renames the
 * user-facing surface to align with industry-standard automation + agentic
 * vocabulary, while leaving every internal identifier (DB columns, JSON
 * `type` enum values, MCP tool function names, API paths, class names)
 * byte-identical to the previous schema.
 *
 * Mapping (internal -> display):
 *   - Task         -> Tool
 *   - CodeBundle   -> Skill Template
 *   - SLI          -> Monitor       (scheduled, continuous, numeric output)
 *   - TaskSet      -> Runbook       (on-demand, event-triggered, findings)
 *   - CodeCollection (unchanged)
 *
 * Lifecycle distinction:
 *   - A **Skill Template** is the registry-side, parameterised package
 *     (formerly "CodeBundle"). Vars and secrets are unresolved placeholders.
 *   - A **Skill** is the runtime instantiation of a Skill Template inside a
 *     workspace, with vars/secrets materialised against real infrastructure.
 *     The registry itself never holds Skills — only Skill Templates — but the
 *     umbrella word "Skill" is used colloquially in user-facing page titles
 *     (e.g. "All Skills") because it reads naturally and aligns with
 *     industry usage (Anthropic Agent Skills, OpenAI tools, etc.).
 *
 * This module is the SINGLE source of truth for those display labels. Any
 * new user-facing string that references one of the renamed concepts must
 * either import a label from here or be added to this file.
 */

export type InternalType = "TaskSet" | "SLI" | "CodeBundle";

interface LabelPair {
  singular: string;
  plural: string;
}

/**
 * Display labels keyed by the JSON `type` enum value that the backend emits
 * on `/api/v1/registry/tasks` and friends. The backend still returns
 * `"TaskSet"`, `"SLI"`, or `"CodeBundle"` verbatim; the UI translates here.
 */
export const TYPE_LABELS: Record<InternalType, LabelPair> = {
  TaskSet: { singular: "Runbook", plural: "Runbooks" },
  SLI: { singular: "Monitor", plural: "Monitors" },
  CodeBundle: { singular: "Skill Template", plural: "Skill Templates" },
} as const;

/**
 * Higher-level concept labels used in page titles, navigation, and prose.
 * These are referenced directly by components instead of hard-coding
 * "Tasks"/"CodeBundles" string literals.
 */
export const CONCEPTS = {
  TASK: { singular: "Tool", plural: "Tools" },
  CODEBUNDLE: { singular: "Skill Template", plural: "Skill Templates" },
  // Runtime instantiation of a Skill Template (vars/secrets materialised
  // inside a workspace). The registry itself only stores Skill Templates,
  // but "Skill" is the umbrella word used in user-facing page titles.
  SKILL: { singular: "Skill", plural: "Skills" },
  CODECOLLECTION: { singular: "CodeCollection", plural: "CodeCollections" },
  SLI: { singular: "Monitor", plural: "Monitors" },
  TASKSET: { singular: "Runbook", plural: "Runbooks" },
} as const;

/**
 * Resolve the display label for a given internal `type` value. Returns the
 * raw input if the type is unknown so unexpected values stay debuggable
 * rather than rendering blank.
 */
export const labelForType = (type: InternalType | string, plural = false): string => {
  if (type in TYPE_LABELS) {
    return TYPE_LABELS[type as InternalType][plural ? "plural" : "singular"];
  }
  return type;
};

/**
 * Convenience helper that returns the label as a count-friendly string like
 * "Runbook (3)" or "Monitors (12)". Pluralises automatically when count != 1.
 */
export const labelWithCount = (type: InternalType | string, count: number): string => {
  const label = labelForType(type, count !== 1);
  return `${label} (${count})`;
};
