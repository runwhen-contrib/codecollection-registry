# App → MCP → Indexing Workflow

This document explains how the CodeCollection Registry app integrates with the MCP server and how indexing works.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CodeCollection Registry v2                    │
│  (cc-registry-v2: FastAPI Backend + React Frontend)             │
└─────────────────────────────────────────────────────────────────┘
           │                                        ▲
           │ 1. HTTP API calls                      │ 3. Returns semantic
           │    (find_codebundle,                   │    search results
           │     find_documentation,                │    (markdown formatted)
           │     keyword_usage_help)                │
           ▼                                        │
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Server                               │
│   (mcp-server: HTTP API + Vector Store)                         │
│                                                                  │
│   - server_http.py: HTTP API endpoint                           │
│   - tools/: Semantic search tools                               │
│   - utils/vector_store.py: ChromaDB interface                   │
│   - chroma_db/: Vector database (embeddings)                    │
└─────────────────────────────────────────────────────────────────┘
           ▲                                        │
           │ 2. Queries vector DB                   │ 4. Indexer updates
           │    using embeddings                    │    embeddings
           │                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Indexer                                 │
│   (mcp-server/indexer.py)                                       │
│                                                                  │
│   Processes:                                                     │
│   - GitHub repos → Parse codebundles                            │
│   - sources.yaml → Crawl documentation                          │
│   - Generate embeddings (Azure OpenAI)                          │
│   - Store in ChromaDB                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow

### 1. User Asks Question in Chat UI

```
User: "How do I check Kubernetes pod health?"
  │
  ▼
Chat.tsx → POST /api/v1/chat/query
  │
  ▼
mcp_chat.py (FastAPI endpoint)
```

### 2. App Calls MCP Server for Semantic Search

```python
# In cc-registry-v2/backend/app/routers/mcp_chat.py

mcp = get_mcp_client()

# Search for relevant codebundles
result = await mcp.find_codebundle(
    query="check Kubernetes pod health",
    max_results=10
)
# Returns markdown with codebundles ranked by relevance
```

```python
# In cc-registry-v2/backend/app/services/mcp_client.py

class MCPClient:
    async def find_codebundle(self, query: str, ...):
        # Makes HTTP POST to MCP server
        response = await client.post(
            "http://mcp-server:8000/tools/call",
            json={
                "tool_name": "find_codebundle",
                "arguments": {"query": query, ...}
            }
        )
```

### 3. MCP Server Performs Semantic Search

```
MCP Server receives request
  │
  ▼
tools/codebundle_tools.py
  │
  ├─ Generate embedding for query
  │  (using Azure OpenAI text-embedding-ada-002)
  │
  ├─ Search ChromaDB for similar embeddings
  │  (cosine similarity)
  │
  ├─ Rank results by relevance score
  │
  └─ Format as markdown response
```

### 4. App Enhances with LLM and Returns to User

```
MCP results (codebundles with scores)
  │
  ▼
AIEnhancementService synthesizes natural language answer
  │
  ▼
Returns ChatResponse with:
  - answer: Natural language response
  - relevant_tasks: Structured codebundle data
  - confidence_score: How confident the AI is
  - sources_used: Which MCP tools were used
```

## 🔄 Indexing Process

### When Data is Indexed

1. **Scheduled (Automated)**
   - Daily at 3:00 AM: Documentation indexing
   - Weekly (optional): Full re-index of everything

2. **Manual Triggers**
   - Admin panel → Schedules → "Run Now" button
   - Direct API call to `/api/v1/schedule/schedules/{schedule_id}/trigger`
   - Command line: `python mcp-server/indexer.py`

3. **Workflow Integration**
   - After sync/parse workflow updates codebundles in registry DB
   - MCP indexer reads from GitHub repos (not registry DB)
   - Both stay in sync because they read from same source

### Indexing Pipeline: Codebundles

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Clone/Update GitHub Repos                                 │
│    - rw-cli-codecollection                                   │
│    - rw-public-codecollection                                │
│    - etc.                                                     │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Parse Codebundles                                         │
│    For each codebundle directory:                            │
│    - Parse meta.yaml (metadata)                              │
│    - Parse *.robot files (tasks, keywords)                   │
│    - Parse README.md (description)                           │
│    - Extract: name, tasks, platform, tags, etc.             │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Create Embedding Documents                                │
│    Rich text combining:                                      │
│    - Display name & slug                                     │
│    - Description                                             │
│    - Platform & tags                                         │
│    - Task names & documentation (capabilities)              │
│    - README excerpts                                         │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Generate Embeddings                                       │
│    Azure OpenAI text-embedding-ada-002                       │
│    - Input: Document text                                    │
│    - Output: 1536-dimensional vector                         │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Store in ChromaDB                                         │
│    Collection: "codebundles"                                 │
│    - Embedding vector                                        │
│    - Metadata (all fields)                                   │
│    - Document ID (slug)                                      │
└──────────────────────────────────────────────────────────────┘
```

### Indexing Pipeline: Documentation

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Load sources.yaml                                         │
│    Documentation sources:                                    │
│    - RunWhen docs                                            │
│    - CodeCollection repos                                    │
│    - Library documentation                                   │
│    - FAQs, guides, examples                                  │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Crawl Web Pages                                           │
│    For each URL:                                             │
│    - Fetch HTML content                                      │
│    - Extract text, headings, code blocks                     │
│    - Store up to 15,000 chars per page                       │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Create Embedding Documents                                │
│    Combining:                                                │
│    - Page title & description                                │
│    - Crawled content (main text)                             │
│    - Section headings                                        │
│    - Code examples                                           │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Generate Embeddings                                       │
│    Azure OpenAI text-embedding-ada-002                       │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Store in ChromaDB                                         │
│    Collection: "documentation"                               │
└──────────────────────────────────────────────────────────────┘
```

