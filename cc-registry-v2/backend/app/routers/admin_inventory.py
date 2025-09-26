"""
Admin Inventory API endpoints - Detailed database views for debugging and inspection
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models import CodeCollection, Codebundle

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/api/v1/admin/inventory", tags=["admin-inventory"])


class CodeBundleInventoryItem(BaseModel):
    # Basic info
    id: int
    name: str
    slug: str
    display_name: Optional[str]
    description: Optional[str]
    doc: Optional[str]
    author: Optional[str]
    
    # Collection info
    collection_id: int
    collection_name: str
    collection_slug: str
    
    # Task info
    tasks: List[str]
    slis: List[str]
    task_count: int
    sli_count: int
    support_tags: List[str]
    categories: List[str]
    
    # AI Enhancement data
    enhancement_status: str
    ai_enhanced_description: Optional[str]
    access_level: str
    minimum_iam_requirements: List[str]
    ai_enhanced_metadata: dict
    last_enhanced: Optional[datetime]
    
    # Discovery info
    is_discoverable: bool
    discovery_platform: Optional[str]
    discovery_resource_types: List[str]
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime]


class CollectionInventoryItem(BaseModel):
    # Basic info
    id: int
    name: str
    slug: str
    description: Optional[str]
    owner: Optional[str]
    owner_email: Optional[str]
    
    # Git info
    git_url: str
    git_ref: str
    
    # Statistics
    codebundle_count: int
    total_tasks: int
    total_slis: int
    
    # AI Enhancement statistics
    ai_enhancement_stats: dict
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime]
    last_synced: Optional[datetime]


@router.get("/codebundles", response_model=List[CodeBundleInventoryItem])
async def get_codebundle_inventory(
    limit: int = Query(100, description="Number of codebundles to return"),
    offset: int = Query(0, description="Offset for pagination"),
    collection_slug: Optional[str] = Query(None, description="Filter by collection slug"),
    enhancement_status: Optional[str] = Query(None, description="Filter by enhancement status"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    search: Optional[str] = Query(None, description="Search in name or description"),
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get detailed inventory of all CodeBundles with AI enhancement data"""
    
    # Build query
    query = db.query(Codebundle).filter(Codebundle.is_active == True)
    
    # Apply filters
    if collection_slug:
        query = query.join(CodeCollection).filter(CodeCollection.slug == collection_slug)
    
    if enhancement_status:
        query = query.filter(Codebundle.enhancement_status == enhancement_status)
    
    if access_level:
        query = query.filter(Codebundle.access_level == access_level)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Codebundle.name.ilike(search_term)) |
            (Codebundle.display_name.ilike(search_term)) |
            (Codebundle.description.ilike(search_term))
        )
    
    # Apply pagination
    codebundles = query.offset(offset).limit(limit).all()
    
    # Build response
    result = []
    for cb in codebundles:
        # Get collection info
        collection = db.query(CodeCollection).filter(CodeCollection.id == cb.codecollection_id).first()
        
        result.append(CodeBundleInventoryItem(
            # Basic info
            id=cb.id,
            name=cb.name,
            slug=cb.slug,
            display_name=cb.display_name,
            description=cb.description,
            doc=cb.doc,
            author=cb.author,
            
            # Collection info
            collection_id=cb.codecollection_id,
            collection_name=collection.name if collection else "Unknown",
            collection_slug=collection.slug if collection else "unknown",
            
            # Task info
            tasks=cb.tasks or [],
            slis=cb.slis or [],
            task_count=cb.task_count or 0,
            sli_count=cb.sli_count or 0,
            support_tags=cb.support_tags or [],
            categories=cb.categories or [],
            
            # AI Enhancement data
            enhancement_status=cb.enhancement_status or "pending",
            ai_enhanced_description=cb.ai_enhanced_description,
            access_level=cb.access_level or "unknown",
            minimum_iam_requirements=cb.minimum_iam_requirements or [],
            ai_enhanced_metadata=cb.ai_enhanced_metadata or {},
            last_enhanced=cb.last_enhanced,
            
            # Discovery info
            is_discoverable=cb.is_discoverable or False,
            discovery_platform=cb.discovery_platform,
            discovery_resource_types=cb.discovery_resource_types or [],
            
            # Timestamps
            created_at=cb.created_at,
            updated_at=cb.updated_at
        ))
    
    return result


