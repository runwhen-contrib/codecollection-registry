# MCP Server Workflow: Search and Indexing

How data ingestion, embedding generation, and search work in the CodeCollection Registry.

## Unified Pipeline

There is **one pipeline** for all environments. The backend Celery worker:

1. Syncs CodeCollection repos from GitHub
2. Parses codebundles from Robot files
3. AI-enhances metadata for new codebundles
4. Generates embeddings and stores them in pgvector

The MCP server is a **stateless HTTP proxy** that delegates all queries to the backend API.

---

## Data Ingestion

### Sync → Parse → Enhance → Embed workflow

The primary scheduled task `sync_parse_enhance_workflow_task` runs every 6 hours:

```
Celery Beat dispatches → Redis → Worker picks up task
         │
         ▼
Step 1: sync_all_collections_task
  - For each CodeCollection in the database:
    - git clone (or git pull) the repo
    - Store raw repo data
         │
         ▼
Step 2: parse_all_codebundles_task
  - For each collection repo:
    - Walk directory tree looking for meta.yaml + *.robot files
    - Parse meta.yaml: extract name, description, tags
    - Parse *.robot files: extract tasks, SLIs, keywords, variables
    - Parse README.md for documentation content
    - INSERT or UPDATE codebundle rows in PostgreSQL
         │
         ▼
Step 3: enhance_pending_codebundles_task
  - Query codebundles WHERE enhancement_status IS NULL or 'pending'
  - For each unenhanced codebundle:
    - Send to Azure OpenAI GPT for analysis
    - Generate: improved description, platform classification,
      access level, IAM requirements, data classifications
    - UPDATE the codebundle row
         │
         ▼
Step 4: index_codebundles_task
  - Query all active codebundles and codecollections from PostgreSQL
  - Build document text for each (name + description + tags + tasks + readme)
  - Generate embeddings via Azure OpenAI text-embedding-3-small
  - Upsert into vector_codebundles and vector_codecollections (pgvector)
```

### Documentation indexing

A separate daily task crawls external documentation:

```
Celery Beat dispatches index-documentation-daily (3 AM)
         │
         ▼
Worker: index_documentation_task
  │
  ├── Load documentation entries from sources.yaml
  │     (URLs for RunWhen docs, library references, FAQs, etc.)
  │
  ├── Crawl each URL with httpx + BeautifulSoup
  │     Extract title, headings, code blocks, body text
  │
  ├── Build document text from crawled content + metadata
  │
  ├── Generate embeddings via Azure OpenAI
  │
  └── Upsert into vector_documentation (pgvector)
```

### Full weekly reindex

`reindex_all_task` runs weekly (Sunday 2 AM) and rebuilds all vector tables from scratch.

---

## Search

### Keyword search

The existing keyword search remains available at `GET /api/v1/codebundles?search=`. It runs weighted ILIKE matching directly on PostgreSQL:

| Field | Weight |
|---|---|
| name | 4 |
| display_name | 3 |
| support_tags | 3 |
| description | 1 |
| doc | 1 |

Results are ranked by aggregate relevance score. This endpoint is used by the MCP server's `find_codebundle` and `search_codebundles` tools.

### Semantic (vector) search

The backend's `/api/v1/vector/search/*` endpoints provide embedding-based search:

```
Client sends query string
         │
         ▼
Backend: embed query via Azure OpenAI
         │
         ▼
PostgreSQL: cosine similarity search (embedding <=> query_vector)
  - Uses HNSW index for fast approximate nearest-neighbor lookup
  - Optional metadata filters (platform, category, collection_slug)
         │
         ▼
Return ranked results with similarity scores
```

The MCP server's `find_documentation` tool uses this path (with keyword fallback if the backend's vector tables are empty or the embedding service is unavailable).

---

## MCP Server: Stateless Proxy

The MCP server (`../mcp-server/server_http.py`) is a FastAPI app that:

1. Registers MCP tools on startup
2. Delegates all data access to the backend via `RegistryClient`
3. Formats results as markdown for LLM consumption

### How `find_codebundle` works

```
1. MCP Server receives: find_codebundle(query="kubernetes pod restarts")
2. Tool extracts keywords, removes stop words
3. Calls RegistryClient.search_codebundles(search="kubernetes pod restarts")
4. RegistryClient hits: GET http://backend:8001/api/v1/codebundles?search=kubernetes+pod+restarts
5. Backend runs weighted ILIKE search on PostgreSQL
6. Results returned as JSON → MCP tool formats as markdown
```

### How `find_documentation` works

```
1. MCP Server receives: find_documentation(query="how to install runwhen local")
2. Tool calls RegistryClient.vector_search_documentation(query="how to install runwhen local")
3. RegistryClient hits: GET http://backend:8001/api/v1/vector/search/documentation?query=...
4. Backend generates query embedding, runs pgvector cosine search
5. Results returned with similarity scores
6. If backend unavailable: falls back to keyword matching on local docs.yaml
```

---

## Key Files

### Backend (embedding & vector)

| File | Purpose |
|---|---|
| `backend/app/services/embedding_service.py` | Azure OpenAI embedding generation |
| `backend/app/services/vector_service.py` | pgvector CRUD and similarity search |
| `backend/app/services/web_crawler.py` | Documentation URL crawling |
| `backend/app/services/documentation_source_loader.py` | sources.yaml loader |
| `backend/app/tasks/indexing_tasks.py` | Celery tasks for embedding generation |
| `backend/app/tasks/workflow_tasks.py` | Orchestrates the 4-step pipeline |
| `backend/app/routers/vector_search.py` | `/api/v1/vector/*` API endpoints |
| `backend/app/models/vector_models.py` | SQLAlchemy models for pgvector tables |

### MCP Server

| File | Purpose |
|---|---|
| `mcp-server/server_http.py` | FastAPI HTTP server (stateless) |
| `mcp-server/utils/registry_client.py` | HTTP client for backend API (includes vector search methods) |
| `mcp-server/tools/documentation_tools.py` | Documentation search (backend vector → local keyword fallback) |
| `mcp-server/sources.yaml` | Documentation URLs (mounted into backend container) |

### Deprecated (kept for reference)

| File | Replaced by |
|---|---|
| `mcp-server/indexer.py` | `backend/app/tasks/indexing_tasks.py` |
| `mcp-server/utils/vector_store.py` | `backend/app/services/vector_service.py` |
| `mcp-server/utils/embeddings.py` | `backend/app/services/embedding_service.py` |
| `mcp-server/utils/semantic_search.py` | Backend `/api/v1/vector/search/*` endpoints |
| `backend/app/tasks/mcp_tasks.py` | `backend/app/tasks/indexing_tasks.py` (stubs redirect) |
