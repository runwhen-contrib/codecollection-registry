# Schedule Management & Job History Feature

## Overview
Added comprehensive schedule management and job history viewing capabilities to the Admin Panel.

## What Was Added

### Backend APIs

#### 1. Schedule Configuration API (`/api/v1/schedule/schedules`)
**File:** `backend/app/routers/schedule_config.py`

New endpoints:
- `GET /api/v1/schedule/schedules` - Get all configured schedules
- `GET /api/v1/schedule/schedules/{schedule_name}` - Get specific schedule details
- `PUT /api/v1/schedule/schedules/{schedule_name}` - Update schedule (provides instructions)
- `POST /api/v1/schedule/schedules/{schedule_name}/trigger` - Manually trigger a scheduled task

Features:
- View all current Celery Beat schedules with human-readable descriptions
- See schedule types (crontab vs interval)
- Manually trigger any scheduled task immediately
- Get instructions for how to modify schedules (requires celery_app.py edit + restart)

#### 2. Task History API (Already existed, now integrated)
**File:** `backend/app/routers/task_management.py`

Existing endpoints now integrated into Admin UI:
- `GET /api/v1/task-management/tasks` - Get task execution history
- `GET /api/v1/task-management/tasks/running` - Get currently running tasks
- `GET /api/v1/task-management/tasks/{task_id}` - Get specific task status
- `GET /api/v1/task-management/stats` - Get task execution statistics
- `POST /api/v1/task-management/cleanup` - Clean up old tasks

### Frontend UI

#### 1. Admin Panel Updates
**File:** `frontend/src/pages/Admin.tsx`

Added two new tabs to the Admin Panel:

##### Tab 3: Job History
Shows:
- Task statistics (last 7 days)
  - Total tasks executed
  - Currently running tasks
  - Success/failure counts
  - Average task duration
- Recent task execution history table with:
  - Task name and type
  - Status (SUCCESS, FAILURE, PENDING, STARTED)
  - Start time
  - Duration
  - Progress percentage
- Auto-refreshes every 30 seconds when viewing this tab
- Manual refresh button

##### Tab 4: Schedules
Shows:
- All configured Celery Beat schedules
- For each schedule:
  - Task name and description
  - Schedule (e.g., "Daily at 2 AM", "Every 5 minutes")
  - Schedule type (crontab/interval)
  - Active status
  - Task path
  - "Run Now" button to trigger immediately

Features:
- View all 10 configured schedules
- One-click manual triggering of any scheduled task
- Information banner about how schedules work
- Clean, card-based UI for each schedule

#### 2. API Service Methods
**File:** `frontend/src/services/api.ts`

Added methods:
- `getSchedules(token)` - Fetch all schedules
- `getSchedule(scheduleName, token)` - Get specific schedule
- `updateSchedule(scheduleName, scheduleData, token)` - Update schedule
- `triggerScheduleNow(scheduleName, token)` - Manually trigger
- `getTaskHistory(params, token)` - Get task history with filters
- `getRunningTasks(token)` - Get currently running tasks
- `getTaskStatus(taskId, token)` - Get specific task status
- `getTaskStats(days, token)` - Get task statistics
- `cleanupOldTasks(days, token)` - Clean up old tasks

## Current Schedules

The system has 10 configured schedules:

1. **validate-yaml-seed-daily** - Daily at 1:00 AM
   - Validates YAML entries exist in database

2. **sync-collections-daily** - Daily at 2:00 AM
   - Syncs all collections from YAML

3. **parse-codebundles-daily** - Daily at 3:00 AM
   - Parses all codebundles from repositories

4. **enhance-codebundles-weekly** - Weekly on Monday at 4:00 AM
   - Runs AI enhancement on codebundles

5. **generate-metrics-daily** - Daily at 5:00 AM
   - Generates daily metrics and statistics

6. **scheduled-sync** - Daily at 6:00 AM
   - Full registry population (main sync job)

7. **update-statistics-hourly** - Every hour
   - Updates collection statistics

8. **health-check** - Every 5 minutes
   - System health check

9. **cleanup-old-tasks** - Daily at 12:30 AM
   - Cleans up old completed tasks

