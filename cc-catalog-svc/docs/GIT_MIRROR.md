# cc-catalog-svc — Git mirror hosting

`cc-catalog-svc` can host read-only git mirrors of every
CodeCollection's source repo and serve them over Smart HTTP. The
intended use-case is air-gapped deployments where the RunWhen platform
needs to `git clone` / `git fetch` CC code but the platform pods don't
have outbound access to github.com.

Quick links:

* Example config — [`config-examples/config.airgap.yaml`](../config-examples/config.airgap.yaml)
* Bake manifest — [`config-examples/config.bake.yaml`](../config-examples/config.bake.yaml)
* Source — [`app/git_http/server.py`](../app/git_http/server.py), [`app/services/git_mirror.py`](../app/services/git_mirror.py)

---

## End-to-end shape

```
  CI build (has internet)                  air-gap pod (no internet)
  ────────────────────────                  ───────────────────────────
   bake_git_mirrors.py                       /opt/cc-catalog/git/
     ⬇  git clone --mirror                     ├── rw-cli-codecollection.git/
   /opt/cc-catalog/git/*.git    ─── COPY ──►   ├── rw-public-codecollection.git/
                                                └── …
                                              ▲
                                              │   git http-backend (per request)
                                              │
                              cc-catalog-svc  │   FastAPI
                              ──────────────  │   /git/<slug>.git/info/refs
                                              │   /git/<slug>.git/git-upload-pack
                                              │
   platform pod (taskiq-worker, gitget)  ─────┘
   GET / POST /git/<slug>.git/...
```

Two life-cycle phases:

1. **Build-time bake** (CI). `scripts/bake_git_mirrors.py` clones every
   repo listed in `config.bake.yaml` into `/opt/cc-catalog/git/` inside
   the image. Lives outside `/data` so a PVC mount can't hide it.
2. **Runtime serve** (any cluster). When `git.enabled: true`,
   `cc-catalog-svc` mounts a WSGI app on `git.mount_path` (default
   `/git`) that delegates each request to the native `git http-backend`
   CGI binary against `git.data_dir`.

The catalog API rewrites `git_url` on every CC response to
`git.public_base_url/<slug>.git` whenever a local bare repo exists, so
platform consumers don't need to know about the rewrite at all.

---

## Configuration

```yaml
git:
  enabled: true                                       # off by default
  data_dir: /opt/cc-catalog/git                       # default; matches Dockerfile bake
  mount_path: /git                                    # default
  public_base_url: https://cc-catalog.example.com/git # required for git_url rewrite
  runtime_sync: false                                 # true = fetch on schedule; false = air-gap
  codecollections: []                                 # empty = every CC with a git_url
  auth:                                               # optional — for private upstreams
    token_env: GITHUB_TOKEN                           # OR user_env + pass_env
  clone_timeout_seconds: 900
  fetch_timeout_seconds: 600
```

| Field | Default | Notes |
|-------|---------|-------|
| `enabled` | `false` | Master switch. When false, no `/git` mount, no rewrite, no scheduler job. |
| `data_dir` | `/opt/cc-catalog/git` | Matches the release image's bake target. Override to a writable path on a PVC when `runtime_sync: true` and you want fetched objects to survive pod restarts. |
| `mount_path` | `/git` | FastAPI mount prefix. Clone URL becomes `public_base_url + /<slug>.git`. |
| `public_base_url` | `null` | Required for `git_url` rewrite. Omit to keep upstream URLs in catalog responses even while serving mirrors locally (useful for staged migrations). |
| `runtime_sync` | `true` | When false, the scheduler and the admin endpoint refuse to reach upstream. Use this for air-gap deployments whose mirrors are baked at build time. |
| `codecollections` | `[]` | Allow-list. Empty = every CC with a `git_url`. |
| `auth` | `{}` | Bearer token (`token_env`) or HTTP Basic (`user_env` + `pass_env`). Values are env var **names**, not the secrets themselves. |

`scheduler.git_sync_minutes` (top-level scheduler block) controls how
often runtime sync runs; ignored when `runtime_sync: false`.

---

## Deployment scenarios

### Connected cluster (default)

* `git.enabled: true`
* `git.runtime_sync: true`
* `git.data_dir: /data/git` (on the PVC so fetches persist)
* Image baking is not required — the first scheduler tick clones every
  configured repo.

### Air-gapped cluster (no outbound git)

* Build the release image with `BAKE_GIT_MIRRORS=true` and a
  `config.bake.yaml` listing every CC slug + git_url to bake.
* Deploy with the
  [`config.airgap.yaml`](../config-examples/config.airgap.yaml) shape:
  * `git.enabled: true`
  * `git.runtime_sync: false`
  * `git.data_dir: /opt/cc-catalog/git` (default)
* No PVC mount is required for `/data/git`; the bake stage writes
  outside `/data`.

### Mixed (mostly air-gap, occasional refresh)

If an operator needs to refresh the baked mirrors from upstream after
deploy (e.g. you forgot a CC in the bake manifest), the admin endpoint
exposes an explicit override:

```bash
# Default — refuses, because runtime_sync is false:
curl -X POST -H "Authorization: Bearer $ADMIN" \
     https://cc-catalog/api/v1/admin/sync-git
# → { "skipped": "runtime_sync disabled ..." }

# With the explicit override flag:
curl -X POST -H "Authorization: Bearer $ADMIN" \
     'https://cc-catalog/api/v1/admin/sync-git?allow_runtime_sync=true'
```

The override is intentionally opt-in so a stray click in an
air-gapped console can't egress to github.com.

---

## Build-time bake

The Dockerfile has a dedicated `git-bake` stage:

