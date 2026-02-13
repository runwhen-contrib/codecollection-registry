"""
Schedule Configuration API - Manage Celery Beat schedules
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/schedule", tags=["schedule-config"])

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials


class ScheduleInfo(BaseModel):
    """Schedule information"""
    task_name: str
    task_path: str
    schedule_type: str  # crontab, interval
    schedule_value: str  # e.g., "Daily at 2 AM", "Every hour"
    cron_hour: int = None
    cron_minute: int = None
    cron_day_of_week: str = None
    interval_minutes: int = None
    description: str
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    """Update schedule configuration"""
    cron_hour: int = None
    cron_minute: int = None
    cron_day_of_week: str = None
    interval_minutes: int = None
    is_active: bool = None


@router.get("/schedules")
async def get_schedules(token: str = Depends(verify_admin_token)) -> Dict[str, Any]:
    """Get all configured schedules from celery_app.py"""
    try:
        from app.tasks.celery_app import celery_app
        
        schedules = []
        beat_schedule = celery_app.conf.beat_schedule
        
        for schedule_name, schedule_config in beat_schedule.items():
            task_path = schedule_config['task']
            schedule_obj = schedule_config['schedule']
            
            # Parse schedule information
            schedule_type = "crontab"
            schedule_value = ""
            cron_hour = None
            cron_minute = None
            cron_day_of_week = None
            interval_minutes = None
            
            # Extract schedule details - handle both crontab and interval types
            if hasattr(schedule_obj, 'run_every'):
                # Interval schedule - run_every is a timedelta object
                from datetime import timedelta
                interval_td = schedule_obj.run_every
                interval_seconds = interval_td.total_seconds() if isinstance(interval_td, timedelta) else interval_td
                
                if interval_seconds >= 86400:
                    days = int(interval_seconds / 86400)
                    schedule_value = f"Every {days} day{'s' if days > 1 else ''}"
                    schedule_type = "interval"
                elif interval_seconds >= 3600:
                    hours = int(interval_seconds / 3600)
                    schedule_value = f"Every {hours} hour{'s' if hours > 1 else ''}"
                    schedule_type = "interval"
                elif interval_seconds >= 60:
                    minutes = int(interval_seconds / 60)
                    schedule_value = f"Every {minutes} minute{'s' if minutes > 1 else ''}"
                    schedule_type = "interval"
                    interval_minutes = minutes
                else:
                    schedule_value = f"Every {int(interval_seconds)} second{'s' if interval_seconds != 1 else ''}"
                    schedule_type = "interval"
            elif hasattr(schedule_obj, 'hour'):
                hour = schedule_obj.hour
                minute = schedule_obj.minute
                day_of_week = getattr(schedule_obj, 'day_of_week', None)
                
                # Convert sets to readable strings
                def parse_cron_value(val):
                    if isinstance(val, set):
                        return sorted(list(val))
                    return val
                
                hour_val = parse_cron_value(hour)
                minute_val = parse_cron_value(minute)
                dow_val = parse_cron_value(day_of_week)
                
                # Store original values as strings for API
                cron_hour = hour_val[0] if isinstance(hour_val, list) and len(hour_val) == 1 else None
                cron_minute = minute_val[0] if isinstance(minute_val, list) and len(minute_val) == 1 else None
                cron_day_of_week = dow_val[0] if isinstance(dow_val, list) and len(dow_val) == 1 else None
                
                # Helper to format time values
                def format_time_val(val):
                    if isinstance(val, list) and len(val) == 1:
                        return val[0]
                    return val
                
                hour_display = format_time_val(hour_val)
                minute_display = format_time_val(minute_val)
                
                # Format human-readable schedule
                if dow_val is not None and dow_val != set() and isinstance(dow_val, list) and len(dow_val) == 1:
                    # Weekly schedule
                    days = {0: 'Monday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 
                            4: 'Thursday', 5: 'Friday', 6: 'Saturday', 7: 'Sunday'}
                    day_name = days.get(dow_val[0], f'Day {dow_val[0]}')
                    if isinstance(hour_display, int) and isinstance(minute_display, int):
                        schedule_value = f"Weekly on {day_name} at {hour_display:02d}:{minute_display:02d}"
                    else:
                        schedule_value = f"Weekly on {day_name}"
                elif isinstance(hour_display, int) and isinstance(minute_display, int):
                    # Daily at specific time
                    schedule_value = f"Daily at {hour_display:02d}:{minute_display:02d}"
                elif isinstance(hour_val, list) and len(hour_val) > 1 and isinstance(minute_display, int):
                    # Multiple hours (every hour)
                    if minute_display == 0:
                        schedule_value = "Every hour"
                    else:
                        schedule_value = f"Every hour at :{minute_display:02d}"
                    schedule_type = "interval"
                elif isinstance(minute_val, list) and len(minute_val) > 1:
                    # Multiple minutes (every N minutes)
                    minute_diff = minute_val[1] - minute_val[0] if len(minute_val) > 1 else 5
                    interval_minutes = minute_diff
                    schedule_value = f"Every {minute_diff} minutes"
                    schedule_type = "interval"
                elif isinstance(minute_val, str) and minute_val.startswith('*/'):
                    mins = int(minute_val[2:])
                    interval_minutes = mins
                    schedule_value = f"Every {mins} minutes"
                    schedule_type = "interval"
                else:
                    schedule_value = f"Custom: {hour_val} hour(s), {minute_val} minute(s)"
            
            # Task descriptions
            descriptions = {
                'validate-yaml-seed-daily': 'Validate that all YAML entries exist in database',
                'sync-collections-daily': 'Sync all collections from YAML and update database',
                'parse-codebundles-daily': 'Parse all codebundles from cloned repositories',
                'enhance-codebundles-weekly': 'Run AI enhancement on all codebundles',
                'generate-metrics-daily': 'Generate daily metrics and statistics',
                'update-statistics-hourly': 'Update collection statistics',
                'health-check': 'System health check',
                'scheduled-sync': 'Full registry population (clone, parse, sync)',
                'cleanup-old-tasks': 'Clean up old completed tasks',
                'health-check-tasks': 'Health check for task queues and workers'
            }
            
            schedules.append({
                'id': schedule_name,
                'task_name': schedule_name,
                'task_path': task_path,
                'schedule_type': schedule_type,
                'schedule_value': schedule_value,
                'cron_hour': cron_hour,
                'cron_minute': cron_minute,
                'cron_day_of_week': cron_day_of_week,
                'interval_minutes': interval_minutes,
                'description': descriptions.get(schedule_name, 'No description'),
                'is_active': True  # All schedules are active when in beat_schedule
            })
        
        return {
            'schedules': schedules,
            'total': len(schedules),
            'note': 'Schedules are configured in schedules.yaml. Edit the file and restart the scheduler to apply changes.'
        }
        
    except Exception as e:
        logger.error(f"Failed to get schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedules: {str(e)}")


@router.get("/schedules/{schedule_name}")
async def get_schedule(
    schedule_name: str,
    token: str = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Get a specific schedule configuration"""
    try:
        from app.tasks.celery_app import celery_app
        
        beat_schedule = celery_app.conf.beat_schedule
        
        if schedule_name not in beat_schedule:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_name}' not found")
        
        schedule_config = beat_schedule[schedule_name]
        schedule_obj = schedule_config['schedule']
        
        return {
            'id': schedule_name,
            'task_name': schedule_name,
            'task_path': schedule_config['task'],
            'schedule': str(schedule_obj),
            'is_active': True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedule: {str(e)}")


@router.put("/schedules/{schedule_name}")
async def update_schedule(
    schedule_name: str,
    schedule_update: ScheduleUpdate,
    token: str = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    Update a schedule configuration (Note: requires Celery Beat restart to take effect)
    
    This endpoint provides information about how to update schedules, but actual changes
    need to be made in celery_app.py and require a service restart.
    """
    try:
        from app.tasks.celery_app import celery_app
        
        beat_schedule = celery_app.conf.beat_schedule
        
        if schedule_name not in beat_schedule:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_name}' not found")
        
        # Return instructions for manual update
        return {
            'message': 'Schedule update noted. To apply changes:',
            'instructions': [
                '1. Edit /workspaces/codecollection-registry/cc-registry-v2/backend/app/tasks/celery_app.py',
                f"2. Update the '{schedule_name}' schedule configuration",
                '3. Restart the Celery Beat scheduler service',
                '4. Changes will take effect after restart'
            ],
            'requested_changes': schedule_update.dict(exclude_unset=True),
            'current_schedule': str(beat_schedule[schedule_name]['schedule']),
            'note': 'Dynamic schedule updates require implementing django-celery-beat or similar database-backed scheduler'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


@router.post("/schedules/{schedule_name}/trigger")
async def trigger_schedule_now(
    schedule_name: str,
    token: str = Depends(verify_admin_token)
) -> Dict[str, Any]:
    """Manually trigger a scheduled task immediately"""
    try:
        from app.tasks.celery_app import celery_app
        
        beat_schedule = celery_app.conf.beat_schedule
        
        if schedule_name not in beat_schedule:
            raise HTTPException(status_code=404, detail=f"Schedule '{schedule_name}' not found")
        
        # Get the task path
        task_path = beat_schedule[schedule_name]['task']
        
        # Import and trigger the task
        # Dynamic task invocation
        task_parts = task_path.split('.')
        module_path = '.'.join(task_parts[:-1])
        task_name = task_parts[-1]
        
        import importlib
        module = importlib.import_module(module_path)
        task_func = getattr(module, task_name)
        
        # Trigger the task
        result = task_func.apply_async()
        
        return {
            'message': f"Task '{schedule_name}' triggered successfully",
            'task_id': result.id,
            'task_path': task_path,
            'status': 'triggered'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger schedule: {str(e)}")
