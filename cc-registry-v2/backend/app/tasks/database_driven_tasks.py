"""
Database-Driven Task System
- Database is the source of truth
- YAML is only used for seeding/validation
- All operations read from database CodeCollections
"""
import os
import yaml
import shutil
import tempfile
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from git import Repo
from robot.api import get_model
from robot.parsing.model import TestCase

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawRepositoryData, CodeCollectionMetrics, SystemMetrics
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'database_driven_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
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

# Scheduled tasks
celery_app.conf.beat_schedule = {
    'validate-yaml-seed-daily': {
        'task': 'app.tasks.database_driven_tasks.validate_yaml_seed_task',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'sync-collections-daily': {
        'task': 'app.tasks.database_driven_tasks.sync_all_collections_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'parse-codebundles-daily': {
        'task': 'app.tasks.database_driven_tasks.parse_all_codebundles_task',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'enhance-codebundles-weekly': {
        'task': 'app.tasks.database_driven_tasks.enhance_all_codebundles_task',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Weekly on Monday at 4 AM
    },
    'generate-metrics-hourly': {
        'task': 'app.tasks.database_driven_tasks.generate_metrics_task',
        'schedule': crontab(minute=0),  # Every hour
    },
}


@celery_app.task(bind=True)
def seed_database_from_yaml_task(self, yaml_file_path: str = "/app/codecollections.yaml"):
    """
    SEED TASK: Load YAML entries into database (one-time or when new entries added)
    Database becomes the source of truth after this
    """
    try:
        logger.info(f"Starting database seeding from YAML: {yaml_file_path}")
        self.update_state(state='PROGRESS', meta={'step': 'loading_yaml', 'progress': 10})
        
        # Load YAML
        with open(yaml_file_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        db = SessionLocal()
        collections_added = 0
        collections_updated = 0
        
        self.update_state(state='PROGRESS', meta={'step': 'processing_collections', 'progress': 30})
        
        for collection_data in yaml_data.get('codecollections', []):
            slug = collection_data.get('slug')
            if not slug:
                logger.warning(f"Skipping collection without slug: {collection_data}")
                continue
            
            # Check if collection exists
            existing = db.query(CodeCollection).filter(CodeCollection.slug == slug).first()
            
            if existing:
                # Update existing collection
                existing.name = collection_data.get('name', existing.name)
                existing.git_url = collection_data.get('git_url', existing.git_url)
                existing.description = collection_data.get('description', existing.description)
                existing.owner = collection_data.get('owner', existing.owner)
                existing.owner_email = collection_data.get('owner_email', existing.owner_email)
                existing.owner_icon = collection_data.get('owner_icon', existing.owner_icon)
                existing.git_ref = collection_data.get('git_ref', existing.git_ref)
                existing.updated_at = datetime.utcnow()
                collections_updated += 1
                logger.info(f"Updated existing collection: {slug}")
            else:
                # Create new collection
                new_collection = CodeCollection(
                    name=collection_data.get('name', slug),
                    slug=slug,
                    git_url=collection_data['git_url'],
                    description=collection_data.get('description'),
                    owner=collection_data.get('owner'),
                    owner_email=collection_data.get('owner_email'),
                    owner_icon=collection_data.get('owner_icon'),
                    git_ref=collection_data.get('git_ref', 'main'),
                    is_active=True
                )
                db.add(new_collection)
                collections_added += 1
                logger.info(f"Added new collection: {slug}")
        
        db.commit()
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Database seeded from YAML successfully',
            'collections_added': collections_added,
            'collections_updated': collections_updated,
            'total_collections': collections_added + collections_updated
        }
        
        logger.info(f"Database seeding completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def validate_yaml_seed_task(self, yaml_file_path: str = "/app/codecollections.yaml"):
    """
    VALIDATION TASK: Ensure all YAML entries exist in database
    This is the reverse check - YAML validates against database
    """
    try:
        logger.info("Starting YAML seed validation against database")
        self.update_state(state='PROGRESS', meta={'step': 'loading_yaml', 'progress': 20})
        
        # Load YAML
        with open(yaml_file_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        db = SessionLocal()
        missing_collections = []
        existing_collections = []
        
        self.update_state(state='PROGRESS', meta={'step': 'validating', 'progress': 50})
        
        for collection_data in yaml_data.get('codecollections', []):
            slug = collection_data.get('slug')
            if not slug:
                continue
                
            existing = db.query(CodeCollection).filter(CodeCollection.slug == slug).first()
            if existing:
                existing_collections.append(slug)
            else:
                missing_collections.append(slug)
                logger.warning(f"YAML collection not found in database: {slug}")
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'YAML validation completed',
            'existing_collections': existing_collections,
            'missing_collections': missing_collections,
            'validation_passed': len(missing_collections) == 0
        }
        
        if missing_collections:
            logger.warning(f"YAML validation found missing collections: {missing_collections}")
        else:
            logger.info("YAML validation passed - all collections exist in database")
        
        return result
        
    except Exception as e:
        logger.error(f"YAML validation failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def sync_all_collections_task(self):
    """
    SYNC TASK: Read from database CodeCollections and sync their repositories
    Database is the source of truth
    """
    try:
        logger.info("Starting sync of all collections from database")
        self.update_state(state='PROGRESS', meta={'step': 'loading_collections', 'progress': 10})
        
        db = SessionLocal()
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        synced_collections = []
        failed_collections = []
        
        total_collections = len(collections)
        
        for i, collection in enumerate(collections):
            try:
                progress = int(20 + (i / total_collections) * 70)
                self.update_state(state='PROGRESS', meta={
                    'step': f'syncing_{collection.slug}', 
                    'progress': progress,
                    'current_collection': collection.slug
                })
                
                # Sync this collection
                result = sync_single_collection_task.apply_async(args=[collection.id])
                result.get()  # Wait for completion
                
                synced_collections.append(collection.slug)
                logger.info(f"Successfully synced collection: {collection.slug}")
                
            except Exception as e:
                failed_collections.append({'slug': collection.slug, 'error': str(e)})
                logger.error(f"Failed to sync collection {collection.slug}: {e}")
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Collection sync completed',
            'synced_collections': synced_collections,
            'failed_collections': failed_collections,
            'total_processed': len(synced_collections) + len(failed_collections)
        }
        
        logger.info(f"Collection sync completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Collection sync failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def sync_single_collection_task(self, collection_id: int):
    """
    Sync a single collection's repository and store raw files
    """
    try:
        db = SessionLocal()
        collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
        
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")
        
        logger.info(f"Syncing collection: {collection.slug}")
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = os.path.join(temp_dir, collection.slug)
            
            # Clone repository
            logger.info(f"Cloning {collection.git_url} to {repo_path}")
            repo = Repo.clone_from(collection.git_url, repo_path, branch=collection.git_ref)
            
            # Store repository files in database
            files_stored = _store_repository_files(db, collection.slug, repo_path)
            
            # Update collection sync timestamp
            collection.last_synced = datetime.utcnow()
            db.commit()
            
            logger.info(f"Stored {files_stored} files for collection {collection.slug}")
            
            return {
                'status': 'success',
                'collection_slug': collection.slug,
                'files_stored': files_stored,
                'synced_at': collection.last_synced.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to sync collection {collection_id}: {e}")
        raise
    finally:
        db.close()


def _store_repository_files(db, collection_slug: str, repo_path: str) -> int:
    """Store all repository files in RawRepositoryData table"""
    files_stored = 0
    
    # Clear existing files for this collection
    db.query(RawRepositoryData).filter(
        RawRepositoryData.collection_slug == collection_slug
    ).delete()
    
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, repo_path)
            
            # Skip .git directory and other unwanted files
            if '.git' in relative_path or file.startswith('.'):
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Determine file type
                file_ext = os.path.splitext(file)[1].lower()
                file_type = 'robot' if file_ext == '.robot' else file_ext.lstrip('.')
                
                # Store in database
                raw_data = RawRepositoryData(
                    collection_slug=collection_slug,
                    repository_path=repo_path,
                    file_path=relative_path,
                    file_content=content,
                    file_type=file_type,
                    is_processed=False
                )
                db.add(raw_data)
                files_stored += 1
                
            except (UnicodeDecodeError, IOError) as e:
                logger.warning(f"Skipping file {relative_path}: {e}")
                continue
    
    db.commit()
    return files_stored


@celery_app.task(bind=True)
def parse_all_codebundles_task(self):
    """
    PARSE TASK: Read from database collections and parse their codebundles
    Uses stored repository data, not direct file access
    """
    try:
        logger.info("Starting codebundle parsing from database")
        self.update_state(state='PROGRESS', meta={'step': 'loading_collections', 'progress': 10})
        
        db = SessionLocal()
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        total_codebundles_created = 0
        total_tasks_indexed = 0
        
        for i, collection in enumerate(collections):
            progress = int(20 + (i / len(collections)) * 70)
            self.update_state(state='PROGRESS', meta={
                'step': f'parsing_{collection.slug}',
                'progress': progress,
                'current_collection': collection.slug
            })
            
            # Parse codebundles for this collection
            result = parse_collection_codebundles_task.apply_async(args=[collection.id])
            collection_result = result.get()
            
            total_codebundles_created += collection_result.get('codebundles_created', 0)
            total_tasks_indexed += collection_result.get('tasks_indexed', 0)
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Codebundle parsing completed',
            'collections_processed': len(collections),
            'codebundles_created': total_codebundles_created,
            'tasks_indexed': total_tasks_indexed
        }
        
        logger.info(f"Codebundle parsing completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Codebundle parsing failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def parse_collection_codebundles_task(self, collection_id: int):
    """
    Parse codebundles for a single collection using stored repository data
    """
    try:
        db = SessionLocal()
        collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
        
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")
        
        logger.info(f"Parsing codebundles for collection: {collection.slug}")
        
        # Get all robot files for this collection
        robot_files = db.query(RawRepositoryData).filter(
            RawRepositoryData.collection_slug == collection.slug,
            RawRepositoryData.file_type == 'robot',
            RawRepositoryData.is_processed == False
        ).all()
        
        codebundles_created = 0
        tasks_indexed = 0
        
        for robot_file in robot_files:
            try:
                # Parse robot file content
                codebundle_data = _parse_robot_file_content(robot_file.file_content, robot_file.file_path)
                
                if codebundle_data:
                    # Create or update codebundle
                    codebundle = _create_or_update_codebundle(db, collection, codebundle_data, robot_file.file_path)
                    
                    if codebundle:
                        codebundles_created += 1
                        tasks_indexed += len(codebundle.tasks or [])
                        
                        # Mark as processed
                        robot_file.is_processed = True
                        
            except Exception as e:
                logger.error(f"Failed to parse robot file {robot_file.file_path}: {e}")
                continue
        
        db.commit()
        
        result = {
            'status': 'success',
            'collection_slug': collection.slug,
            'codebundles_created': codebundles_created,
            'tasks_indexed': tasks_indexed
        }
        
        logger.info(f"Parsed {codebundles_created} codebundles with {tasks_indexed} tasks for {collection.slug}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse codebundles for collection {collection_id}: {e}")
        raise
    finally:
        db.close()


def _parse_robot_file_content(content: str, file_path: str) -> Optional[Dict[str, Any]]:
    """Parse Robot Framework file content and extract codebundle data"""
    try:
        # Create temporary file for robot parser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.robot', delete=False) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Parse with Robot Framework
            model = get_model(temp_file_path)
            
            # Extract basic information
            name = os.path.splitext(os.path.basename(file_path))[0]
            slug = name.lower().replace(' ', '-').replace('_', '-')
            
            # Extract documentation
            doc = ""
            if hasattr(model, 'doc') and model.doc:
                doc = str(model.doc)
            
            # Extract tasks/test cases
            tasks = []
            if hasattr(model, 'sections'):
                for section in model.sections:
                    if hasattr(section, 'body'):
                        for item in section.body:
                            if isinstance(item, TestCase):
                                tasks.append(item.name)
            
            # Extract metadata from settings
            author = ""
            tags = []
            if hasattr(model, 'sections'):
                for section in model.sections:
                    if section.__class__.__name__ == 'SettingSection':
                        for setting in section.body:
                            if hasattr(setting, 'type') and setting.type == 'METADATA':
                                if len(setting.tokens) >= 3:
                                    key = setting.tokens[1].value
                                    value = setting.tokens[2].value
                                    if key.lower() == 'author':
                                        author = value
                            elif hasattr(setting, 'type') and setting.type == 'FORCE TAGS':
                                if len(setting.tokens) >= 2:
                                    tags.extend([token.value for token in setting.tokens[1:]])
            
            return {
                'name': name,
                'slug': slug,
                'display_name': name.replace('-', ' ').replace('_', ' ').title(),
                'description': doc.split('\n')[0] if doc else f"Codebundle for {name}",
                'doc': doc,
                'author': author,
                'tasks': tasks,
                'support_tags': tags,
                'runbook_path': file_path,
                'task_count': len(tasks)
            }
            
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Failed to parse robot file content: {e}")
        return None


def _create_or_update_codebundle(db, collection: CodeCollection, codebundle_data: Dict[str, Any], file_path: str) -> Optional[Codebundle]:
    """Create or update a codebundle with task indexing"""
    try:
        slug = codebundle_data['slug']
        
        # Check if codebundle exists
        existing = db.query(Codebundle).filter(
            Codebundle.codecollection_id == collection.id,
            Codebundle.slug == slug
        ).first()
        
        if existing:
            codebundle = existing
        else:
            codebundle = Codebundle(
                codecollection_id=collection.id,
                slug=slug
            )
            db.add(codebundle)
        
        # Update basic fields
        codebundle.name = codebundle_data['name']
        codebundle.display_name = codebundle_data['display_name']
        codebundle.description = codebundle_data['description']
        codebundle.doc = codebundle_data['doc']
        codebundle.author = codebundle_data['author']
        codebundle.tasks = codebundle_data['tasks']
        codebundle.support_tags = codebundle_data['support_tags']
        codebundle.runbook_path = codebundle_data['runbook_path']
        codebundle.task_count = codebundle_data['task_count']
        codebundle.last_synced = datetime.utcnow()
        
        # Generate task index (task name -> unique index)
        task_index = {}
        for task_name in codebundle_data['tasks']:
            # Create unique index based on collection + codebundle + task name
            index_source = f"{collection.slug}:{slug}:{task_name}"
            task_index[task_name] = hashlib.md5(index_source.encode()).hexdigest()[:8]
        
        codebundle.task_index = task_index
        
        # Reset enhancement status if tasks changed
        if existing and existing.tasks != codebundle_data['tasks']:
            codebundle.enhancement_status = "pending"
            codebundle.last_enhanced = None
        
        db.commit()
        return codebundle
        
    except Exception as e:
        logger.error(f"Failed to create/update codebundle: {e}")
        return None


@celery_app.task(bind=True)
def enhance_all_codebundles_task(self):
    """
    ENHANCEMENT TASK: Use AI to enhance codebundle metadata
    """
    try:
        logger.info("Starting AI enhancement of all codebundles")
        self.update_state(state='PROGRESS', meta={'step': 'loading_codebundles', 'progress': 10})
        
        db = SessionLocal()
        
        # Get codebundles that need enhancement
        codebundles = db.query(Codebundle).filter(
            Codebundle.is_active == True,
            Codebundle.enhancement_status.in_(['pending', 'failed'])
        ).all()
        
        enhanced_count = 0
        failed_count = 0
        
        for i, codebundle in enumerate(codebundles):
            progress = int(20 + (i / len(codebundles)) * 70)
            self.update_state(state='PROGRESS', meta={
                'step': f'enhancing_{codebundle.slug}',
                'progress': progress,
                'current_codebundle': codebundle.slug
            })
            
            try:
                # Enhance this codebundle
                result = enhance_single_codebundle_task.apply_async(args=[codebundle.id])
                result.get()
                enhanced_count += 1
                
            except Exception as e:
                logger.error(f"Failed to enhance codebundle {codebundle.slug}: {e}")
                failed_count += 1
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Codebundle enhancement completed',
            'enhanced_count': enhanced_count,
            'failed_count': failed_count,
            'total_processed': enhanced_count + failed_count
        }
        
        logger.info(f"Codebundle enhancement completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Codebundle enhancement failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def enhance_single_codebundle_task(self, codebundle_id: int):
    """
    Enhance a single codebundle with AI-generated metadata
    """
    try:
        db = SessionLocal()
        codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
        
        if not codebundle:
            raise ValueError(f"Codebundle with ID {codebundle_id} not found")
        
        logger.info(f"Enhancing codebundle: {codebundle.slug}")
        
        # Mark as processing
        codebundle.enhancement_status = "processing"
        db.commit()
        
        # TODO: Implement actual AI enhancement
        # For now, create mock enhanced metadata
        enhanced_metadata = {
            'ai_generated_description': f"Enhanced description for {codebundle.name}",
            'suggested_categories': ['troubleshooting', 'monitoring'],
            'difficulty_level': 'intermediate',
            'estimated_runtime': '5-10 minutes',
            'prerequisites': ['kubectl access', 'cluster permissions'],
            'related_codebundles': [],
            'enhancement_timestamp': datetime.utcnow().isoformat(),
            'enhancement_version': '1.0'
        }
        
        # Store enhanced metadata
        codebundle.ai_enhanced_metadata = enhanced_metadata
        codebundle.enhancement_status = "completed"
        codebundle.last_enhanced = datetime.utcnow()
        
        db.commit()
        
        result = {
            'status': 'success',
            'codebundle_slug': codebundle.slug,
            'enhanced_metadata': enhanced_metadata
        }
        
        logger.info(f"Enhanced codebundle {codebundle.slug}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to enhance codebundle {codebundle_id}: {e}")
        
        # Mark as failed
        if 'codebundle' in locals():
            codebundle.enhancement_status = "failed"
            db.commit()
        
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def generate_metrics_task(self):
    """
    METRICS TASK: Generate and store metrics for collections and system
    """
    try:
        logger.info("Starting metrics generation")
        self.update_state(state='PROGRESS', meta={'step': 'calculating_metrics', 'progress': 20})
        
        db = SessionLocal()
        
        # Generate collection metrics
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        for collection in collections:
            # Calculate metrics for this collection
            codebundles = db.query(Codebundle).filter(
                Codebundle.codecollection_id == collection.id,
                Codebundle.is_active == True
            ).all()
            
            total_tasks = sum(cb.task_count or 0 for cb in codebundles)
            enhanced_count = len([cb for cb in codebundles if cb.enhancement_status == 'completed'])
            pending_count = len([cb for cb in codebundles if cb.enhancement_status == 'pending'])
            failed_count = len([cb for cb in codebundles if cb.enhancement_status == 'failed'])
            
            # Store collection metrics
            metrics = CodeCollectionMetrics(
                codecollection_id=collection.id,
                codebundle_count=len(codebundles),
                total_task_count=total_tasks,
                enhanced_codebundles=enhanced_count,
                pending_enhancements=pending_count,
                failed_enhancements=failed_count,
                avg_tasks_per_codebundle=int(total_tasks / len(codebundles)) if codebundles else 0
            )
            db.add(metrics)
        
        # Generate system metrics
        total_collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).count()
        total_codebundles = db.query(Codebundle).filter(Codebundle.is_active == True).count()
        total_tasks = db.query(Codebundle).filter(Codebundle.is_active == True).with_entities(
            db.func.sum(Codebundle.task_count)
        ).scalar() or 0
        
        system_metrics = SystemMetrics(
            total_collections=total_collections,
            total_codebundles=total_codebundles,
            total_tasks=total_tasks
        )
        db.add(system_metrics)
        
        db.commit()
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Metrics generation completed',
            'collections_processed': len(collections),
            'total_collections': total_collections,
            'total_codebundles': total_codebundles,
            'total_tasks': total_tasks
        }
        
        logger.info(f"Metrics generation completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Metrics generation failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        db.close()
