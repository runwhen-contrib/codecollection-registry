"""
Database-Driven Task Management Endpoints
Database is the source of truth, YAML is only for seeding
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from celery.result import AsyncResult

from app.tasks.database_driven_tasks import celery_app

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/api/v1/tasks", tags=["database-driven-tasks"])


class TaskRequest(BaseModel):
    collection_ids: Optional[List[int]] = None
    collection_slugs: Optional[List[str]] = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/seed-database", response_model=TaskResponse)
async def trigger_seed_database(
    yaml_file_path: str = "/app/codecollections.yaml",
    _: dict = Depends(verify_admin_token)
):
    """SEED: Load YAML entries into database (one-time operation)"""
    try:
        from app.tasks.database_driven_tasks import seed_database_from_yaml_task
        
        task = seed_database_from_yaml_task.apply_async(args=[yaml_file_path])
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="Database seeding from YAML started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-yaml", response_model=TaskResponse)
async def trigger_validate_yaml(
    yaml_file_path: str = "/app/codecollections.yaml",
    _: dict = Depends(verify_admin_token)
):
    """VALIDATE: Ensure YAML entries exist in database"""
    try:
        from app.tasks.database_driven_tasks import validate_yaml_seed_task
        
        task = validate_yaml_seed_task.apply_async(args=[yaml_file_path])
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="YAML validation against database started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-collections", response_model=TaskResponse)
async def trigger_sync_collections(
    _: dict = Depends(verify_admin_token)
):
    """SYNC: Read from database and sync all active collections"""
    try:
        from app.tasks.database_driven_tasks import sync_all_collections_task
        
        task = sync_all_collections_task.apply_async()
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="Database-driven collection sync started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-collection/{collection_id}", response_model=TaskResponse)
async def trigger_sync_single_collection(
    collection_id: int,
    _: dict = Depends(verify_admin_token)
):
    """SYNC: Sync a single collection by ID"""
    try:
        from app.tasks.database_driven_tasks import sync_single_collection_task
        
        task = sync_single_collection_task.apply_async(args=[collection_id])
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message=f"Sync started for collection ID {collection_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-codebundles", response_model=TaskResponse)
async def trigger_parse_codebundles(
    _: dict = Depends(verify_admin_token)
):
    """PARSE: Parse codebundles from stored repository data"""
    try:
        from app.tasks.database_driven_tasks import parse_all_codebundles_task
        
        task = parse_all_codebundles_task.apply_async()
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="Codebundle parsing from database started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-collection/{collection_id}", response_model=TaskResponse)
async def trigger_parse_collection_codebundles(
    collection_id: int,
    _: dict = Depends(verify_admin_token)
):
    """PARSE: Parse codebundles for a single collection"""
    try:
        from app.tasks.database_driven_tasks import parse_collection_codebundles_task
        
        task = parse_collection_codebundles_task.apply_async(args=[collection_id])
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message=f"Codebundle parsing started for collection ID {collection_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enhance-codebundles", response_model=TaskResponse)
async def trigger_enhance_codebundles(
    _: dict = Depends(verify_admin_token)
):
    """ENHANCE: Use AI to enhance all codebundle metadata"""
    try:
        from app.tasks.database_driven_tasks import enhance_all_codebundles_task
        
        task = enhance_all_codebundles_task.apply_async()
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="AI enhancement of codebundles started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enhance-codebundle/{codebundle_id}", response_model=TaskResponse)
async def trigger_enhance_single_codebundle(
    codebundle_id: int,
    _: dict = Depends(verify_admin_token)
):
    """ENHANCE: Use AI to enhance a single codebundle"""
    try:
        from app.tasks.database_driven_tasks import enhance_single_codebundle_task
        
        task = enhance_single_codebundle_task.apply_async(args=[codebundle_id])
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message=f"AI enhancement started for codebundle ID {codebundle_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-metrics", response_model=TaskResponse)
async def trigger_generate_metrics(
    _: dict = Depends(verify_admin_token)
):
    """METRICS: Generate system and collection metrics"""
    try:
        from app.tasks.database_driven_tasks import generate_metrics_task
        
        task = generate_metrics_task.apply_async()
        
        return TaskResponse(
            task_id=task.id,
            status="started",
            message="Metrics generation started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    _: dict = Depends(verify_admin_token)
):
    """Get status of a specific task"""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        response = TaskStatusResponse(
            task_id=task_id,
            status=result.status
        )
        
        if result.ready():
            if result.successful():
                response.result = result.result
            else:
                response.error = str(result.result)
        else:
            # Get progress info if available
            if hasattr(result, 'info') and isinstance(result.info, dict):
                response.progress = result.info
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check for database-driven task system"""
    try:
        # Test Celery connection
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            return {
                "status": "healthy",
                "celery_status": "connected",
                "workers": list(stats.keys()),
                "task_system": "database_driven"
            }
        else:
            return {
                "status": "unhealthy",
                "celery_status": "no_workers",
                "task_system": "database_driven"
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "celery_status": "disconnected",
            "error": str(e),
            "task_system": "database_driven"
        }