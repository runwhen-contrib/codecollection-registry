from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import logging

from app.services.data_migration_service import DataPopulationService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    # For development, accept any token that starts with 'admin-'
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

@router.post("/populate-data")
async def trigger_data_population(token: str = Depends(verify_admin_token)):
    """Trigger comprehensive data population from original generate_registry.py"""
    try:
        logger.info("Starting data population triggered by admin")
        
        population_service = DataPopulationService()
        result = population_service.populate_registry_data()
        
        if result["status"] == "success":
            return {
                "message": "Registry data population completed successfully",
                "details": result
            }
        else:
            raise HTTPException(status_code=500, detail=f"Population failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Data population error: {e}")
        raise HTTPException(status_code=500, detail=f"Population failed: {str(e)}")

@router.get("/population-status")
async def get_population_status(token: str = Depends(verify_admin_token)):
    """Get current population status and statistics"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        
        db = SessionLocal()
        try:
            collections_count = db.query(CodeCollection).count()
            codebundles_count = db.query(Codebundle).count()
            # Count tasks from JSON field in codebundles
            codebundles = db.query(Codebundle).all()
            tasks_count = sum(len(cb.tasks or []) for cb in codebundles)
            
            return {
                "collections": collections_count,
                "codebundles": codebundles_count,
                "tasks": tasks_count,
                "status": "ready"
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/clear-data")
async def clear_all_data(token: str = Depends(verify_admin_token)):
    """Clear all data from the database (use with caution!)"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        
        db = SessionLocal()
        try:
            # Delete in reverse order to respect foreign key constraints
            db.query(Codebundle).delete()
            db.query(CodeCollection).delete()
            db.commit()
            
            return {
                "message": "All data cleared successfully",
                "collections_deleted": True,
                "codebundles_deleted": True,
                "tasks_deleted": True
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=f"Clear data failed: {str(e)}")
