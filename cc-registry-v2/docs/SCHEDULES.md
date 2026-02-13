# Schedule Configuration Guide

## Overview

All scheduled tasks are configured in **`schedules.yaml`** at the project root. Edit this file to change when tasks run - no code changes needed!

## Quick Start

### View Current Schedules

**Admin UI**: http://localhost:3000/admin → "Schedules" tab

You'll see all configured schedules with their timing and descriptions.

### The Main Workflow (Every 4 Hours)

**`update-workflow-every-4h`** automatically:
1. ✅ Syncs codecollection repos
2. ✅ Parses Robot Framework files
3. ✅ AI enhances ONLY NEW codebundles

This runs every 4 hours and only processes new content (cost-efficient).

### Edit Schedule Frequency

1. Open `schedules.yaml` in project root
2. Find the workflow:
   ```yaml
   - name: update-workflow-every-4h
     task: app.tasks.workflow_tasks.sync_parse_enhance_workflow_task
     schedule_type: interval
     interval:
       hours: 4  # ← Change this
     enabled: true
   ```
3. Modify the interval
4. Restart: `docker-compose restart scheduler`

## Schedule Types

### Interval (Run Every N Hours/Minutes)

```yaml
schedule_type: interval
interval:
  hours: 4       # Every 4 hours
  # OR
  minutes: 30    # Every 30 minutes
  # OR  
  seconds: 60    # Every 60 seconds
```

**Examples:**
```yaml
# Every 2 hours
interval:
  hours: 2

# Every 15 minutes
interval:
  minutes: 15
```

### Crontab (Run at Specific Times)

```yaml
schedule_type: crontab
crontab:
  hour: 2        # 0-23, or null for every hour
  minute: 0      # 0-59, or null for every minute
  day_of_week: null    # 0-6 (0=Sunday, 1=Monday), or null
  day_of_month: null   # 1-31, or null
  month_of_year: null  # 1-12, or null
```

**Examples:**
```yaml
# Daily at 2 AM
crontab:
  hour: 2
  minute: 0

# Every Monday at 4 AM
crontab:
  hour: 4
  minute: 0
  day_of_week: 1

# Every hour on the hour
crontab:
  hour: null  # every hour
  minute: 0

# First day of every month at midnight
crontab:
  hour: 0
  minute: 0
  day_of_month: 1
```

## Current Schedules

| Schedule | Frequency | Description |
|----------|-----------|-------------|
| **update-workflow-every-4h** | **Every 4 hours** | **Main workflow: sync → parse → enhance NEW** |
| validate-yaml-seed-daily | Daily at 01:00 | Validates YAML consistency |
| generate-metrics-daily | Daily at 05:00 | Generates system metrics |
| scheduled-sync | Daily at 06:00 | Legacy full sync |
| update-statistics-hourly | Every hour | Updates collection statistics |
| health-check | Every 5 minutes | System health check |
| cleanup-old-tasks | Daily at 00:30 | Cleans old task records |
| health-check-tasks | Every 10 minutes | Task queue health check |

## Enable/Disable Schedules

To disable a schedule without deleting it:

```yaml
- name: some-task
  task: app.tasks.some_module.some_task
  interval:
    hours: 4
  enabled: false  # ← Set to false to disable
```

The schedule will remain in the file but won't run until you set `enabled: true` again.

## Add a New Schedule

```yaml
- name: my-custom-task
  task: app.tasks.my_module.my_task_function
  description: What this task does
  schedule_type: interval
  interval:
    hours: 6
  enabled: true
```

Then restart the scheduler: `docker-compose restart scheduler`

## Manual Execution

### From Admin UI

1. Go to http://localhost:3000/admin
2. Click "Schedules" tab
3. Find the schedule
4. Click "Run Now"
5. Check "Job History" tab for results

### From Command Line

```bash
# Run the main workflow manually
docker exec registry-worker celery -A app.tasks.celery_app call \
  app.tasks.workflow_tasks.sync_parse_enhance_workflow_task
```

## Monitoring

### Job History

**Admin UI**: http://localhost:3000/admin → "Job History" tab

View:
- Recent task executions
- Success/failure status
- Execution duration
- Error messages

### Flower UI

**Flower**: http://localhost:5555

Monitor:
- Active tasks
- Task progress
- Worker health
- Queue lengths

## Workflow Details

### What Gets Enhanced?

The workflow only enhances codebundles where:
- `enhancement_status IS NULL` (never enhanced)
- `enhancement_status = 'pending'` (needs enhancement)

Already-enhanced codebundles are **skipped** to save API costs.

### Workflow Steps

1. **Sync** - `app.tasks.registry_tasks.sync_all_collections_task`
   - Clones/pulls git repos
   - Detects new codebundles

2. **Parse** - `app.tasks.registry_tasks.parse_all_codebundles_task`
   - Parses Robot Framework files
   - Extracts tasks and metadata

3. **Enhance** - `app.tasks.ai_enhancement_tasks.enhance_pending_codebundles_task`
   - AI enhances NEW codebundles only
   - Generates descriptions and classifications

## Cost Control

### Limit AI Enhancement

To control API costs, you can limit how many codebundles are enhanced per run.

Edit `backend/app/tasks/workflow_tasks.py`:

```python
# Current: enhance ALL pending
sync_parse_enhance_workflow_task(limit=None)

# Limit to 20 per run
sync_parse_enhance_workflow_task(limit=20)
```

Or create a new schedule with a limit in `schedules.yaml`.

### Reduce Frequency

```yaml
interval:
  hours: 8  # Run every 8 hours instead of 4
```

## Troubleshooting

### Schedules not running?

1. Check if enabled:
   ```bash
   grep -A5 "update-workflow" schedules.yaml
   ```

2. Check scheduler logs:
   ```bash
   docker logs registry-scheduler --tail 50
   ```

3. Restart scheduler:
   ```bash
   docker-compose restart scheduler
   ```

### Verify schedules loaded

```bash
curl -s http://localhost:8001/api/v1/schedule/schedules \
  -H "Authorization: Bearer admin-dev-token" | python3 -m json.tool
```

### Check workflow execution

```bash
# View worker logs
docker logs registry-worker --tail 100

# View scheduler logs
docker logs registry-scheduler --tail 100
```

## Best Practices

1. **Start conservative** - Begin with longer intervals (6-8 hours)
2. **Monitor costs** - Check Azure OpenAI usage regularly
3. **Use limits** - Add AI enhancement limits for cost control
4. **Test manually** - Use "Run Now" button to test before scheduling
5. **Check logs** - Monitor Job History for errors

## File Locations

- **Schedule config**: `cc-registry-v2/schedules.yaml`
- **Workflow code**: `cc-registry-v2/backend/app/tasks/workflow_tasks.py`
- **Task implementations**: `cc-registry-v2/backend/app/tasks/`

## Summary

✅ Edit `schedules.yaml` to change task timing  
✅ Restart scheduler to apply changes  
✅ Monitor via Admin UI Job History  
✅ Main workflow runs every 4 hours  
✅ Only NEW codebundles are enhanced  
✅ Cost-efficient and automated  

For more details, see the inline comments in `schedules.yaml`.
