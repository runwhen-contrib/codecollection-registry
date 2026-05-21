# cc-catalog-svc — Architecture

This document explains *why* the service is shaped the way it is. For
operator how-tos, see the per-plugin docs (e.g.
[JFROG.md](JFROG.md), [GIT_MIRROR.md](GIT_MIRROR.md)) and the
top-level [README.md](../README.md).

---

## Goals & non-goals

### Goals

1. **PAPI-compatible catalog API** — drop-in replacement for
   `cc-registry-v2/backend/app/routers/cc_catalog.py` so PAPI can be
   re-pointed at this service without code changes.
2. **Self-contained** — one container, one process. No Celery + Redis
   to deploy or babysit. Default storage is a single SQLite file.
3. **Destination plugin system** — same plugin shape as the existing
   `ImageSource` system, but for *publishing* mirrored images. v1
   ships JFrog Artifactory; ECR/GAR/Harbor are drop-ins.
4. **Additive** — the existing registry's image-catalog features stay
   exactly as they are. No deletions, no behavior changes on the
   `ccv/image-catalog` branch.

### Non-goals

- Replacing the registry website or its MCP server. They run alongside;
  this service is just the slim catalog half.
- Building images. The catalog reads what each CC repo's GitHub Actions
  already pushed — same as `cc-registry-v2`.
- Multi-tenant or per-customer scoping inside one instance. Run one
  instance per environment / customer. Each is small and cheap.

---

## End-to-end shape

```
   sources                  catalog (this svc)             destinations
  ┌───────────┐            ┌────────────────────┐         ┌──────────────┐
  │ ghcr.io   │──poll──►   │ SQLite (default)   │         │ JFrog        │
  │ (oci)     │            │ /api/v1/catalog/*  │──mirror─►│ Artifactory │
  └───────────┘            │   (PAPI contract)  │         │              │
                           │ /api/v1/mirror/*   │         └──────────────┘
  ┌───────────┐            └────────────────────┘
  │ another   │──poll──►          ▲
  │ catalog   │                   │  APScheduler in-process:
  │ (upstream)│                   │    catalog-poll
  └───────────┘                   │    mirror-enqueue
                                  │    mirror-drain
  ┌───────────┐                   │
  │ static    │──read──►          │
  │ (json)    │                   │
  └───────────┘                   │
                                  ▼
                            PAPI / debug consumers
```

The three scheduler loops:

| Loop | Cadence | What it does |
|---|---|---|
| `catalog-poll` | `cfg.scheduler.catalog_poll_minutes` (default 5m) | For each configured CC, ask its source for refs; upsert `codecollections` + `image_refs` rows. |
| `mirror-enqueue` | `cfg.scheduler.mirror_poll_minutes` (default 5m) | For each `(cc, destination)` pair, compute the set of refs not yet mirrored and create `mirror_jobs` rows. Skips refs already in `mirror_targets` or with a non-terminal job. |
| `mirror-drain` | `cfg.scheduler.mirror_poll_minutes` (offset by 30s) | Pull pending `mirror_jobs`, run each through `destination.push()` in a thread pool. Successful jobs upsert `mirror_targets`; failures retry up to `max_attempts` then sit in `failed` for an operator to inspect. |

All three loops are idempotent and safe to run concurrently with reads.

---

## Why no Celery + Redis?

`cc-registry-v2` uses Celery + Redis because it runs ~10 distinct task
families (analytics, AI enhancement, indexing, registry sync, image
sync, etc.) with different cadences, retry semantics, and a UI for
monitoring them.

This service has **three** task functions, all owned by one team, all
sharing the same DB. APScheduler in-process is the right tool:

- One container, one Pod, one binary to ship.
- The task functions are pure Python and architecture-agnostic — moving
  them to Celery later is a 50-line change if HA ever becomes a
  requirement.
- No external broker to provision, secure, or back up.

### HA (when you need it)

Two patterns are supported without code changes:

1. **Active-passive**: two replicas of this Deployment; the second is a
   warm standby. Acceptable for most environments because the catalog
   is read-mostly and the scheduler tasks tolerate a few minutes of
   missed runs.
2. **Split**: 1 scheduler pod (`CC_CATALOG_DISABLE_SCHEDULER` unset) +
   N API pods (`CC_CATALOG_DISABLE_SCHEDULER=1`) behind a Service. All
   pods share a Postgres DB (set `CC_CATALOG_DB_URL=postgresql+psycopg2://...`).

Going beyond that (HA scheduler, leader election) lands you in the same
infra zone as the registry — at which point Celery + Redis is the right
answer and we'd graduate this code there.

---

## Source plugins

Same contract as `cc-registry-v2/backend/app/sources/`. Subclasses
implement three methods:

```python
class ImageSource(ABC):
    name: str
    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]: ...
    def resolve_latest(self, cc, refs) -> str | None: ...
    def resolve_stable(self, cc, refs) -> str | None: ...
```

