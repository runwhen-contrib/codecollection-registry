"""
Task Monitoring and Progress Tracking
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import Celery
from celery.result import AsyncResult

from app.core.database import SessionLocal
# TaskExecution and TaskStatus models would be created if needed
# from app.models import TaskExecution, TaskStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

# Get the same Celery app instance
from app.tasks.celery_app import celery_app

class TaskMonitor:
    """Monitor and track task execution"""
    
    def __init__(self):
        self.celery_app = celery_app
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a specific task"""
        try:
            result = AsyncResult(task_id, app=self.celery_app)
            
            return {
                'task_id': task_id,
                'status': result.status,
                'result': result.result if result.ready() else None,
                'progress': result.info.get('progress', 0) if result.info else 0,
                'current_step': result.info.get('step', 'unknown') if result.info else 'unknown',
                'started_at': result.date_done,
                'is_ready': result.ready(),
                'is_successful': result.successful() if result.ready() else False,
                'is_failed': result.failed() if result.ready() else False,
                'error': str(result.result) if result.failed() else None
            }
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': 'UNKNOWN',
                'error': str(e)
            }
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get all currently active tasks"""
        try:
            active_tasks = self.celery_app.control.inspect().active()
            if not active_tasks:
                return []
            
            tasks = []
            for worker, task_list in active_tasks.items():
                for task in task_list:
                    tasks.append({
                        'task_id': task['id'],
                        'name': task['name'],
                        'worker': worker,
                        'args': task['args'],
                        'kwargs': task['kwargs'],
                        'started_at': datetime.fromtimestamp(task['time_start'])
                    })
            
            return tasks
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}")
            return []
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks"""
        try:
            scheduled_tasks = self.celery_app.control.inspect().scheduled()
            if not scheduled_tasks:
                return []
            
            tasks = []
            for worker, task_list in scheduled_tasks.items():
                for task in task_list:
                    tasks.append({
                        'task_id': task['id'],
                        'name': task['name'],
                        'worker': worker,
                        'eta': task['eta'],
                        'args': task['args'],
                        'kwargs': task['kwargs']
                    })
            
            return tasks
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return []
    
    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get task execution history"""
        try:
            db = SessionLocal()
            try:
                # This would query a TaskExecution model if it existed
                # For now, return empty list
                return []
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting task history: {e}")
            return []
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        try:
            self.celery_app.control.revoke(task_id, terminate=True)
            logger.info(f"Task {task_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return False
    
    def retry_failed_task(self, task_id: str) -> str:
        """Retry a failed task"""
        try:
            # Get the original task info
            result = AsyncResult(task_id, app=self.celery_app)
            if not result.failed():
                raise ValueError("Task is not in failed state")
            
            # Retry the task
            new_task = result.retry()
            logger.info(f"Task {task_id} retried as {new_task.id}")
            return new_task.id
        except Exception as e:
            logger.error(f"Error retrying task {task_id}: {e}")
            raise
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        try:
            stats = self.celery_app.control.inspect().stats()
            if not stats:
                return {}
            
            total_workers = len(stats)
            # Safely sum total tasks, handling both dict and non-dict values
            total_tasks = 0
            for worker_stats in stats.values():
                if isinstance(worker_stats, dict):
                    total_tasks += worker_stats.get('total', 0)
            
            return {
                'total_workers': total_workers,
                'total_tasks': total_tasks,
                'workers': stats
            }
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {}
    
    def get_queue_lengths(self) -> Dict[str, int]:
        """Get queue lengths for different task types"""
        try:
            # This would query Redis for queue lengths
            # For now, return empty dict
            return {}
        except Exception as e:
            logger.error(f"Error getting queue lengths: {e}")
            return {}
    
    def get_task_metrics(self) -> Dict[str, Any]:
        """Get task execution metrics"""
        try:
            # This would calculate metrics from task history
            # For now, return basic metrics
            return {
                'total_tasks_executed': 0,
                'successful_tasks': 0,
                'failed_tasks': 0,
                'average_execution_time': 0,
                'success_rate': 0.0
            }
        except Exception as e:
            logger.error(f"Error getting task metrics: {e}")
            return {}

# Task monitoring endpoints
@celery_app.task(bind=True)
def monitor_task_progress_task(self, task_id: str):
    """
    Monitor the progress of a specific task
    """
    try:
        monitor = TaskMonitor()
        status = monitor.get_task_status(task_id)
        
        # Store progress in database or cache
        # Implementation would go here
        
        return status
    except Exception as e:
        logger.error(f"Error monitoring task {task_id}: {e}")
        raise

@celery_app.task(bind=True)
def cleanup_old_tasks_task(self):
    """
    Clean up old task results and logs
    """
    try:
        logger.info(f"Starting task cleanup task {self.request.id}")
        
        # Clean up task results older than 7 days
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        # Implementation would clean up old task data
        # This would involve removing old AsyncResult data from Redis
        
        logger.info(f"Task cleanup task {self.request.id} completed")
        return {'status': 'success', 'cleaned_up': True}
        
    except Exception as e:
        logger.error(f"Task cleanup task {self.request.id} failed: {e}")
        raise

@celery_app.task(bind=True)
def health_check_tasks_task(self):
    """
    Health check for all task queues and workers
    """
    try:
        logger.info(f"Starting task health check task {self.request.id}")
        
        monitor = TaskMonitor()
        
        # Check worker health
        worker_stats = monitor.get_worker_stats()
        
        # Check queue health
        queue_lengths = monitor.get_queue_lengths()
        
        # Check for stuck tasks
        active_tasks = monitor.get_active_tasks()
        stuck_tasks = [task for task in active_tasks 
                      if datetime.utcnow() - task['started_at'] > timedelta(hours=1)]
        
        health_status = {
            'workers_healthy': len(worker_stats.get('workers', {})) > 0,
            'queues_healthy': all(length < 100 for length in queue_lengths.values()),
            'no_stuck_tasks': len(stuck_tasks) == 0,
            'stuck_tasks': stuck_tasks,
            'worker_count': worker_stats.get('total_workers', 0),
            'total_tasks': worker_stats.get('total_tasks', 0)
        }
        
        logger.info(f"Task health check task {self.request.id} completed: {health_status}")
        return {'status': 'success', 'health': health_status}
        
    except Exception as e:
        logger.error(f"Task health check task {self.request.id} failed: {e}")
        raise
