"""
Admin CRUD operations for CodeCollections
Database is the source of truth - no YAML dependency
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models import CodeCollection, Codebundle, CodeCollectionMetrics, SystemMetrics
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/api/v1/admin", tags=["admin-crud"])


# Pydantic models
class CodeCollectionCreate(BaseModel):
    name: str
    slug: str
    git_url: str
    description: Optional[str] = None
    owner: Optional[str] = None
    owner_email: Optional[str] = None
    owner_icon: Optional[str] = None
    git_ref: str = "main"
    is_active: bool = True


class CodeCollectionUpdate(BaseModel):
    name: Optional[str] = None
    git_url: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    owner_email: Optional[str] = None
    owner_icon: Optional[str] = None
    git_ref: Optional[str] = None
    is_active: Optional[bool] = None


class CodeCollectionResponse(BaseModel):
    id: int
    name: str
    slug: str
    git_url: str
    description: Optional[str]
    owner: Optional[str]
    owner_email: Optional[str]
    owner_icon: Optional[str]
    git_ref: str
    is_active: bool
    last_synced: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    codebundle_count: int = 0

    class Config:
        from_attributes = True


class MetricsResponse(BaseModel):
    collection_metrics: List[dict]
    system_metrics: dict
    
    class Config:
        from_attributes = True


@router.get("/collections", response_model=List[CodeCollectionResponse])
async def get_all_collections(
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Get all CodeCollections with optional filtering"""
    query = db.query(CodeCollection)
    
    if not include_inactive:
        query = query.filter(CodeCollection.is_active == True)
    
    collections = query.offset(skip).limit(limit).all()
    
    # Add codebundle counts
    result = []
    for collection in collections:
        collection_data = CodeCollectionResponse.from_orm(collection)
        collection_data.codebundle_count = db.query(Codebundle).filter(
            Codebundle.codecollection_id == collection.id,
            Codebundle.is_active == True
        ).count()
        result.append(collection_data)
    
    return result


@router.get("/collections/{collection_id}", response_model=CodeCollectionResponse)
async def get_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Get a specific CodeCollection by ID"""
    collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CodeCollection with ID {collection_id} not found"
        )
    
    collection_data = CodeCollectionResponse.from_orm(collection)
    collection_data.codebundle_count = db.query(Codebundle).filter(
        Codebundle.codecollection_id == collection.id,
        Codebundle.is_active == True
    ).count()
    
    return collection_data


@router.post("/collections", response_model=CodeCollectionResponse)
async def create_collection(
    collection_data: CodeCollectionCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Create a new CodeCollection"""
    
    # Check if slug already exists
    existing = db.query(CodeCollection).filter(CodeCollection.slug == collection_data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CodeCollection with slug '{collection_data.slug}' already exists"
        )
    
    # Create new collection
    new_collection = CodeCollection(
        name=collection_data.name,
        slug=collection_data.slug,
        git_url=collection_data.git_url,
        description=collection_data.description,
        owner=collection_data.owner,
        owner_email=collection_data.owner_email,
        owner_icon=collection_data.owner_icon,
        git_ref=collection_data.git_ref,
        is_active=collection_data.is_active
    )
    
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)
    
    collection_response = CodeCollectionResponse.from_orm(new_collection)
    collection_response.codebundle_count = 0
    
    return collection_response


@router.put("/collections/{collection_id}", response_model=CodeCollectionResponse)
async def update_collection(
    collection_id: int,
    collection_data: CodeCollectionUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Update an existing CodeCollection"""
    
    collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CodeCollection with ID {collection_id} not found"
        )
    
    # Update fields that were provided
    update_data = collection_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(collection, field, value)
    
    collection.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(collection)
    
    collection_response = CodeCollectionResponse.from_orm(collection)
    collection_response.codebundle_count = db.query(Codebundle).filter(
        Codebundle.codecollection_id == collection.id,
        Codebundle.is_active == True
    ).count()
    
    return collection_response


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: int,
    hard_delete: bool = False,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Delete a CodeCollection (soft delete by default)"""
    
    collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CodeCollection with ID {collection_id} not found"
        )
    
    if hard_delete:
        # Hard delete - remove from database entirely
        db.delete(collection)
        message = f"CodeCollection '{collection.slug}' permanently deleted"
    else:
        # Soft delete - mark as inactive
        collection.is_active = False
        collection.updated_at = datetime.utcnow()
        message = f"CodeCollection '{collection.slug}' deactivated"
    
    db.commit()
    
    return {"message": message, "collection_slug": collection.slug}


