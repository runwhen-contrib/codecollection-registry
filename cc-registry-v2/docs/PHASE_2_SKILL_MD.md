# Phase 2 — `SKILL.md` Authoring and Rendering

> **Status:** Draft outline (Phase 2 of the 2026 terminology realignment). Phase 1 (display-only cosmetic rename) is complete; this document plans the *next* phase, which adds real authoring artifacts to each Skill Template and renders them in the registry. Phase 2 is independent of Phase 1 and can be designed and scheduled separately.

## Goal

Adopt the [Anthropic Agent Skills specification](https://agentskills.io/specification) for every Skill Template (formerly "CodeBundle") in the registry. Each Skill Template gains a first-class `SKILL.md` file authored by the codebundle owner; the registry parses, stores, indexes, and renders that file as the canonical "what this Skill Template does, and when to use it" surface for both humans and LLMs.

## Why a separate phase

Phase 1 was purely a display-string rename — reversible, zero schema/API churn, low risk. Phase 2 introduces:

- A new on-disk convention in every external CodeCollection repo (`SKILL.md` per Skill Template).
- A new column (or columns) on the `codebundles` table → migration + reindex.
- Authoring tooling (LLM-assisted starter generator + spec validator).
- A material change to how the chat assistant frames Skill Template descriptions.

These are non-trivial and benefit from being scheduled, rolled out, and measured on their own cadence.

## Scope

### In scope

1. **Author convention.** Define and document the `SKILL.md` frontmatter + body contract for RunWhen Skill Templates.
2. **Parser.** Extend the sync/parse pipeline to ingest `SKILL.md` alongside `runbook.robot` and `sli.robot`.
3. **Storage.** Add a column for the SKILL.md raw markdown plus a parsed metadata blob.
4. **Indexing.** Include SKILL.md content in vector embeddings so semantic search hits real authored intent (not just auto-generated descriptions).
5. **UI rendering.** Display the SKILL.md body on the Skill Template detail page as the primary descriptive content (above the Tools tabs).
6. **MCP integration.** Return SKILL.md content via `get_codebundle_details` and bias `find_codebundle` toward SKILL.md-rich Skill Templates when relevant.
7. **Authoring tooling.** Optional LLM-assisted generator that reads `meta.yaml` + Robot docstrings and proposes a starter `SKILL.md`; spec validator that runs at indexing time and at PR-CI time.

### Out of scope (for Phase 2)

- Renaming MCP tool function names (`find_codebundle` → `find_skill_template`). Still deferred to a future phase.
- Renaming API paths or DB columns. Still deferred.
- Source-repo folder convention changes (`codebundles/` → `skill-templates/` on disk). Still deferred.
- Renaming "CodeCollection" itself. Not planned.

## Author convention

Each `codebundles/{slug}/SKILL.md` follows the Anthropic Agent Skills spec, adapted for RunWhen:

```markdown
---
name: Azure App Service Health
description: |
  Triage an Azure App Service Web App when it's slow, returning 5xx, or failing health probes.
  Covers App Service Plan capacity, web app config, application logs, and dependent resources.
allowed-tools:
  - RW.CLI
  - RW.K8s
platform: azure
support-tags: [azure, appservice, webapp]
when-to-use: |
  Use when an Azure App Service Web App reports degraded performance or errors AND you have
  Reader access to the resource group containing the app and its plan.
when-not-to-use: |
  Don't use for Function Apps or Container Apps — those have dedicated Skill Templates.
---

# Azure App Service Health

## What this Skill Template does

This Skill Template provides Tools for…

## Runbooks

- **App Service Plan Health** — checks CPU/memory pressure and scale events on the underlying Plan.
- **Web App Configuration Audit** — flags risky settings (HTTPS-only off, missing slot settings, expired certs).
- …

## Monitors

- **App Service 5xx Rate** — emits a 0-1 health value based on the percentage of 5xx responses over a 10-minute window.

## Required user variables

- `RESOURCE_GROUP_NAME` — the Azure Resource Group containing the app.
- `WEB_APP_NAME` — the Web App's name.

## Required secrets

- `azure-credentials`

## Notes

…
```

Decisions to lock down during Phase 2 design:

| Question | Default | Alternatives |
|---|---|---|
| Frontmatter format | YAML | TOML (Anthropic uses YAML — stay aligned) |
| `name` value relationship to `meta.yaml` `name` | Must match | Could allow override (probably no) |
| Required vs optional sections | `name`, `description`, `when-to-use` required; rest optional | All-optional (weaker contract) |
| Markdown flavor | CommonMark + GitHub tables | Strict CommonMark only |
| Image embedding | Relative paths to repo files | Disallowed (text-only) |
| Max body length | 16 KB suggested, hard cap 64 KB | No cap |

## Schema changes

```sql
ALTER TABLE codebundles
  ADD COLUMN skill_md_content TEXT,           -- raw markdown body (without frontmatter)
  ADD COLUMN skill_md_frontmatter JSONB,      -- parsed YAML frontmatter
  ADD COLUMN skill_md_present BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN skill_md_validation_errors JSONB; -- spec-validator findings, NULL if clean
```

Plus a vector table column or sub-document for the embedded skill body.

Migration plan:

1. Alembic migration adds the columns with defaults.
2. Backfill is non-blocking: Skill Templates without `SKILL.md` keep their existing auto-generated description as the rendering fallback.
3. No data loss / rollback risk — pure additive change.

## Parser changes

`backend/app/tasks/registry_tasks.py` (the parse step in the sync→parse→enhance→embed pipeline) gains:

1. Detect `SKILL.md` in `codebundles/{slug}/SKILL.md`.
2. Split frontmatter (YAML between `---` fences) from body.
3. Validate frontmatter against a Pydantic `SkillFrontmatter` model.
4. Persist `skill_md_content`, `skill_md_frontmatter`, `skill_md_present`, `skill_md_validation_errors`.
5. Emit a structured log line per Skill Template summarizing parse outcome (used by the dashboards described below).

## Indexing changes

Vector embedding pipeline (`backend/app/tasks/indexing_tasks.py`):

1. When building the embedded text for a Skill Template, prepend the SKILL.md `description` + `when-to-use` + the first ~1.5 KB of body if `skill_md_present` is true.
2. Re-embed any Skill Template whose `skill_md_content` changes (use a content hash to detect drift).
3. Optionally store a second, SKILL.md-only embedding so `find_codebundle` can be biased toward intent matches.

## UI rendering

`CodeBundleDetail.tsx` gains a top section:

- If `skill_md_present` is `true` and no validation errors → render the SKILL.md body via the existing Markdown renderer, above the Tools tabs.
- If validation errors exist → render the body anyway but show a non-blocking warning ("This Skill Template's SKILL.md has 3 validation warnings"). The warning is admin-visible only on the public site.
- If `skill_md_present` is `false` → keep the current auto-generated description as today (no regression).

Search/list pages get a small badge ("Skill" or a green checkmark icon) on Skill Templates that ship a real `SKILL.md`, so users can spot first-class authored Skill Templates.

## MCP integration

- `get_codebundle_details` returns a new `skill_md` field with the parsed content + frontmatter.
- `find_codebundle` and `search_codebundles` rerank to prefer Skill Templates with valid SKILL.md content, breaking ties in favor of authored intent.
- The chat system prompt is amended: "If a Skill Template has a SKILL.md `when-to-use` block, use that to decide whether to recommend it."

## Authoring tooling

### LLM-assisted starter generator

CLI command (lives in `codecollection-devtools` or `cc-registry-v2/scripts/`):

```bash
generate-skill-md codebundles/azure-appservice-webapp-ops/
```

Reads `meta.yaml`, `runbook.robot`, `sli.robot`, and `README.md` (if any), then calls Azure OpenAI to draft a starter `SKILL.md` matching the spec. The output is **a draft**, never committed automatically — authors review and refine before checking in.

### Spec validator

`scripts/validate-skill-md.py` (runs in PR-CI for each codecollection repo, and at indexing time on the server):

- Parses frontmatter, checks required fields.
- Lints body for: required H2 sections, max length, no absolute image URLs unless allow-listed.
- Emits non-zero exit code only on hard errors (missing required field, malformed YAML). Warnings (over-length section, missing recommended section) are surfaced but don't block.

## Rollout plan

| Step | Owner | Gate |
|---|---|---|
| 1. Finalize the SKILL.md contract (frontmatter schema, required sections) | Registry team | Design review |
| 2. Land Alembic migration + parser + indexer changes (server-side, gated by feature flag `SKILL_MD_INGEST_ENABLED`) | Registry team | Migration deploys cleanly to nonprod |
| 3. Ship UI rendering behind a frontend flag | Registry team | UAT on nonprod |
| 4. Pilot: author SKILL.md for **5 high-traffic Skill Templates** (Kubernetes, Azure App Service, AWS EKS, Postgres, GCP Cloud Run) | CodeCollection owners | Author sign-off on pilot pages |
| 5. Enable flags in prod | Registry team + ops | Manual approval |
| 6. Backfill remaining Skill Templates with LLM-assisted starter drafts; owners review and merge | Distributed (per repo) | Tracked via a public dashboard "% of Skill Templates with SKILL.md" |
| 7. Once coverage > 80%, the chat assistant starts preferring SKILL.md `when-to-use` over auto-generated descriptions | Registry team | Coverage threshold met |

## Success metrics

- **Coverage:** % of active Skill Templates with a valid SKILL.md.
- **Search quality:** A/B compare `find_codebundle` precision before vs. after SKILL.md is included in embeddings.
- **Chat quality:** Chat-Debug "thumbs up" rate on responses that cite SKILL.md-equipped Skill Templates.
- **Authoring effort:** Median time from "generate starter" to "merged" per Skill Template (rough sense of friction).

## Open questions

1. Should `SKILL.md` live at `codebundles/{slug}/SKILL.md` (alongside `runbook.robot`) or at the CodeCollection level (`SKILL.md` per repo)? Default: per Skill Template — matches Anthropic's per-skill granularity.
2. What does `allowed-tools` mean operationally? Just metadata, or do we enforce that the Skill Template only uses the listed RW libraries at runtime?
3. Do we expose a public "SKILL.md only" mode of the registry where each Skill Template is rendered as a portable Anthropic-spec skill package (zip with `SKILL.md` + supporting files) for direct download into Claude? Probably yes — fits the broader "Skill Template" framing.
4. How do we handle multi-language Skill Templates (Robot + Python helper)? The SKILL.md `allowed-tools` enumerates RW libraries, but `tools` in the Anthropic spec usually maps to MCP tools. Need a glossary in the contract.

---

This Phase 2 plan is intentionally lighter than Phase 1 because the heavy semantic work — defining the new vocabulary — is already done. Phase 2 is about *operationalizing* the vocabulary by putting authored skill artifacts inside each Skill Template and surfacing them everywhere the registry communicates with users and agents.