```dockerfile
ARG BAKE_GIT_MIRRORS=true
ARG BAKE_CONFIG=config-examples/config.bake.yaml
RUN --mount=type=secret,id=github_token \
    python scripts/bake_git_mirrors.py \
      --config "${BAKE_CONFIG}" \
      --dest /opt/cc-catalog/git
```

The runtime stage `COPY --from=git-bake /opt/cc-catalog/git
/opt/cc-catalog/git` to land the bare repos in the final image.

The bake script:

* Reads `git_url` from every CodeCollection in the manifest. Unlike
  `repos_to_sync`, it does **not** require `git.enabled: true` — the
  bake manifest exists solely to list URLs.
* Fetches via `git clone --mirror`, optionally with a `GITHUB_TOKEN`
  secret for private repos.
* Exits non-zero if any repo fails to clone, so CI fails loudly rather
  than shipping an image with partial mirrors.

---

## Security model

Smart HTTP is **read-only by design**:

* `git http-backend` is invoked with `GIT_HTTP_EXPORT_ALL=1` and no
  `http.receivepack` enabled, so push (`git-receive-pack`) is rejected
  at the CGI layer.
* The WSGI router only accepts these paths:
  ```
  /<slug>.git/info/refs
  /<slug>.git/git-upload-pack
  /<slug>.git/HEAD
  ```
  Anything else returns 404 without spawning the CGI process.
* Slugs are validated against `^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$`
  before being joined onto `data_dir`. Path traversal (`../etc`,
  `foo/bar`, etc.) is rejected outright.
* The WSGI app is parameterised with `allowed_slugs` derived from
  `repos_to_sync(cfg)`. Stale or operator-staged `*.git` directories
  under `data_dir` that aren't in the config are 404, not served.

The service does not do per-client authentication on `/git`. Front it
with an ingress that enforces network ACLs or mTLS if you need access
control — the same way the catalog API itself is protected.

---

## Operational notes

### Concurrency

`run_git_sync` holds a process-wide `threading.Lock` for the entire
run. The scheduler and the admin endpoint both go through this code
path, so they cannot race on the same on-disk bare repo. A second
sync that arrives while the first is still running returns
`{"skipped": "another git sync is already running"}` instead of
queueing.

### Idempotency

`sync_one_repo` is safe to call repeatedly:

* If `<data_dir>/<slug>.git` exists but has no `HEAD` / `objects/`
  (interrupted clone), the directory is removed and a fresh clone is
  attempted. Without this, every subsequent run would `git remote
  update` the junked directory forever.
* If the configured upstream URL changes (operator edited
  `config.yaml`), `origin` is reset via `git remote set-url` before
  the next fetch. Without this, mirrors would silently keep pulling
  from the old upstream.
* On success the DB row's `git_head_commit`, `git_last_synced`, and
  `git_last_sync_error` are updated. On failure only
  `git_last_sync_error` is touched, so the operator sees the failure
  without losing the previous good HEAD.

### Status visibility

```
GET /api/v1/git/repos
[
  {
    "slug": "rw-cli-codecollection",
    "upstream_url": "https://github.com/runwhen-contrib/rw-cli-codecollection",
    "public_url": "https://cc-catalog.example.com/git/rw-cli-codecollection.git",
    "present": true,
    "head_commit": "e2f76a4...",
    "last_synced": "2026-05-21T16:10:01",
    "last_sync_error": null
  },
  ...
]
```

`head_commit` is populated from the DB on every successful runtime
sync. For build-time baked mirrors (`runtime_sync: false`), the
service runs `populate_baked_head_commits` at startup so the field
is non-null even before any runtime sync has fired — operators can
trust it.

### Streaming

`git http-backend` writes its CGI response to a pipe that we forward
to the WSGI `write()` callback in 64 KiB chunks. We never buffer the
full packfile in memory, so cloning a large CC mirror does not spike
the uvicorn worker's RSS or block other API traffic.

### Database upgrade

The `git_head_commit`, `git_last_synced`, and `git_last_sync_error`
columns were added after the initial release. `init_db` issues
idempotent `ALTER TABLE … ADD COLUMN` statements at startup so
already-deployed databases pick up the new columns without an Alembic
migration. The mechanism lives in
[`app/db.py`](../app/db.py) (`_LEGACY_COLUMN_ADDITIONS`) — add to that
dict for any future columns until we adopt Alembic.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `git clone http://…/git/<slug>.git` → 404 | Slug not in `allowed_slugs`. Either missing from `config.yaml`'s sources, or filtered out by `git.codecollections`. | Add the slug to a source, or to the explicit `git.codecollections` allow-list. Restart the pod. |
| `git clone` → `transfer closed with outstanding read data remaining` | Almost always a proxy / ingress timeout, not the service. Check that your ingress allows long-running HTTP responses (some default to 30s; `git fetch` of a large repo can need longer). | Bump ingress `proxy-read-timeout` / `proxy-send-timeout` to e.g. 600s. |
| `GET /api/v1/git/repos` shows `present: false` | The `<slug>.git` directory doesn't exist under `data_dir`. | Confirm `git.data_dir` matches where mirrors were baked (`/opt/cc-catalog/git` for release images). For runtime sync, hit `/api/v1/admin/sync-git` and check the response. |
| `POST /admin/sync-git` returns `{"skipped":"runtime_sync disabled …"}` | Air-gap guard rail. | Re-issue with `?allow_runtime_sync=true` if you really want to reach upstream. |
| Logs show `git http-backend exited rc=…` | Most often a permissions issue on the bare repo or a malformed slug. The full stderr is captured at WARN level. | Check `ls -la <data_dir>/<slug>.git`; ensure the `catalog` user owns it. |
