"""
Task Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List, Optional
import logging

from app.tasks.data_tasks import (
    populate_registry_task,
    store_yaml_data_task,
    clone_repositories_task,
    parse_stored_data_task
)
from app.tasks.sync_tasks import (
    sync_collections_task,
    health_check_task
)
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
        yaml_data = request_data.get('yaml_data') if request_data else None
        task = sync_collections_task.delay(yaml_data)
        return {
            "message": "Collections sync started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting collections sync: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {str(e)}")

@router.post("/store-yaml")
async def trigger_yaml_storage(token: str = Depends(verify_admin_token)):
    """Trigger YAML data storage"""
    try:
        task = store_yaml_data_task.delay()
        return {
            "message": "YAML storage started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting YAML storage: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start YAML storage: {str(e)}")

@router.post("/clone-repositories")
async def trigger_repository_cloning(
    request_data: Dict[str, Any] = None,
    token: str = Depends(verify_admin_token)
):
    """Trigger repository cloning"""
    try:
        collection_slugs = request_data.get('collection_slugs') if request_data else None
        task = clone_repositories_task.delay(collection_slugs)
        return {
            "message": "Repository cloning started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting repository cloning: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start cloning: {str(e)}")

@router.post("/parse-data")
async def trigger_data_parsing(token: str = Depends(verify_admin_token)):
    """Trigger stored data parsing"""
    try:
        task = parse_stored_data_task.delay()
        return {
            "message": "Data parsing started",
            "task_id": task.id,
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting data parsing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start parsing: {str(e)}")

@router.get("/health")
async def get_task_health(token: str = Depends(verify_admin_token)):
    """Get task system health"""
    try:
        task = health_check_task.delay()
        result = task.get(timeout=10)  # Wait up to 10 seconds
        return result
    except Exception as e:
        logger.error(f"Error getting task health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Task system health check failed"
        }
