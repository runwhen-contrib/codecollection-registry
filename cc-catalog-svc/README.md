# cc-catalog-svc

> Self-contained CodeCollection image catalog + mirror microservice.
> PAPI-compatible catalog API. Pluggable sources. Pluggable destinations
> (JFrog Artifactory ships in v1).

This is a **sibling** to `cc-registry-v2/` — not a replacement. The
existing image-catalog features in `cc-registry-v2/backend/app/sources/`
and `cc-registry-v2/backend/app/routers/cc_catalog.py` stay exactly
where they are.

What this service adds:

- A **standalone** PAPI-compatible catalog API you can deploy without
  pulling in the registry website's frontend, MCP server, Celery, Redis,
  Postgres, or AI dependencies. One container, one process.
- A **destination plugin system** so the same catalog that discovers
  images on GHCR can also mirror them into a customer-private registry.
  JFrog Artifactory is the v1 destination.
- A new **upstream source** plugin that can ride on another catalog's
  `/api/v1/catalog/*` API instead of polling OCI directly — useful for
  self-hosted instances that want to point at RunWhen's public catalog.

If you just need a one-screen overview, read [TL;DR](#tldr) below.

---

## TL;DR

```
   sources                  catalog (this svc)             destinations
  ┌───────────┐            ┌────────────────────┐         ┌──────────────┐
  │ ghcr.io   │──poll──►   │ SQLite (default)   │         │ JFrog        │
  │ (oci)     │            │ /api/v1/catalog/*  │──mirror─►│ Artifactory │
  └───────────┘            │   (PAPI contract)  │         │   (Docker    │
                           │ /api/v1/mirror/*   │         │    repo)     │
  ┌───────────┐            └────────────────────┘         └──────────────┘
  │ another   │──poll──►          ▲
  │ catalog   │                   │
  │ (upstream)│                   │ APScheduler in-process
  └───────────┘                   │  catalog-poll        every N min
                                  │  mirror-enqueue      every N min
  ┌───────────┐                   │  mirror-drain        every N min
  │ static    │──read──►          │
  │ (json)    │                   │
  └───────────┘                   │
                                 PAPI / debug consumers
```

- Catalog API is **identical in shape** to
  `cc-registry-v2/backend/app/routers/cc_catalog.py`. PAPI can be
  pointed at either service.
- Mirror engine shells out to `crane` (Google's go-containerregistry CLI)
  for OCI-compliant image copy. Pinned in the Dockerfile.
- No Celery, no Redis. APScheduler runs the three loops in the FastAPI
  process via the lifespan. Single container.

---

## Run it

### Docker Compose (local)

```bash
cp config-examples/config.example.yaml config.yaml
docker compose up --build
curl http://localhost:8080/api/v1/catalog/codecollections
curl http://localhost:8080/api/docs           # Swagger
```

Set `JFROG_ACCESS_TOKEN` in `.env` (or via the shell) to exercise the
mirror engine against a real Artifactory.

### Kubernetes

```bash
# Edit k8s/configmap.yaml (sources + destinations) and replace the
# example secret with a real one (SealedSecret / ExternalSecret).
kubectl apply -k k8s/
```

The deployment runs a single replica because the scheduler runs
in-process. For HA, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#ha).

---

## Configuration

Two layers:

| Where | Holds | Why |
|---|---|---|
| **Env vars** (`CC_CATALOG_*`) | DB URL, log level, admin token, port | Per-deployment knobs, rotate without rebuilding configmaps |
| **`config.yaml`** | sources, destinations, schedule intervals | Structured/list-shaped config that benefits from PR review |

See [config-examples/config.example.yaml](config-examples/config.example.yaml)
for the full schema with comments.

| Env var | Default | Purpose |
|---|---|---|
| `CC_CATALOG_CONFIG_FILE` | `config.yaml` | YAML file path |
| `CC_CATALOG_DB_URL` | `sqlite:///./data/catalog.db` | SQLAlchemy URL |
| `CC_CATALOG_HOST` | `0.0.0.0` | Listen address |
| `CC_CATALOG_PORT` | `8080` | Listen port |
| `CC_CATALOG_LOG_LEVEL` | `INFO` | stdlib log level |
| `CC_CATALOG_ADMIN_TOKEN` | _(unset)_ | Bearer for admin POST endpoints. Empty disables them. |
| `CC_CATALOG_DISABLE_SCHEDULER` | _(unset)_ | Set to `1` to run as API-only (no in-process scheduler) |
| `CC_CATALOG_EXTRA_SOURCES` | _(unset)_ | `:`-separated import paths for custom source plugins |
| `CC_CATALOG_EXTRA_DESTINATIONS` | _(unset)_ | `:`-separated import paths for custom destination plugins |

---

## API

Catalog (read-only, no auth — matches the existing
`cc-registry-v2/backend/app/routers/cc_catalog.py` shape):

| Method | Path |
|---|---|
| GET | `/api/v1/catalog/codecollections` |
| GET | `/api/v1/catalog/codecollections/{slug}` |
| GET | `/api/v1/catalog/codecollections/{slug}/refs` |
| GET | `/api/v1/catalog/codecollections/{slug}/refs/{ref}` |
| GET | `/api/v1/catalog/codecollections/{slug}/resolve?pointer=latest\|stable` |
| GET | `/api/v1/catalog/codecollections/{slug}/resolve?ref=<git_ref>` |
| GET | `/api/v1/catalog/codecollections/{slug}/resolve?...&destination=<name>` |

Mirror (read endpoints are anon; writes require `CC_CATALOG_ADMIN_TOKEN`):

| Method | Path |
|---|---|
| GET | `/api/v1/mirror/destinations` |
| GET | `/api/v1/mirror/jobs?status=&destination=&cc_slug=` |
| GET | `/api/v1/mirror/jobs/{id}` |
| POST | `/api/v1/mirror/destinations/{name}/sync` (admin) |
| POST | `/api/v1/mirror/destinations/{name}/codecollections/{slug}/sync` (admin) |
| POST | `/api/v1/mirror/drain` (admin) |

Admin (writes):

| Method | Path |
|---|---|
| POST | `/api/v1/admin/reload-config` |
| POST | `/api/v1/admin/sync-catalog` |

Health:

| Method | Path |
|---|---|
| GET | `/healthz` (liveness) |
| GET | `/readyz` (readiness — DB ping) |
| — | Swagger UI at `/api/docs`, ReDoc at `/api/redoc` |

The `?destination=<name>` query param on `/resolve` is the additive
hook PAPI uses in air-gapped envs: omit it and you get the source ref
exactly as before; include it and the response includes
`target_image_ref` for the mirrored copy on that destination.

---

## Sources

`config.yaml` `sources:` is a list of source instances. Each instance
binds a `type` (plugin) to a list of CodeCollections.

| Plugin | Use for | Reads from |
|---|---|---|
| `oci` | Anything OCI-compliant (GHCR, GAR, ECR, Quay, Harbor, Artifactory) | OCI Distribution v2 |
| `static` | Air-gap, tests, pinning | A JSON file (see `app/sources/static.py`) |
| `upstream` | Ride on another catalog instance | Another catalog's `/api/v1/catalog/*` |

Custom plugins drop in via `CC_CATALOG_EXTRA_SOURCES`. Contract is in
[`app/sources/base.py`](app/sources/base.py).

---

## Destinations

`config.yaml` `destinations:` is a list of destination instances. Each
instance binds a `type` (plugin) plus its plugin-specific config plus a
`mirror:` block describing which refs of which CCs to push.

| Plugin | Notes |
|---|---|
| `jfrog` | JFrog Artifactory Docker repos. Auth via access token or docker config file. Optional Xray scan trigger after push. See [docs/JFROG.md](docs/JFROG.md). |

Add a destination by writing a class that satisfies `ImageDestination`
([`app/destinations/base.py`](app/destinations/base.py)) and registering
it via `CC_CATALOG_EXTRA_DESTINATIONS=mycorp.dst_ecr`. The default
`push()` calls `crane copy` — most destinations only need to provide
auth via `crane_env()` and never touch `push()` itself.

---

## Development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -v                  # 38 tests, no infra required
ruff check app tests       # lint
black --check app tests    # format check
```

Tests stub the source/destination plugins so they run without crane,
without network, without Postgres.

---

## Related docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — design rationale, HA, schema
- [docs/JFROG.md](docs/JFROG.md) — JFrog destination operator guide
- [docs/PAPI_INTEGRATION.md](docs/PAPI_INTEGRATION.md) — how PAPI consumes the catalog and the `?destination=` extension
- `cc-registry-v2/docs/CCV.md` — the contract this service is compatible with (in the sibling project)
