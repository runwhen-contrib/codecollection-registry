"""
Registry Task System - Sync and Parse Collections/Codebundles
"""
import os
import yaml
import tempfile
import logging
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import Celery
from git import Repo

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawRepositoryData
from app.models.version import CodeCollectionVersion
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'registry_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

def _create_display_name(name: str) -> str:
    """Create a display name from a codebundle name"""
    import re
    display_words = []
    words = re.split(r'[-_]', name)
    
    for word in words:
        if word:
            camel_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', word)
            if camel_words:
                display_words.extend([w.capitalize() for w in camel_words])
            else:
                display_words.append(word.capitalize())
    
    return ' '.join(display_words)

def _parse_robot_file_content(content: str, file_path: str, collection_slug: str = None) -> Optional[Dict[str, Any]]:
    """Parse Robot Framework file content using the WORKING parser from generate_registry.py"""
    from app.tasks.fixed_parser import parse_robot_file_content
    return parse_robot_file_content(content, file_path, collection_slug)

@celery_app.task(bind=True)
def sync_all_collections_task(self):
    """
    Sync all collections from YAML file:
    - Load codecollections.yaml
    - Create/update CodeCollection records in DB
    - Clone repositories to temp directory for parsing
    """
    try:
        logger.info(f"Starting sync_all_collections_task {self.request.id}")
        
        # Load YAML
        yaml_path = "/app/codecollections.yaml"
        if not os.path.exists(yaml_path):
            return {"status": "error", "message": f"YAML file not found: {yaml_path}"}
        
        with open(yaml_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        collections_data = yaml_data.get('codecollections', [])
        logger.info(f"Loaded {len(collections_data)} collections from YAML")
        
        collections_synced = 0
        db = SessionLocal()
        
        try:
            for collection_data in collections_data:
                collection_slug = collection_data.get('slug')
                git_url = collection_data.get('git_url')
                
                if not collection_slug or not git_url:
                    logger.warning(f"Skipping collection with missing slug or git_url")
                    continue
                
                # Create/update collection in DB
                collection = db.query(CodeCollection).filter(
                    CodeCollection.slug == collection_slug
                ).first()
                
                if not collection:
                    collection = CodeCollection(
                        name=collection_data.get('name', collection_slug),
                        slug=collection_slug,
                        git_url=git_url,
                        description=collection_data.get('description', ''),
                        owner=collection_data.get('owner', ''),
                        owner_email=collection_data.get('owner_email', ''),
                        owner_icon=collection_data.get('owner_icon', ''),
                        git_ref=collection_data.get('git_ref', 'main'),
                        is_active=True
                    )
                    db.add(collection)
                    logger.info(f"Created collection: {collection_slug}")
                else:
                    collection.name = collection_data.get('name', collection_slug)
                    collection.git_url = git_url
                    collection.description = collection_data.get('description', '')
                    collection.is_active = True
                    logger.info(f"Updated collection: {collection_slug}")
                
                db.commit()
                collections_synced += 1
            
            logger.info(f"Synced {collections_synced} collections")
            return {"status": "success", "collections_synced": collections_synced}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"sync_all_collections_task failed: {e}")
        return {"status": "error", "message": str(e)}

