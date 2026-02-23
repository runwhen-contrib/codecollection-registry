# Architecture

System architecture for the CodeCollection Registry v2.

## Service Overview

The registry runs as 8 Docker services coordinated by `docker-compose.yml`.

| Service | Image / Stack | Port | Role |
|---|---|---|---|
| **frontend** | React 19 + TypeScript + MUI v7 | 3000 | SPA for browsing and managing CodeBundles |
| **backend** | FastAPI + SQLAlchemy 2.0 | 8001 | REST API (`/api/v1/`), business logic, AI enhancement |
| **mcp-server** | FastAPI (separate repo: `../mcp-server`) | 8000 | Stateless MCP tool server, delegates to backend API |
| **worker** | Celery (shares backend image) | -- | Background task processing |
| **scheduler** | Celery Beat (shares backend image) | -- | Cron-driven task scheduling |
| **database** | PostgreSQL 15 + pgvector (`pgvector/pgvector:pg15`) | 5432 | Primary data store, vector extension enabled |
| **redis** | Redis 7 Alpine | 6379 | Celery broker and result backend |
| **flower** | Flower 2.0 | 5555 | Celery monitoring dashboard |

## Component Diagram

```
                   ┌──────────────────────────────────────────────┐
                   │                  Frontend                     │
                   │         React 19 + TypeScript + MUI v7        │
                   │                 :3000                         │
                   └────────────────────┬─────────────────────────┘
                                        │ HTTP (REST)
                                        ▼
┌───────────────────┐          ┌────────────────────┐          ┌─────────────────┐
│    MCP Server     │◄─────────│      Backend       │─────────►│     Worker      │
│  (stateless API)  │  HTTP    │     (FastAPI)      │  Celery  │   (Celery)      │
│     :8000         │  /tools/ │      :8001         │  tasks   │                 │
└───────────────────┘  call    └────────┬───────────┘          └────────┬────────┘
        │                               │                               │
        │ REGISTRY_API_URL              │                               │
        │ (delegates all                │                               │
        │  data queries                 │                               │
        │  back to backend)             │                               │
        └──────────────────►────────────┘                               │
                                        │                               │
                          ┌─────────────┼───────────────────────────────┘
                          │             │
                          ▼             ▼
                 ┌──────────────┐  ┌──────────┐  ┌───────────┐
                 │  PostgreSQL  │  │  Redis   │  │ Scheduler │
                 │  + pgvector  │  │  :6379   │  │ (Beat)    │
                 │    :5432     │  └──────────┘  └───────────┘
                 └──────────────┘
```

## Data Flow

### Primary data path: Registry API

All persistent data lives in PostgreSQL. The backend is the only service that talks to the database directly.

```
Frontend  ──HTTP──►  Backend  ──SQLAlchemy──►  PostgreSQL
```

### MCP Server path: Tool-based access

The MCP server is a **thin, stateless proxy**. It exposes MCP tools (find_codebundle, find_documentation, etc.) that clients can call. Every tool delegates to the backend REST API via `RegistryClient` -- the MCP server never touches the database.

```
Client  ──POST /tools/call──►  MCP Server  ──HTTP──►  Backend API  ──►  PostgreSQL
```

### Background tasks: Celery pipeline

Long-running operations (repo sync, codebundle parsing, AI enhancement, indexing) run as Celery tasks dispatched by the scheduler or triggered manually from the admin UI.

```
Scheduler (Beat)  ──dispatches──►  Redis  ──consumed by──►  Worker  ──►  PostgreSQL
```

### Document indexing path

The indexer (`mcp-server/indexer.py`) is a standalone CLI tool. It clones GitHub repos, parses codebundles and libraries, crawls documentation URLs, generates vector embeddings, and stores them in a local vector index file (`data/vector_index.json`). This index is used by the MCP server for semantic search when configured, or the MCP server can delegate to the backend API for text-based search instead.

```
Indexer  ──git clone──►  GitHub
    │
    ├── Parse codebundles (meta.yaml, *.robot, README.md)
    ├── Parse libraries (Python AST, Robot keywords)
    ├── Crawl documentation (sources.yaml URLs)
    │
    ▼
Embedding Generator  ──API──►  Azure OpenAI (text-embedding-3-small)
    │
    ▼
LocalVectorStore  ──writes──►  data/vector_index.json
```

## PostgreSQL + pgvector

