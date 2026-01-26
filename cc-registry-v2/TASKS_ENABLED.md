# Task Functions Enabled

## Changes Made

The following task functions in `backend/app/tasks/registry_tasks.py` have been **enabled with real implementations**:

### 1. `sync_all_collections_task()`
**What it does:**
- Loads `/app/codecollections.yaml`
- Creates/updates `CodeCollection` records in the database
- Syncs metadata for all collections

**Returns:**
```python
{
    "status": "success",
    "collections_synced": <count>
}
```

### 2. `parse_all_codebundles_task()`
**What it does:**
- Clones each active collection's Git repository
- Finds `codebundles/` directory
- Parses `runbook.robot` and/or `sli.robot` files
- Extracts tasks, metadata, documentation
- Gets git commit dates (excluding meta.yml updates)
- Creates/updates `Codebundle` records in database

**Returns:**
```python
{
    "status": "success",
    "codebundles_created": <count>,
    "codebundles_updated": <count>
}
```

## Workflow Integration

The `sync_parse_enhance_workflow_task` now works end-to-end:
1. **Step 1**: Sync collections (loads YAML, updates DB)
2. **Step 2**: Parse codebundles (clones repos, parses robot files, creates codebundle records)
3. **Step 3**: Enhance codebundles (AI enhancement for pending items)

## Deployment

After deploying these changes, your scheduled workflows will actually:
- ✅ Sync collection data from YAML
- ✅ Clone repositories
- ✅ Parse robot files
- ✅ Create/update codebundle records
- ✅ Extract tasks and metadata
- ✅ Track git update dates

No more "DISABLED" messages! The tasks will now do real work.

## Testing

```bash
# Rebuild and deploy
docker-compose build backend worker
docker push <your-registry>/cc-registry-v2-backend:latest
docker push <your-registry>/cc-registry-v2-worker:latest

# Restart in K8s
kubectl rollout restart deployment/cc-registry-worker -n registry-test

# Trigger manually to test
curl -X POST http://your-backend/api/v1/admin/trigger-workflow \
  -H "Authorization: Bearer admin-<your-token>"

# Watch logs
kubectl logs -f deployment/cc-registry-worker -n registry-test | grep -E "Synced|Parsed|codebundles"
```

Expected output:
```
Starting sync_all_collections_task...
Loaded 5 collections from YAML
Created collection: runwhen-contrib
...
Synced 5 collections

Starting parse_all_codebundles_task...
Found 5 active collections to parse
Cloning https://github.com/runwhen-contrib/rw-cli-codecollection.git...
Parsing codebundles...
Parsed codebundles: 45 created, 23 updated
```
