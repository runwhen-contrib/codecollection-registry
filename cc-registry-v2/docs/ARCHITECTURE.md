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

## Production Data Flows

These are the flows that run in production today.

### 1. Data ingestion: Sync-Parse-Enhance pipeline

The **backend Celery worker** is responsible for populating the database. The `sync_parse_enhance_workflow_task` runs every 6 hours and is the primary ingestion path:

```
Celery Beat dispatches scheduled-sync
         │
         ▼
Worker: sync_parse_enhance_workflow_task
  │
  ├── Step 1: sync_all_collections_task
  │     Clone/update git repos for each CodeCollection
  │
  ├── Step 2: parse_all_codebundles_task
  │     Parse meta.yaml, *.robot files, README.md
  │     Extract tasks, SLIs, metadata, support tags
  │     INSERT/UPDATE codebundles in PostgreSQL
  │
  └── Step 3: enhance_pending_codebundles_task
        AI-enhance NEW codebundles only (pending/NULL status)
        Generate descriptions, classify platforms, etc.
        UPDATE codebundles in PostgreSQL
```

All parsed and enhanced data is written to the `codebundles` and `codecollections` tables in PostgreSQL. This is the single source of truth for all search and browsing.

### 2. Search: Backend keyword search on PostgreSQL

All search -- whether from the frontend, the MCP server, or the chat system -- ultimately hits the backend's `GET /api/v1/codebundles?search=` endpoint, which runs **weighted keyword search** directly on PostgreSQL:

```
Frontend / MCP Server / Chat
         │
         ▼
Backend: GET /api/v1/codebundles?search=...
         │
         ▼
PostgreSQL: ILIKE keyword matching across multiple fields
  - name:         weight 4  (most specific)
  - display_name: weight 3
  - support_tags: weight 3  (curated metadata)
  - description:  weight 1
  - doc:          weight 1  (long text)
  Results ranked by aggregate relevance score
```

No embeddings or vector search are used in the production search path.

### 3. Chat: MCP tool delegation

The chat system uses the MCP server as an intermediary, but the MCP server is stateless and delegates back to the backend:

```
User question → Frontend → POST /api/v1/chat/query
  │
  ▼
Backend (mcp_chat.py):
  1. Classify question type
  2. Call MCP Server: POST http://mcp-server:8000/tools/call
  │
  ▼
MCP Server (server_http.py):
  1. Look up tool in ToolRegistry
  2. Tool strips stop words, extracts keywords
  3. Call backend: GET http://backend:8001/api/v1/codebundles?search=...
  4. Format results as markdown
  │
  ▼
Backend (mcp_chat.py):
  5. LLM synthesizes natural language answer from results
  6. Return structured response to frontend
```

### 4. Frontend browsing

Direct REST API calls from the frontend to the backend. No MCP server involvement.

```
Frontend  ──HTTP──►  Backend  ──SQLAlchemy──►  PostgreSQL
```

## Development / Offline Flows

These components exist in the codebase but are **not part of the production search or ingestion pipeline**.

### MCP Indexer (`mcp-server/indexer.py`)

A standalone CLI tool that can build a local vector search index. It clones repos, parses codebundles and libraries, crawls documentation URLs, generates embeddings, and writes them to `data/vector_index.json`.

The `mcp_tasks.py` Celery tasks (`index_documentation_task`, `reindex_all_task`) shell out to this indexer as a subprocess. The resulting `vector_index.json` file is **not read by the production MCP HTTP server** -- the server uses the backend API for all queries instead.

This indexer is useful for:
- Development and testing of semantic search
- Generating embeddings for future pgvector migration
- Offline analysis of the codebundle corpus

### LocalVectorStore (`mcp-server/utils/vector_store.py`)

In-memory numpy vector store with JSON file persistence. Used by the indexer to store embeddings. Not used by the MCP HTTP server at runtime.

### pgvector tables