10. **health-check-tasks** - Every 10 minutes
    - Health check for task queues and workers

## How to Modify Schedules

Currently, schedules are **hardcoded** in `backend/app/tasks/celery_app.py`. To change them:

1. Edit the `beat_schedule` dictionary in `celery_app.py`
2. Modify the crontab times or intervals as needed
3. Restart the Celery Beat scheduler service

### Example: Change sync time from 2 AM to 3 AM

```python
'sync-collections-daily': {
    'task': 'app.tasks.registry_tasks.sync_all_collections_task',
    'schedule': crontab(hour=3, minute=0),  # Changed from hour=2
},
```

Then restart:
```bash
docker-compose restart scheduler
```

## Future Enhancements

To make schedules truly dynamic (editable via UI without restart), you would need to:

1. Implement database-backed schedules using a library like `django-celery-beat`
2. Store schedule configurations in the database
3. Use Celery's dynamic task registration
4. Add UI forms to modify cron expressions
5. Implement real-time schedule updates

For now, the UI provides:
- ✅ View all schedules
- ✅ Manually trigger any schedule
- ✅ View complete task execution history
- ✅ Monitor running tasks
- ✅ Task statistics and metrics
- ⏳ Dynamic schedule editing (requires architecture change)

## Testing

To test the new features:

1. Start the services:
   ```bash
   cd /workspaces/codecollection-registry/cc-registry-v2
   task start
   ```

2. Open the Admin Panel:
   ```
   http://localhost:3000/admin
   ```

3. **Login credentials:**
   - Email: `admin@runwhen.com`
   - Password: `admin-dev-password` (NOT the token!)

4. Click on the "Job History" tab to see recent task executions

5. Click on the "Schedules" tab to see all configured schedules:
   - validate-yaml-seed-daily: Daily at 01:00
   - sync-collections-daily: Daily at 02:00
   - parse-codebundles-daily: Daily at 03:00
   - enhance-codebundles-weekly: Weekly on Monday at 04:00
   - generate-metrics-daily: Daily at 05:00
   - update-statistics-hourly: Every hour
   - health-check: Every 5 minutes
   - scheduled-sync: Daily at 06:00
   - cleanup-old-tasks: Daily at 00:30
   - health-check-tasks: Every 10 minutes

6. Try clicking "Run Now" on any schedule to trigger it immediately

7. Go back to "Job History" tab to see the triggered task appear

## Bug Fixes Applied

### Issue: Empty schedules page with "unhashable type: 'set'" error
**Root Cause:** Celery's crontab objects return sets for hour/minute values when they represent multiple values (like `crontab(minute='*/5')` or `crontab(hour='*')`). Python sets cannot be directly serialized to JSON.

**Fix:** Updated `schedule_config.py` to properly handle sets by converting them to lists and formatting them into human-readable strings.

**Changes:**
- Added set detection and conversion logic
- Improved schedule value formatting for:
  - Single time values: "Daily at 02:00"
  - Weekly schedules: "Weekly on Monday at 04:00"  
  - Hourly schedules: "Every hour"
  - Interval schedules: "Every 5 minutes"
  - Custom schedules: Displays hour/minute ranges

## Files Modified

### Backend
- ✅ `backend/app/routers/schedule_config.py` (NEW)
- ✅ `backend/app/main.py` (added schedule_config router)
- ✅ `backend/app/services/task_monitoring_service.py` (added missing import)

### Frontend
- ✅ `frontend/src/services/api.ts` (added schedule & task history methods)
- ✅ `frontend/src/pages/Admin.tsx` (added new tabs and UI)

## Summary

The Admin Panel now provides comprehensive visibility into:
- **What's scheduled**: All 10 automated tasks with their schedules
- **What's running**: Currently executing tasks with real-time status
- **What happened**: Complete history of task executions with statistics
- **Manual control**: Ability to trigger any scheduled task on-demand

This addresses the original request to show job history and make schedule information visible in the admin UI. While the schedules themselves still need to be modified in code (a design decision to keep things simple), the UI now provides full transparency and control over the scheduling system.
