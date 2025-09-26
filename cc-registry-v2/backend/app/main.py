from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import engine, Base
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import all models to ensure they're registered with SQLAlchemy
from app.models import *

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Interactive CodeCollection Registry",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CodeCollection Registry API",
        "version": "1.0.0",
        "docs": "/docs" if settings.DEBUG else "Documentation not available in production",
        "health": "/api/v1/health"
    }

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from app.core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        database_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = "disconnected"
    
    return {
        "status": "healthy" if database_status == "connected" else "unhealthy",
        "database": database_status,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

# Include routers
from app.routers import admin, tasks, raw_data, admin_crud, ai_admin, ai_enhancement_admin, task_execution_admin, versions, task_management, admin_inventory
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(raw_data.router)
app.include_router(admin_crud.router)
app.include_router(ai_admin.router)
app.include_router(ai_enhancement_admin.router, prefix="/api/v1")
app.include_router(task_execution_admin.router, prefix="/api/v1")
app.include_router(admin_inventory.router)
app.include_router(versions.router, prefix="/api/v1/registry")
app.include_router(task_management.router)

@app.get("/api/v1/registry/collections")
async def list_collections():
    """List all codecollections with statistics"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            
            result = []
            for collection in collections:
                # Calculate statistics for each collection
                codebundle_stats = db.query(
                    func.count(Codebundle.id).label('codebundle_count'),
                    func.sum(Codebundle.task_count).label('total_tasks')
                ).filter(
                    Codebundle.codecollection_id == collection.id,
                    Codebundle.is_active == True
                ).first()
                
                codebundle_count = codebundle_stats.codebundle_count or 0
                total_tasks = codebundle_stats.total_tasks or 0
                
                result.append({
                    "id": collection.id,
                    "name": collection.name,
                    "slug": collection.slug,
                    "git_url": collection.git_url,
                    "description": collection.description,
                    "owner": collection.owner,
                    "owner_email": collection.owner_email,
                    "owner_icon": collection.owner_icon,
                    "git_ref": collection.git_ref,
                    "last_synced": collection.last_synced,
                    "is_active": collection.is_active,
                    "created_at": collection.created_at,
                    "updated_at": collection.updated_at,
                    "statistics": {
                        "codebundle_count": codebundle_count,
                        "total_tasks": total_tasks
                    }
                })
            
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return []

@app.get("/api/v1/registry/collections/{collection_slug}")
async def get_collection_by_slug(collection_slug: str):
    """Get a specific collection by slug with statistics"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            # Find the collection
            collection = db.query(CodeCollection).filter(
                CodeCollection.slug == collection_slug,
                CodeCollection.is_active == True
            ).first()
            
            if not collection:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Collection '{collection_slug}' not found"}
                )
            
            # Calculate statistics for this collection
            codebundle_stats = db.query(
                func.count(Codebundle.id).label('codebundle_count'),
                func.sum(Codebundle.task_count).label('total_tasks')
            ).filter(
                Codebundle.codecollection_id == collection.id,
                Codebundle.is_active == True
            ).first()
            
            codebundle_count = codebundle_stats.codebundle_count or 0
            total_tasks = codebundle_stats.total_tasks or 0
            
            return {
                "id": collection.id,
                "name": collection.name,
                "slug": collection.slug,
                "git_url": collection.git_url,
                "description": collection.description,
                "owner": collection.owner,
                "owner_email": collection.owner_email,
                "owner_icon": collection.owner_icon,
                "git_ref": collection.git_ref,
                "last_synced": collection.last_synced,
                "is_active": collection.is_active,
                "created_at": collection.created_at,
                "updated_at": collection.updated_at,
                "statistics": {
                    "codebundle_count": codebundle_count,
                    "total_tasks": total_tasks
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting collection: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )


@app.get("/api/v1/registry/tasks")
async def get_all_tasks(
    support_tags: str = None,  # Comma-separated list of tags
    search: str = None,
    collection_slug: str = None,
    limit: int = 100,
    offset: int = 0
):
    """Get all tasks with filtering and pagination"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import func, and_, or_
        from sqlalchemy.dialects.postgresql import JSONB
        
        db = SessionLocal()
        try:
            # Build the query
            query = db.query(Codebundle).filter(Codebundle.is_active == True)
            
            # Filter by collection if specified
            if collection_slug:
                query = query.join(CodeCollection).filter(CodeCollection.slug == collection_slug)
            
            # Filter by support tags if specified (multiple tags)
            if support_tags:
                # Parse comma-separated tags
                tag_list = [tag.strip() for tag in support_tags.split(',') if tag.strip()]
                if tag_list:
                    # Use PostgreSQL JSON contains operator for each tag (AND logic)
                    for tag in tag_list:
                        query = query.filter(
                            func.cast(Codebundle.support_tags, JSONB).op('@>')([tag])
                        )
            
            # Search in display names and descriptions
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Codebundle.display_name.ilike(search_term),
                        Codebundle.description.ilike(search_term)
                    )
                )
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply pagination
            codebundles = query.offset(offset).limit(limit).all()
            
            # Flatten tasks and SLIs from all codebundles
            all_tasks = []
            for codebundle in codebundles:
                # Clean up support tags - remove empty/whitespace-only tags
                clean_support_tags = []
                if codebundle.support_tags:
                    clean_support_tags = [tag.strip() for tag in codebundle.support_tags if tag and tag.strip()]
                
                # Add TaskSet tasks
                if codebundle.tasks:
                    for task_name in codebundle.tasks:
                        # Get unique task ID from task_index
                        task_id = codebundle.task_index.get(task_name, f"{codebundle.id}_task_{hash(task_name) % 10000}")
                        
                        all_tasks.append({
                            "id": task_id,
                            "name": task_name,
                            "type": "TaskSet",
                            "codebundle_id": codebundle.id,
                            "codebundle_name": codebundle.display_name or codebundle.name,
                            "codebundle_slug": codebundle.slug,
                            "collection_name": codebundle.codecollection.name,
                            "collection_slug": codebundle.codecollection.slug,
                            "description": codebundle.description,
                            "support_tags": clean_support_tags,
                            "categories": codebundle.categories or [],
                            "author": codebundle.author,
                            "runbook_path": codebundle.runbook_path,
                            "runbook_source_url": codebundle.runbook_source_url,
                            "git_url": codebundle.codecollection.git_url,
                            "git_ref": codebundle.codecollection.git_ref
                        })
                
                # Add SLI tasks
                if codebundle.slis:
                    for sli_name in codebundle.slis:
                        # Generate unique SLI ID
                        sli_id = f"{codebundle.id}_sli_{hash(sli_name) % 10000}"
                        
                        all_tasks.append({
                            "id": sli_id,
                            "name": sli_name,
                            "type": "SLI",
                            "codebundle_id": codebundle.id,
                            "codebundle_name": codebundle.display_name or codebundle.name,
                            "codebundle_slug": codebundle.slug,
                            "collection_name": codebundle.codecollection.name,
                            "collection_slug": codebundle.codecollection.slug,
                            "description": codebundle.description,
                            "support_tags": clean_support_tags,
                            "categories": codebundle.categories or [],
                            "author": codebundle.author,
                            "runbook_path": codebundle.runbook_path,
                            "runbook_source_url": codebundle.runbook_source_url,
                            "git_url": codebundle.codecollection.git_url,
                            "git_ref": codebundle.codecollection.git_ref
                        })
            
            # Get all unique support tags for filtering
            all_support_tags = set()
            all_codebundles = db.query(Codebundle).filter(
                Codebundle.is_active == True,
                Codebundle.support_tags != None
            ).all()
            
            for cb in all_codebundles:
                if cb.support_tags:
                    # Clean up tags (remove empty/whitespace-only tags)
                    clean_tags = [tag.strip() for tag in cb.support_tags if tag and tag.strip()]
                    all_support_tags.update(clean_tags)
            
            return {
                "tasks": all_tasks,
                "total_count": len(all_tasks),
                "codebundles_count": total_count,
                "support_tags": sorted(list(all_support_tags)),
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > offset + limit
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

@app.get("/api/v1/codebundles")
async def list_codebundles():
    """List all codebundles"""
    try:
        from app.core.database import SessionLocal
        from app.models import Codebundle, CodeCollection
        
        db = SessionLocal()
        try:
            codebundles = db.query(Codebundle).filter(Codebundle.is_active == True).all()
            
            result = []
            for cb in codebundles:
                # Get codecollection data separately to avoid lazy loading issues
                collection = db.query(CodeCollection).filter(CodeCollection.id == cb.codecollection_id).first()
                
                result.append({
                    "id": cb.id,
                    "name": cb.name,
                    "slug": cb.slug,
                    "display_name": cb.display_name,
                    "description": cb.description,
                    "doc": cb.doc,
                    "author": cb.author,
                    "support_tags": cb.support_tags,
                    "tasks": cb.tasks,
                    "slis": cb.slis,
                    "task_count": cb.task_count,
                    "sli_count": cb.sli_count,
                    "runbook_source_url": cb.runbook_source_url,
                    "created_at": cb.created_at,
                    # AI Enhancement fields
                    "enhancement_status": cb.enhancement_status or "pending",
                    "ai_enhanced_description": cb.ai_enhanced_description,
                    "access_level": cb.access_level or "unknown",
                    "minimum_iam_requirements": cb.minimum_iam_requirements or [],
                    "ai_enhanced_metadata": cb.ai_enhanced_metadata or {},
                    "last_enhanced": cb.last_enhanced,
                    # Discovery information
                    "discovery": {
                        "is_discoverable": cb.is_discoverable,
                        "platform": cb.discovery_platform,
                        "resource_types": cb.discovery_resource_types,
                        "match_patterns": cb.discovery_match_patterns,
                        "templates": cb.discovery_templates,
                        "output_items": cb.discovery_output_items,
                        "level_of_detail": cb.discovery_level_of_detail,
                        "runwhen_directory_path": cb.runwhen_directory_path
                    },
                    "codecollection": {
                        "id": collection.id,
                        "name": collection.name,
                        "slug": collection.slug,
                        "git_url": collection.git_url
                    } if collection else None
                })
            
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error listing codebundles: {e}")
        return []

@app.get("/api/v1/collections/{collection_slug}/codebundles/{codebundle_slug}")
async def get_codebundle_by_slug(collection_slug: str, codebundle_slug: str):
    """Get a specific codebundle by collection slug and codebundle slug"""
    try:
        from app.core.database import SessionLocal
        from app.models import Codebundle, CodeCollection
        
        db = SessionLocal()
        try:
            # First find the collection
            collection = db.query(CodeCollection).filter(
                CodeCollection.slug == collection_slug,
                CodeCollection.is_active == True
            ).first()
            
            if not collection:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Collection '{collection_slug}' not found"}
                )
            
            # Then find the codebundle within that collection
            codebundle = db.query(Codebundle).filter(
                Codebundle.codecollection_id == collection.id,
                Codebundle.slug == codebundle_slug,
                Codebundle.is_active == True
            ).first()
            
            if not codebundle:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Codebundle '{codebundle_slug}' not found in collection '{collection_slug}'"}
                )
            
            return {
                "id": codebundle.id,
                "name": codebundle.name,
                "slug": codebundle.slug,
                "display_name": codebundle.display_name,
                "description": codebundle.description,
                "doc": codebundle.doc,
                "author": codebundle.author,
                "support_tags": codebundle.support_tags,
                "tasks": codebundle.tasks,
                "slis": codebundle.slis,
                "task_count": codebundle.task_count,
                "sli_count": codebundle.sli_count,
                "runbook_path": codebundle.runbook_path,
                "sli_path": codebundle.sli_path,
                "runbook_source_url": codebundle.runbook_source_url,
                "created_at": codebundle.created_at,
                "updated_at": codebundle.updated_at,
                # AI Enhancement fields
                "enhancement_status": codebundle.enhancement_status or "pending",
                "ai_enhanced_description": codebundle.ai_enhanced_description,
                "access_level": codebundle.access_level or "unknown",
                "minimum_iam_requirements": codebundle.minimum_iam_requirements or [],
                "ai_enhanced_metadata": codebundle.ai_enhanced_metadata or {},
                "last_enhanced": codebundle.last_enhanced,
                # Discovery information
                "discovery": {
                    "is_discoverable": codebundle.is_discoverable,
                    "platform": codebundle.discovery_platform,
                    "resource_types": codebundle.discovery_resource_types,
                    "match_patterns": codebundle.discovery_match_patterns,
                    "templates": codebundle.discovery_templates,
                    "output_items": codebundle.discovery_output_items,
                    "level_of_detail": codebundle.discovery_level_of_detail,
                    "runwhen_directory_path": codebundle.runwhen_directory_path
                },
                "codecollection": {
                    "id": collection.id,
                    "name": collection.name,
                    "slug": collection.slug,
                    "git_url": collection.git_url
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting codebundle: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