Built-ins:

| Plugin | Where it reads from |
|---|---|
| `oci` | OCI Distribution v2 (`/v2/<repo>/tags/list`). Handles the anonymous-bearer dance. |
| `static` | A JSON file (see `app/sources/static.py` docstring). |
| `upstream` | Another catalog's `/api/v1/catalog/codecollections/{slug}/refs`. |

The `oci` source parses tags with the same regex the registry uses:

```
^(?P<ref>.+?)-(?P<cc_sha>[0-9a-f]{7,40})-(?P<rt_sha>[0-9a-f]{7,40})$
```

Tags that don't match are silently ignored — that's deliberate, so
`latest` / `main` / `<date>` tags coexist on the registry without
confusing the catalog.

---

## Destination plugins

New contract, deliberately three methods:

```python
class ImageDestination(ABC):
    name: str

    def target_ref(self, dest_cfg, cc, image_tag) -> str: ...
    def exists(self, dest_cfg, target_ref) -> bool: ...
    def push(self, dest_cfg, source_ref, target_ref, *, timeout=600) -> MirrorResult: ...
```

The base class ships a default `push()` that wraps `crane copy <src>
<dst>`. Most destinations only need to provide auth via `crane_env()`
and never touch `push()` itself.

`exists()` is what keeps the mirror engine idempotent — the engine
calls it before every push and skips the copy if the destination
already has the tag. This composes cleanly with manual operator
workflows: an operator who pushes one image by hand doesn't trigger
an endless push loop.

### Why `crane`?

`crane` is a small static Go binary (~10 MB) from
google/go-containerregistry. It's the de-facto OCI copy tool, handles
multi-arch manifest lists correctly, supports digest-preserving copies,
and reads auth from the standard `DOCKER_CONFIG` env var. Pure-Python
alternatives exist (`oras-py`) but each has its own auth and multi-arch
edge cases — pinning crane is the lowest-cost path.

The Dockerfile pins a specific crane release in a multi-stage build so
the final image carries one binary, no `curl`/`ca-certificates` churn.

---

## Data model

Five tables, all narrow:

```
codecollections      one row per tracked CC
image_refs           one row per discovered image (ccv-shaped)
destinations         one row per configured destination
mirror_targets       one row per successfully mirrored (cc, dest, tag)
mirror_jobs          one row per pending/running/done/failed copy
```

`image_refs` mirrors the column shape of
`cc-registry-v2`'s `CodeCollectionVersion`. We don't reuse that model
class because we don't want a hard runtime dependency on the registry
package — but anyone who's read the registry's catalog code will find
this familiar.

### Schema bootstrap

We use `Base.metadata.create_all` rather than Alembic for v1. The
schema is small and single-writer; an Alembic chain is overhead with no
payoff at this size. When schema evolution becomes a thing we'll add
Alembic — the migration is mechanical.

---

## API contract

All catalog endpoints have the same path shape and response model as the
registry's `cc-registry-v2/backend/app/routers/cc_catalog.py`. The only
addition is the `?destination=<name>` query param on `/resolve`, which
is the seam PAPI uses in air-gapped envs:

```bash
# Public env: PAPI gets the source ref, same as today.
curl ".../catalog/codecollections/rw-cli-codecollection/resolve?pointer=latest"

# Air-gapped env: PAPI asks for the destination ref of the same image.
curl ".../catalog/codecollections/rw-cli-codecollection/resolve?pointer=latest&destination=acme-jfrog"
```

When the destination hasn't mirrored the requested ref yet, the
response still carries the source ref but with `destination=<name>` and
`target_image_ref=null`. Callers can fall back to the source ref or
wait for the next mirror cycle.

---

## Security model

- **Catalog read endpoints**: unauthenticated by design. Matches the
  registry's PAPI contract; if you need auth, front it with an ingress.
- **Admin POST endpoints**: bearer-token, constant-time compare. Set
  `CC_CATALOG_ADMIN_TOKEN`. Leaving it unset returns 503 for those
  routes — the service runs in read-only mode.
- **Destination credentials**: never in `config.yaml`. Plugins reference
  *env var names* (`auth.token_env: JFROG_ACCESS_TOKEN`); the values
  come from a Secret. The DB persists the env var name, never the token.
- **Image trust**: the catalog inherits whatever trust model the source
  registry has. If you need image signing or attestation enforcement,
  do it at pull time in the consumer (PAPI / runner). The catalog does
  not gate on signatures.

---

## What this service does *not* do

- It does not build images. CC repo GitHub Actions own that.
- It does not push to source registries. It only **mirrors** from a
  source to a configured destination.
- It does not index codebundles, run AI enhancement, or talk to MCP.
  Those live in `cc-registry-v2/` and stay there.
