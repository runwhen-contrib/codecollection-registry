# Workflow Task Fix - Run Now Button Issue

## Problem

When clicking the "Run Now" button for the `update-workflow-every-4h` schedule:
- The workflow task would start and complete
- BUT the subtasks (sync, parse, enhance) would be created as PENDING in the database
- These subtasks were NEVER dispatched to Celery workers
- They just sat in PENDING state forever with no indication of why
- Result: New codebundles (like `cron-scheduler-sli`) were not imported

## Root Cause

The workflow task in `workflow_tasks.py` was using `.apply().get()` to run subtasks:

```python
# WRONG - runs task locally in current process, not via worker
sync_result = sync_all_collections_task.apply().get()
parse_result = parse_all_codebundles_task.apply().get()
enhance_result = enhance_pending_codebundles_task.apply(kwargs={'limit': limit}).get()
```

**Issue with `.apply()`:**
- `.apply()` executes the task **synchronously in the current process** (bypasses Celery workers)
- When called from within a worker, it creates task monitoring records but doesn't properly execute
- This resulted in orphaned PENDING tasks that never ran

## Solution

Changed to use `.apply_async().get(timeout=X)` which properly dispatches tasks to workers:

```python
# CORRECT - dispatches to worker, waits for result
sync_result = sync_all_collections_task.apply_async().get(timeout=300)
parse_result = parse_all_codebundles_task.apply_async().get(timeout=600)
enhance_result = enhance_pending_codebundles_task.apply_async(kwargs={'limit': limit}).get(timeout=1800)
```

**Why this works:**
- `.apply_async()` sends the task to Celery workers via the message broker (Redis)
- `.get(timeout=X)` waits for the task to complete with a timeout
- Tasks are properly tracked and executed by workers
- The workflow orchestration works as intended

## Timeouts

Set reasonable timeouts for each step:
- **Sync collections**: 300s (5 minutes) - just git operations
- **Parse codebundles**: 600s (10 minutes) - parsing robot files
- **AI enhance**: 1800s (30 minutes) - API calls can be slow
- **Quick workflow**: 3600s (1 hour) - sum of all steps

## Testing

To test the fix, click "Run Now" on the `update-workflow-every-4h` schedule:

1. The workflow task should start and show progress
2. Subtasks should appear in the Task Manager as STARTED (not stuck in PENDING)
3. Each subtask should complete successfully
4. New codebundles should be imported

## Files Changed

- `cc-registry-v2/backend/app/tasks/workflow_tasks.py`
  - Changed `.apply()` to `.apply_async()` in 4 places
  - Added appropriate timeouts for each subtask

## Related Issues

This also explains why:
- The scheduled workflow (every 4 hours) might have been silently failing
- Manual sync/parse operations via admin API worked fine
- Task history showed SUCCESS for workflows but no actual work was done
