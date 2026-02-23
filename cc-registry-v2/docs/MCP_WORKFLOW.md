# MCP Server Workflow: Search and Indexing

How data ingestion, search, and the offline indexing pipeline work in the CodeCollection Registry.

## Production vs Development

This document covers two separate systems:

1. **Production** -- The backend Celery worker ingests data into PostgreSQL. The MCP server and chat system search that data via the backend API using keyword matching. No embeddings or vector store involved.
2. **Development / Future** -- The standalone MCP indexer (`indexer.py`) generates vector embeddings and writes them to a local JSON file. This is not used by the production search path today.

---

## Production: Data Ingestion

The backend Celery worker populates PostgreSQL by cloning CodeCollection repos, parsing codebundles, and optionally AI-enhancing metadata.

### Sync-Parse-Enhance workflow

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
  - Walk each repo's codebundles/ directory
  - Parse meta.yaml → name, author, tags, platform
  - Parse *.robot files → tasks, SLIs, keywords, libraries
  - Parse README.md → description
  - INSERT or UPDATE codebundles rows in PostgreSQL
  - Set task_count, sli_count, support_tags, etc.
         │
         ▼
Step 3: enhance_pending_codebundles_task
  - Query codebundles WHERE enhancement_status IS NULL or 'pending'
  - For each: call Azure OpenAI GPT to generate:
    - Enhanced description
    - Platform classification
    - Access level, IAM requirements
    - Data classifications
  - UPDATE codebundle rows with AI metadata
```

After this workflow completes, the `codebundles` table in PostgreSQL contains all the data that search operates on.

### What gets stored in PostgreSQL

Each codebundle row includes fields used for search:

- `name`, `display_name` -- canonical names
- `slug` -- URL-safe identifier
- `description`, `doc`, `readme` -- text content
- `support_tags` -- JSONB array of tags (e.g., `["kubernetes", "pods", "health"]`)
- `discovery_platform` -- inferred platform (Kubernetes, AWS, Azure, etc.)
- `tasks`, `slis` -- JSONB arrays of extracted task/SLI definitions
- `ai_enhanced_description` -- GPT-generated description
- `enhancement_status` -- tracks AI enhancement state

---

## Production: Search

All search in the system uses **weighted keyword matching on PostgreSQL**. No embeddings, no vector similarity, no cosine distance.

### How the backend search works

The endpoint `GET /api/v1/codebundles?search=` implements this:

1. Strip stop words from the query ("How do I check Kubernetes pod health?" becomes "check Kubernetes pod health")
2. For 1-2 keywords: require ALL to match (AND) via ILIKE across fields
3. For 3+ keywords: require ANY to match (OR), then rank by weighted relevance score
4. Relevance scoring weights:
   - `name` match: **+4** (most specific)
   - `display_name` match: **+3**
   - `support_tags` match: **+3** (curated metadata)
   - `description` match: **+1**
   - `doc` match: **+1** (long text, many false positives)
5. Results sorted by aggregate score descending, then by name

### Chat search flow

```
User types question in Chat UI
         │
         ▼
Frontend: POST /api/v1/chat/query
         │
         ▼
Backend (mcp_chat.py):
  1. Classifies question type (follow-up, meta, codebundle search, etc.)
  2. Calls MCP Server via MCPClient
         │
         ▼
MCPClient: POST http://mcp-server:8000/tools/call
  {
    "tool_name": "find_codebundle",
    "arguments": {"query": "check Kubernetes pod health", "max_results": 10}
  }
         │
         ▼
MCP Server (server_http.py):
  1. Looks up tool in ToolRegistry
  2. FindCodeBundleTool strips stop words from query
  3. Calls RegistryClient: GET /api/v1/codebundles?search=check+Kubernetes+pod+health
         │
         ▼
Backend: Weighted ILIKE keyword search on PostgreSQL
         │
         ▼
Results flow back:
  MCP Server → formats as markdown with relevance scores
         │
         ▼
Backend (mcp_chat.py):
  Azure OpenAI GPT synthesizes natural language answer
         │
         ▼
