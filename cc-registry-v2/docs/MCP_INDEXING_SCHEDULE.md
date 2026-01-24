# MCP Server Documentation Indexing - Scheduled Tasks

## Overview

Automated scheduled tasks have been added to keep the MCP server's documentation embeddings up to date.

## New Scheduled Tasks

### 1. Documentation Indexing (Daily)

**Schedule:** `index-documentation-daily`
- **Runs:** Daily at 3:00 AM
- **Status:** ✅ Enabled
- **Task:** `app.tasks.mcp_tasks.index_documentation_task`

**What it does:**
- Re-indexes documentation sources from `mcp-server/docs.yaml` or `sources.yaml`
- Crawls linked documentation pages for content
- Generates fresh embeddings for all documentation
- Updates the vector database (ChromaDB)
- **Does NOT** re-index codebundles (faster, more focused)

**Duration:** ~5-10 minutes depending on doc count

**Use case:** Keep documentation search results fresh when docs are updated

---

### 2. Full MCP Re-index (Weekly)

**Schedule:** `reindex-mcp-weekly`
- **Runs:** Sunday at 2:00 AM
- **Status:** ⚠️ **Disabled by default**
- **Task:** `app.tasks.mcp_tasks.reindex_all_task`

**What it does:**
- Complete rebuild of the entire vector database
- Re-indexes ALL codebundles from scratch
- Re-indexes ALL documentation sources
- Regenerates ALL embeddings
- Completely refreshes the semantic search index

**Duration:** ~20-30 minutes for full registry

**Use case:** Periodic maintenance, fixing index corruption, major updates

---

## Manual Triggering

### Via Admin UI

1. Go to Admin Panel → Schedules tab
2. Find the schedule you want to run
3. Click "Run Now"

### Via API

```bash
# Trigger documentation indexing
curl -X POST "http://localhost:8001/api/v1/schedules/index-documentation-daily/trigger" \
  -H "Authorization: Bearer admin-dev-token"

# Trigger full re-index
curl -X POST "http://localhost:8001/api/v1/schedules/reindex-mcp-weekly/trigger" \
  -H "Authorization: Bearer admin-dev-token"
```

### Via Command Line (Direct)

```bash
# Documentation only (fast)
cd mcp-server
python indexer.py --docs-only

# Full re-index (slow)
cd mcp-server
python indexer.py
```

---

## Configuration

### Enable/Disable Schedules

Edit `cc-registry-v2/schedules.yaml`:

```yaml
# Enable daily documentation indexing
- name: index-documentation-daily
  enabled: true   # Change to false to disable

# Enable weekly full re-index
- name: reindex-mcp-weekly
  enabled: true   # Change to false to disable
```

After changes:
```bash
docker-compose restart scheduler
```

### Adjust Schedule Times

**Documentation indexing:**
```yaml
crontab:
  hour: 3      # 0-23 (3 AM)
  minute: 0
```

**Full re-index:**
```yaml
crontab:
  hour: 2           # 0-23 (2 AM)
  minute: 0
  day_of_week: 0    # 0=Sunday, 1=Monday, ..., 6=Saturday
```

---

## Monitoring

### Check Task Status

1. **Admin UI:** Go to Admin Panel → Schedules tab
2. **Task Manager:** Go to `/tasks` to see execution history
3. **Logs:**
   ```bash
   # Scheduler logs
   docker logs registry-scheduler --tail=100
   
   # Worker logs
   docker logs registry-worker --tail=100
   ```

### Task Execution Records

Tasks are tracked in the `task_executions` table with:
- Start/end timestamps
- Duration
- Success/failure status
- Error messages if failed
- Full output logs

### MCP Server Health

Check that the MCP server has indexed data:
```bash
curl http://localhost:8000/health
```

Should show:
```json
{
  "status": "healthy",
  "stats": {
    "codebundles": 387,
    "documentation": 50,  // Should be non-zero
    "libraries": 45
  }
}
```

---

## Troubleshooting

### Documentation not updating

1. **Check if task ran:**
   - Go to Task Manager and search for "index_documentation"
   - Check if it completed successfully

2. **Check MCP server logs:**
   ```bash
   docker logs mcp-server --tail=100
   ```

3. **Manually trigger:**
   ```bash
   cd mcp-server
   python indexer.py --docs-only
   ```

4. **Verify docs.yaml exists:**
   ```bash
   ls -la mcp-server/docs.yaml
   ls -la mcp-server/sources.yaml
   ```

### Task timing out

The tasks have generous timeouts:
- Documentation indexing: 10 minutes
- Full re-index: 30 minutes

If hitting timeouts, check:
- Network connectivity for web crawling
- Azure OpenAI API availability
- Disk space for vector database

### Embeddings not generating

Check Azure OpenAI credentials in the MCP server environment:
```bash
# In mcp-server/.env
AZURE_OPENAI_EMBEDDING_ENDPOINT=...
AZURE_OPENAI_EMBEDDING_API_KEY=...
```

Or use local embeddings:
```bash
cd mcp-server
python indexer.py --local --docs-only
```

---

## Files Created/Modified

### New Files
- `backend/app/tasks/mcp_tasks.py` - MCP indexing tasks

### Modified Files
- `backend/app/tasks/__init__.py` - Added mcp_tasks import
- `schedules.yaml` - Added index-documentation-daily and reindex-mcp-weekly

---

## Next Steps

1. **Test the daily schedule:** Wait for 3 AM or manually trigger via Admin UI
2. **Consider enabling weekly re-index:** Set `enabled: true` if you want periodic full refreshes
3. **Monitor execution:** Check Task Manager for successful runs
4. **Adjust timing:** Change schedule times if 3 AM doesn't work for your timezone

---

## Related Documentation

- `MCP_SERVER_INTEGRATION.md` - MCP server setup and configuration
- `DEPLOYMENT_GUIDE.md` - Overall deployment guide
- `schedules.yaml` - Full schedule configuration reference
