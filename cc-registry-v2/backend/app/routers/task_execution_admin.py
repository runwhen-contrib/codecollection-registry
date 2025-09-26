"""
Task Execution Administration API
Provides access to Celery task execution logs
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.task_execution import TaskExecution

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/admin/task-executions", tags=["Task Execution Admin"])


class TaskExecutionResponse(BaseModel):
    id: int
    task_id: str
    task_name: str
    status: str
    result: Optional[dict]
    error_message: Optional[str]
    traceback: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]


@router.get("", response_model=List[TaskExecutionResponse])
async def get_task_executions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    task_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get Celery task execution logs with filtering"""
    
    query = db.query(TaskExecution)
    
    if status:
        query = query.filter(TaskExecution.status == status)
    
    if task_name:
        query = query.filter(TaskExecution.task_name.like(f"%{task_name}%"))
    
    executions = query.order_by(TaskExecution.started_at.desc()).offset(skip).limit(limit).all()
    
    return [
        TaskExecutionResponse(
            id=execution.id,
            task_id=execution.task_id,
            task_name=execution.task_name,
            status=execution.status,
            result=execution.result,
            error_message=execution.error_message,
            traceback=execution.traceback,
            started_at=execution.started_at.isoformat() if execution.started_at else None,
            completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
            duration_seconds=execution.duration_seconds
        )
        for execution in executions
    ]


@router.get("/{execution_id}", response_model=TaskExecutionResponse)
async def get_task_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get specific task execution with full details"""
    
    execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Task execution not found")
    
    return TaskExecutionResponse(
        id=execution.id,
        task_id=execution.task_id,
        task_name=execution.task_name,
        status=execution.status,
        result=execution.result,
        error_message=execution.error_message,
        traceback=execution.traceback,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        processing_time_seconds=execution.processing_time_seconds
    )


@router.get("/stats")
async def get_task_execution_stats(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get task execution statistics"""
    
    total_tasks = db.query(TaskExecution).count()
    successful = db.query(TaskExecution).filter(TaskExecution.status == 'SUCCESS').count()
    failed = db.query(TaskExecution).filter(TaskExecution.status == 'FAILURE').count()
    pending = db.query(TaskExecution).filter(TaskExecution.status == 'PENDING').count()
    
    # Average processing time
    avg_time = db.query(TaskExecution.duration_seconds).filter(
        TaskExecution.duration_seconds.isnot(None)
    ).all()
    
    avg_processing_time = sum(t[0] for t in avg_time) / len(avg_time) if avg_time else 0
    
    return {
        "total_tasks": total_tasks,
        "successful": successful,
        "failed": failed,
        "pending": pending,
        "success_rate": (successful / total_tasks * 100) if total_tasks > 0 else 0,
        "average_duration_seconds": avg_processing_time
    }