Frontend: Displays answer + relevant codebundles
```

### MCP tools used at runtime

All tools delegate to the backend API via `RegistryClient` (`utils/registry_client.py`). The MCP server makes HTTP requests to the backend -- it never queries a database or vector store directly.

| Tool | Backend endpoint | Purpose |
|---|---|---|
| `find_codebundle` | `GET /api/v1/codebundles?search=` | Natural language codebundle search |
| `search_codebundles` | `GET /api/v1/codebundles?search=&platform=&tags=` | Filtered keyword search |
| `list_codebundles` | `GET /api/v1/codebundles` | List all codebundles |
| `get_codebundle_details` | `GET /api/v1/collections/{coll}/codebundles/{cb}` | Single codebundle detail |
| `find_codecollection` | `GET /api/v1/registry/collections` | Search collections |
| `list_codecollections` | `GET /api/v1/registry/collections` | List all collections |
| `keyword_usage_help` | `GET /api/v1/codebundles?search=` | Robot Framework keyword help |
| `find_library_info` | `GET /api/v1/codebundles?search=` | Library information |
| `find_documentation` | Local `docs.yaml` | Search managed documentation |
| `get_development_requirements` | Local `docs.yaml` | Dev requirements for a feature |
| `request_codebundle` | GitHub API | Create GitHub issue |
| `check_existing_requests` | GitHub API | Search existing GitHub issues |

---

## Development / Future: Offline Indexing Pipeline

The MCP indexer (`mcp-server/indexer.py`) is a standalone CLI tool that generates vector embeddings. It is **not part of the production search path** -- its output (`data/vector_index.json`) is not read by the MCP HTTP server or the backend.

This pipeline exists for development, testing, and as groundwork for a future migration to vector similarity search.

### Pipeline stages

```
Stage 1: Data Acquisition
─────────────────────────
  codecollections.yaml (repo root)
         │
         ▼
  For each collection:
    git clone / git pull
    (repos stored in mcp-server/data/repos/)

Stage 2: Parsing
────────────────
  For each repo:
    codebundles/ directory:
      ├── meta.yaml        → name, author, tags, platform
      ├── *.robot files    → tasks, keywords, libraries (RobotParser)
      └── README.md        → description text

    libraries/ directory:
      └── *.py files       → functions, classes, docstrings (PythonParser AST)

Stage 3: Document Creation
──────────────────────────
  Each codebundle → single text document combining:
    - Display name, slug, description
    - Platform and support tags
    - Task names + documentation (up to 20 capabilities)
    - README excerpt (up to 2000 chars)

  Each library → single text document combining:
    - Name, import path, category, description
    - Function signatures + docstrings (up to 15)
    - Class info + methods (up to 10)
    - Robot Framework keywords (up to 20)

Stage 4: Documentation Crawling
───────────────────────────────
  mcp-server/sources.yaml
         │
         ▼
  WebCrawler (crawl4ai headless browser, or httpx+BeautifulSoup fallback)
    - Fetches each URL
    - Extracts title, body text, headings, code blocks
    - Converts to clean markdown
    - Stores up to 12,000 chars per page in embedding document

Stage 5: Embedding Generation
─────────────────────────────
  All documents (codebundles + libraries + collections + docs)
         │
         ▼
  EmbeddingGenerator (utils/embeddings.py)
    - Azure OpenAI: text-embedding-3-small (1536 dimensions)
    - Batches of 100 texts per API call
    - Fallback: local sentence-transformers all-MiniLM-L6-v2 (384 dimensions)

Stage 6: Vector Storage
───────────────────────
  LocalVectorStore (utils/vector_store.py)
    - In-memory numpy arrays
    - Persisted to data/vector_index.json
    - 4 tables: vector_codebundles, vector_codecollections,
                vector_libraries, vector_documentation
    - Brute-force cosine similarity search
    - Metadata filtering (platform, collection, category)
```

### Running the indexer

```bash
cd mcp-server

# Full index (codebundles + libraries + documentation)
python indexer.py

# Documentation only (faster)
python indexer.py --docs-only

# Specific collection
python indexer.py --collection rw-cli-codecollection