The database image is `pgvector/pgvector:pg15`, which bundles the pgvector extension. On first start, `database/init/01-init.sql` enables the extension:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
```

### Core tables (managed by Alembic)

| Table | Purpose |
|---|---|
| `codecollections` | Collection metadata (name, slug, git_url, owner) |
| `codebundles` | CodeBundle details (name, slug, description, tasks, SLIs, AI metadata) |
| `tasks` | Individual task definitions extracted from codebundles |
| `metrics` | Collection-level metrics and statistics |
| `ai_enhancement_log` | AI enhancement audit trail |
| `helm_charts` | Helm chart versions and templates |
| `analytics` | Task growth metrics |
| `task_executions` | Celery task execution history |

### Vector tables (created by migration `006_add_pgvector.sql`)

| Table | Embedding dim | Purpose |
|---|---|---|
| `vector_codebundles` | 1536 | CodeBundle embeddings |
| `vector_codecollections` | 1536 | Collection embeddings |
| `vector_libraries` | 1536 | Library/keyword embeddings |
| `vector_documentation` | 1536 | Documentation page embeddings |

Each vector table uses HNSW indexes for cosine similarity search plus B-tree indexes on metadata columns.

**Current state:** The pgvector tables exist in the schema but are not yet used by the MCP server in production. The MCP server's indexer writes to a `LocalVectorStore` (in-memory numpy + JSON file). Migration to pgvector-backed search is planned.

## MCP Server Architecture

The MCP server (`../mcp-server/`) is a sibling directory, not nested inside cc-registry-v2. It is built as a separate Docker image.

### Runtime mode: Stateless API

In production, `server_http.py` runs as a FastAPI app. It registers MCP tools on startup and delegates all data access to the backend API through `RegistryClient`.

- No database connection
- No local vector store at runtime
- No embedding generation at runtime
- Pure HTTP proxy with tool-call semantics

### Indexer mode: Batch processing

`indexer.py` is a separate CLI tool that runs offline (or via Celery task). It **does** use the local vector store and embedding generator to build the search index.

### Tool categories

| Category | Tools | Data source |
|---|---|---|
| **search** | `find_codebundle`, `search_codebundles`, `find_codecollection`, `keyword_usage_help`, `find_library_info`, `find_documentation`, `check_existing_requests` | Backend API |
| **info** | `list_codebundles`, `list_codecollections`, `get_codebundle_details`, `get_development_requirements` | Backend API / local docs.yaml |
| **action** | `request_codebundle` | GitHub API |

## Celery Task System

### Task types

| Module | Key tasks |
|---|---|
| `workflow_tasks` | `sync_parse_enhance_workflow_task` -- the primary pipeline |
| `registry_tasks` | `sync_all_collections_task`, `parse_all_codebundles_task` |
| `ai_enhancement_tasks` | `enhance_pending_codebundles_task` |
| `mcp_tasks` | `index_documentation_task`, `reindex_all_task` |
| `data_population_tasks` | `update_collection_statistics_task` |
| `analytics_tasks` | `compute_task_growth_analytics` |
| `task_monitoring` | `cleanup_old_tasks_task`, `health_check_tasks_task` |

### Scheduling

All schedules are defined in `schedules.yaml` and loaded by Celery Beat. Key schedules:

| Schedule | Frequency | Task |
|---|---|---|
| `scheduled-sync` | Every 6 hours | Full sync-parse-enhance workflow |
| `index-documentation-daily` | Daily 3 AM | Re-index documentation embeddings |
| `update-statistics-hourly` | Hourly | Refresh collection statistics |
| `health-check` | Every 5 min | System health check |
| `cleanup-old-tasks` | Daily 12:30 AM | Purge old task execution records |

See [SCHEDULES.md](SCHEDULES.md) and [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) for details.

## Deployment Topology

### Local development

All 8 services run via `docker-compose.yml`. The backend and frontend mount source code as volumes for hot-reload.

### Kubernetes (production/staging)

- **Namespace:** `registry-test`
- **Database:** Zalando Postgres Operator (Spilo) with pgvector extension
- **Redis:** Sentinel mode (`redis-sentinel:26379`, master `mymaster`)
- **Images:** Pushed to `us-docker.pkg.dev/runwhen-nonprod-shared/public-images/`
- **Secrets:** Kubernetes secrets for Azure OpenAI, database credentials, Redis password

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) and [k8s/README.md](../k8s/README.md) for Kubernetes details.

## Related Documentation

- [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables and secrets
- [MCP_WORKFLOW.md](MCP_WORKFLOW.md) -- Document indexing pipeline and search flow
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) -- Automated indexing setup
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI configuration
- [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) -- Database and Redis setup
