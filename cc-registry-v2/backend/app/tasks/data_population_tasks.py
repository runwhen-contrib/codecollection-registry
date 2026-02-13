"""
Data Population Tasks - Statistics updates and collection management

Note: The primary sync/parse workflow is in registry_tasks.py and workflow_tasks.py.
This file contains supplementary tasks (statistics updates, etc.).

DO NOT define sync_all_collections_task or parse_all_codebundles_task here.
Those canonical tasks live in registry_tasks.py to avoid duplicate registrations.
"""
import logging
from datetime import datetime

from app.core.database import SessionLocal
from app.models import CodeCollection

logger = logging.getLogger(__name__)

# Use the shared Celery app (single instance for the entire application)
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True)
def update_collection_statistics_task(self):
    """
    Update collection statistics and metrics.
    Referenced by schedules.yaml as 'update-statistics-hourly'.
    """
    try:
        logger.info(f"Starting statistics update task {self.request.id}")
        
        db = SessionLocal()
        try:
            # Update statistics for all collections
            collections = db.query(CodeCollection).all()
            for collection in collections:
                collection.last_synced = datetime.utcnow()
            
            db.commit()
            
        finally:
            db.close()
        
        logger.info(f"Statistics update task {self.request.id} completed")
        return {'status': 'success', 'statistics_updated': True}
        
    except Exception as e:
        logger.error(f"Statistics update task {self.request.id} failed: {e}")
        raise
