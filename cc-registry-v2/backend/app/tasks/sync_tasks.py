"""
Synchronization and scheduled tasks
"""
import logging
from typing import Dict, Any, List
from celery import current_task
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import CodeCollection, RawYamlData

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def sync_collections_task(self, yaml_data: Dict[str, Any] = None):
    """Sync collections from YAML data"""
    try:
        db = SessionLocal()
        
        # Get YAML data from database if not provided
        if not yaml_data:
            raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
            if not raw_yaml:
                raise ValueError("No YAML data found")
            yaml_data = raw_yaml.parsed_data
        
        collections_data = yaml_data.get('codecollections', [])
        synced_collections = []
        
        for collection_data in collections_data:
            try:
                slug = collection_data['slug']
                
                # Check if collection exists
                existing = db.query(CodeCollection).filter(CodeCollection.slug == slug).first()
                
                if existing:
                    # Update existing collection
                    existing.name = collection_data['name']
                    existing.git_url = collection_data['git_url']
                    existing.description = collection_data.get('description', '')
                    existing.owner = collection_data.get('owner', '')
                    existing.owner_email = collection_data.get('owner_email', '')
                    existing.owner_icon = collection_data.get('owner_icon', '')
                    existing.git_ref = collection_data.get('git_ref', 'main')
                    existing.is_active = collection_data.get('is_active', True)
                    
                    synced_collections.append({'action': 'updated', 'slug': slug})
                else:
                    # Create new collection
                    collection = CodeCollection(
                        name=collection_data['name'],
                        slug=slug,
                        git_url=collection_data['git_url'],
                        description=collection_data.get('description', ''),
                        owner=collection_data.get('owner', ''),
                        owner_email=collection_data.get('owner_email', ''),
                        owner_icon=collection_data.get('owner_icon', ''),
                        git_ref=collection_data.get('git_ref', 'main'),
                        is_active=collection_data.get('is_active', True)
                    )
                    db.add(collection)
                    synced_collections.append({'action': 'created', 'slug': slug})
                
            except Exception as e:
                logger.error(f"Failed to sync collection {collection_data.get('slug', 'unknown')}: {e}")
                continue
        
        db.commit()
        
        return {
            'status': 'success',
            'synced_collections': synced_collections,
            'total_synced': len(synced_collections),
            'message': f'Successfully synced {len(synced_collections)} collections'
        }
        
    except Exception as e:
        logger.error(f"Failed to sync collections: {e}")
        raise
    finally:
        db.close()

@celery_app.task(bind=True)
def scheduled_sync_task(self):
    """Scheduled task to sync all data"""
    try:
        logger.info("Starting scheduled sync")
        
        # Import data tasks to avoid circular imports
        from app.tasks.data_tasks import populate_registry_task
        
        # Trigger full registry population
        result = populate_registry_task.apply_async()
        # Note: Not waiting for completion to avoid blocking
        
        return {
            'status': 'success',
            'message': 'Scheduled sync initiated successfully'
        }
        
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")
        raise

@celery_app.task(bind=True)
def health_check_task(self):
    """Health check task for monitoring"""
    try:
        db = SessionLocal()
        
        # Check database connection
        collections_count = db.query(CodeCollection).count()
        
        # Check Redis connection (implicit through Celery)
        
        return {
            'status': 'healthy',
            'database': 'connected',
            'collections_count': collections_count,
            'timestamp': str(current_task.request.id),
            'message': 'All systems operational'
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': 'System health check failed'
        }
    finally:
        db.close()

# Periodic tasks configuration
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'scheduled-sync': {
        'task': 'app.tasks.sync_tasks.scheduled_sync_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'health-check': {
        'task': 'app.tasks.sync_tasks.health_check_task', 
        'schedule': 300.0,  # Every 5 minutes
    },
}
