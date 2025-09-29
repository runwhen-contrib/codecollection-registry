"""
Registry Task System
- Register CodeCollections from YAML seed data
- Index and sync CodeCollections from repositories  
- Parse and index Codebundles from stored repository data
- Enhance Codebundles with AI-generated metadata
- Generate metrics for collections and system health
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
from app.models.version import CodeCollectionVersion, VersionCodebundle
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'registry_tasks',
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
        'task': 'app.tasks.registry_tasks.validate_yaml_seed_task',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'sync-collections-daily': {
        'task': 'app.tasks.registry_tasks.sync_all_collections_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'parse-codebundles-daily': {
        'task': 'app.tasks.registry_tasks.parse_all_codebundles_task',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'enhance-codebundles-weekly': {
        'task': 'app.tasks.registry_tasks.enhance_all_codebundles_task',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Weekly on Monday at 4 AM
    },
    'generate-metrics-hourly': {
        'task': 'app.tasks.registry_tasks.generate_metrics_task',
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
                # Note: Not waiting for completion to avoid blocking
                
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
    Sync a single collection's repository, discover versions, and store raw files for each version
    """
    try:
        db = SessionLocal()
        collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
        
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")
        
        logger.info(f"Syncing collection with version discovery: {collection.slug}")
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = os.path.join(temp_dir, collection.slug)
            
            # Clone repository (full clone to get all refs)
            logger.info(f"Cloning {collection.git_url} to {repo_path}")
            repo = Repo.clone_from(collection.git_url, repo_path)
            
            # Discover and sync all versions
            versions_synced = _discover_and_sync_versions(db, collection, repo, repo_path)
            
            # Update collection sync timestamp
            collection.last_synced = datetime.utcnow()
            db.commit()
            
            logger.info(f"Synced {versions_synced['total_versions']} versions for collection {collection.slug}")
            
            return {
                'status': 'success',
                'collection_slug': collection.slug,
                'versions_synced': versions_synced,
                'synced_at': collection.last_synced.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to sync collection {collection_id}: {e}")
        raise
    finally:
        db.close()


def _discover_and_sync_versions(db, collection: CodeCollection, repo: Repo, repo_path: str) -> Dict[str, Any]:
    """
    Discover all versions (tags and main branch) and sync their files
    """
    versions_synced = {'tags': 0, 'main': 0, 'total_versions': 0, 'total_files': 0}
    
    # Process tags (releases)
    tags = list(repo.tags)
    logger.info(f"Found {len(tags)} tags for {collection.name}")
    
    for tag in tags:
        try:
            # Checkout the tag
            repo.git.checkout(tag.name)
            
            # Create or update version record
            version_data = {
                'version_name': tag.name,
                'git_ref': tag.commit.hexsha,
                'display_name': tag.name,
                'version_type': 'tag',
                'version_date': datetime.fromtimestamp(tag.commit.committed_date),
                'synced_at': datetime.utcnow(),
                'is_prerelease': _is_prerelease_version(tag.name)
            }
            
            version = _create_or_update_version(db, collection, version_data)
            if version:
                files_stored = _store_repository_files_for_version(db, collection.slug, repo_path, version.id)
                versions_synced['tags'] += 1
                versions_synced['total_files'] += files_stored
                logger.info(f"Synced version {tag.name} with {files_stored} files")
                
        except Exception as e:
            logger.error(f"Error processing tag {tag.name}: {str(e)}")
            continue
    
    # Process main branch
    try:
        main_branch = collection.git_ref or 'main'
        repo.git.checkout(main_branch)
        
        version_data = {
            'version_name': 'main',
            'git_ref': repo.head.commit.hexsha,
            'display_name': 'Main Branch',
            'version_type': 'main',
            'version_date': datetime.fromtimestamp(repo.head.commit.committed_date),
            'synced_at': datetime.utcnow(),
            'is_latest': True  # Main is always considered latest
        }
        
        version = _create_or_update_version(db, collection, version_data)
        if version:
            files_stored = _store_repository_files_for_version(db, collection.slug, repo_path, version.id)
            versions_synced['main'] += 1
            versions_synced['total_files'] += files_stored
            logger.info(f"Synced main branch with {files_stored} files")
            
    except Exception as e:
        logger.error(f"Error processing main branch: {str(e)}")
    
    # Mark the latest tag version
    if tags:
        latest_tag = max(tags, key=lambda t: t.commit.committed_date)
        latest_version = db.query(CodeCollectionVersion).filter(
            CodeCollectionVersion.codecollection_id == collection.id,
            CodeCollectionVersion.version_name == latest_tag.name
        ).first()
        
        if latest_version:
            # Reset all other tag versions' is_latest flag
            db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.codecollection_id == collection.id,
                CodeCollectionVersion.version_type == 'tag'
            ).update({'is_latest': False})
            
            latest_version.is_latest = True
            db.commit()
    
    versions_synced['total_versions'] = versions_synced['tags'] + versions_synced['main']
    return versions_synced


