# Architecture

System architecture for the CodeCollection Registry v2.

## Service Overview

The registry runs as 8 Docker services coordinated by `docker-compose.yml`.

| Service | Image / Stack | Port | Role |
|---|---|---|---|
| **frontend** | React 19 + TypeScript + MUI v7 | 3000 | SPA for browsing and managing CodeBundles |
| **backend** | FastAPI + SQLAlchemy 2.0 | 8001 | REST API (`/api/v1/`), business logic, AI enhancement, embedding generation |
| **mcp-server** | FastAPI (separate repo: `../mcp-server`) | 8000 | Stateless MCP tool server, delegates all queries to backend API |
| **worker** | Celery (shares backend image) | -- | Background task processing (sync, parse, enhance, embed) |
| **scheduler** | Celery Beat (shares backend image) | -- | Cron-driven task scheduling |
| **database** | PostgreSQL 15 + pgvector (`pgvector/pgvector:pg15`) | 5432 | Primary data store + vector embeddings |
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
        │ (delegates all queries        │                               │
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

## Data Pipeline: Sync → Parse → Enhance → Embed

The backend Celery worker runs a unified pipeline that populates both the relational tables **and** the vector tables. The `sync_parse_enhance_workflow_task` runs every 6 hours:

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
  ├── Step 3: enhance_pending_codebundles_task
  │     AI-enhance NEW codebundles only (pending/NULL status)
  │     Generate descriptions, classify platforms, etc.
  │     UPDATE codebundles in PostgreSQL
  │
  └── Step 4: index_codebundles_task
        Generate embeddings (Azure OpenAI text-embedding-3-small)
        Upsert into vector_codebundles and vector_codecollections
        via pgvector
```

A separate daily task crawls external documentation:

```
Celery Beat dispatches index-documentation-daily (3 AM)
         │
         ▼
Worker: index_documentation_task
  │
  ├── Load documentation sources from sources.yaml
  ├── Crawl each URL (httpx + BeautifulSoup)
  ├── Generate embeddings for crawled content
  └── Upsert into vector_documentation via pgvector
```

## Search

### Keyword search (existing)

All keyword-based search hits the backend's `GET /api/v1/codebundles?search=` endpoint, which runs **weighted ILIKE** directly on PostgreSQL:

```
Frontend / MCP Server / Chat
         │
         ▼
Backend: GET /api/v1/codebundles?search=...
         │
         ▼
PostgreSQL: ILIKE keyword matching
  - name:         weight 4
  - display_name: weight 3
  - support_tags: weight 3
  - description:  weight 1
  - doc:          weight 1
  Results ranked by aggregate relevance score
```

### Semantic (vector) search

The backend exposes embedding-based search through `/api/v1/vector/search/*`:

```
MCP Server / Chat / Frontend
         │
         ▼
Backend: GET /api/v1/vector/search?query=...&tables=codebundles,documentation
         │
         ├── Generate query embedding (Azure OpenAI)
         ├── Cosine similarity search via pgvector (<=> operator)
         └── Return ranked results with scores
```

Available endpoints:

| Endpoint | Searches |
|---|---|
| `GET /api/v1/vector/search` | All tables (unified) |
| `GET /api/v1/vector/search/codebundles` | Codebundle embeddings |
| `GET /api/v1/vector/search/documentation` | Documentation embeddings |
| `GET /api/v1/vector/search/libraries` | Library embeddings |
| `GET /api/v1/vector/stats` | Row counts per table |
| `POST /api/v1/vector/reindex` | Trigger full reindex |

## Chat: MCP Tool Delegation

The chat system uses the MCP server as an intermediary:

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
  2. Tool calls backend API (keyword search or vector search)
  3. Format results as markdown
  │
  ▼
Backend (mcp_chat.py):
  4. LLM synthesizes natural language answer from results
  5. Return structured response to frontend
```

## Frontend Browsing

Direct REST API calls from the frontend to the backend. No MCP server involvement.

```
Frontend  ──HTTP──►  Backend  ──SQLAlchemy──►  PostgreSQL
```

## PostgreSQL + pgvector

The database image is `pgvector/pgvector:pg15`. The pgvector extension is enabled on first start.

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

### Vector tables (created by `006_add_pgvector.sql`)

| Table | Embedding dim | Content |
|---|---|---|
| `vector_codebundles` | 1536 | CodeBundle embeddings (name, description, tasks, readme) |
| `vector_codecollections` | 1536 | Collection embeddings |
| `vector_libraries` | 1536 | Library/keyword embeddings |
| `vector_documentation` | 1536 | Documentation page embeddings (crawled from sources.yaml) |

Each vector table has HNSW indexes for cosine similarity (`vector_cosine_ops`) plus B-tree indexes on metadata JSONB columns.

## MCP Server Architecture

The MCP server (`../mcp-server/`) is a sibling directory, not nested inside cc-registry-v2. It is built as a separate Docker image.

The server is **stateless**. `server_http.py` runs as a FastAPI app, registers MCP tools on startup, and delegates all data access to the backend API through `RegistryClient`. It does not have a database connection, vector store, or embedding generator.

### Tool categories

| Category | Tools | Data source |
|---|---|---|
| **search** | `find_codebundle`, `search_codebundles`, `find_codecollection`, `find_documentation`, `find_library_info`, `keyword_usage_help`, `check_existing_requests` | Backend API (vector search with keyword fallback) |
| **info** | `list_codebundles`, `list_codecollections`, `get_codebundle_details`, `get_development_requirements` | Backend API |
| **action** | `request_codebundle` | GitHub API |

## Celery Task System

### Task modules

| Module | Key tasks | Purpose |
|---|---|---|
| `workflow_tasks` | `sync_parse_enhance_workflow_task` | 4-step pipeline: sync → parse → enhance → embed |
| `registry_tasks` | `sync_all_collections_task`, `parse_all_codebundles_task` | Steps 1-2 of the pipeline |
| `ai_enhancement_tasks` | `enhance_pending_codebundles_task` | Step 3: AI metadata enhancement |
| `indexing_tasks` | `index_codebundles_task`, `index_documentation_task`, `reindex_all_task` | Step 4: embedding generation + pgvector storage |
| `data_population_tasks` | `update_collection_statistics_task` | Hourly stats refresh |
| `analytics_tasks` | `compute_task_growth_analytics` | Daily analytics |
| `task_monitoring` | `cleanup_old_tasks_task`, `health_check_tasks_task` | Maintenance |
| `mcp_tasks` | *(deprecated stubs)* | Redirect to `indexing_tasks` |

### Scheduling

All schedules are defined in `schedules.yaml` and loaded by Celery Beat.

| Schedule | Frequency | Task |
|---|---|---|
| `scheduled-sync` | Every 6 hours | Full pipeline: sync → parse → enhance → embed |
| `index-documentation-daily` | Daily 3 AM | Crawl documentation URLs, generate embeddings |
| `reindex-vectors-weekly` | Sunday 2 AM | Full rebuild of all vector embeddings |
| `update-statistics-hourly` | Hourly | Refresh collection statistics |
| `compute-task-growth-analytics` | Daily 2:30 AM | Git history analysis for task growth |
| `health-check` | Every 5 min | System health check |
| `cleanup-old-tasks` | Daily 12:30 AM | Purge old task execution records |

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

- [CONFIGURATION.md](CONFIGURATION.md) — Environment variables and secrets
- [MCP_WORKFLOW.md](MCP_WORKFLOW.md) — Search and indexing flows in detail
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) — Automated indexing setup
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) — Azure OpenAI configuration
- [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) — Database and Redis setup
