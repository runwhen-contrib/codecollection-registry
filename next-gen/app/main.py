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
from app.routers import admin, tasks, raw_data
app.include_router(admin.router)
app.include_router(tasks.router)
app.include_router(raw_data.router)

@app.get("/api/v1/registry/collections")
async def list_collections():
    """List all codecollections"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection
        
        db = SessionLocal()
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        db.close()
        
        return [
            {
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
                "updated_at": collection.updated_at
            }
            for collection in collections
        ]
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return []

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
                    "task_count": cb.task_count,
                    "created_at": cb.created_at,
                    "codecollection": {
                        "id": collection.id,
                        "name": collection.name,
                        "slug": collection.slug
                    } if collection else None
                })
            
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error listing codebundles: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
