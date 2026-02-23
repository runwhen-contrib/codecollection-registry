# MCP Indexing: Scheduled Tasks

Automated and manual indexing of the MCP server's vector search index.

## Scheduled Tasks

Two indexing schedules are defined in `schedules.yaml` under the "MCP Server Indexing" section. They run as Celery tasks dispatched by the Beat scheduler.

### Documentation Indexing (daily)

| Field | Value |
|---|---|
| Schedule name | `index-documentation-daily` |
| Celery task | `app.tasks.mcp_tasks.index_documentation_task` |
| Frequency | Daily at 3:00 AM |
| Enabled | Yes |

Re-indexes documentation sources from `mcp-server/sources.yaml`. Crawls linked URLs, generates embeddings, and writes them to the local vector store (`data/vector_index.json`). Does **not** re-index codebundles.

Typical duration: 5-10 minutes depending on the number of documentation URLs and web crawling speed.

### Full Re-index (weekly)

| Field | Value |
|---|---|
| Schedule name | `reindex-mcp-weekly` |
| Celery task | `app.tasks.mcp_tasks.reindex_all_task` |
| Frequency | Sunday at 2:00 AM |
| Enabled | **No** (disabled by default) |

Complete rebuild of the vector index. Clones/updates all git repos, parses all codebundles and libraries, crawls all documentation, regenerates all embeddings.

Typical duration: 20-30 minutes for the full registry.

Enable it in `schedules.yaml` if you want periodic full refreshes:

```yaml
- name: reindex-mcp-weekly
  enabled: true  # change from false to true
```

Then restart the scheduler:

```bash
docker-compose restart scheduler
```

## Manual Triggers

### From the Admin UI

1. Navigate to Admin Panel, then the Schedules tab
2. Find `index-documentation-daily` or `reindex-mcp-weekly`
3. Click "Run Now"
4. Monitor progress in the Task Manager view

### Via API

```bash
# Documentation indexing
curl -X POST "http://localhost:8001/api/v1/schedules/index-documentation-daily/trigger" \
  -H "Authorization: Bearer $TOKEN"

# Full re-index
curl -X POST "http://localhost:8001/api/v1/schedules/reindex-mcp-weekly/trigger" \
  -H "Authorization: Bearer $TOKEN"
```

### Via command line (direct)

Run the indexer directly without Celery:

```bash
cd mcp-server

# Documentation only (fast)
python indexer.py --docs-only

# Full index (codebundles + libraries + documentation)
python indexer.py

# Specific collection only
python indexer.py --collection rw-cli-codecollection

# Use local embeddings (no Azure OpenAI API calls)
python indexer.py --local
```

## How Scheduled Indexing Works

```
1. Celery Beat (scheduler container) reads schedules.yaml
2. At the scheduled time, Beat dispatches the task to Redis
3. Celery Worker picks up the task from Redis
4. Worker executes mcp_tasks.py::index_documentation_task()
5. Task invokes the indexer as a subprocess:
     cd mcp-server && python indexer.py --docs-only
6. Indexer crawls sources.yaml URLs, generates embeddings, writes vector_index.json
7. Task execution is recorded in the task_executions table
```

## Configuration

### Adjust schedule times

Edit `schedules.yaml`. Crontab fields:

```yaml
crontab:
  hour: 3        # 0-23
  minute: 0      # 0-59
  day_of_week: 0 # 0=Sunday, 1=Monday, ... 6=Saturday (or null for every day)
```

### Enable/disable schedules

Set `enabled: true` or `enabled: false` in `schedules.yaml`, then restart the scheduler:

```bash
docker-compose restart scheduler
```

### Azure OpenAI credentials

The indexer needs embedding API credentials. Set them in `az.secret` (loaded by all backend services via `env_file`):

```bash
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_EMBEDDING_API_KEY=your-key
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

Or fall back to the shared Azure OpenAI credentials:

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
```

If no Azure credentials are available, the indexer falls back to local `sentence-transformers` (lower quality, zero API cost).

## Monitoring

### Check task execution history

- Admin UI: Task Manager tab shows all recent task executions with status, duration, and error messages
- Flower: http://localhost:5555 for real-time Celery monitoring

### Check worker and scheduler logs

```bash
docker logs registry-worker --tail=100
docker logs registry-scheduler --tail=100
```

### Verify the MCP server has indexed data

```bash
curl http://localhost:8000/health
```

The `data_stats` field shows counts for codebundles, collections, libraries, and documentation.

## Sync vs Index

These are separate processes that serve different purposes:

| | Sync (registry_tasks) | Index (mcp_tasks / indexer.py) |
|---|---|---|
| **Writes to** | PostgreSQL (backend database) | `data/vector_index.json` (local file) |
| **Used by** | Web UI for browsing, REST API for querying | Semantic search (MCP server, when vector store is active) |
| **Data source** | GitHub repos (clone + parse) | GitHub repos (clone + parse) + documentation URLs |
| **Schedule** | Every 6 hours (`scheduled-sync`) | Daily at 3 AM (`index-documentation-daily`) |
| **Generates embeddings** | No | Yes (Azure OpenAI or local) |

Both read from the same GitHub repos but maintain separate data stores.

## Troubleshooting

### Task not running on schedule

1. Check that the scheduler container is running:
   ```bash
   docker ps | grep scheduler
   ```
2. Verify the schedule is enabled in `schedules.yaml`
3. Check scheduler logs for errors:
   ```bash
   docker logs registry-scheduler --tail=50
   ```

### Indexing task failing

1. Check worker logs:
   ```bash
   docker logs registry-worker --tail=100
   ```
2. Run the indexer manually to see detailed errors:
   ```bash
   cd mcp-server && python indexer.py --docs-only
   ```
3. Common causes:
   - Azure OpenAI credentials missing or expired
   - Network connectivity issues for web crawling
   - Git clone failures (authentication, network)

### Embeddings not generating

Verify Azure OpenAI credentials are set:

```bash
# Check if the env vars are reaching the worker
docker exec registry-worker env | grep AZURE_OPENAI
```

Or bypass the API entirely with local embeddings:

```bash
cd mcp-server && python indexer.py --local --docs-only
```

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture
- [MCP_WORKFLOW.md](MCP_WORKFLOW.md) -- Complete indexing pipeline details
- [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables reference
- [SCHEDULES.md](SCHEDULES.md) -- General schedule management
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI credential setup