def _create_or_update_version(db, collection: CodeCollection, version_data: Dict[str, Any]) -> CodeCollectionVersion:
    """Create or update a CodeCollectionVersion"""
    existing_version = db.query(CodeCollectionVersion).filter(
        CodeCollectionVersion.codecollection_id == collection.id,
        CodeCollectionVersion.version_name == version_data['version_name']
    ).first()
    
    if existing_version:
        # Update existing version
        for key, value in version_data.items():
            setattr(existing_version, key, value)
        existing_version.updated_at = datetime.utcnow()
        version = existing_version
    else:
        # Create new version
        version = CodeCollectionVersion(
            codecollection_id=collection.id,
            **version_data
        )
        db.add(version)
    
    db.commit()
    db.refresh(version)
    return version


def _is_prerelease_version(version_name: str) -> bool:
    """Check if a version is a prerelease based on naming conventions"""
    prerelease_indicators = ['alpha', 'beta', 'rc', 'pre', 'dev', 'snapshot']
    version_lower = version_name.lower()
    return any(indicator in version_lower for indicator in prerelease_indicators)


def _store_repository_files_for_version(db, collection_slug: str, repo_path: str, version_id: int) -> int:
    """Store all repository files for a specific version"""
    files_stored = 0
    
    # Clear existing files for this collection version
    db.query(RawRepositoryData).filter(
        RawRepositoryData.collection_slug == collection_slug,
        RawRepositoryData.version_id == version_id
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
                
                # Store in database with version reference
                raw_data = RawRepositoryData(
                    collection_slug=collection_slug,
                    repository_path=repo_path,
                    file_path=relative_path,
                    file_content=content,
                    version_id=version_id,
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
            # Note: Not waiting for completion to avoid blocking
            
            # For now, we'll track that parsing was initiated
            # Individual collection results will be available via task status API
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Codebundle parsing initiated for all collections',
            'collections_processed': len(collections),
            'note': 'Individual parsing tasks are running asynchronously'
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
    Now processes all versions of the collection
    """
    db = SessionLocal()
    try:
        collection = db.query(CodeCollection).filter(CodeCollection.id == collection_id).first()
        
        if not collection:
            raise ValueError(f"Collection with ID {collection_id} not found")
        
        logger.info(f"Parsing codebundles for all versions of collection: {collection.slug}")
        
        # Get all versions for this collection
        versions = db.query(CodeCollectionVersion).filter(
            CodeCollectionVersion.codecollection_id == collection.id,
            CodeCollectionVersion.is_active == True
        ).all()
        
        total_codebundles_created = 0
        total_tasks_indexed = 0
        total_slis_indexed = 0
        
        for version in versions:
            logger.info(f"Processing version {version.version_name} for collection {collection.slug}")
            
            # Get all robot files for this collection version
            robot_files = db.query(RawRepositoryData).filter(
                RawRepositoryData.collection_slug == collection.slug,
                RawRepositoryData.version_id == version.id,
                RawRepositoryData.file_type == 'robot',
                RawRepositoryData.is_processed == False
            ).all()
            
            # Group files by codebundle directory for this version
            codebundle_files = {}
            for robot_file in robot_files:
                # Extract codebundle directory from path like "codebundles/aws-cloudwatch-metricquery/runbook.robot"
                path_parts = robot_file.file_path.split('/')
                if len(path_parts) >= 2 and path_parts[0] == 'codebundles':
                    codebundle_dir = path_parts[1]
                    if codebundle_dir not in codebundle_files:
                        codebundle_files[codebundle_dir] = {'runbook': None, 'sli': None}
                    
                    if robot_file.file_path.endswith('runbook.robot'):
                        codebundle_files[codebundle_dir]['runbook'] = robot_file
                    elif robot_file.file_path.endswith('sli.robot'):
                        codebundle_files[codebundle_dir]['sli'] = robot_file
            
            codebundles_created = 0
            tasks_indexed = 0
            slis_indexed = 0
            
            for codebundle_dir, files in codebundle_files.items():
                try:
                    runbook_file = files['runbook']
                    sli_file = files['sli']
                    
                    # Parse runbook file first (this creates the main codebundle)
                    codebundle_data = None
                    if runbook_file:
                        codebundle_data = _parse_robot_file_content(runbook_file.file_content, runbook_file.file_path)
                    elif sli_file:
                        # If there's no runbook file, create codebundle from SLI file but with empty tasks
                        codebundle_data = _parse_robot_file_content(sli_file.file_content, sli_file.file_path)
                        if codebundle_data:
                            # Move the parsed tasks to SLIs and clear tasks
                            codebundle_data['slis'] = codebundle_data.get('tasks', [])
                            codebundle_data['sli_count'] = len(codebundle_data.get('tasks', []))
                            codebundle_data['sli_path'] = sli_file.file_path
                            codebundle_data['tasks'] = []
                            codebundle_data['task_count'] = 0
                            # Update runbook_path to be None since this is SLI-only
                            codebundle_data['runbook_path'] = None
                    
                    # Parse SLI file and add SLIs to the codebundle data (if we have both files)
                    if sli_file and codebundle_data and runbook_file:
                        sli_data = _parse_robot_file_content(sli_file.file_content, sli_file.file_path)
                        if sli_data and sli_data.get('tasks'):
                            # SLI tasks are stored in the 'tasks' field from parsing, but we want them as 'slis'
                            codebundle_data['slis'] = sli_data['tasks']
                            codebundle_data['sli_count'] = len(sli_data['tasks'])
                            codebundle_data['sli_path'] = sli_file.file_path
                    
                    if codebundle_data:
                        # Create or update version-specific codebundle
                        version_codebundle = _create_or_update_version_codebundle(db, version, codebundle_data, runbook_file.file_path if runbook_file else sli_file.file_path)
                        
                        # Also create or update main codebundle (for API compatibility)
                        logger.info(f"Creating main codebundle for {codebundle_data['slug']}")
                        main_codebundle = _create_or_update_codebundle(db, collection, codebundle_data, runbook_file.file_path if runbook_file else sli_file.file_path)
                        if main_codebundle:
                            logger.info(f"Successfully created/updated main codebundle: {main_codebundle.slug}")
                        else:
                            logger.error(f"Failed to create main codebundle for {codebundle_data['slug']}")
                        
                        if version_codebundle:
                            codebundles_created += 1
                            tasks_indexed += len(version_codebundle.tasks or [])
                            slis_indexed += len(version_codebundle.slis or [])
                            
                            # Mark files as processed
                            if runbook_file:
                                runbook_file.is_processed = True
                            if sli_file:
                                sli_file.is_processed = True
                            
                except Exception as e:
                    logger.error(f"Failed to parse codebundle {codebundle_dir} for version {version.version_name}: {e}")
                    continue
            
            total_codebundles_created += codebundles_created
            total_tasks_indexed += tasks_indexed
            total_slis_indexed += slis_indexed
            
            logger.info(f"Processed version {version.version_name}: {codebundles_created} codebundles, {tasks_indexed} tasks, {slis_indexed} SLIs")
        
        # Commit the transaction
        db.commit()
        
        result = {
            'status': 'success',
            'collection_slug': collection.slug,
            'versions_processed': len(versions),
            'total_codebundles_created': total_codebundles_created,
            'total_tasks_indexed': total_tasks_indexed,
            'total_slis_indexed': total_slis_indexed
        }
        
        logger.info(f"Parsed {total_codebundles_created} codebundles across {len(versions)} versions with {total_tasks_indexed} tasks and {total_slis_indexed} SLIs for {collection.slug}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse codebundles for collection {collection_id}: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _create_display_name(name: str) -> str:
    """Create a proper display name with intelligent capitalization for tech terms"""
    # Common tech abbreviations and proper capitalizations
    replacements = {
        'aws': 'AWS',
        'gcp': 'GCP', 
        'azure': 'Azure',
        'k8s': 'K8s',
        'api': 'API',
        'url': 'URL',
        'http': 'HTTP',
        'https': 'HTTPS',
        'ssl': 'SSL',
        'tls': 'TLS',
        'dns': 'DNS',
        'cpu': 'CPU',
        'gpu': 'GPU',
        'ram': 'RAM',
        'sli': 'SLI',
        'slo': 'SLO',
        'vm': 'VM',
        'vpc': 'VPC',
        'rds': 'RDS',
        's3': 'S3',
        'ec2': 'EC2',
        'ecs': 'ECS',
        'eks': 'EKS',
        'aks': 'AKS',
        'gke': 'GKE',
        'cloudwatch': 'CloudWatch',
        'cloudformation': 'CloudFormation',
        'kubernetes': 'Kubernetes',
        'docker': 'Docker',
        'nginx': 'Nginx',
        'redis': 'Redis',
        'mysql': 'MySQL',
        'postgresql': 'PostgreSQL',
        'mongodb': 'MongoDB',
        'elasticsearch': 'Elasticsearch',
        'prometheus': 'Prometheus',
        'grafana': 'Grafana',
        'jenkins': 'Jenkins',
        'github': 'GitHub',
        'gitlab': 'GitLab',
        'bitbucket': 'Bitbucket',
        'jira': 'Jira',
        'slack': 'Slack',
        'discord': 'Discord',
        'oauth': 'OAuth',
        'jwt': 'JWT',
        'json': 'JSON',
        'xml': 'XML',
        'yaml': 'YAML',
        'csv': 'CSV',
        'pdf': 'PDF',
        'sql': 'SQL',
        'nosql': 'NoSQL',
        'rest': 'REST',
        'grpc': 'gRPC',
        'graphql': 'GraphQL',
        'websocket': 'WebSocket',
        'tcp': 'TCP',
        'udp': 'UDP',
        'ip': 'IP',
        'ipv4': 'IPv4',
        'ipv6': 'IPv6',
        'cidr': 'CIDR',
        'nat': 'NAT',
        'vpn': 'VPN',
        'cdn': 'CDN',
        'lb': 'Load Balancer',
        'alb': 'ALB',
        'nlb': 'NLB',
        'elb': 'ELB',
        'acm': 'ACM',
        'iam': 'IAM',
        'rbac': 'RBAC',
        'saml': 'SAML',
        'ldap': 'LDAP',
        'ad': 'Active Directory',
        'sso': 'SSO',
        'mfa': 'MFA',
        '2fa': '2FA',
        'pki': 'PKI',
        'ca': 'Certificate Authority',
        'csr': 'CSR',
        'crl': 'CRL',
        'ocsp': 'OCSP'
    }
    
    words = name.replace('-', ' ').replace('_', ' ').split()
    display_words = []
    
    for word in words:
        lower_word = word.lower()
        if lower_word in replacements:
            display_words.append(replacements[lower_word])
        else:
            display_words.append(word.capitalize())
    
    return ' '.join(display_words)


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
            
            # Extract basic information - use directory name for slug instead of filename
            # file_path example: "codebundles/azure-appservice-functionapp-health/runbook.robot"
            path_parts = file_path.split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'codebundles':
                # Use the codebundle directory name as the slug
                codebundle_dir = path_parts[1]
                name = codebundle_dir
                slug = codebundle_dir.lower().replace(' ', '-').replace('_', '-')
            else:
                # Fallback to filename if path doesn't match expected structure
                name = os.path.splitext(os.path.basename(file_path))[0]
                slug = name.lower().replace(' ', '-').replace('_', '-')
            
            # Extract documentation
            doc = ""
            if hasattr(model, 'doc') and model.doc:
                doc = str(model.doc)
            
            # Extract tasks/test cases (both TestCase and Task objects)
            tasks = []
            detailed_tasks = []
            if hasattr(model, 'sections'):
                for section in model.sections:
                    if hasattr(section, 'body'):
                        for item in section.body:
                            if isinstance(item, TestCase):
                                # Extract basic task name for backward compatibility
                                tasks.append(item.name)
                                
                                # Extract detailed task information
                                task_info = {
                                    'name': item.name,
                                    'description': '',
                                    'documentation': '',
                                    'tags': [],
                                    'steps': []
                                }
                                
                                # Extract task documentation
                                if hasattr(item, 'doc') and item.doc:
                                    task_info['documentation'] = str(item.doc)
                                    # Use first line as description
                                    doc_lines = str(item.doc).split('\n')
                                    task_info['description'] = doc_lines[0].strip() if doc_lines else ''
                                
                                # Extract task tags
                                if hasattr(item, 'tags') and item.tags:
                                    task_info['tags'] = [str(tag) for tag in item.tags]
                                
                                # Extract task steps/keywords
                                if hasattr(item, 'body') and item.body:
                                    for step in item.body:
                                        if hasattr(step, 'keyword'):
                                            step_name = str(step.keyword) if step.keyword else ''
                                            if step_name and not step_name.startswith('['):  # Skip settings like [Documentation]
                                                task_info['steps'].append(step_name)
                                
                                detailed_tasks.append(task_info)
            
            # Extract metadata from settings
            author = ""
            tags = []
            if hasattr(model, 'sections'):
                for section in model.sections:
                    if section.__class__.__name__ == 'SettingSection':
                        for setting in section.body:
                            if hasattr(setting, 'type') and setting.type == 'METADATA':
                                if len(setting.tokens) >= 5:
                                    # Robot Framework tokenizes: ['Metadata', '    ', 'Key', '    ', 'Value', '\n']
                                    key = setting.tokens[2].value
                                    value = setting.tokens[4].value
                                    if key.lower() == 'author':
                                        author = value
                                    elif key.lower() == 'supports':
                                        # Parse Supports metadata - can be comma or space separated
                                        support_items = []
                                        if ',' in value:
                                            # Comma separated: "Kubernetes,AKS,EKS,GKE,OpenShift,FluxCD"
                                            support_items = [item.strip() for item in value.split(',')]
                                        else:
                                            # Space separated: "Kubernetes AKS EKS GKE OpenShift FluxCD"
                                            support_items = [item.strip() for item in value.split()]
                                        
                                        # Clean and filter - remove empty items
                                        clean_supports = [item for item in support_items if item]
                                        tags.extend(clean_supports)
                            # Note: Removed FORCE TAGS parsing - we only want Support Tags from Metadata section
            
            return {
                'name': name,
                'slug': slug,
                'display_name': _create_display_name(name),
                'description': doc.split('\n')[0] if doc else f"Codebundle for {name.replace('-', ' ').replace('_', ' ').title()}",
                'doc': doc,
                'author': author,
                'tasks': tasks,  # Keep for backward compatibility
                'detailed_tasks': detailed_tasks,  # New detailed task information
                'support_tags': tags,
                'runbook_path': file_path,
                'task_count': len(tasks)
            }
            
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Failed to parse robot file content: {e}")
        return None


def _parse_runwhen_discovery(db, collection_slug: str, codebundle_name: str) -> Dict[str, Any]:
    """Parse .runwhen directory for discovery configuration"""
    discovery_info = {
        'is_discoverable': False,
        'platform': None,
        'resource_types': [],
        'match_patterns': [],
        'templates': [],
        'output_items': [],
        'level_of_detail': None,
        'runwhen_directory_path': None
    }
    
    try:
        # Look for .runwhen directory files in raw repository data
        from app.models.raw_data import RawRepositoryData
        
        # Check for generation-rules YAML file
        generation_rules_pattern = f"codebundles/{codebundle_name}/.runwhen/generation-rules/"
        generation_rules_files = db.query(RawRepositoryData).filter(
            RawRepositoryData.collection_slug == collection_slug,
            RawRepositoryData.file_path.like(f"{generation_rules_pattern}%.yaml")
        ).all()
        
        if generation_rules_files:
            discovery_info['is_discoverable'] = True
            discovery_info['runwhen_directory_path'] = f"codebundles/{codebundle_name}/.runwhen"
            
            # Parse the first generation rules file found
            rules_file = generation_rules_files[0]
            try:
                rules_content = yaml.safe_load(rules_file.file_content)
                
                if 'spec' in rules_content:
                    spec = rules_content['spec']
                    
                    # Extract platform
                    discovery_info['platform'] = spec.get('platform')
                    
                    # Extract generation rules
                    if 'generationRules' in spec:
                        gen_rules = spec['generationRules']
                        
                        for rule in gen_rules:
                            # Extract resource types
                            if 'resourceTypes' in rule:
                                discovery_info['resource_types'].extend(rule['resourceTypes'])
                            
                            # Extract match rules
                            if 'matchRules' in rule:
                                discovery_info['match_patterns'] = rule['matchRules']
                            
                            # Extract SLX configuration
                            if 'slxs' in rule:
                                for slx in rule['slxs']:
                                    if 'levelOfDetail' in slx:
                                        discovery_info['level_of_detail'] = slx['levelOfDetail']
                                    
                                    if 'outputItems' in slx:
                                        discovery_info['output_items'] = slx['outputItems']
                
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse generation rules YAML for {codebundle_name}: {e}")
        
        # Check for template files
        templates_pattern = f"codebundles/{codebundle_name}/.runwhen/templates/"
        template_files = db.query(RawRepositoryData).filter(
            RawRepositoryData.collection_slug == collection_slug,
            RawRepositoryData.file_path.like(f"{templates_pattern}%")
        ).all()
        
        if template_files:
            discovery_info['templates'] = [
                os.path.basename(tf.file_path) for tf in template_files
            ]
        
        # Remove duplicates from resource types
        discovery_info['resource_types'] = list(set(discovery_info['resource_types']))
        
    except Exception as e:
        logger.error(f"Failed to parse .runwhen directory for {codebundle_name}: {e}")
    
    return discovery_info


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
        codebundle.slis = codebundle_data.get('slis', [])
        codebundle.support_tags = codebundle_data['support_tags']
        codebundle.runbook_path = codebundle_data['runbook_path']
        codebundle.sli_path = codebundle_data.get('sli_path')
        codebundle.task_count = codebundle_data['task_count']
        codebundle.sli_count = codebundle_data.get('sli_count', 0)
        codebundle.last_synced = datetime.utcnow()
        
        # Generate task index (task name -> unique index)
        task_index = {}
        for task_name in codebundle_data['tasks']:
            # Create unique index based on collection + codebundle + task name
            index_source = f"{collection.slug}:{slug}:{task_name}"
            task_index[task_name] = hashlib.md5(index_source.encode()).hexdigest()[:8]
        
        codebundle.task_index = task_index
        
        # Parse discovery information from .runwhen directory
        discovery_info = _parse_runwhen_discovery(db, collection.slug, codebundle_data['name'])
        
        # Update discovery fields
        codebundle.is_discoverable = discovery_info['is_discoverable']
        codebundle.discovery_platform = discovery_info['platform']
        codebundle.discovery_resource_types = discovery_info['resource_types']
        codebundle.discovery_match_patterns = discovery_info['match_patterns']
        codebundle.discovery_templates = discovery_info['templates']
        codebundle.discovery_output_items = discovery_info['output_items']
        codebundle.discovery_level_of_detail = discovery_info['level_of_detail']
        codebundle.runwhen_directory_path = discovery_info['runwhen_directory_path']
        
        # Update has_genrules flag for backward compatibility
        codebundle.has_genrules = discovery_info['is_discoverable']
        
        # Reset enhancement status if tasks changed
        if existing and existing.tasks != codebundle_data['tasks']:
            codebundle.enhancement_status = "pending"
            codebundle.last_enhanced = None
        
        # Don't commit here - let the main parsing task handle commits
        return codebundle
        
    except Exception as e:
        logger.error(f"Failed to create/update codebundle: {e}")
        return None


def _create_or_update_version_codebundle(db, version: CodeCollectionVersion, codebundle_data: Dict[str, Any], file_path: str) -> Optional[VersionCodebundle]:
    """Create or update a version-specific codebundle"""
    try:
        slug = codebundle_data['slug']
        
        # Check if version codebundle exists
        existing = db.query(VersionCodebundle).filter(
            VersionCodebundle.version_id == version.id,
            VersionCodebundle.slug == slug
        ).first()
        
        if existing:
            version_codebundle = existing
        else:
            version_codebundle = VersionCodebundle(
                version_id=version.id,
                slug=slug
            )
            db.add(version_codebundle)
        
        # Update basic fields
        version_codebundle.name = codebundle_data['name']
        version_codebundle.display_name = codebundle_data['display_name']
        version_codebundle.description = codebundle_data['description']
        version_codebundle.doc = codebundle_data['doc']
        version_codebundle.author = codebundle_data['author']
        version_codebundle.tasks = codebundle_data['tasks']
        version_codebundle.slis = codebundle_data.get('slis', [])
        version_codebundle.support_tags = codebundle_data['support_tags']
        version_codebundle.runbook_path = codebundle_data['runbook_path']
        version_codebundle.sli_path = codebundle_data.get('sli_path')
        version_codebundle.task_count = codebundle_data['task_count']
        version_codebundle.sli_count = codebundle_data.get('sli_count', 0)
        version_codebundle.synced_at = datetime.utcnow()
        
        # Generate task index (task name -> unique index)
        task_index = {}
        for task_name in codebundle_data['tasks']:
            # Create unique index based on version + codebundle + task name
            index_source = f"{version.codecollection.slug}:{version.version_name}:{slug}:{task_name}"
            task_index[task_name] = hashlib.md5(index_source.encode()).hexdigest()[:8]
        
        version_codebundle.task_index = task_index
        
        # Parse discovery information from .runwhen directory
        discovery_info = _parse_runwhen_discovery(db, version.codecollection.slug, codebundle_data['name'])
        
        # Update discovery fields
        version_codebundle.is_discoverable = discovery_info['is_discoverable']
        version_codebundle.discovery_platform = discovery_info['platform']
        version_codebundle.discovery_resource_types = discovery_info['resource_types']
        version_codebundle.discovery_match_patterns = discovery_info['match_patterns']
        version_codebundle.discovery_templates = discovery_info['templates']
        version_codebundle.discovery_output_items = discovery_info['output_items']
        version_codebundle.discovery_level_of_detail = discovery_info['level_of_detail']
        version_codebundle.runwhen_directory_path = discovery_info['runwhen_directory_path']
        
        # Don't commit here - let the main parsing task handle commits
        return version_codebundle
        
    except Exception as e:
        logger.error(f"Failed to create/update version codebundle: {e}")
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
                # Note: Not waiting for completion to avoid blocking
                enhanced_count += 1
                
            except Exception as e:
                logger.error(f"Failed to initiate enhancement for codebundle {codebundle.slug}: {e}")
                failed_count += 1
        
        self.update_state(state='PROGRESS', meta={'step': 'completed', 'progress': 100})
        
        result = {
            'status': 'success',
            'message': 'Codebundle enhancement initiated',
            'enhancement_tasks_started': enhanced_count,
            'failed_to_start': failed_count,
            'total_processed': enhanced_count + failed_count,
            'note': 'Individual enhancement tasks are running asynchronously'
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