## 🔧 Key Components

### cc-registry-v2 (App)

**Purpose:** Main web application for browsing and chatting

**Key Files:**
- `backend/app/routers/mcp_chat.py` - Chat API endpoint
- `backend/app/services/mcp_client.py` - MCP HTTP client
- `backend/app/tasks/mcp_tasks.py` - Celery tasks to trigger indexing
- `frontend/src/pages/Chat.tsx` - Chat UI

**Database:** PostgreSQL (stores codebundles, collections, tasks, user data)

**Environment Variables:**
```bash
MCP_SERVER_URL=http://host.docker.internal:8000
```

### mcp-server

**Purpose:** Semantic search engine using vector embeddings

**Key Files:**
- `server_http.py` - HTTP API server (port 8000)
- `indexer.py` - Generates embeddings and updates database
- `tools/codebundle_tools.py` - Codebundle search tools
- `tools/documentation_tools.py` - Documentation search tools
- `utils/vector_store.py` - ChromaDB interface
- `utils/embeddings.py` - Azure OpenAI embedding generator

**Database:** ChromaDB (vector database for embeddings)
- Location: `mcp-server/chroma_db/`
- Collections: `codebundles`, `codecollections`, `libraries`, `documentation`

**Environment Variables:**
```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT_NAME=...
```

## 🔁 Automated Indexing Schedule

Defined in `cc-registry-v2/schedules.yaml`:

```yaml
# Daily documentation indexing (enabled)
- id: index-documentation-daily
  task: app.tasks.mcp_tasks.index_documentation_task
  schedule_type: crontab
  crontab:
    hour: 3
    minute: 0
  enabled: true

# Weekly full re-index (disabled by default)
- id: reindex-mcp-weekly
  task: app.tasks.mcp_tasks.reindex_all_task
  schedule_type: crontab
  crontab:
    hour: 2
    minute: 0
    day_of_week: 0  # Sunday
  enabled: false
```

**How it works:**

1. Celery Beat scheduler runs in `cc-registry-v2/scheduler` container
2. At scheduled time, Beat dispatches task to Celery worker
3. Worker executes `app/tasks/mcp_tasks.py::index_documentation_task()`
4. Task runs `subprocess` to execute:
   ```bash
   cd /workspaces/codecollection-registry/mcp-server
   python indexer.py --docs-only
   ```
5. Indexer updates ChromaDB
6. MCP server immediately uses updated embeddings for queries

## 🎯 Search Flow Example

### User Query: "troubleshoot slow Kubernetes pods"

1. **Frontend** (`Chat.tsx`):
   ```typescript
   POST /api/v1/chat/query
   {
     "question": "troubleshoot slow Kubernetes pods",
     "context_limit": 10
   }
   ```

2. **Backend** (`mcp_chat.py`):
   ```python
   # Call MCP server
   mcp_result = await mcp.find_codebundle(
       query="troubleshoot slow Kubernetes pods",
       max_results=10
   )
   
   # MCP returns markdown with relevant codebundles:
   # - k8s-pod-healthcheck (score: 0.89)
   # - k8s-deployment-healthcheck (score: 0.85)
   # - k8s-pod-logs (score: 0.78)
   
   # Parse markdown and get structured data from registry DB
   # Enhance with LLM for natural language answer
   ```

3. **MCP Server** (`tools/codebundle_tools.py`):
   ```python
   # Generate embedding for query
   query_embedding = embeddings.embed_text(
       "troubleshoot slow Kubernetes pods"
   )
   
   # Search ChromaDB
   results = vector_store.query(
       collection="codebundles",
       query_embeddings=[query_embedding],
       n_results=10,
       where={"platform": "Kubernetes"}  # Optional filter
   )
   
   # Results are ranked by cosine similarity
   # Returns formatted markdown with codebundles
   ```

4. **Response to User**:
   ```json
   {
     "answer": "To troubleshoot slow Kubernetes pods, I recommend...",
     "relevant_tasks": [
       {
         "codebundle_slug": "k8s-pod-healthcheck",
         "description": "Checks pod health and resource usage",
         "relevance_score": 0.89
       }
     ],
     "sources_used": ["MCP Codebundle Lookup"],
     "query_metadata": {
       "mcp_tools": ["find_codebundle"],
       "search_time_ms": 245
     }
   }
   ```

## 🔍 Available MCP Tools

The app can call these MCP tools via `MCPClient`:

