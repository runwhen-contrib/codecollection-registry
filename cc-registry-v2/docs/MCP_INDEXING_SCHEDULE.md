# Indexing and Scheduled Tasks

Scheduled tasks that keep the registry data current, and the offline MCP indexer.

## Production Schedules

These tasks run in production and keep the PostgreSQL database up to date. All are defined in `schedules.yaml` and dispatched by Celery Beat.

### Sync-Parse-Enhance Workflow (every 6 hours)

| Field | Value |
|---|---|
| Schedule name | `scheduled-sync` |
| Celery task | `app.tasks.workflow_tasks.sync_parse_enhance_workflow_task` |
| Frequency | Every 6 hours (midnight, 6 AM, noon, 6 PM) |
| Enabled | Yes |

This is the primary data ingestion pipeline. It runs three steps in sequence:

1. **Sync** -- Clone or pull all CodeCollection git repos
2. **Parse** -- Extract codebundles, tasks, SLIs, metadata from repos into PostgreSQL
3. **Enhance** -- AI-enhance only NEW codebundles (pending/NULL status) via Azure OpenAI GPT

This is what populates the `codebundles` table that all search queries operate on.

Typical duration: 10-20 minutes depending on repo count and number of new codebundles to enhance.

### Statistics Update (hourly)

| Field | Value |
|---|---|
| Schedule name | `update-statistics-hourly` |
| Celery task | `app.tasks.data_population_tasks.update_collection_statistics_task` |
| Frequency | Every hour |
| Enabled | Yes |

Refreshes collection-level statistics (codebundle counts, task totals, etc.).

### Other Production Schedules

| Schedule | Frequency | Purpose |
|---|---|---|
| `validate-yaml-seed-daily` | Daily 1 AM | Ensure all YAML-defined collections exist in database |
| `compute-task-growth-analytics` | Daily 2:30 AM | Analyze git history for task growth metrics |
| `health-check` | Every 5 min | System health check |
| `health-check-tasks` | Every 10 min | Task queue and worker health |
| `cleanup-old-tasks` | Daily 12:30 AM | Purge old task execution records |

## MCP Indexer Schedules (Development / Future)

These tasks shell out to `mcp-server/indexer.py` as a subprocess. The indexer generates vector embeddings and writes them to `data/vector_index.json`. This output is **not used by the production search path** -- the MCP HTTP server queries the backend API for keyword-based search instead.

These schedules exist as infrastructure for a future migration to vector similarity search.

### Documentation Indexing (daily)

| Field | Value |
|---|---|
| Schedule name | `index-documentation-daily` |
| Celery task | `app.tasks.mcp_tasks.index_documentation_task` |
| Frequency | Daily at 3:00 AM |
| Enabled | Yes (but output not used in production search) |

Re-indexes documentation sources from `mcp-server/sources.yaml`. Crawls linked URLs, generates embeddings, and writes them to `data/vector_index.json`.

### Full Re-index (weekly)

| Field | Value |
|---|---|
| Schedule name | `reindex-mcp-weekly` |
| Celery task | `app.tasks.mcp_tasks.reindex_all_task` |
| Frequency | Sunday at 2:00 AM |
| Enabled | **No** (disabled by default) |

Complete rebuild of the local vector index. Clones/updates all git repos, parses all codebundles and libraries, crawls all documentation, regenerates all embeddings.

Enable in `schedules.yaml` if needed for development:

```yaml
- name: reindex-mcp-weekly
  enabled: true
```

Then restart the scheduler:

```bash
docker-compose restart scheduler
```

## Manual Triggers

### From the Admin UI

1. Navigate to Admin Panel, then the Schedules tab
2. Find any schedule
3. Click "Run Now"
4. Monitor progress in the Task Manager view

### Via API

```bash
# Trigger the sync-parse-enhance workflow (production)
curl -X POST "http://localhost:8001/api/v1/schedules/scheduled-sync/trigger" \
  -H "Authorization: Bearer $TOKEN"

# Trigger documentation indexing (development)
curl -X POST "http://localhost:8001/api/v1/schedules/index-documentation-daily/trigger" \
  -H "Authorization: Bearer $TOKEN"
```

### Via command line (indexer only)

Run the MCP indexer directly without Celery:

```bash
cd mcp-server

# Documentation only (fast)
python indexer.py --docs-only

# Full index (codebundles + libraries + documentation)
python indexer.py

# Specific collection
python indexer.py --collection rw-cli-codecollection

# Use local embeddings (no Azure OpenAI API calls)
python indexer.py --local
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

The sync-parse-enhance workflow needs GPT credentials (for AI enhancement). The MCP indexer needs embedding credentials (for vector generation).

See [CONFIGURATION.md](CONFIGURATION.md) for environment variable details and [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) for setup instructions.

## Monitoring

### Check task execution history

- Admin UI: Task Manager tab shows all recent task executions with status, duration, and error messages
- Flower: http://localhost:5555 for real-time Celery monitoring

### Check worker and scheduler logs

```bash
docker logs registry-worker --tail=100
docker logs registry-scheduler --tail=100
```

### Verify data is current

```bash
# Check codebundle count in the database
curl "http://localhost:8001/api/v1/codebundles?limit=1" | python -m json.tool | grep total_count

# Check MCP server health (stats come from backend API)
curl http://localhost:8000/health
```

## Troubleshooting

### Sync workflow not running

1. Check that the scheduler container is running:
   ```bash
   docker ps | grep scheduler
   ```
2. Verify the schedule is enabled in `schedules.yaml`
3. Check scheduler logs:
   ```bash
   docker logs registry-scheduler --tail=50
   ```

### Codebundles not updating after repo changes

1. Check worker logs for sync errors:
   ```bash
   docker logs registry-worker --tail=100 | grep -i "sync\|parse\|error"
   ```
2. Trigger the workflow manually from Admin UI
3. Common causes:
   - Git authentication failures
   - Network connectivity issues
   - Database connection errors

### AI enhancement not running

1. Check Azure OpenAI GPT credentials are set:
   ```bash
   docker exec registry-worker env | grep AZURE_OPENAI
   ```
2. Check worker logs for enhancement errors
3. Enhancement only runs on NEW codebundles (status NULL or 'pending')

### MCP indexer failing (development)

1. Run manually to see errors:
   ```bash
   cd mcp-server && python indexer.py --docs-only
   ```
2. Check Azure OpenAI embedding credentials
3. Use local embeddings to bypass: `python indexer.py --local`

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture
- [MCP_WORKFLOW.md](MCP_WORKFLOW.md) -- Complete search and indexing flow details
- [CONFIGURATION.md](CONFIGURATION.md) -- Environment variables reference
- [SCHEDULES.md](SCHEDULES.md) -- General schedule format reference
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI credential setup
