# CCV Catalog (CodeCollection Versions)

The **CCV catalog** is the read-only mirror of every published image tag for
every tracked CodeCollection. PAPI calls into it on the workspace-reconcile
path to translate a logical reference like `rw-cli-codecollection@main` or
`rw-cli-codecollection@stable` into a concrete, pullable OCI image tag. This
document covers everything you need to:

- Add a new CodeCollection to the catalog
- Understand the contract a CC's build pipeline must honor
- Query the catalog over HTTP
- Diagnose why a CC is showing zero refs or stale pointers

If you just need a one-screen summary, skip to [TL;DR](#tldr).

---

## TL;DR

```
                ┌──────────────────────────────┐
   per-repo CI  │ codecollection build-push.yaml│ → pushes  ghcr.io/.../<repo>:<ref>-<cc_sha7>-<rt_sha7>
                └──────────────────────────────┘
                              │
                              ▼  (every 5 min — Celery beat)
                ┌──────────────────────────────┐
  cc-registry-v2│ sync_image_tags_task          │ → ImageSource.discover_refs(cc)
                │ (per CC in codecollections.yaml)│   resolve_latest / resolve_stable
                └──────────────────────────────┘
                              │
                              ▼
                ┌──────────────────────────────┐
                │ codecollection_versions (DB) │ ← one row per discovered image tag
                └──────────────────────────────┘
                              │
                              ▼  read-only, no auth
                ┌──────────────────────────────┐
            PAPI│ GET /api/v1/catalog/...      │
                └──────────────────────────────┘
```

The catalog **does not build images** and **does not push tags**. Codecollection
repos own their builds (via their own `.github/workflows/build-push.yaml`); the
catalog polls each repo's registry every 5 minutes and mirrors what it finds.

---

## Registering a CodeCollection

Catalog membership is declared in [`codecollections.yaml`](../../codecollections.yaml)
at the repo root.

### Minimal entry (catalog-tracked)

```yaml
- name: My CodeCollection
  slug: my-codecollection
  git_url: https://github.com/runwhen-contrib/my-codecollection
  owner: RunWhen
  owner_icon: https://.../icon.svg
  owner_email: you@example.com
  description: Short blurb
  image_source: oci                                              # turn on tracking
  image_registry: ghcr.io/runwhen-contrib/my-codecollection      # OCI repo path
```

Omit `image_source` to keep the CC indexed by the website but skip image
catalog polling — useful for CCs that don't yet have a build workflow.

### All optional fields the image catalog honors

| Field | Default | Effect |
|---|---|---|
| `image_source` | _(unset)_ | Which plugin drives discovery: `oci`, `static`, or a name registered via `CC_REGISTRY_EXTRA_SOURCES`. If unset, the CC is skipped on every poll. |
| `image_registry` | _(required for `oci`)_ | The OCI repo path the `oci` source lists tags from (e.g. `ghcr.io/runwhen-contrib/rw-cli-codecollection`). No scheme, no trailing slash. |
| `default_ref` | `main` | Git ref whose newest build is considered `latest`. |
| `static_path` | _(required for `static`)_ | Filesystem path to a JSON file with refs (see [Sources → static](#static)). |
| `visibility` | `public` | `public` (default) or `hidden`. Hidden CCs are still catalogued for PAPI but excluded from website / MCP / AI search surfaces. **OCI ACLs remain the source of truth for who can pull the image.** This is a UX toggle, not a security boundary. |

---

## The tag-schema contract

The default `oci` source parses tags with this regex:

```
^(?P<ref>.+?)-(?P<cc_sha>[0-9a-f]{7,40})-(?P<rt_sha>[0-9a-f]{7,40})$
```

Translated to English: every tag must end in two hex SHA groups (7-40 chars
each) separated by hyphens, and everything before those is the git ref.

| Tag | Parsed `ref` | Parsed `cc_sha` | Parsed `rt_sha` |
|---|---|---|---|
| `main-c1a2b3d-e4f5a6b` | `main` | `c1a2b3d` | `e4f5a6b` |
| `pr-42-9988aab-e4f5a6b` | `pr-42` | `9988aab` | `e4f5a6b` |
| `v1.2.0-aabbccd-e4f5a6b` | `v1.2.0` | `aabbccd` | `e4f5a6b` |
| `latest` | _(rejected)_ | _(rejected)_ | _(rejected)_ |
| `main-only` | _(rejected — missing rt_sha)_ |

**`cc_sha`** is the codecollection commit. **`rt_sha`** is the
`rw-base-runtime` commit that was baked in at build time. The dual-sha shape
is what lets the catalog reason about which runtime + which CC produced a
given image without manifest introspection.

Tags that don't match the regex are silently ignored. That's a feature, not a
bug — it lets `:latest` and other floating tags coexist on the registry
without confusing the catalog. The trade-off is that **misconfigured
pipelines produce zero parsed refs**, which the catalog reports but cannot
auto-recover from. See [troubleshooting](#troubleshooting).

### Pointers

After tags are parsed, two pointers are resolved per CC:

- **`latest`** — newest build whose `ref` equals `default_ref` (defaults to
  `main`). "Newest" is by `built_at` from the OCI manifest when available, or
  lexicographic tag order otherwise (the dual-sha suffix makes this
  monotonic in practice).
- **`stable`** — highest semver-looking `ref` (`v?\d+\.\d+(\.\d+)?...`). Falls
  back to `latest` if no semver tag exists.

---

## API reference

Base path: `/api/v1/catalog`. All endpoints are GET-only and unauthenticated.
Responses are JSON. Pretty-print is up to the caller.

> **Interactive Swagger UI:** `https://<host>/api/docs` (e.g.
> `https://registry-test.shared.runwhen.com/api/docs`). The OpenAPI JSON
> schema lives at `/api/openapi.json` and the hand-written YAML mirror at
> `/api/openapi.yaml`. Note the `/api/` prefix — the frontend SPA owns `/`
> at the public hostname, so the backend's docs UI is intentionally mounted
> under `/api/`.

### `GET /codecollections`

List every tracked CC plus its currently-resolved pointers.

| Query param | Default | Meaning |
|---|---|---|
| `visibility` | _(none)_ | Filter to `public` or `hidden`. Omit to see all. |
| `only_with_image` | `true` | Skip CCs that have no parsed image tags yet. Set `false` to see opted-in CCs that haven't built anything. |

```bash
curl https://registry.runwhen.com/api/v1/catalog/codecollections | jq '.[0]'
```

```json
{
  "slug": "rw-cli-codecollection",
  "name": "RunWhen CLI CodeCollection",
  "git_url": "https://github.com/runwhen-contrib/rw-cli-codecollection",
  "visibility": "public",
  "latest_image_tag": "main-c1a2b3d-e4f5a6b",
  "stable_image_tag": "v1.2.0-aabbccd-e4f5a6b",
  "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
  "last_synced": "2026-05-12T14:55:03Z"
}
```

### `GET /codecollections/{slug}`

Same as above but includes the full list of known refs in `.refs[]`.

### `GET /codecollections/{slug}/refs`

Just the refs for one CC. Add `?include_inactive=true` to see refs that
were tracked previously but have since disappeared from the registry.

```bash
curl https://registry.runwhen.com/api/v1/catalog/codecollections/rw-cli-codecollection/refs | jq '.[] | .ref' | sort -u
```

### `GET /codecollections/{slug}/refs/{ref}`

Look up a single ref by name (branch or tag). Returns 404 if the ref isn't
tracked or has no image.

### `GET /codecollections/{slug}/resolve`

The endpoint PAPI hits on the workspace-reconcile path. Pass **exactly one**
of `pointer` or `ref`:

```bash
# Named pointer
curl 'https://registry.runwhen.com/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?pointer=latest'

# Specific git ref
curl 'https://registry.runwhen.com/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?ref=v1.2.0'
```

Response:

```json
{
  "slug": "rw-cli-codecollection",
  "requested": "latest",
  "image_tag": "main-c1a2b3d-e4f5a6b",
  "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
  "image_digest": null,
  "commit_hash": "c1a2b3def123...",
  "rt_revision": "e4f5a6b789..."
}
```

The full pull reference for the workspace's runner is
`{image_registry}:{image_tag}` (or `{image_registry}@{image_digest}` once
digest pinning rolls in).

### Visibility filter

`/codecollections` and `/codecollections/{slug}` **intentionally bypass** the
`visibility = 'public'` filter that protects the registry website. PAPI
needs to resolve images for hidden CCs (workspaces use them), so it sees
the full list. The website / MCP / AI search go through different routers
(`versions.py`, `cc.py`, etc.) which apply `public_only()`.

---

## Sources

Each `image_source` is a plugin under
[`backend/app/sources/`](../backend/app/sources/) implementing
`ImageSource.discover_refs / resolve_latest / resolve_stable`. Built-ins:

### `oci`

Walks the OCI Distribution v2 `/v2/<repo>/tags/list` endpoint with
`Link`-header pagination. Handles the anonymous-bearer-token dance for GHCR
and Docker Hub. No auth secrets required — the catalog only reads public
listings.

Configure with `image_registry: <host>/<path>`.

### `static`

Reads refs from a checked-in JSON file. Use for:
- Customer self-hosted catalogs where image discovery happens in the
  customer's own pipeline and lands as a committed file
- Test fixtures
- Pinning a CC to a known-good ref set without polling a registry

Configure with `image_source: static` + `static_path: /path/to/refs.json`.
JSON shape is documented inline in
[`sources/static.py`](../backend/app/sources/static.py).

### Custom (third-party) sources

Set the env var `CC_REGISTRY_EXTRA_SOURCES` to a colon-separated list of
import paths. Each module must expose a top-level `SOURCE` of type
`ImageSource`. Useful for self-hosted Harbor / internal registries with
non-standard tag schemas, without forking the catalog.

```bash
CC_REGISTRY_EXTRA_SOURCES=mycorp.harbor_source:mycorp.gerrit_source
```

---

## Sync schedule

The Celery beat schedule lives in
[`cc-registry-v2/schedules.yaml`](../schedules.yaml). The relevant entry:

```yaml
- name: sync-image-tags
  task: app.tasks.image_sync_tasks.sync_image_tags_task
  description: "Poll OCI registries for each CC and refresh the image catalog"
  schedule_type: interval
  interval:
    minutes: 5
  enabled: true
```

The task is idempotent (one HTTP listing per CC, upsert by `(cc_id, version_name)`)
and fast (the slow leg is the network call, capped at a 10s read timeout per
CC). A CC that errors does not block the others — errors are logged and
included in the task's return summary.

### Manually triggering a sync

**Over HTTP** (requires the admin bearer token — any value starting with
`admin-` per `verify_admin_token`):

```bash
curl -X POST \
  -H "Authorization: Bearer admin-<your-token>" \
  https://registry-test.shared.runwhen.com/api/v1/tasks/sync-image-tags
```

Response is a Celery task id you can poll at
`GET /api/v1/tasks/status/{task_id}`.

**From inside the backend container** (no auth needed):

```bash
docker compose exec backend python -c "from app.tasks.image_sync_tasks import sync_image_tags_task; print(sync_image_tags_task.delay())"
```

**From the admin UI:** Admin → Tasks → "Sync Image Tags" (same endpoint
under the hood).

Use the HTTP path when the 5-minute beat schedule is too slow, or when
debugging why `/api/v1/catalog` is missing image data after a fresh
deploy.

---

## Operational tools

### `scripts/dry_run_oci_sources.py` — offline catalog validation

Exercises the real source plugins against every CC in `codecollections.yaml`
without touching the database, Celery, or FastAPI. Useful for:

- Pre-flight check before flipping a new CC's `image_source` to `oci`
- Catching tag-schema regressions (a pipeline emitting `<ref>-<cc_sha>`
  with no `rt_sha` would show up as zero parsed refs)
- Separating transient registry flakiness from real misconfiguration

```bash
cd cc-registry-v2/backend
python scripts/dry_run_oci_sources.py            # full pre-flight
python scripts/dry_run_oci_sources.py --only rw-cli-codecollection -v
python scripts/dry_run_oci_sources.py --source oci -q
```

Exit codes:
- `0` — every configured CC discovered ≥1 ref
- `1` — one or more sources raised (network / auth / parse error)
- `2` — one or more sources returned 0 refs (likely a tag-schema mismatch)

The non-zero exit codes are designed so you can drop this into a CI job
later. See the script's module docstring for the full CLI.

---

## Troubleshooting

### A CC shows 0 refs in the catalog

Most likely the build pipeline isn't producing tags that match the
`<ref>-<cc_sha7>-<rt_sha7>` regex. Verify:

```bash
# Public GHCR repos do not require auth for tag listing
curl -s https://ghcr.io/v2/runwhen-contrib/<repo>/tags/list?n=50 | jq .tags
```

If the tags look like `latest`, `main`, `2026-05-12`, or `sha-<7chars>`,
they will not match. The build workflow has to emit catalog-shaped tags
on top of (or instead of) those. See the
[`rw-cli-codecollection/.github/workflows/build-push.yaml`](https://github.com/runwhen-contrib/rw-cli-codecollection/blob/main/.github/workflows/build-push.yaml)
template; the `prepare` job computes `tags:` with the canonical schema.

The dry-run script will surface this case explicitly with exit code 2.

### `latest_image_tag` is null but refs exist

The CC has builds, but none of them are on `default_ref`. Run:

```bash
curl https://registry.runwhen.com/api/v1/catalog/codecollections/<slug>/refs | jq '[.[].ref] | unique'
```

If you only see `pr-*` or feature-branch refs, no PR has merged to `main`
yet. Once it does, the next sync (≤ 5 min) will populate `latest`.

### `stable_image_tag` equals `latest_image_tag`

That's by design — `stable` falls back to `latest` when no semver-looking
ref (`v1.2.3`, etc.) exists for the CC. Tag a release on the codecollection
repo to populate `stable` independently.

### Transient `ReadTimeout` against a registry

The default per-CC timeout is 10s. GHCR occasionally goes slow on a
specific repo for ~30s at a time; the next sync picks up where this one
left off. If you see persistent timeouts, raise it via `OCISource(timeout=...)`
in `app/sources/registry.py`.

### "Unknown image_source" errors

A typo in `codecollections.yaml` or an `image_source: my-custom` that
isn't registered. Check the `SOURCE_REGISTRY` in
[`backend/app/sources/registry.py`](../backend/app/sources/registry.py)
and `CC_REGISTRY_EXTRA_SOURCES` env if you're plugging in a custom one.

---

## How PAPI consumes the catalog

PAPI does not run a registry of its own. On the workspace-reconcile path
it makes one HTTP call per used CC:

```
GET /api/v1/catalog/codecollections/<slug>/resolve?pointer=<latest|stable>
```

…and rewrites the workspace's container manifest to use `{image_registry}:{image_tag}`
returned by that call. Workspaces that pin to a specific git ref instead
of a pointer go through `?ref=<git_ref>`.

This is the radically-simple replacement for the previous
`corestate-operator` flow that ran inside each remote cluster:

| Before | After |
|---|---|
| `corestate-operator` per cluster | one HTTP read per workspace reconcile |
| CRDs in remote clusters | none (zero remote install footprint) |
| build-manager polls & pushes to registry | each CC repo owns its build via GitHub Actions |
| custom image-listing service | OCI Distribution v2 (vendor standard) |

See the [radically-simple design doc](/docs/migration/radically-simple-design.md)
in `platform-robot-runtime` for the full rationale.

---

## Related docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — services, data flow, DB schema
- [`CONFIGURATION.md`](CONFIGURATION.md) — environment variables for the
  backend container
- [`SCHEDULES.md`](SCHEDULES.md) — Celery beat schedule semantics
- [`../backend/app/sources/oci.py`](../backend/app/sources/oci.py) —
  reference implementation of the tag parser
- [`../backend/scripts/dry_run_oci_sources.py`](../backend/scripts/dry_run_oci_sources.py)
  — offline catalog validation
