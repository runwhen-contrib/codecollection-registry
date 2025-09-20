"""
Task Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List, Optional
import logging

from app.tasks.data_population_tasks import (
    populate_registry_task,
    sync_collections_task,
    parse_all_codebundles_task,
    generate_categories_task,
    update_collection_statistics_task,
    sync_single_collection_task
)
from app.tasks.data_enhancement_tasks import (
    enhance_all_codebundles_task,
    enhance_single_codebundle_task,
    generate_ai_insights_task,
    validate_codebundle_quality_task
)
from app.tasks.task_monitoring import TaskMonitor
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

@router.post("/populate-registry")
async def trigger_registry_population(
    request_data: Dict[str, Any] = None,
    token: str = Depends(verify_admin_token)
):
    """Trigger full registry population"""
    try:
        collection_slugs = request_data.get('collection_slugs') if request_data else None
        task = populate_registry_task.delay(collection_slugs)
        return {
            "message": "Registry population started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting registry population: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start population: {str(e)}")

@router.post("/sync-collections")
async def trigger_collections_sync(
    request_data: Dict[str, Any] = None,
    token: str = Depends(verify_admin_token)
):
    """Trigger collections sync"""
    try:
        collection_slugs = request_data.get('collection_slugs') if request_data else None
        task = sync_collections_task.delay(collection_slugs)
        return {
            "message": "Collections sync started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting collections sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {str(e)}")

@router.post("/parse-codebundles")
async def trigger_codebundles_parsing(token: str = Depends(verify_admin_token)):
    """Trigger codebundles parsing"""
    try:
        task = parse_all_codebundles_task.delay()
        return {
            "message": "Codebundles parsing started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting codebundles parsing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start parsing: {str(e)}")

@router.post("/enhance-codebundles")
async def trigger_codebundles_enhancement(token: str = Depends(verify_admin_token)):
    """Trigger codebundles enhancement"""
    try:
        task = enhance_all_codebundles_task.delay()
        return {
            "message": "Codebundles enhancement started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting codebundles enhancement: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start enhancement: {str(e)}")

@router.post("/enhance-codebundle/{codebundle_id}")
async def trigger_single_codebundle_enhancement(
    codebundle_id: int,
    token: str = Depends(verify_admin_token)
):
    """Trigger enhancement for a single codebundle"""
    try:
        task = enhance_single_codebundle_task.delay(codebundle_id)
        return {
            "message": f"Codebundle {codebundle_id} enhancement started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting codebundle enhancement: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start enhancement: {str(e)}")

@router.post("/generate-insights")
async def trigger_ai_insights_generation(token: str = Depends(verify_admin_token)):
    """Trigger AI insights generation"""
    try:
        task = generate_ai_insights_task.delay()
        return {
            "message": "AI insights generation started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting AI insights generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start insights generation: {str(e)}")

@router.get("/status/{task_id}")
async def get_task_status(task_id: str, token: str = Depends(verify_admin_token)):
    """Get the status of a specific task"""
    try:
        monitor = TaskMonitor()
        status = monitor.get_task_status(task_id)
        return status
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@router.get("/active")
async def get_active_tasks(token: str = Depends(verify_admin_token)):
    """Get all currently active tasks"""
    try:
        monitor = TaskMonitor()
        active_tasks = monitor.get_active_tasks()
        return {
            "active_tasks": active_tasks,
            "count": len(active_tasks)
        }
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active tasks: {str(e)}")

@router.get("/scheduled")
async def get_scheduled_tasks(token: str = Depends(verify_admin_token)):
    """Get all scheduled tasks"""
    try:
        monitor = TaskMonitor()
        scheduled_tasks = monitor.get_scheduled_tasks()
        return {
            "scheduled_tasks": scheduled_tasks,
            "count": len(scheduled_tasks)
        }
    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduled tasks: {str(e)}")

@router.get("/history")
async def get_task_history(
    limit: int = 100,
    token: str = Depends(verify_admin_token)
):
    """Get task execution history"""
    try:
        monitor = TaskMonitor()
        history = monitor.get_task_history(limit)
        return {
            "task_history": history,
            "count": len(history)
        }
    except Exception as e:
        logger.error(f"Error getting task history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task history: {str(e)}")

@router.get("/metrics")
async def get_task_metrics(token: str = Depends(verify_admin_token)):
    """Get task execution metrics"""
    try:
        monitor = TaskMonitor()
        metrics = monitor.get_task_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting task metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task metrics: {str(e)}")

@router.get("/workers")
async def get_worker_stats(token: str = Depends(verify_admin_token)):
    """Get worker statistics"""
    try:
        monitor = TaskMonitor()
        stats = monitor.get_worker_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting worker stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker stats: {str(e)}")

@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str, token: str = Depends(verify_admin_token)):
    """Cancel a running task"""
    try:
        monitor = TaskMonitor()
        success = monitor.cancel_task(task_id)
        if success:
            return {"message": f"Task {task_id} cancelled successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to cancel task {task_id}")
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")

@router.post("/retry/{task_id}")
async def retry_task(task_id: str, token: str = Depends(verify_admin_token)):
    """Retry a failed task"""
    try:
        monitor = TaskMonitor()
        new_task_id = monitor.retry_failed_task(task_id)
        return {
            "message": f"Task {task_id} retried successfully",
            "new_task_id": new_task_id
        }
    except Exception as e:
        logger.error(f"Error retrying task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry task: {str(e)}")

@router.get("/health")
async def get_task_health(token: str = Depends(verify_admin_token)):
    """Get task system health"""
    try:
        monitor = TaskMonitor()
        worker_stats = monitor.get_worker_stats()
        queue_lengths = monitor.get_queue_lengths()
        active_tasks = monitor.get_active_tasks()
        
        health_status = {
            "workers_healthy": len(worker_stats.get('workers', {})) > 0,
            "queues_healthy": all(length < 100 for length in queue_lengths.values()),
            "active_tasks_count": len(active_tasks),
            "worker_count": worker_stats.get('total_workers', 0),
            "total_tasks": worker_stats.get('total_tasks', 0),
            "queue_lengths": queue_lengths
        }
        
        return health_status
    except Exception as e:
        logger.error(f"Error getting task health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task health: {str(e)}")