The PostgreSQL database has pgvector enabled and four vector tables created by migration `006_add_pgvector.sql`. These tables are empty -- no code writes to or reads from them yet. They are prepared for a future migration from keyword search to vector similarity search.

See [MCP_WORKFLOW.md](MCP_WORKFLOW.md) for full details on both production and development flows.

## PostgreSQL + pgvector

The database image is `pgvector/pgvector:pg15`, which bundles the pgvector extension. On first start, `database/init/01-init.sql` enables the extension:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
```

### Core tables (managed by Alembic) -- used in production

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

### Vector tables (created by `006_add_pgvector.sql`) -- not yet used

| Table | Embedding dim | Purpose |
|---|---|---|
| `vector_codebundles` | 1536 | CodeBundle embeddings |
| `vector_codecollections` | 1536 | Collection embeddings |
| `vector_libraries` | 1536 | Library/keyword embeddings |
| `vector_documentation` | 1536 | Documentation page embeddings |

Each vector table has HNSW indexes for cosine similarity search plus B-tree indexes on metadata columns. The schema is ready but no code path writes to or queries these tables.

## MCP Server Architecture

The MCP server (`../mcp-server/`) is a sibling directory, not nested inside cc-registry-v2. It is built as a separate Docker image.

### Production: Stateless HTTP proxy

In production, `server_http.py` runs as a FastAPI app. It registers MCP tools on startup and delegates **all data access** to the backend API through `RegistryClient`. It does not use a database connection, vector store, or embedding generator.

### Tool categories

| Category | Tools | Data source |
|---|---|---|
| **search** | `find_codebundle`, `search_codebundles`, `find_codecollection`, `keyword_usage_help`, `find_library_info`, `find_documentation`, `check_existing_requests` | Backend API (keyword search on PostgreSQL) |
| **info** | `list_codebundles`, `list_codecollections`, `get_codebundle_details`, `get_development_requirements` | Backend API / local docs.yaml |
| **action** | `request_codebundle` | GitHub API |

## Celery Task System

### Task types

| Module | Key tasks | Production? |
|---|---|---|
| `workflow_tasks` | `sync_parse_enhance_workflow_task` | Yes -- primary ingestion pipeline |
| `registry_tasks` | `sync_all_collections_task`, `parse_all_codebundles_task` | Yes -- steps within the workflow |
| `ai_enhancement_tasks` | `enhance_pending_codebundles_task` | Yes -- AI metadata enhancement |
| `data_population_tasks` | `update_collection_statistics_task` | Yes -- hourly stats refresh |
| `analytics_tasks` | `compute_task_growth_analytics` | Yes -- daily analytics |
| `task_monitoring` | `cleanup_old_tasks_task`, `health_check_tasks_task` | Yes -- maintenance |
| `mcp_tasks` | `index_documentation_task`, `reindex_all_task` | No -- writes to local vector_index.json, not used by production search |

### Scheduling

All schedules are defined in `schedules.yaml` and loaded by Celery Beat.

**Production schedules (active):**

| Schedule | Frequency | Task |
|---|---|---|
| `scheduled-sync` | Every 6 hours | Sync repos, parse codebundles, AI enhance new entries |
| `update-statistics-hourly` | Hourly | Refresh collection statistics |
| `compute-task-growth-analytics` | Daily 2:30 AM | Git history analysis for task growth |
| `health-check` | Every 5 min | System health check |
| `cleanup-old-tasks` | Daily 12:30 AM | Purge old task execution records |

**Development/future schedules:**

| Schedule | Frequency | Task | Status |
|---|---|---|---|
| `index-documentation-daily` | Daily 3 AM | MCP indexer (vector_index.json) | Enabled but output not used in production |
| `reindex-mcp-weekly` | Sunday 2 AM | Full MCP re-index | Disabled by default |

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
- [MCP_WORKFLOW.md](MCP_WORKFLOW.md) -- Search and indexing flows in detail
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) -- Automated indexing setup
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI configuration
- [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) -- Database and Redis setup