@celery_app.task(bind=True)
def parse_all_codebundles_task(self):
    """
    Parse all codebundles from collections:
    - Clone each collection repository
    - Parse robot files and create/update Codebundle records
    - Extract tasks, metadata, discovery config
    """
    try:
        logger.info(f"Starting parse_all_codebundles_task {self.request.id}")
        
        db = SessionLocal()
        codebundles_created = 0
        codebundles_updated = 0
        
        try:
            collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            logger.info(f"Found {len(collections)} active collections to parse")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                for collection in collections:
                    try:
                        # Clone repository
                        repo_path = os.path.join(tmp_dir, collection.slug)
                        logger.info(f"Cloning {collection.git_url} to {repo_path}")
                        
                        try:
                            Repo.clone_from(collection.git_url, repo_path)
                        except Exception as clone_err:
                            logger.error(f"Failed to clone {collection.git_url}: {clone_err}")
                            continue
                        
                        # Find and parse codebundles
                        codebundles_dir = os.path.join(repo_path, 'codebundles')
                        if not os.path.exists(codebundles_dir):
                            logger.warning(f"No codebundles directory in {collection.slug}")
                            continue
                        
                        for bundle_name in os.listdir(codebundles_dir):
                            bundle_path = os.path.join(codebundles_dir, bundle_name)
                            if not os.path.isdir(bundle_path):
                                continue
                            
                            runbook_path = os.path.join(bundle_path, 'runbook.robot')
                            sli_path = os.path.join(bundle_path, 'sli.robot')
                            
                            has_runbook = os.path.exists(runbook_path)
                            has_sli = os.path.exists(sli_path)
                            
                            if not has_runbook and not has_sli:
                                continue
                            
                            # Parse robot files
                            runbook_parsed = None
                            if has_runbook:
                                with open(runbook_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/runbook.robot"
                                runbook_parsed = _parse_robot_file_content(content, relative_path, collection.slug)
                            
                            sli_parsed = None
                            if has_sli:
                                with open(sli_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/sli.robot"
                                sli_parsed = _parse_robot_file_content(content, relative_path, collection.slug)
                            
                            primary_parsed = runbook_parsed or sli_parsed
                            if not primary_parsed:
                                continue
                            
                            # Extract tasks
                            taskset_tasks = runbook_parsed.get('tasks', []) if runbook_parsed else []
                            sli_tasks = sli_parsed.get('tasks', []) if sli_parsed else []
                            
                            support_tags = list(set(
                                (runbook_parsed.get('support_tags', []) if runbook_parsed else []) +
                                (sli_parsed.get('support_tags', []) if sli_parsed else [])
                            ))
                            
                            # Read README
                            readme_content = ""
                            readme_path_file = os.path.join(bundle_path, "README.md")
                            if os.path.exists(readme_path_file):
                                with open(readme_path_file, 'r', encoding='utf-8') as f:
                                    readme_content = f.read()
                            
                            # Create/update codebundle
                            existing = db.query(Codebundle).filter(
                                Codebundle.slug == primary_parsed['slug'],
                                Codebundle.codecollection_id == collection.id
                            ).first()
                            
                            runbook_source_url = f"{collection.git_url.rstrip('.git')}/tree/main/codebundles/{bundle_name}"
                            
                            # Get git date
                            git_date = _get_git_last_commit_date(repo_path, f"codebundles/{bundle_name}")
                            
                            if existing:
                                existing.name = primary_parsed.get('name', bundle_name)
                                existing.display_name = primary_parsed.get('display_name', bundle_name)
                                existing.description = primary_parsed.get('description', '')
                                existing.doc = primary_parsed.get('doc', '')
                                existing.readme = readme_content
                                existing.author = primary_parsed.get('author', '')
                                existing.support_tags = support_tags
                                existing.tasks = taskset_tasks
                                existing.slis = sli_tasks
                                existing.task_count = len(taskset_tasks)
                                existing.sli_count = len(sli_tasks)
                                existing.runbook_source_url = runbook_source_url
                                if git_date:
                                    existing.git_updated_at = git_date
                                codebundles_updated += 1
                            else:
                                codebundle = Codebundle(
                                    name=primary_parsed.get('name', bundle_name),
                                    slug=primary_parsed['slug'],
                                    display_name=primary_parsed.get('display_name', bundle_name),
                                    description=primary_parsed.get('description', ''),
                                    doc=primary_parsed.get('doc', ''),
                                    readme=readme_content,
                                    author=primary_parsed.get('author', ''),
                                    support_tags=support_tags,
                                    tasks=taskset_tasks,
                                    slis=sli_tasks,
                                    task_count=len(taskset_tasks),
                                    sli_count=len(sli_tasks),
                                    codecollection_id=collection.id,
                                    runbook_source_url=runbook_source_url,
                                    is_active=True,
                                    git_updated_at=git_date
                                )
                                db.add(codebundle)
                                codebundles_created += 1
                            
                            db.commit()
                            
                    except Exception as e:
                        logger.error(f"Error processing collection {collection.slug}: {e}")
                        continue
            
            logger.info(f"Parsed codebundles: {codebundles_created} created, {codebundles_updated} updated")
            return {
                "status": "success",
                "codebundles_created": codebundles_created,
                "codebundles_updated": codebundles_updated
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"parse_all_codebundles_task failed: {e}")
        return {"status": "error", "message": str(e)}

def _get_git_last_commit_date(repo_path: str, folder_path: str) -> Optional[datetime]:
    """Get the last commit date for files in a folder, excluding meta.yml"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ct', '--', folder_path,
             f':(exclude){folder_path}/meta.yml',
             f':(exclude){folder_path}/meta.yaml'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            timestamp = int(result.stdout.strip())
            return datetime.fromtimestamp(timestamp)
    except Exception as e:
        logger.warning(f"Could not get git date for {folder_path}: {e}")
    return None

def _parse_runwhen_discovery(db, collection_slug: str, codebundle_name: str) -> Dict[str, Any]:
    """Parse .runwhen directory for discovery configuration"""
    return {}