# Use local embeddings instead of Azure OpenAI
python indexer.py --local
```

### LocalVectorStore details

The vector store is a zero-infrastructure, in-memory implementation using numpy for cosine similarity search. It persists to a single JSON file.

**Storage format** (`data/vector_index.json`):

```json
{
  "vector_codebundles": {
    "rw-cli-codecollection/k8s-pod-healthcheck": {
      "embedding": [0.012, -0.034, ...],
      "document": "Kubernetes Pod Healthcheck\nPlatform: Kubernetes\n...",
      "metadata": {
        "slug": "k8s-pod-healthcheck",
        "collection_slug": "rw-cli-codecollection",
        "platform": "Kubernetes",
        "tags": "kubernetes,pods,health"
      }
    }
  },
  "vector_codecollections": { ... },
  "vector_libraries": { ... },
  "vector_documentation": { ... }
}
```

**Search algorithm:**
1. Normalize the query embedding vector
2. For each stored vector, compute cosine similarity: `dot(query_vec, stored_vec / norm)`
3. Convert to distance: `distance = 1.0 - cosine_similarity`
4. Apply optional metadata filters (platform, collection_slug, category)
5. Sort by distance ascending (lowest = most similar)
6. Return top N results as `SearchResult` objects

### pgvector tables (future)

The PostgreSQL database has pgvector enabled and four vector tables created by migration `006_add_pgvector.sql` with `vector(1536)` columns and HNSW indexes. The schema is ready but no code path writes to or queries these tables yet. A future migration could:

1. Add a backend API endpoint for writing embeddings (called by the indexer via `RegistryClient`)
2. Add a backend API endpoint for vector similarity search
3. Wire the MCP server tools to use the vector search endpoint instead of keyword search

### Embedding generation

**Azure OpenAI (default when credentials available):**

| Setting | Value |
|---|---|
| Model | `text-embedding-3-small` |
| Dimensions | 1536 |
| Batch size | 100 texts per API call |
| API version | `2024-02-15-preview` |

Environment variables (checked in order):

1. `AZURE_OPENAI_EMBEDDING_ENDPOINT` + `AZURE_OPENAI_EMBEDDING_API_KEY` (dedicated)
2. `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` (shared with GPT)

**Local fallback:**

If no Azure credentials are available, the indexer uses `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors). Force with `python indexer.py --local`.

### Web Crawler

Documentation sources defined in `mcp-server/sources.yaml` are crawled for content.

- **Crawl4AI** (primary) -- headless Chromium, renders JavaScript, outputs clean markdown
- **BeautifulSoup** (fallback) -- simple HTTP fetch + HTML parsing

---

## Key Files

### cc-registry-v2 (backend) -- production

| File | Purpose |
|---|---|
| `backend/app/main.py` | `GET /api/v1/codebundles` endpoint with weighted keyword search |
| `backend/app/routers/mcp_chat.py` | Chat API endpoint, calls MCP server, LLM synthesis |
| `backend/app/services/mcp_client.py` | HTTP client for MCP server |
| `backend/app/tasks/workflow_tasks.py` | Sync-parse-enhance pipeline |
| `backend/app/tasks/registry_tasks.py` | Git sync and codebundle parsing |
| `backend/app/tasks/ai_enhancement_tasks.py` | GPT-based metadata enhancement |
| `schedules.yaml` | Celery Beat schedule configuration |

### mcp-server -- production (HTTP server)

| File | Purpose |
|---|---|
| `server_http.py` | Stateless HTTP server, delegates to backend API |
| `utils/registry_client.py` | HTTP client for backend API |
| `tools/codebundle_tools.py` | CodeBundle search/list/detail tools |
| `tools/collection_tools.py` | CodeCollection tools |
| `tools/library_tools.py` | Library and keyword tools |
| `tools/documentation_tools.py` | Documentation search (local docs.yaml) |
| `tools/github_issue.py` | GitHub issue creation tool |
| `docs.yaml` | Managed documentation catalog |

### mcp-server -- development (indexer)

| File | Purpose |
|---|---|
| `indexer.py` | Offline indexing CLI tool |
| `utils/vector_store.py` | LocalVectorStore (numpy + JSON) |
| `utils/embeddings.py` | Azure OpenAI / local embedding generator |
| `utils/web_crawler.py` | Documentation page crawler |
| `utils/robot_parser.py` | Robot Framework file parser |
| `utils/python_parser.py` | Python AST parser for libraries |
| `sources.yaml` | Documentation source URLs for crawling |
| `codecollections.yaml` | CodeCollection repo definitions (repo root) |

---

## Troubleshooting

### Chat not returning results

1. Verify MCP server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Verify backend API is reachable from MCP server:
   ```bash
   docker exec registry-mcp-server curl http://backend:8001/api/v1/health
   ```

3. Check that codebundles exist in the database:
   ```bash
   curl "http://localhost:8001/api/v1/codebundles?limit=5"
   ```

4. Check MCP server logs:
   ```bash
   docker logs registry-mcp-server --tail=50
   ```

### Codebundles not appearing after repo update

1. Check that the sync workflow ran:
   ```bash
   docker logs registry-worker --tail=100 | grep sync
   ```

2. Trigger manually from Admin UI: Schedules tab, find `scheduled-sync`, click "Run Now"

3. Check for parse errors in worker logs

### Search results not relevant

The backend uses keyword matching, not semantic search. If results are poor:

1. Check that the codebundle has good `support_tags`, `display_name`, and `description` fields
2. Verify AI enhancement has run (`enhancement_status` should not be NULL)
3. Try different search terms -- the system matches literal keywords

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture overview
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) -- Automated indexing schedules
- [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables and secrets
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI credential setup
