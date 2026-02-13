"""
Task Management API - Live task monitoring and history
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.services.task_monitoring_service import task_monitor
from app.models.task_execution import TaskExecution
from app.core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/task-management", tags=["task-management"])

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    # For development, accept any token that starts with 'admin-'
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials


@router.get("/tasks")
async def get_task_history(
    limit: int = Query(50, description="Number of tasks to return"),
    offset: int = Query(0, description="Offset for pagination"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    token: str = Depends(verify_admin_token)
):
    """Get task execution history with live status updates"""
    try:
        tasks = task_monitor.get_task_history(
            limit=limit,
            offset=offset,
            task_type=task_type,
            status=status
        )
        
        # Convert to response format
        task_list = []
        for task in tasks:
            task_dict = {
                "id": task.id,
                "task_id": task.task_id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "duration_seconds": task.duration_seconds,
                "result": task.result,
                "error_message": task.error_message,
                "traceback": task.traceback,
                "triggered_by": task.triggered_by,
                "parameters": task.parameters,
                "worker_name": task.worker_name,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "is_running": task.is_running,
                "is_completed": task.is_completed,
                "is_successful": task.is_successful,
                "is_failed": task.is_failed
            }
            task_list.append(task_dict)
        
        return {
            "tasks": task_list,
            "total_count": len(task_list),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get task history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task history: {str(e)}")


@router.get("/tasks/running")
async def get_running_tasks(token: str = Depends(verify_admin_token)):
    """Get currently running tasks with live status updates"""
    try:
        tasks = task_monitor.get_running_tasks()
        
        # Convert to response format
        task_list = []
        for task in tasks:
            task_dict = {
                "id": task.id,
                "task_id": task.task_id,
                "task_name": task.task_name,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "duration_seconds": task.duration_seconds,
                "triggered_by": task.triggered_by,
                "parameters": task.parameters,
                "worker_name": task.worker_name,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat()
            }
            task_list.append(task_dict)
        
        return {
            "running_tasks": task_list,
            "count": len(task_list)
        }
        
    except Exception as e:
        logger.error(f"Failed to get running tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get running tasks: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    token: str = Depends(verify_admin_token)
):
    """Get specific task status with live updates"""
    try:
        task = task_monitor.get_task_by_id(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "id": task.id,
            "task_id": task.task_id,
            "task_name": task.task_name,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "current_step": task.current_step,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "duration_seconds": task.duration_seconds,
            "result": task.result,
            "error_message": task.error_message,
            "traceback": task.traceback,
            "triggered_by": task.triggered_by,
            "parameters": task.parameters,
            "worker_name": task.worker_name,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "is_running": task.is_running,
            "is_completed": task.is_completed,
            "is_successful": task.is_successful,
            "is_failed": task.is_failed
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/stats")
async def get_task_stats(
    days: int = Query(7, description="Number of days to include in stats"),
    token: str = Depends(verify_admin_token)
):
    """Get task execution statistics"""
    try:
        db = next(get_db())
        
        # Get task counts by status
        from sqlalchemy import func, and_
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Status counts
        status_counts = db.query(
            TaskExecution.status,
            func.count(TaskExecution.id).label('count')
        ).filter(
            TaskExecution.created_at >= cutoff_date
        ).group_by(TaskExecution.status).all()
        
        # Task type counts
        type_counts = db.query(
            TaskExecution.task_type,
            func.count(TaskExecution.id).label('count')
        ).filter(
            TaskExecution.created_at >= cutoff_date
        ).group_by(TaskExecution.task_type).all()
        
        # Average duration for completed tasks
        avg_duration = db.query(
            func.avg(TaskExecution.duration_seconds).label('avg_duration')
        ).filter(
            and_(
                TaskExecution.created_at >= cutoff_date,
                TaskExecution.status == 'SUCCESS',
                TaskExecution.duration_seconds.isnot(None)
            )
        ).scalar()
        
        # Total tasks
        total_tasks = db.query(func.count(TaskExecution.id)).filter(
            TaskExecution.created_at >= cutoff_date
        ).scalar()
        
        # Running tasks
        running_tasks = db.query(func.count(TaskExecution.id)).filter(
            TaskExecution.status.in_(['PENDING', 'STARTED'])
        ).scalar()
        
        return {
            "period_days": days,
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "average_duration_seconds": float(avg_duration) if avg_duration else 0.0,
            "status_counts": {status: count for status, count in status_counts},
            "type_counts": {task_type: count for task_type, count in type_counts}
        }
        
    except Exception as e:
        logger.error(f"Failed to get task stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task stats: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = Query(30, description="Delete tasks older than this many days"),
    token: str = Depends(verify_admin_token)
):
    """Clean up old completed tasks"""
    try:
        task_monitor.cleanup_old_tasks(days=days)
        
        return {
            "message": f"Cleaned up tasks older than {days} days",
            "cutoff_days": days
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup tasks: {str(e)}")

