# JFrog Artifactory — operator guide

The `jfrog` destination plugin mirrors CodeCollection images from the
catalog's configured sources (typically GHCR) into a JFrog Artifactory
Docker repository.

This doc covers the JFrog-side prerequisites, the catalog-side config,
and the failure modes you'll most often see.

---

## What you get

For each tracked CodeCollection ref that matches the destination's
`mirror:` filter, the engine produces an image at:

```
<artifactory-host>/<repo_key>/<path_prefix>/<cc_slug>:<source_image_tag>
```

e.g. with `base_url: https://acme.jfrog.io`, `repo_key:
runwhen-virtual`, `path_prefix: codecollections`:

```
acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-c1a2b3d-e4f5a6b
```

The tag is preserved verbatim from the source so PAPI's existing
ref-resolution logic still works (the only thing that changes is the
host prefix).

---

## Prerequisites in Artifactory

1. **A Docker repository.** Local or virtual; the plugin treats them
   the same.
   - Recommended: a *virtual* Docker repo that aggregates a local Docker
     repo (where we push) and any other Docker repos the same team
     consumes. The catalog config points at the virtual repo's
     `repo_key`; the underlying push lands in the local. That keeps a
     single pull URL for downstream consumers.
2. **An access token** with `read,write` scope on the target repo.
   Generate via Artifactory → *User Profile → Generate Access Token*
   (or the platform's identity provider). Save it as a Kubernetes Secret
   value.
3. **(Optional)** **JFrog Xray** indexing enabled on the repo if you
   plan to set `enable_xray_scan: true`. The catalog only kicks the
   scan trigger; Xray itself does the indexing.

---

## Catalog config

In `config.yaml`:

```yaml
destinations:
  - name: acme-jfrog
    type: jfrog
    base_url: https://acme.jfrog.io
    repo_key: runwhen-virtual          # must exist in Artifactory
    path_prefix: codecollections       # optional
    auth:
      token_env: JFROG_ACCESS_TOKEN    # env var that holds the bearer token

    enable_xray_scan: false            # opt-in; see below

    mirror:
      codecollections: ["*"]           # or explicit slug list
      include_pointers: [latest, stable]
      include_branches: [main]
      include_semver_tags: true
      include_pr_refs: false
```

Then provide the token via env:

```bash
# Local dev
export JFROG_ACCESS_TOKEN=eyJ...

# K8s
kubectl -n cc-catalog-svc create secret generic cc-catalog-svc-secrets \
    --from-literal=JFROG_ACCESS_TOKEN='eyJ...' \
    --from-literal=CC_CATALOG_ADMIN_TOKEN="admin-$(openssl rand -hex 16)"
```

The deployment's `envFrom: secretRef` already wires this in.

---

## Auth: two patterns

| Pattern | Set in `auth:` | When to use |
|---|---|---|
| **Bearer access token** | `token_env: JFROG_ACCESS_TOKEN` | Default. Smallest setup. The plugin synthesizes a temporary `DOCKER_CONFIG` per push so the token never lands on argv or in any persistent file. |
| **External docker config** | `docker_config_env: JFROG_DOCKER_CONFIG` (pointing at a path) | You already have a Docker `config.json` produced by an external tool (Vault, JFrog CLI, etc.) and want to reuse it. |

Token wins if both are set.

---

## Triggering a sync

The scheduler does this automatically every
`cfg.scheduler.mirror_poll_minutes` (default 5 min). For an immediate
sync after changing config:

```bash
# Force a full catalog poll first (refreshes refs from sources)
curl -X POST -H "Authorization: Bearer $CC_CATALOG_ADMIN_TOKEN" \
     https://catalog.example.com/api/v1/admin/sync-catalog

# Enqueue mirror jobs for this destination
curl -X POST -H "Authorization: Bearer $CC_CATALOG_ADMIN_TOKEN" \
     https://catalog.example.com/api/v1/mirror/destinations/acme-jfrog/sync

# Drain immediately (otherwise the scheduler's drain loop picks up jobs
# on its next interval)
curl -X POST -H "Authorization: Bearer $CC_CATALOG_ADMIN_TOKEN" \
     https://catalog.example.com/api/v1/mirror/drain
```

---

## Inspecting state

```bash
# Per-destination summary (last sync, error, mirrored tag count)
curl https://catalog.example.com/api/v1/mirror/destinations

# Pending or failed jobs
curl 'https://catalog.example.com/api/v1/mirror/jobs?status=pending&destination=acme-jfrog'
curl 'https://catalog.example.com/api/v1/mirror/jobs?status=failed&destination=acme-jfrog'

# Full detail (includes log_text — the crane stdout/stderr tail)
curl https://catalog.example.com/api/v1/mirror/jobs/42

# What PAPI gets when it asks for the JFrog-mirrored ref
curl 'https://catalog.example.com/api/v1/catalog/codecollections/rw-cli-codecollection/resolve?pointer=latest&destination=acme-jfrog'
```

---

## Xray scan trigger (optional)

Set `enable_xray_scan: true` on a destination and after every successful
push the plugin POSTs to:

```
{base_url}/xray/api/v1/scanArtifact
{ "componentID": "docker://<repo_key>/<path>/<tag>/manifest.json" }
```

Failures here are logged but never fail the mirror — Xray scan
registration is eventually-consistent and a slow scan trigger should
not gate the catalog's own success accounting.

---

## Failure modes

### Job fails with `crane copy exited 1` and `unauthorized`

The access token doesn't have push permission on `repo_key`. Re-check
the token's scope in Artifactory's *User Management → Access Tokens*.
The catalog short-circuits early on `exists()`-time 401/403 with a
`PermissionError`, so this specific symptom usually means the read
worked but the push didn't (e.g. read-only scope).

### Every job is `failed` after 3 attempts

Three knobs to check:
1. `JFROG_ACCESS_TOKEN` actually populated in the running container
   (`kubectl exec ... -- env | grep JFROG`).
2. `base_url` host actually resolves and is reachable from the pod
   (`kubectl exec ... -- python -c "import httpx; print(httpx.head('https://acme.jfrog.io/artifactory/api/system/ping').status_code)"`).
3. The image hasn't been pulled at all — try
   `crane manifest ghcr.io/runwhen-contrib/rw-cli-codecollection:<tag>`
   inside the pod to confirm the source is reachable too.

### `target_image_ref` is null but the job succeeded

Check `last_error` is null on `/api/v1/mirror/destinations` — if so,
the `MirrorTarget` row is missing for some reason (rare, but possible
if a manual cleanup wiped it). Re-trigger the sync; the next pass will
recreate the row from the existing destination tag via the `exists()`
shortcut.

### `enable_xray_scan: true` but no scans show up

The plugin POST succeeds (200) but Xray hasn't indexed the artifact
yet. Wait a few minutes and re-check. Persistent failure usually means
the token doesn't have Xray scope; check `last_error` in the job's log
tail for an `[xray scan trigger failed: ...]` annotation.

---

## Hardening

- Put the catalog behind an ingress that enforces auth on POST routes,
  even though `CC_CATALOG_ADMIN_TOKEN` is sufficient for v1.
- Rotate `JFROG_ACCESS_TOKEN` on a schedule. The plugin re-reads env on
  every push, so a rolling Secret rotation followed by a pod restart is
  enough — no config edit required.
- Run a JFrog identity scoped to *only* the target Docker repo, not the
  whole instance. The catalog never needs other repos.
