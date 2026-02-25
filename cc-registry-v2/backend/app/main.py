from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
from app.core.config import settings
from app.core.database import engine, Base
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import all models to ensure they're registered with SQLAlchemy
from app.models import *

# Database tables are now managed via Alembic migrations
# Migrations run automatically on container startup via run_migrations.py

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Interactive CodeCollection Registry API — see /openapi.yaml for the full spec.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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

@app.get("/openapi.yaml", include_in_schema=False)
async def openapi_yaml():
    """Serve the hand-written OpenAPI spec as YAML."""
    from pathlib import Path
    spec_path = Path(__file__).parent.parent / "openapi.yaml"
    if spec_path.exists():
        return FileResponse(spec_path, media_type="application/x-yaml")
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="openapi.yaml not found")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CodeCollection Registry API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_yaml": "/openapi.yaml",
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
from app.routers import admin, tasks, raw_data, admin_crud, task_execution_admin, versions, task_management, admin_inventory, helm_charts, mcp_chat, chat_debug, github_issues, schedule_config, analytics, vector_search
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(raw_data.router)
app.include_router(admin_crud.router)
app.include_router(task_execution_admin.router, prefix="/api/v1")
app.include_router(admin_inventory.router)
app.include_router(versions.router, prefix="/api/v1/registry")
app.include_router(task_management.router)
app.include_router(schedule_config.router)
app.include_router(helm_charts.router, prefix="/api/v1", tags=["helm-charts"])
app.include_router(mcp_chat.router)
app.include_router(chat_debug.router)
app.include_router(github_issues.router, prefix="/api/v1")
app.include_router(analytics.router)
app.include_router(vector_search.router)

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
                    func.sum(Codebundle.task_count).label('total_tasks'),
                    func.sum(Codebundle.sli_count).label('total_slis')
                ).filter(
                    Codebundle.codecollection_id == collection.id,
                    Codebundle.is_active == True
                ).first()
                
                codebundle_count = codebundle_stats.codebundle_count or 0
                total_tasks = (codebundle_stats.total_tasks or 0) + (codebundle_stats.total_slis or 0)
                
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
                func.sum(Codebundle.task_count).label('total_tasks'),
                func.sum(Codebundle.sli_count).label('total_slis')
            ).filter(
                Codebundle.codecollection_id == collection.id,
                Codebundle.is_active == True
            ).first()
            
            codebundle_count = codebundle_stats.codebundle_count or 0
            total_tasks = (codebundle_stats.total_tasks or 0) + (codebundle_stats.total_slis or 0)
            
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
                    # Use PostgreSQL JSON contains operator with OR logic (match ANY tag)
                    tag_conditions = [
                        func.cast(Codebundle.support_tags, JSONB).op('@>')([tag])
                        for tag in tag_list
                    ]
                    query = query.filter(or_(*tag_conditions))
            
            # Search in display names and descriptions
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Codebundle.display_name.ilike(search_term),
                        Codebundle.description.ilike(search_term)
                    )
                )
            
            # Get total codebundle count before pagination
            codebundles_total = query.count()
            
            # Get the GLOBAL task count across ALL matching codebundles (not just the page).
            # Uses the authoritative task_count/sli_count integer fields set by the parser.
            global_task_stats = query.with_entities(
                func.coalesce(func.sum(Codebundle.task_count), 0).label('total_tasks'),
                func.coalesce(func.sum(Codebundle.sli_count), 0).label('total_slis')
            ).first()
            global_total_count = int(global_task_stats.total_tasks) + int(global_task_stats.total_slis)
            
            # Apply pagination
            codebundles = query.offset(offset).limit(limit).all()
            
            # Flatten tasks and SLIs from paginated codebundles
            all_tasks = []
            for codebundle in codebundles:
                # Clean up support tags - remove empty/whitespace-only tags
                clean_support_tags = []
                if codebundle.support_tags:
                    clean_support_tags = [tag.strip() for tag in codebundle.support_tags if tag and tag.strip()]
                
                # Add TaskSet tasks (handle both old string format and new object format)
                if codebundle.tasks:
                    for task in codebundle.tasks:
                        # Handle both old string format and new object format
                        if isinstance(task, str):
                            # Old format - just task name
                            task_name = task
                            task_id = codebundle.task_index.get(task_name, f"{codebundle.id}_task_{hash(task_name) % 10000}")
                        elif isinstance(task, dict):
                            # New format - task object
                            task_name = task.get('name', 'Unknown Task')
                            task_id = task.get('id', f"{codebundle.id}_task_{hash(task_name) % 10000}")
                        else:
                            continue
                        
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
                
                # Add SLI tasks (handle both old string format and new object format)
                if codebundle.slis:
                    for sli in codebundle.slis:
                        # Handle both old string format and new object format
                        if isinstance(sli, str):
                            # Old format - just SLI name
                            sli_name = sli
                        elif isinstance(sli, dict):
                            # New format - SLI object
                            sli_name = sli.get('name', 'Unknown SLI')
                        else:
                            continue
                            
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
                "total_count": global_total_count,
                "codebundles_count": codebundles_total,
                "support_tags": sorted(list(all_support_tags)),
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": codebundles_total > offset + limit
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
async def list_codebundles(
    limit: int = Query(50, description="Number of codebundles to return"), 
    offset: int = Query(0, description="Offset for pagination"),
    search: Optional[str] = Query(None, description="Search in name, display_name, or description"),
    collection_id: Optional[int] = Query(None, description="Filter by collection ID"),
    tags: Optional[str] = Query(None, description="Filter by support tags (comma-separated)"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    has_auto_discovery: Optional[bool] = Query(None, description="Filter by auto-discovery capability"),
    sort_by: Optional[str] = Query("name", description="Sort by: name, updated, tasks")
):
    """List codebundles with pagination, search, and filters"""
    try:
        from app.core.database import SessionLocal
        from app.models import Codebundle, CodeCollection
        import sqlalchemy
        from sqlalchemy import or_, desc, func
        
        db = SessionLocal()
        try:
            # Build base query
            query = db.query(Codebundle).filter(Codebundle.is_active == True)
            
            # Apply search filter — supports natural language queries
            # by splitting into keywords and matching word-by-word
            if search:
                _STOP_WORDS = {
                    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
                    'am', 'do', 'does', 'did', 'have', 'has', 'had', 'having',
                    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she',
                    'it', 'its', 'they', 'them', 'their', 'there', 'here',
                    'and', 'or', 'but', 'if', 'so', 'yet', 'nor', 'not', 'no',
                    'at', 'by', 'for', 'from', 'in', 'into', 'of', 'on', 'to',
                    'up', 'out', 'off', 'with', 'as', 'than', 'too', 'very',
                    'how', 'what', 'when', 'where', 'why', 'which', 'who',
                    'whom', 'this', 'that', 'these', 'those', 'can', 'could',
                    'will', 'would', 'shall', 'should', 'may', 'might',
                    'about', 'over', 'just', 'also', 'some', 'any', 'all',
                }
                raw_words = [w.strip('?.,!:;()[]"\' ') for w in search.split()]
                keywords = [w for w in raw_words
                            if len(w) >= 2 and w.lower() not in _STOP_WORDS]
                # Fallback: if everything was filtered, keep the longest words
                if not keywords:
                    keywords = sorted(raw_words, key=len, reverse=True)[:3]
                
                # support_tags is a JSON column — cast to text for ILIKE
                tags_text = func.cast(Codebundle.support_tags, sqlalchemy.Text)
                
                def _kw_filter(kw):
                    """Match a keyword in any searchable field."""
                    t = f"%{kw}%"
                    return or_(
                        Codebundle.name.ilike(t),
                        Codebundle.display_name.ilike(t),
                        Codebundle.description.ilike(t),
                        Codebundle.doc.ilike(t),
                        tags_text.ilike(t),
                    )
                
                if len(keywords) == 1:
                    # Single keyword: simple substring search
                    query = query.filter(_kw_filter(keywords[0]))
                elif len(keywords) == 2:
                    # Two keywords: require BOTH to match (AND)
                    for kw in keywords:
                        query = query.filter(_kw_filter(kw))
                else:
                    # Natural-language query (4+ keywords):
                    # Use OR matching — a codebundle matches if ANY keyword
                    # appears in its searchable fields.  Results are scored
                    # by how many keywords match so the most relevant bubble up.
                    from sqlalchemy import case, literal
                    keyword_conditions = [_kw_filter(kw) for kw in keywords[:6]]
                    query = query.filter(or_(*keyword_conditions))
                    
                    # Build a weighted relevance score per keyword.
                    # Name/slug matches are much more specific than
                    # description matches (which often contain common words).
                    #   name match:         +4  (most specific)
                    #   display_name match: +3
                    #   tags match:         +3  (curated metadata)
                    #   description match:  +1
                    #   doc match:          +1  (long text, many false positives)
                    score_terms = []
                    for kw in keywords[:6]:
                        t = f"%{kw}%"
                        kw_score = (
                            case((Codebundle.name.ilike(t), literal(4)), else_=literal(0))
                            + case((Codebundle.display_name.ilike(t), literal(3)), else_=literal(0))
                            + case((tags_text.ilike(t), literal(3)), else_=literal(0))
                            + case((Codebundle.description.ilike(t), literal(1)), else_=literal(0))
                            + case((Codebundle.doc.ilike(t), literal(1)), else_=literal(0))
                        )
                        score_terms.append(kw_score)
                    relevance = score_terms[0]
                    for term in score_terms[1:]:
                        relevance = relevance + term
                    
                    # Override default sort: rank by relevance first
                    sort_by = "__relevance__"
                    query = query.order_by(relevance.desc(), Codebundle.name)
            
            # Apply collection filter
            if collection_id:
                query = query.filter(Codebundle.codecollection_id == collection_id)
            
            # Apply tags filter (match any of the provided tags)
            if tags:
                tag_list = [tag.strip().upper() for tag in tags.split(',')]
                # support_tags is a JSON column — cast to text for ILIKE matching
                tags_as_text = func.cast(Codebundle.support_tags, sqlalchemy.Text)
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append(tags_as_text.ilike(f'%{tag}%'))
                if tag_conditions:
                    query = query.filter(or_(*tag_conditions))
            
            # Apply platform filter
            if platform:
                query = query.filter(Codebundle.discovery_platform == platform)
            
            # Apply access level filter
            if access_level:
                query = query.filter(Codebundle.access_level == access_level)
            
            # Apply auto-discovery filter
            if has_auto_discovery is not None:
                query = query.filter(Codebundle.has_genrules == has_auto_discovery)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply sorting (skip if relevance scoring already applied)
            if sort_by == "__relevance__":
                pass  # Already sorted by keyword-match relevance
            elif sort_by == "updated":
                query = query.order_by(desc(Codebundle.git_updated_at), desc(Codebundle.updated_at))
            elif sort_by == "tasks":
                query = query.order_by(desc(Codebundle.task_count))
            else:  # Default to name
                query = query.order_by(Codebundle.name)
            
            # Apply pagination
            codebundles = query.limit(limit).offset(offset).all()
            
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
                    "readme": cb.readme,
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
                    "data_classifications": cb.data_classifications or {},
                    "minimum_iam_requirements": cb.minimum_iam_requirements or [],
                    "ai_enhanced_metadata": cb.ai_enhanced_metadata or {},
                    "last_enhanced": cb.last_enhanced,
                    # Top-level platform for easy access by MCP / API consumers
                    "platform": cb.discovery_platform,
                    # Discovery information
                    "configuration_type": {
                        "type": "Automatically Discovered" if cb.has_genrules else "Manual",
                        "has_generation_rules": cb.has_genrules,
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
            
            return {
                "codebundles": result,
                "total_count": total_count,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > offset + limit
                }
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error listing codebundles: {e}")
        return {"codebundles": [], "total_count": 0, "pagination": {"limit": limit, "offset": offset, "has_more": False}}

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
                "readme": codebundle.readme,
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
                "git_updated_at": codebundle.git_updated_at,
                # Configuration variables
                "user_variables": codebundle.user_variables or [],
                # AI Enhancement fields
                "enhancement_status": codebundle.enhancement_status or "pending",
                "ai_enhanced_description": codebundle.ai_enhanced_description,
                "access_level": codebundle.access_level or "unknown",
                "data_classifications": codebundle.data_classifications or {},
                "minimum_iam_requirements": codebundle.minimum_iam_requirements or [],
                "ai_enhanced_metadata": codebundle.ai_enhanced_metadata or {},
                "last_enhanced": codebundle.last_enhanced,
                # Discovery information
                "configuration_type": {
                    "type": "Automatically Discovered" if codebundle.has_genrules else "Manual",
                    "has_generation_rules": codebundle.has_genrules,
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

@app.get("/api/v1/registry/recent-codebundles")
async def get_recent_codebundles():
    """Get the 10 most recently updated codebundles based on git update date"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import desc
        
        db = SessionLocal()
        try:
            # Get recent codebundles ordered by git_updated_at only, excluding rw-generic-codecollection
            codebundles = db.query(Codebundle).join(
                CodeCollection, Codebundle.codecollection_id == CodeCollection.id
            ).filter(
                Codebundle.is_active == True,
                Codebundle.git_updated_at.isnot(None),  # Only codebundles with git dates
                CodeCollection.slug != 'rw-generic-codecollection'  # Exclude generics
            ).order_by(
                desc(Codebundle.git_updated_at)
            ).limit(20).all()
            
            result = []
            for cb in codebundles:
                collection = db.query(CodeCollection).filter(
                    CodeCollection.id == cb.codecollection_id
                ).first()
                
                result.append({
                    "id": cb.id,
                    "name": cb.name,
                    "slug": cb.slug,
                    "display_name": cb.display_name or cb.name,
                    "description": cb.description[:150] + "..." if cb.description and len(cb.description) > 150 else cb.description,
                    "collection_name": collection.name if collection else "Unknown",
                    "collection_slug": collection.slug if collection else "",
                    "platform": cb.discovery_platform or "Unknown",
                    "task_count": cb.task_count or 0,
                    "git_updated_at": cb.git_updated_at.isoformat() if cb.git_updated_at else None,
                    "updated_at": cb.updated_at.isoformat() if cb.updated_at else None,
                })
            
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting recent codebundles: {e}")
        return []


@app.get("/api/v1/registry/recent-tasks")
async def get_recent_tasks():
    """Get the 10 most recently added tasks based on git update date"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import desc
        
        db = SessionLocal()
        try:
            # Get codebundles with tasks, ordered by git_updated_at, excluding rw-generic-codecollection
            codebundles = db.query(Codebundle).join(
                CodeCollection, Codebundle.codecollection_id == CodeCollection.id
            ).filter(
                Codebundle.is_active == True,
                Codebundle.git_updated_at.isnot(None),
                Codebundle.tasks.isnot(None),
                CodeCollection.slug != 'rw-generic-codecollection'  # Exclude generics
            ).order_by(
                desc(Codebundle.git_updated_at)
            ).limit(100).all()  # Get more codebundles to extract tasks from
            
            result = []
            for cb in codebundles:
                collection = db.query(CodeCollection).filter(
                    CodeCollection.id == cb.codecollection_id
                ).first()
                
                # Skip if somehow we got a generic collection (shouldn't happen)
                if collection and collection.slug == 'rw-generic-codecollection':
                    continue
                
                # Extract task names from the codebundle
                if cb.tasks:
                    for task in cb.tasks:
                        # Handle both string and dict formats
                        if isinstance(task, str):
                            task_name = task
                        elif isinstance(task, dict):
                            task_name = task.get('name', 'Unknown Task')
                        else:
                            continue
                        
                        result.append({
                            "task_name": task_name,
                            "codebundle_name": cb.display_name or cb.name,
                            "codebundle_slug": cb.slug,
                            "collection_name": collection.name if collection else "Unknown",
                            "collection_slug": collection.slug if collection else "",
                            "git_updated_at": cb.git_updated_at.isoformat() if cb.git_updated_at else None,
                        })
                        
                        # Stop once we have 20 tasks
                        if len(result) >= 20:
                            break
                
                if len(result) >= 20:
                    break
            
            return result[:20]
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting recent tasks: {e}")
        return []


@app.get("/api/v1/registry/tag-icons")
async def get_tag_icons():
    """Get tag-to-icon mappings from map-tag-icons.yaml"""
    import yaml
    import os
    
    # Try multiple possible locations for the yaml file
    possible_paths = [
        "/app/map-tag-icons.yaml",
        "/workspaces/codecollection-registry/map-tag-icons.yaml",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "map-tag-icons.yaml"),
        "map-tag-icons.yaml"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)
                    # Convert to a more usable format: {TAG: icon_url}
                    icon_map = {}
                    for item in data.get('icons', []):
                        url = item.get('url', '')
                        for tag in item.get('tags', []):
                            icon_map[tag.upper()] = url
                    return {"icons": icon_map}
            except Exception as e:
                logger.error(f"Error reading tag icons from {path}: {e}")
                continue
    
    # Fallback to hardcoded defaults if file not found
    logger.warning("map-tag-icons.yaml not found, using defaults")
    return {
        "icons": {
            "KUBERNETES": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/kubernetes-icon-color.svg",
            "GKE": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/gcp/google_kubernetes_engine/google_kubernetes_engine.svg",
            "AKS": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/azure/containers/10023-icon-service-Kubernetes-Services.svg",
            "EKS": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/amazon-eks.svg",
            "OPENSHIFT": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/OpenShift-LogoType.svg",
            "GCP": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/google-cloud-platform.svg",
            "AWS": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/Amazon_Web_Services_Logo.svg",
            "AZURE": "https://storage.googleapis.com/runwhen-nonprod-shared-images/icons/azure-icon.svg",
        }
    }


@app.get("/api/v1/registry/stats")
async def get_registry_stats():
    """Get registry-wide statistics for the homepage"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            # Count collections
            collections_count = db.query(CodeCollection).filter(CodeCollection.is_active == True).count()
            
            # Count codebundles
            codebundles_count = db.query(Codebundle).filter(Codebundle.is_active == True).count()
            
            # Count tasks and SLIs using the authoritative integer fields (task_count, sli_count)
            # set by the canonical parser. This is both more efficient (SQL SUM vs loading all
            # records) and more reliable than counting JSON array lengths, which could drift
            # if a competing code path updates the arrays without updating the counts.
            stats = db.query(
                func.coalesce(func.sum(Codebundle.task_count), 0).label('total_tasks'),
                func.coalesce(func.sum(Codebundle.sli_count), 0).label('total_slis')
            ).filter(Codebundle.is_active == True).first()
            
            total_tasks = int(stats.total_tasks)
            total_slis = int(stats.total_slis)
            total_items = total_tasks + total_slis
            
            # Get tasks over time (by collection for now - simulated growth data)
            # In production, you'd track this in a separate table
            tasks_over_time = [
                {"month": "Jan 2024", "tasks": int(total_items * 0.4)},
                {"month": "Feb 2024", "tasks": int(total_items * 0.5)},
                {"month": "Mar 2024", "tasks": int(total_items * 0.6)},
                {"month": "Apr 2024", "tasks": int(total_items * 0.7)},
                {"month": "May 2024", "tasks": int(total_items * 0.75)},
                {"month": "Jun 2024", "tasks": int(total_items * 0.8)},
                {"month": "Jul 2024", "tasks": int(total_items * 0.85)},
                {"month": "Aug 2024", "tasks": int(total_items * 0.9)},
                {"month": "Sep 2024", "tasks": int(total_items * 0.92)},
                {"month": "Oct 2024", "tasks": int(total_items * 0.95)},
                {"month": "Nov 2024", "tasks": int(total_items * 0.98)},
                {"month": "Dec 2024", "tasks": int(total_items)},
            ]
            
            return {
                "collections": collections_count,
                "codebundles": codebundles_count,
                "tasks": total_items,
                "slis": total_slis,
                "tasks_over_time": tasks_over_time
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"collections": 0, "codebundles": 0, "tasks": 0, "slis": 0, "tasks_over_time": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