@router.get("/collections", response_model=List[CollectionInventoryItem])
async def get_collection_inventory(
    limit: int = Query(50, description="Number of collections to return"),
    offset: int = Query(0, description="Offset for pagination"),
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get detailed inventory of all CodeCollections with statistics"""
    
    collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).offset(offset).limit(limit).all()
    
    result = []
    for collection in collections:
        # Get codebundle statistics
        codebundles = db.query(Codebundle).filter(
            Codebundle.codecollection_id == collection.id,
            Codebundle.is_active == True
        ).all()
        
        # Calculate statistics
        codebundle_count = len(codebundles)
        total_tasks = sum(cb.task_count or 0 for cb in codebundles)
        total_slis = sum(cb.sli_count or 0 for cb in codebundles)
        
        # AI Enhancement statistics
        enhancement_stats = {
            "pending": len([cb for cb in codebundles if cb.enhancement_status == "pending"]),
            "processing": len([cb for cb in codebundles if cb.enhancement_status == "processing"]),
            "completed": len([cb for cb in codebundles if cb.enhancement_status == "completed"]),
            "failed": len([cb for cb in codebundles if cb.enhancement_status == "failed"]),
            "read_only": len([cb for cb in codebundles if cb.access_level == "read-only"]),
            "read_write": len([cb for cb in codebundles if cb.access_level == "read-write"]),
            "unknown": len([cb for cb in codebundles if cb.access_level == "unknown"])
        }
        
        result.append(CollectionInventoryItem(
            # Basic info
            id=collection.id,
            name=collection.name,
            slug=collection.slug,
            description=collection.description,
            owner=collection.owner,
            owner_email=collection.owner_email,
            
            # Git info
            git_url=collection.git_url,
            git_ref=collection.git_ref,
            
            # Statistics
            codebundle_count=codebundle_count,
            total_tasks=total_tasks,
            total_slis=total_slis,
            
            # AI Enhancement statistics
            ai_enhancement_stats=enhancement_stats,
            
            # Timestamps
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            last_synced=collection.last_synced
        ))
    
    return result


@router.get("/codebundles/{codebundle_id}", response_model=CodeBundleInventoryItem)
async def get_codebundle_details(
    codebundle_id: int,
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific CodeBundle"""
    
    codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
    if not codebundle:
        raise HTTPException(status_code=404, detail="CodeBundle not found")
    
    collection = db.query(CodeCollection).filter(CodeCollection.id == codebundle.codecollection_id).first()
    
    return CodeBundleInventoryItem(
        # Basic info
        id=codebundle.id,
        name=codebundle.name,
        slug=codebundle.slug,
        display_name=codebundle.display_name,
        description=codebundle.description,
        doc=codebundle.doc,
        author=codebundle.author,
        
        # Collection info
        collection_id=codebundle.codecollection_id,
        collection_name=collection.name if collection else "Unknown",
        collection_slug=collection.slug if collection else "unknown",
        
        # Task info
        tasks=codebundle.tasks or [],
        slis=codebundle.slis or [],
        task_count=codebundle.task_count or 0,
        sli_count=codebundle.sli_count or 0,
        support_tags=codebundle.support_tags or [],
        categories=codebundle.categories or [],
        
        # AI Enhancement data
        enhancement_status=codebundle.enhancement_status or "pending",
        ai_enhanced_description=codebundle.ai_enhanced_description,
        access_level=codebundle.access_level or "unknown",
        minimum_iam_requirements=codebundle.minimum_iam_requirements or [],
        ai_enhanced_metadata=codebundle.ai_enhanced_metadata or {},
        last_enhanced=codebundle.last_enhanced,
        
        # Discovery info
        is_discoverable=codebundle.is_discoverable or False,
        discovery_platform=codebundle.discovery_platform,
        discovery_resource_types=codebundle.discovery_resource_types or [],
        
        # Timestamps
        created_at=codebundle.created_at,
        updated_at=codebundle.updated_at
    )


@router.get("/stats")
async def get_inventory_stats(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get overall inventory statistics"""
    
    # Collection stats
    total_collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).count()
    
    # CodeBundle stats
    codebundles = db.query(Codebundle).filter(Codebundle.is_active == True).all()
    total_codebundles = len(codebundles)
    
    # Enhancement stats
    enhancement_stats = {
        "pending": len([cb for cb in codebundles if cb.enhancement_status == "pending"]),
        "processing": len([cb for cb in codebundles if cb.enhancement_status == "processing"]),
        "completed": len([cb for cb in codebundles if cb.enhancement_status == "completed"]),
        "failed": len([cb for cb in codebundles if cb.enhancement_status == "failed"])
    }
    
    # Access level stats
    access_stats = {
        "read_only": len([cb for cb in codebundles if cb.access_level == "read-only"]),
        "read_write": len([cb for cb in codebundles if cb.access_level == "read-write"]),
        "unknown": len([cb for cb in codebundles if cb.access_level == "unknown"])
    }
    
    # Task stats
    total_tasks = sum(cb.task_count or 0 for cb in codebundles)
    total_slis = sum(cb.sli_count or 0 for cb in codebundles)
    
    return {
        "collections": {
            "total": total_collections
        },
        "codebundles": {
            "total": total_codebundles,
            "enhancement_status": enhancement_stats,
            "access_levels": access_stats
        },
        "tasks": {
            "total_tasks": total_tasks,
            "total_slis": total_slis
        }
    }
