"""
Raw Data Storage Tasks - Store raw data in database first
"""
import os
import yaml
import json
import tempfile
import shutil
import logging
from typing import Dict, Any, List
from datetime import datetime
from celery import Celery

from app.core.database import SessionLocal
from app.models import CodeCollection, RawYamlData, RawRepositoryData
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery('raw_data_tasks')
celery_app.config_from_object(settings)

@celery_app.task(bind=True)
def store_yaml_data_task(self, yaml_data: Dict[str, Any] = None):
    """
    Store raw YAML data in database
    """
    try:
        logger.info(f"Starting YAML data storage task {self.request.id}")
        
        # Use provided YAML data or load from file as fallback
        if not yaml_data:
            yaml_path = "/app/codecollections.yaml"
            try:
                with open(yaml_path, 'r') as file:
                    yaml_data = yaml.safe_load(file)
            except FileNotFoundError:
                logger.error("No YAML data provided and file not found")
                return {'status': 'error', 'message': 'No YAML data available'}
        
        db = SessionLocal()
        try:
            # Store raw YAML data in database
            raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
            if raw_yaml:
                # Update existing
                raw_yaml.content = yaml.dump(yaml_data)
                raw_yaml.parsed_data = json.dumps(yaml_data)
                raw_yaml.is_processed = False
            else:
                # Create new
                raw_yaml = RawYamlData(
                    source="codecollections.yaml",
                    content=yaml.dump(yaml_data),
                    parsed_data=json.dumps(yaml_data),
                    is_processed=False
                )
                db.add(raw_yaml)
            
            db.commit()
            logger.info("Stored raw YAML data in database")
            
            return {
                'status': 'success',
                'message': 'YAML data stored successfully',
                'yaml_id': raw_yaml.id
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"YAML data storage task {self.request.id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True)
def clone_repositories_task(self, collection_slugs: List[str] = None):
    """
    Clone repositories and store raw file data in database
    """
    try:
        logger.info(f"Starting repository cloning task {self.request.id}")
        
        # Load YAML data from database
        db = SessionLocal()
        try:
            raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
            if not raw_yaml:
                raise ValueError("No YAML data found in database")
            
            yaml_data = json.loads(raw_yaml.parsed_data)
            
            collections_processed = 0
            temp_dir = tempfile.mkdtemp(prefix="registry_clone_")
            
            try:
                # Process each collection
                for collection_data in yaml_data.get('codecollections', []):
                    # Filter by slugs if provided
                    if collection_slugs and collection_data['slug'] not in collection_slugs:
                        continue
                    
                    logger.info(f"Processing collection: {collection_data['name']}")
                    
                    # Clone repository
                    repo_url = collection_data.get('git_url')
                    if not repo_url:
                        logger.warning(f"No git_url found for {collection_data['name']}")
                        continue
                    
                    repo_path = os.path.join(temp_dir, collection_data['slug'])
                    try:
                        # Clone the repository
                        import git
                        git.Repo.clone_from(repo_url, repo_path)
                        logger.info(f"Cloned {collection_data['name']} to {repo_path}")
                        
                        # Store collection metadata in database
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
                        
                        # Store raw repository files in database
                        files_stored = _store_repository_files(db, collection_data['slug'], repo_path)
                        
                        db.commit()
                        collections_processed += 1
                        logger.info(f"Stored collection and {files_stored} files: {collection_data['name']}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process collection {collection_data['name']}: {e}")
                        continue
            
            finally:
                # Clean up temp directory
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            
            logger.info(f"Repository cloning task {self.request.id} completed: {collections_processed} collections processed")
            return {
                'status': 'success',
                'collections_processed': collections_processed,
                'message': f'Successfully processed {collections_processed} collections'
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Repository cloning task {self.request.id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

def _store_repository_files(db, collection_slug: str, repo_path: str) -> int:
    """Store all relevant files from repository in database"""
    files_stored = 0
    
    # Find all .robot files and other relevant files
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(('.robot', '.yaml', '.yml', '.json')):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repo_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Store raw file data
                    raw_file = RawRepositoryData(
                        collection_slug=collection_slug,
                        repository_path=repo_path,
                        file_path=relative_path,
                        file_content=content,
                        file_type=file.split('.')[-1],
                        is_processed=False
                    )
                    db.add(raw_file)
                    files_stored += 1
                    logger.debug(f"Stored raw file: {relative_path}")
                    
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
                    continue
    
    return files_stored

@celery_app.task(bind=True)
def parse_stored_data_task(self):
    """
    Parse stored raw data and create structured records
    """
    try:
        logger.info(f"Starting data parsing task {self.request.id}")
        
        db = SessionLocal()
        try:
            # Parse raw repository files
            raw_files = db.query(RawRepositoryData).filter(RawRepositoryData.is_processed == False).all()
            
            codebundles_created = 0
            for raw_file in raw_files:
                if raw_file.file_type == 'robot':
                    # Parse Robot Framework file
                    codebundles = _parse_robot_file(raw_file)
                    
                    for codebundle_data in codebundles:
                        # Create or update codebundle
                        codebundle = db.query(Codebundle).filter(
                            Codebundle.slug == codebundle_data['slug'],
                            Codebundle.codecollection_id == raw_file.collection_slug
                        ).first()
                        
                        if not codebundle:
                            codebundle = Codebundle(
                                name=codebundle_data['name'],
                                slug=codebundle_data['slug'],
                                display_name=codebundle_data.get('display_name', codebundle_data['name']),
                                description=codebundle_data.get('description', ''),
                                doc=codebundle_data.get('doc', ''),
                                author=codebundle_data.get('author', ''),
                                support_tags=codebundle_data.get('support_tags', []),
                                tasks=codebundle_data.get('tasks', []),
                                slis=codebundle_data.get('slis', []),
                                codecollection_id=raw_file.collection_slug
                            )
                            db.add(codebundle)
                            codebundles_created += 1
                    
                    # Mark file as processed
                    raw_file.is_processed = True
            
            db.commit()
            logger.info(f"Data parsing task {self.request.id} completed: {codebundles_created} codebundles created")
            return {
                'status': 'success',
                'codebundles_created': codebundles_created,
                'message': f'Successfully created {codebundles_created} codebundles'
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Data parsing task {self.request.id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

def _parse_robot_file(raw_file: RawRepositoryData) -> List[Dict[str, Any]]:
    """Parse Robot Framework file and extract codebundle data"""
    # This is a simplified parser - you'd want to use a proper Robot Framework parser
    content = raw_file.file_content
    codebundles = []
    
    # Basic parsing logic - this would need to be more sophisticated
    lines = content.split('\n')
    current_codebundle = None
    
    for line in lines:
        line = line.strip()
        if line.startswith('*** Test Cases ***'):
            # Start of test cases section
            continue
        elif line and not line.startswith('#'):
            # This is a test case name
            if current_codebundle:
                codebundles.append(current_codebundle)
            
            current_codebundle = {
                'name': line,
                'slug': line.lower().replace(' ', '-'),
                'display_name': line,
                'description': '',
                'doc': '',
                'author': '',
                'support_tags': [],
                'tasks': [],
                'slis': []
            }
    
    if current_codebundle:
        codebundles.append(current_codebundle)
    
    return codebundles

