"""
Task Monitoring Service - Track and persist Celery task execution
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import Celery
from celery.result import AsyncResult
from sqlalchemy.orm import Session
from app.core.database import get_db

from app.core.database import SessionLocal
from app.models.task_execution import TaskExecution
from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskMonitoringService:
    """Service to monitor and persist Celery task execution"""
    
    def __init__(self):
        self.celery_app = Celery(
            'task_monitor',
            broker=settings.REDIS_URL,
            backend=settings.REDIS_URL,
        )
    
    def create_task_record(
        self, 
        task_id: str, 
        task_name: str, 
        task_type: str,
        parameters: Dict[str, Any] = None,
        triggered_by: str = "system"
    ) -> TaskExecution:
        """Create a new task execution record"""
        db = SessionLocal()
        try:
            task_execution = TaskExecution(
                task_id=task_id,
                task_name=task_name,
                task_type=task_type,
                status="PENDING",
                parameters=parameters or {},
                triggered_by=triggered_by,
                created_at=datetime.utcnow()
            )
            db.add(task_execution)
            db.commit()
            db.refresh(task_execution)
            
            logger.info(f"Created task record: {task_id} ({task_name})")
            return task_execution
            
        except Exception as e:
            logger.error(f"Failed to create task record: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    def update_task_status(self, task_id: str) -> Optional[TaskExecution]:
        """Update task status from Celery backend"""
        db = SessionLocal()
        try:
            # Get task from database
            task_execution = db.query(TaskExecution).filter(
                TaskExecution.task_id == task_id
            ).first()
            
            if not task_execution:
                logger.warning(f"Task execution not found: {task_id}")
                return None
            
            # Get status from Celery
            celery_result = AsyncResult(task_id, app=self.celery_app)
            
            # Update status
            old_status = task_execution.status
            task_execution.status = celery_result.status
            task_execution.updated_at = datetime.utcnow()
            
            # Update timing information
            if celery_result.status == 'STARTED' and not task_execution.started_at:
                task_execution.started_at = datetime.utcnow()
            
            if celery_result.status in ['SUCCESS', 'FAILURE', 'REVOKED']:
                if not task_execution.completed_at:
                    task_execution.completed_at = datetime.utcnow()
                    
                    # Calculate duration
                    if task_execution.started_at:
                        duration = task_execution.completed_at - task_execution.started_at
                        task_execution.duration_seconds = duration.total_seconds()
            
            # Update result and error information
            if celery_result.status == 'SUCCESS':
                task_execution.result = celery_result.result
                task_execution.progress = 100.0
            elif celery_result.status == 'FAILURE':
                task_execution.error_message = str(celery_result.info)
                task_execution.traceback = getattr(celery_result.info, 'traceback', None)
            
            # Update progress and current step from task meta
            if hasattr(celery_result, 'info') and isinstance(celery_result.info, dict):
                if 'progress' in celery_result.info:
                    task_execution.progress = celery_result.info['progress']
                if 'step' in celery_result.info:
                    task_execution.current_step = celery_result.info['step']
                if 'current_step' in celery_result.info:
                    task_execution.current_step = celery_result.info['current_step']
            
            db.commit()
            db.refresh(task_execution)
            
            if old_status != task_execution.status:
                logger.info(f"Task {task_id} status changed: {old_status} -> {task_execution.status}")
            
            return task_execution
            
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def get_task_history(
        self, 
        limit: int = 50, 
        offset: int = 0,
        task_type: str = None,
        status: str = None
    ) -> List[TaskExecution]:
        """Get task execution history"""
        db = SessionLocal()
        try:
            query = db.query(TaskExecution)
            
            if task_type:
                query = query.filter(TaskExecution.task_type == task_type)
            
            if status:
                query = query.filter(TaskExecution.status == status)
            
            tasks = query.order_by(TaskExecution.created_at.desc()).offset(offset).limit(limit).all()
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get task history: {e}")
            return []
        finally:
            db.close()
    
    def get_running_tasks(self) -> List[TaskExecution]:
        """Get currently running tasks"""
        db = SessionLocal()
        try:
            tasks = db.query(TaskExecution).filter(
                TaskExecution.status.in_(['PENDING', 'STARTED'])
            ).order_by(TaskExecution.created_at.desc()).all()
            
            # Update status for running tasks
            updated_tasks = []
            for task in tasks:
                updated_task = self.update_task_status(task.task_id)
                if updated_task:
                    updated_tasks.append(updated_task)
            
            return updated_tasks
            
        except Exception as e:
            logger.error(f"Failed to get running tasks: {e}")
            return []
        finally:
            db.close()
    
    def get_task_by_id(self, task_id: str) -> Optional[TaskExecution]:
        """Get task by ID with updated status"""
        task_execution = self.update_task_status(task_id)
        return task_execution
    
    def cleanup_old_tasks(self, days: int = 30):
        """Clean up old completed tasks"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            deleted_count = db.query(TaskExecution).filter(
                TaskExecution.completed_at < cutoff_date,
                TaskExecution.status.in_(['SUCCESS', 'FAILURE', 'REVOKED'])
            ).delete()
            
            db.commit()
            logger.info(f"Cleaned up {deleted_count} old task records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
            db.rollback()
        finally:
            db.close()


# Global instance
task_monitor = TaskMonitoringService()