1. **`find_codebundle`** - Search codebundles by natural language
   - Most commonly used for chat queries
   - Returns ranked codebundles with relevance scores

2. **`find_codecollection`** - Search collections
   - Used when user asks about collections/repos

3. **`keyword_usage_help`** - Get Robot Framework keyword help
   - Used for technical keyword/library questions

4. **`find_documentation`** - Search docs, guides, FAQs
   - Used when user asks how-to questions
   - Searches crawled documentation content

5. **`search_codebundles`** - Advanced search with filters
   - Used internally for complex queries

## 🚀 Manual Indexing

### From Command Line

```bash
# Full index (codebundles + documentation)
cd /workspaces/codecollection-registry/mcp-server
python indexer.py

# Documentation only
python indexer.py --docs-only

# Specific collection only
python indexer.py --collection rw-cli-codecollection

# Use local embeddings (no API calls)
python indexer.py --local
```

### From Admin Panel

1. Navigate to **Admin Panel** → **Schedules**
2. Find `index-documentation-daily` or `reindex-mcp-weekly`
3. Click **"Run Now"** button
4. Task executes immediately via Celery worker
5. Check **Task Manager** for progress

### Via API

```bash
# Trigger documentation indexing
curl -X POST http://localhost:8001/api/v1/admin/trigger-mcp-index \
  -H "Authorization: Bearer $TOKEN"

# Or trigger via schedule
curl -X POST http://localhost:8001/api/v1/schedule/schedules/index-documentation-daily/trigger \
  -H "Authorization: Bearer $TOKEN"
```

## 🔄 Sync vs Index

**Important distinction:**

- **Sync** (`registry_tasks.py`): Updates cc-registry-v2 PostgreSQL database
  - Clones GitHub repos
  - Parses codebundles
  - Stores in PostgreSQL
  - Used by web UI for browsing

- **Index** (`mcp_tasks.py` → `indexer.py`): Updates MCP ChromaDB
  - Clones GitHub repos (separate workspace)
  - Parses codebundles
  - Generates embeddings
  - Stores in ChromaDB
  - Used by chat for semantic search

Both read from the same GitHub repos but maintain separate databases.

## 📦 Data Storage Locations

```
codecollection-registry/
├── cc-registry-v2/
│   └── PostgreSQL database (container)
│       - codebundles table
│       - codecollections table
│       - tasks table
│       - User data, chat logs, etc.
│
└── mcp-server/
    ├── chroma_db/ (vector database)
    │   ├── codebundles collection
    │   ├── codecollections collection
    │   ├── libraries collection
    │   └── documentation collection
    │
    └── data/
        ├── repos/ (cloned GitHub repos)
        ├── codebundles.json (fallback)
        └── libraries.json (fallback)
```

## 🎨 Diagram: Complete Flow

```
User asks question
     ↓
[Chat UI (React)]
     ↓
[FastAPI /chat/query endpoint]
     ↓
[MCPClient.find_codebundle()]
     ↓
[HTTP POST to MCP Server]
     ↓
[MCP tools/codebundle_tools.py]
     ↓
[Generate query embedding] ← Azure OpenAI API
     ↓
[Search ChromaDB]
     ↓
[Rank by cosine similarity]
     ↓
[Format as markdown]
     ↓
[Return to app]
     ↓
[AI synthesizes answer] ← Azure OpenAI API
     ↓
[Return structured response]
     ↓
[Display in Chat UI]


Meanwhile (scheduled):
     ↓
[Celery Beat triggers indexing]
     ↓
[Worker runs mcp_tasks.py]
     ↓
[Executes: python indexer.py --docs-only]
     ↓
[Indexer crawls docs from sources.yaml]
     ↓
[Generate embeddings] ← Azure OpenAI API
     ↓
[Update ChromaDB]
     ↓
[MCP server uses new embeddings immediately]
```

## 🐛 Troubleshooting

### Chat not returning results

1. Check MCP server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check MCP server has data:
   ```bash
   ls -la mcp-server/chroma_db/
   # Should see collection folders
   ```

3. Check embeddings config:
   ```bash
   # In mcp-server/
   cat az.secret | grep AZURE_OPENAI
   ```

### Indexing fails

1. Check worker logs:
   ```bash
   docker-compose logs worker
   ```

2. Run indexer manually to see errors:
   ```bash
   cd mcp-server
   python indexer.py --docs-only
   ```

3. Check Azure OpenAI quota:
   - Rate limits on embedding API
   - Check Azure portal for usage

### Search results not relevant

1. Re-index with latest data:
   ```bash
   cd mcp-server
   python indexer.py
   ```

2. Check embedding document quality:
   ```bash
   # See what text is being embedded
   cat mcp-server/data/codebundles.json | jq '.codebundles[0]'
   ```

3. Adjust search parameters in `mcp_chat.py`:
   - `max_results`: More results → better chance of relevance
   - Filters: Platform, collection filters

---

**Last Updated:** 2026-01-24  
**Related Docs:**
- [MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md) - Automated indexing setup
- [SCHEDULES.md](SCHEDULES.md) - General schedule management
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) - AI service configuration
