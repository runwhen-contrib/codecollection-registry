from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
import logging

from app.services.data_migration_service import DataPopulationService
from app.services.helm_sync import sync_runwhen_local_chart
from app.core.config import settings
from app.core.database import get_db
from sqlalchemy.orm import Session

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

@router.post("/sync-helm-charts")
async def sync_helm_charts(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Sync helm chart versions from repository"""
    try:
        logger.info("Starting helm chart sync triggered by admin")
        
        result = sync_runwhen_local_chart(db)
        
        logger.info(f"Helm chart sync completed: {result}")
        return {
            "status": "success",
            "message": "Helm chart versions synced successfully",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Helm chart sync failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Helm chart sync failed: {str(e)}")

@router.get("/releases/status")
async def get_releases_status(token: str = Depends(verify_admin_token)):
    """Get version management status and statistics (versions are now automatically synced during collection indexing)"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, CodeCollectionVersion, VersionCodebundle
        
        db = SessionLocal()
        try:
            # Get release statistics
            total_collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).count()
            collections_with_versions = db.query(CodeCollection).join(CodeCollectionVersion).distinct().count()
            total_versions = db.query(CodeCollectionVersion).filter(CodeCollectionVersion.is_active == True).count()
            total_version_codebundles = db.query(VersionCodebundle).count()
            
            # Get latest versions
            latest_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.is_latest == True,
                CodeCollectionVersion.is_active == True
            ).count()
            
            # Get prerelease count
            prereleases = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.is_prerelease == True,
                CodeCollectionVersion.is_active == True
            ).count()
            
            # Get version type counts
            main_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.version_type == 'main',
                CodeCollectionVersion.is_active == True
            ).count()
            
            tag_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.version_type == 'tag',
                CodeCollectionVersion.is_active == True
            ).count()
            
            return {
                "total_collections": total_collections,
                "collections_with_versions": collections_with_versions,
                "total_versions": total_versions,
                "latest_versions": latest_versions,
                "prereleases": prereleases,
                "main_versions": main_versions,
                "tag_versions": tag_versions,
                "total_version_codebundles": total_version_codebundles,
                "coverage_percentage": round((collections_with_versions / total_collections * 100) if total_collections > 0 else 0, 2)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting release status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get release status: {str(e)}")
