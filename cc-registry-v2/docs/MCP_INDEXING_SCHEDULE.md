# Indexing and Scheduled Tasks

Scheduled tasks that keep the registry data and vector embeddings current. All tasks are defined in `schedules.yaml` and dispatched by Celery Beat.

## Sync-Parse-Enhance-Embed Workflow (every 6 hours)

| Field | Value |
|---|---|
| Schedule name | `scheduled-sync` |
| Celery task | `app.tasks.workflow_tasks.sync_parse_enhance_workflow_task` |
| Frequency | Every 6 hours (midnight, 6 AM, noon, 6 PM) |
| Enabled | Yes |

The primary data pipeline runs four steps in sequence:

1. **Sync** — Clone or pull all CodeCollection git repos
2. **Parse** — Walk repos, parse `meta.yaml` + `*.robot` files, upsert into PostgreSQL
3. **AI Enhance** — Send new/pending codebundles to Azure OpenAI GPT for metadata enrichment
4. **Embed** — Generate embeddings via Azure OpenAI text-embedding-3-small, upsert into pgvector tables (`vector_codebundles`, `vector_codecollections`)

## Documentation Indexing (daily)

| Field | Value |
|---|---|
| Schedule name | `index-documentation-daily` |
| Celery task | `app.tasks.indexing_tasks.index_documentation_task` |
| Frequency | Daily at 3:00 AM UTC |
| Enabled | Yes |

Crawls documentation URLs defined in `sources.yaml`, generates embeddings, and stores them in `vector_documentation`.

Steps:
1. Load documentation entries from `sources.yaml`
2. Crawl each URL with httpx + BeautifulSoup
3. Build searchable document text from crawled content
4. Generate embeddings
5. Upsert into `vector_documentation`

## Full Vector Reindex (weekly)

| Field | Value |
|---|---|
| Schedule name | `reindex-vectors-weekly` |
| Celery task | `app.tasks.indexing_tasks.reindex_all_task` |
| Frequency | Sunday at 2:00 AM UTC |
| Enabled | Yes |

Rebuilds all vector tables from scratch (codebundles + codecollections + documentation). Useful for recovering from drift or after schema changes.

## Other Schedules

| Schedule | Frequency | Task | Purpose |
|---|---|---|---|
| `validate-yaml-seed-daily` | Daily 1 AM | `sync_all_collections_task` | Ensure all YAML-defined collections exist in the database |
| `update-statistics-hourly` | Hourly | `update_collection_statistics_task` | Refresh collection statistics |
| `compute-task-growth-analytics` | Daily 2:30 AM | `compute_task_growth_analytics` | Analyze git history for task growth |
| `health-check` | Every 5 min | `health_check_task` | System health check |
| `health-check-tasks` | Every 10 min | `health_check_tasks_task` | Task queue health check |
| `cleanup-old-tasks` | Daily 12:30 AM | `cleanup_old_tasks_task` | Purge old task execution records |

## Manual Triggers

All indexing tasks can be triggered manually via the Admin UI or the API:

```bash
# Trigger full vector reindex
curl -X POST http://localhost:8001/api/v1/vector/reindex

# Trigger codebundle embedding only
curl -X POST http://localhost:8001/api/v1/vector/reindex/codebundles

# Trigger documentation embedding only
curl -X POST http://localhost:8001/api/v1/vector/reindex/documentation

# Check vector table stats
curl http://localhost:8001/api/v1/vector/stats
```

## Configuration

Embedding generation requires Azure OpenAI credentials. Set these in `az.secret` or as environment variables:

| Variable | Purpose | Required |
|---|---|---|
| `AZURE_OPENAI_EMBEDDING_ENDPOINT` | Dedicated embedding endpoint (falls back to `AZURE_OPENAI_ENDPOINT`) | If using dedicated endpoint |
| `AZURE_OPENAI_EMBEDDING_API_KEY` | Dedicated embedding API key (falls back to `AZURE_OPENAI_API_KEY`) | If using dedicated key |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Deployment name (default: `text-embedding-3-small`) | No |
| `EMBEDDING_BATCH_SIZE` | Texts per API call (default: `100`) | No |

> **Note:** Vector dimensions are fixed at **1536** to match the `text-embedding-3-small` model and the database schema. This is not configurable.

If embedding credentials are not configured, the embedding step is silently skipped and vector tables remain empty. Keyword search continues to work.
