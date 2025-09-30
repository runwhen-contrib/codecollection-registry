"""
Data Population Tasks - Broken down into logical subtasks
"""
import os
import yaml
import shutil
import tempfile
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawYamlData, RawRepositoryData
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'registry_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks.data_population_tasks', 'app.tasks.data_enhancement_tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=True,
)

@celery_app.task(bind=True)
def populate_registry_task(self, collection_slugs: List[str] = None):
    """
    Main task to populate the registry - store raw data first, then parse
    """
    try:
        logger.info(f"Starting registry population task {self.request.id}")
        
        # Update task status
        self.update_state(state='PROGRESS', meta={'step': 'initializing', 'progress': 0})
        
        # Load YAML data
        yaml_data = self._load_yaml_data()
        if not yaml_data:
            raise ValueError("Failed to load YAML data")
        
        # Step 1: Store raw YAML data
        self.update_state(state='PROGRESS', meta={'step': 'storing_yaml', 'progress': 20})
        from app.tasks.raw_data_tasks import store_yaml_data_task
        yaml_result = store_yaml_data_task(yaml_data)
        
        # Step 2: Clone repositories and store raw files
        self.update_state(state='PROGRESS', meta={'step': 'cloning_repos', 'progress': 50})
        from app.tasks.raw_data_tasks import clone_repositories_task
        clone_result = clone_repositories_task(collection_slugs)
        
        # Step 3: Parse stored raw data
        self.update_state(state='PROGRESS', meta={'step': 'parsing_data', 'progress': 80})
        from app.tasks.raw_data_tasks import parse_stored_data_task
        parse_result = parse_stored_data_task()
        
        # Step 4: Update statistics
        self.update_state(state='PROGRESS', meta={'step': 'updating_statistics', 'progress': 90})
        stats_result = update_collection_statistics_task()
        
        logger.info(f"Registry population task {self.request.id} completed successfully")
        return {
            'status': 'success',
            'message': 'Registry population completed',
            'yaml_stored': yaml_result.get('status') == 'success',
            'collections_cloned': clone_result.get('collections_processed', 0),
            'codebundles_created': parse_result.get('codebundles_created', 0),
            'statistics_updated': stats_result.get('statistics_updated', False)
        }
        
    except Exception as e:
        logger.error(f"Registry population task {self.request.id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

    def _load_yaml_data(self):
        """Load YAML data from file"""
        try:
            yaml_path = "/app/codecollections.yaml"
            with open(yaml_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            logger.error("codecollections.yaml not found")
            return None
        except Exception as e:
            logger.error(f"Error loading YAML data: {e}")
            return None

@celery_app.task(bind=True)
def sync_collections_task(self, yaml_data: Dict[str, Any] = None, collection_slugs: List[str] = None):
    """
    Sync codecollections from YAML data and clone repositories
    """
    try:
        logger.info(f"Starting collections sync task {self.request.id}")
        
        # Use provided YAML data or load from file as fallback
        if not yaml_data:
            yaml_path = "/app/codecollections.yaml"
            try:
                with open(yaml_path, 'r') as file:
                    yaml_data = yaml.safe_load(file)
            except FileNotFoundError:
                logger.error("No YAML data provided and file not found")
                return {'status': 'error', 'message': 'No YAML data available'}
        
        collections_processed = 0
        temp_dir = tempfile.mkdtemp(prefix="registry_sync_")
        
        try:
            for collection_data in yaml_data.get('codecollections', []):
                # Filter by slugs if provided
                if collection_slugs and collection_data['slug'] not in collection_slugs:
                    continue
                
                logger.info(f"Processing collection: {collection_data['name']}")
                
                # Update collection in database
                db = SessionLocal()
                try:
                    collection = db.query(CodeCollection).filter(
                        CodeCollection.slug == collection_data['slug']
                    ).first()
                    
                    if not collection:
                        collection = CodeCollection(
                            name=collection_data['name'],
                            slug=collection_data['slug'],
                            git_url=collection_data['git_url'],
                            description=collection_data.get('description', ''),
                            owner=collection_data.get('owner', ''),
                            owner_email=collection_data.get('owner_email', ''),
                            owner_icon=collection_data.get('owner_icon', ''),
                            git_ref=collection_data.get('git_ref', 'main'),
                            is_active=True
                        )
                        db.add(collection)
                    else:
                        # Update existing collection
                        collection.name = collection_data['name']
                        collection.git_url = collection_data['git_url']
                        collection.description = collection_data.get('description', '')
                        collection.owner = collection_data.get('owner', '')
                        collection.owner_email = collection_data.get('owner_email', '')
                        collection.owner_icon = collection_data.get('owner_icon', '')
                        collection.git_ref = collection_data.get('git_ref', 'main')
                        collection.last_synced = datetime.utcnow()
                    
                    db.commit()
                    db.refresh(collection)
                    
                    # Clone repository
                    self._clone_repository(collection_data, temp_dir)
                    collections_processed += 1
                    
                finally:
                    db.close()
                    
        finally:
            # Cleanup temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
        logger.info(f"Collections sync task {self.request.id} completed: {collections_processed} collections")
        return {'status': 'success', 'collections_processed': collections_processed}
        
    except Exception as e:
        logger.error(f"Collections sync task {self.request.id} failed: {e}")
        raise
    
    def _clone_repository(self, collection_data: Dict[str, Any], temp_dir: str):
        """Clone a repository to temp directory"""
        import git
        
        git_url = collection_data['git_url']
        org = git_url.split("/")[-2]
        repo_name = git_url.split("/")[-1]
        ref = collection_data.get('git_ref', 'main')
        
        clone_path = os.path.join(temp_dir, org)
        if not os.path.exists(clone_path):
            os.makedirs(clone_path)
        
        try:
            git.Repo.clone_from(git_url, os.path.join(clone_path, repo_name), branch=ref)
        except Exception as e:
            logger.error(f"Failed to clone {git_url}: {e}")
            raise

@celery_app.task(bind=True)
def parse_all_codebundles_task(self):
    """
    Parse all robot files and extract codebundles
    """
    try:
        logger.info(f"Starting codebundles parsing task {self.request.id}")
        
        db = SessionLocal()
        try:
            collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            codebundles_processed = 0
            
            for collection in collections:
                logger.info(f"Parsing codebundles for collection: {collection.name}")
                
                # This would parse robot files and extract codebundles
                # Implementation would go here
                
                codebundles_processed += 1
                
            db.commit()
            
        finally:
            db.close()
        
        logger.info(f"Codebundles parsing task {self.request.id} completed: {codebundles_processed} codebundles")
        return {'status': 'success', 'codebundles_processed': codebundles_processed}
        
    except Exception as e:
        logger.error(f"Codebundles parsing task {self.request.id} failed: {e}")
        raise

@celery_app.task(bind=True)
def generate_categories_task(self):
    """
    Generate categories from support tags
    """
    try:
        logger.info(f"Starting categories generation task {self.request.id}")
        
        # Implementation for generating categories
        categories_generated = 0
        
        logger.info(f"Categories generation task {self.request.id} completed: {categories_generated} categories")
        return {'status': 'success', 'categories_generated': categories_generated}
        
    except Exception as e:
        logger.error(f"Categories generation task {self.request.id} failed: {e}")
        raise

@celery_app.task(bind=True)
def update_collection_statistics_task(self):
    """
    Update collection statistics and metrics
    """
    try:
        logger.info(f"Starting statistics update task {self.request.id}")
        
        db = SessionLocal()
        try:
            # Update statistics for all collections
            collections = db.query(CodeCollection).all()
            for collection in collections:
                # Update various statistics
                collection.last_synced = datetime.utcnow()
            
            db.commit()
            
        finally:
            db.close()
        
        logger.info(f"Statistics update task {self.request.id} completed")
        return {'status': 'success', 'statistics_updated': True}
        
    except Exception as e:
        logger.error(f"Statistics update task {self.request.id} failed: {e}")
        raise

@celery_app.task(bind=True)
def sync_single_collection_task(self, collection_slug: str):
    """
    Sync a single collection
    """
    try:
        logger.info(f"Starting single collection sync task {self.request.id} for {collection_slug}")
        
        # Use Celery chain to sequence tasks without .get()
        from celery import chain
        
        # Create a chain of tasks that will execute sequentially
        workflow = chain(
            sync_collections_task.s([collection_slug]),
            parse_collection_codebundles_task.s(collection_slug)
        )
        
        # Apply the chain
        result = workflow.apply_async()
        
        return {
            'status': 'success',
            'message': f'Started workflow for collection {collection_slug}',
            'workflow_id': result.id
        }
        
    except Exception as e:
        logger.error(f"Single collection sync task {self.request.id} failed: {e}")
        raise

@celery_app.task(bind=True)
def parse_collection_codebundles_task(self, collection_slug: str):
    """
    Parse codebundles for a specific collection
    """
    try:
        logger.info(f"Starting collection codebundles parsing task {self.request.id} for {collection_slug}")
        
        # Implementation for parsing codebundles for a specific collection
        codebundles_processed = 0
        
        return {'status': 'success', 'codebundles_processed': codebundles_processed}
        
    except Exception as e:
        logger.error(f"Collection codebundles parsing task {self.request.id} failed: {e}")
        raise