@router.post("/collections/{collection_id}/sync")
async def trigger_collection_sync(
    collection_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Trigger sync for a specific collection"""
    
    collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CodeCollection with ID {collection_id} not found"
        )
    
    # Import and trigger sync task
    from app.tasks.database_driven_tasks import sync_single_collection_task
    
    task = sync_single_collection_task.apply_async(args=[collection_id])
    
    return {
        "message": f"Sync triggered for collection '{collection.slug}'",
        "task_id": task.id,
        "collection_slug": collection.slug
    }


@router.post("/collections/{collection_id}/parse")
async def trigger_collection_parse(
    collection_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Trigger codebundle parsing for a specific collection"""
    
    collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CodeCollection with ID {collection_id} not found"
        )
    
    # Import and trigger parse task
    from app.tasks.database_driven_tasks import parse_collection_codebundles_task
    
    task = parse_collection_codebundles_task.apply_async(args=[collection_id])
    
    return {
        "message": f"Parsing triggered for collection '{collection.slug}'",
        "task_id": task.id,
        "collection_slug": collection.slug
    }


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    days: int = 7,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Get system and collection metrics"""
    
    # Get recent collection metrics
    collection_metrics = db.query(CodeCollectionMetrics).filter(
        CodeCollectionMetrics.snapshot_date >= datetime.utcnow() - timedelta(days=days)
    ).all()
    
    # Get recent system metrics
    system_metrics = db.query(SystemMetrics).filter(
        SystemMetrics.snapshot_date >= datetime.utcnow() - timedelta(days=days)
    ).order_by(SystemMetrics.snapshot_date.desc()).first()
    
    return {
        "collection_metrics": [
            {
                "collection_id": m.codecollection_id,
                "codebundle_count": m.codebundle_count,
                "total_task_count": m.total_task_count,
                "enhanced_codebundles": m.enhanced_codebundles,
                "pending_enhancements": m.pending_enhancements,
                "snapshot_date": m.snapshot_date.isoformat()
            }
            for m in collection_metrics
        ],
        "system_metrics": {
            "total_collections": system_metrics.total_collections if system_metrics else 0,
            "total_codebundles": system_metrics.total_codebundles if system_metrics else 0,
            "total_tasks": system_metrics.total_tasks if system_metrics else 0,
            "snapshot_date": system_metrics.snapshot_date.isoformat() if system_metrics else None
        }
    }


@router.post("/seed-from-yaml")
async def seed_database_from_yaml(
    yaml_file_path: str = "/app/codecollections.yaml",
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Seed database from YAML file (one-time operation)"""
    
    # Import and trigger seed task
    from app.tasks.database_driven_tasks import seed_database_from_yaml_task
    
    task = seed_database_from_yaml_task.apply_async(args=[yaml_file_path])
    
    return {
        "message": "Database seeding from YAML triggered",
        "task_id": task.id,
        "yaml_file": yaml_file_path
    }


@router.post("/validate-yaml-seed")
async def validate_yaml_seed(
    yaml_file_path: str = "/app/codecollections.yaml",
    db: Session = Depends(get_db),
    _: dict = Depends(verify_admin_token)
):
    """Validate that all YAML entries exist in database"""
    
    # Import and trigger validation task
    from app.tasks.database_driven_tasks import validate_yaml_seed_task
    
    task = validate_yaml_seed_task.apply_async(args=[yaml_file_path])
    
    return {
        "message": "YAML seed validation triggered",
        "task_id": task.id,
        "yaml_file": yaml_file_path
    }
