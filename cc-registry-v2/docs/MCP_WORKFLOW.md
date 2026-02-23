# MCP Server Workflow: Indexing and Search

How document indexing, embedding generation, and semantic search work in the CodeCollection Registry.

## Overview

There are two distinct data paths:

1. **Runtime search** -- The MCP server (`server_http.py`) is a stateless API that delegates all queries to the backend Registry API over HTTP. No embeddings or vector store are involved at runtime.
2. **Offline indexing** -- The indexer (`indexer.py`) clones repos, parses codebundles, crawls docs, generates embeddings via Azure OpenAI, and writes them to a local vector index file.

The runtime search path is what production uses today. The offline indexer populates a local vector store that can supplement or replace the backend API search in future.

## Runtime Search Flow

### How a user query becomes results

```
User types question in Chat UI
         │
         ▼
Frontend: POST /api/v1/chat/query
         │
         ▼
Backend (mcp_chat.py):
  1. Classifies question type
  2. Calls MCP Server via MCPClient
         │
         ▼
MCPClient: POST http://mcp-server:8000/tools/call
  {
    "tool_name": "find_codebundle",
    "arguments": {"query": "...", "max_results": 10}
  }
         │
         ▼
MCP Server (server_http.py):
  1. Looks up tool in ToolRegistry
  2. Tool calls RegistryClient (HTTP)
         │
         ▼
RegistryClient: GET http://backend:8001/api/v1/codebundles?search=...
         │
         ▼
Backend: Queries PostgreSQL with text search
         │
         ▼
Results flow back through the chain:
  MCP Server formats as markdown
         │
         ▼
Backend: LLM synthesizes natural language answer
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

## Offline Indexing Pipeline

The indexer (`mcp-server/indexer.py`) is a batch CLI tool that builds a vector search index. It runs independently of the HTTP server.

### Pipeline stages

```
Stage 1: Data Acquisition
─────────────────────────
  codecollections.yaml
         │
         ▼
  For each collection:
    git clone / git pull
    (repos stored in data/repos/)

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
  Each codebundle → single text document containing:
    - Display name and slug
    - Description
    - Platform and support tags
    - Task names and documentation (up to 20 capabilities)
    - README excerpt (up to 2000 chars)

  Each library → single text document containing:
    - Name and import path
    - Category and description
    - Function signatures + docstrings (up to 15)
    - Class info + methods (up to 10)
    - Robot Framework keywords (up to 20)

Stage 4: Documentation Crawling
───────────────────────────────
  sources.yaml
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
  EmbeddingGenerator
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

### No chunking

Documents are **not** chunked. Each codebundle, library, collection, or documentation page is embedded as a single document. Text is truncated to fit within embedding model token limits:

| Document type | Max text length |
|---|---|
| CodeBundle README | 2,000 chars |
| CodeBundle capabilities | Up to 20 items |
| Library functions | Up to 15 signatures |
| Documentation page | 12,000 chars |
| Description fields | 500 chars |

### Running the indexer

```bash
# Full index (codebundles + libraries + documentation)
cd mcp-server
python indexer.py

# Documentation only (faster)
python indexer.py --docs-only

# Specific collection
python indexer.py --collection rw-cli-codecollection

# Use local embeddings instead of Azure OpenAI
python indexer.py --local
```

## Vector Store

### Implementation: LocalVectorStore

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

This brute-force approach works well for the current dataset size (hundreds of vectors). For larger datasets, the pgvector tables in PostgreSQL can be used with HNSW indexing.

### pgvector (future)

The PostgreSQL database has pgvector enabled and four vector tables created by migration `006_add_pgvector.sql`. These tables mirror the local vector store's structure with `vector(1536)` columns and HNSW indexes. They are ready for use but the MCP server has not been migrated to query them yet.

## Embedding Generation

### Azure OpenAI (production)

| Setting | Value |
|---|---|
| Model | `text-embedding-3-small` |
| Dimensions | 1536 |
| Batch size | 100 texts per API call |
| API version | `2024-02-15-preview` |

Environment variables (checked in order):

1. `AZURE_OPENAI_EMBEDDING_ENDPOINT` + `AZURE_OPENAI_EMBEDDING_API_KEY` (dedicated)
2. `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_API_KEY` (shared with GPT)

Deployment name: `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (default: `text-embedding-3-small`)

### Local fallback

If no Azure credentials are available, the indexer uses `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors). No API cost, but lower quality.

Force local mode: `python indexer.py --local`

## Web Crawler

Documentation sources defined in `mcp-server/sources.yaml` are crawled for content.

### Crawl4AI (primary)

Uses headless Chromium to render JavaScript-heavy pages (Confluence, SPAs). Outputs clean markdown. Automatically strips navigation, headers, footers.

### BeautifulSoup (fallback)

Simple HTTP fetch + HTML parsing. Used when crawl4ai is not installed or fails for a URL.

### Source configuration (`sources.yaml`)

```yaml
sources:
  documentation:
    - name: "RunWhen Platform Docs"
      url: "https://docs.runwhen.com/..."
      description: "Platform documentation"
      topics: ["platform", "setup"]
      priority: high

  libraries:
    - name: "RW.CLI Library"
      url: "https://..."
      description: "CLI automation library"
      usage_examples: ["RW.CLI.Run Bash"]

  faq:
    - question: "How do I create a codebundle?"
      answer: "..."
      topics: ["development"]

index_config:
  refresh_interval: 24
  crawl_linked_pages: true
  max_crawl_depth: 3
  include_code_examples: true
```

## Key Files

### cc-registry-v2 (backend)

| File | Purpose |
|---|---|
| `backend/app/routers/mcp_chat.py` | Chat API endpoint, calls MCP server |
| `backend/app/services/mcp_client.py` | HTTP client for MCP server |
| `backend/app/tasks/mcp_tasks.py` | Celery tasks for triggering indexing |
| `schedules.yaml` | Celery Beat schedule configuration |

### mcp-server

| File | Purpose |
|---|---|
| `server_http.py` | Production HTTP server (stateless) |
| `indexer.py` | Offline indexing CLI tool |
| `utils/vector_store.py` | LocalVectorStore (numpy + JSON) |
| `utils/embeddings.py` | Azure OpenAI / local embedding generator |
| `utils/registry_client.py` | HTTP client for backend API |
| `utils/web_crawler.py` | Documentation page crawler |
| `utils/robot_parser.py` | Robot Framework file parser |
| `utils/python_parser.py` | Python AST parser for libraries |
| `tools/codebundle_tools.py` | CodeBundle search/list/detail tools |
| `tools/collection_tools.py` | CodeCollection tools |
| `tools/library_tools.py` | Library and keyword tools |
| `tools/documentation_tools.py` | Documentation search tools |
| `tools/github_issue.py` | GitHub issue creation tool |
| `sources.yaml` | Documentation source URLs |
| `docs.yaml` | Managed documentation catalog |
| `codecollections.yaml` | CodeCollection repo definitions |

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

3. Check MCP server logs:
   ```bash
   docker logs registry-mcp-server --tail=50
   ```

### Indexer failures

1. Run the indexer manually to see errors:
   ```bash
   cd mcp-server
   python indexer.py --docs-only
   ```

2. Check Azure OpenAI credentials:
   ```bash
   echo $AZURE_OPENAI_EMBEDDING_ENDPOINT
   echo $AZURE_OPENAI_EMBEDDING_API_KEY
   ```

3. Use local embeddings to bypass API issues:
   ```bash
   python indexer.py --local
   ```

### Search results not relevant

1. Re-index with fresh data:
   ```bash
   cd mcp-server && python indexer.py
   ```

2. Check what was indexed:
   ```bash
   python -c "import json; d=json.load(open('data/vector_index.json')); print({k:len(v) for k,v in d.items()})"
   ```

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture overview
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) -- Automated indexing schedules
- [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables and secrets
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI credential setup
