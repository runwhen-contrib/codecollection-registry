"""
Data processing tasks
"""
import logging
import json
from typing import Dict, Any, List
from celery import current_task
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import RawYamlData, RawRepositoryData, CodeCollection, Codebundle
from app.services.robot_parser import parse_all_robot_files
import yaml
import os

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def store_yaml_data_task(self, yaml_content: str = None):
    """Store YAML data in database"""
    db = None
    try:
        db = SessionLocal()
        logger.info("Starting store_yaml_data_task")
        
        # Read codecollections.yaml if not provided
        if not yaml_content:
            yaml_file_path = "/app/codecollections.yaml"
            logger.info(f"Reading YAML file from: {yaml_file_path}")
            if not os.path.exists(yaml_file_path):
                logger.error(f"YAML file not found: {yaml_file_path}")
                raise FileNotFoundError(f"YAML file not found: {yaml_file_path}")
            
            with open(yaml_file_path, 'r') as f:
                yaml_content = f.read()
            logger.info(f"YAML content loaded, size: {len(yaml_content)} bytes")
        else:
            logger.info(f"Using provided YAML content, size: {len(yaml_content)} bytes")
        
        # Parse YAML
        logger.info("Parsing YAML content")
        parsed_data = yaml.safe_load(yaml_content)
        collections_count = len(parsed_data.get('codecollections', []))
        logger.info(f"YAML parsed successfully, found {collections_count} collections")
        
        # Convert parsed data to JSON string for storage
        parsed_data_json = json.dumps(parsed_data)
        logger.debug(f"Parsed data converted to JSON, size: {len(parsed_data_json)} bytes")
        
        # Store or update raw YAML data
        logger.info("Checking for existing YAML data in database")
        existing = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
        
        if existing:
            logger.info(f"Updating existing RawYamlData record (id={existing.id})")
            existing.content = yaml_content
            existing.parsed_data = parsed_data_json
            existing.is_processed = False
        else:
            logger.info("Creating new RawYamlData record")
            logger.debug(f"RawYamlData parameters: source='codecollections.yaml', content_size={len(yaml_content)}")
            raw_yaml = RawYamlData(
                source="codecollections.yaml",
                content=yaml_content,
                parsed_data=parsed_data_json,
                is_processed=False
            )
            db.add(raw_yaml)
        
        logger.info("Committing database changes")
        db.commit()
        logger.info("Successfully stored YAML data")
        
        result = {
            'status': 'success',
            'collections_count': collections_count,
            'message': 'YAML data stored successfully'
        }
        logger.info(f"Task completed: {result}")
        return result
        
    except FileNotFoundError as e:
        logger.error(f"File not found error: {e}", exc_info=True)
        raise
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Failed to store YAML data: {e}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error args: {e.args}")
        raise
    finally:
        if db:
            logger.info("Closing database session")
            db.close()

@celery_app.task(bind=True)
def clone_repositories_task(self, collection_slugs: List[str] = None):
    """Clone repositories and store files"""
    try:
        from git import Repo
        import tempfile
        import shutil
        
        db = SessionLocal()
        
        # Get YAML data
        raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
        if not raw_yaml:
            raise ValueError("No YAML data found. Run store_yaml_data_task first.")
        
        collections_data = raw_yaml.parsed_data.get('codecollections', [])
        
        # Filter collections if specified
        if collection_slugs:
            collections_data = [c for c in collections_data if c.get('slug') in collection_slugs]
        
        total_files = 0
        
        for collection_data in collections_data:
            try:
                collection_slug = collection_data['slug']
                git_url = collection_data['git_url']
                git_ref = collection_data.get('git_ref', 'main')
                
                logger.info(f"Cloning {collection_slug} from {git_url}")
                
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Clone repository
                    repo = Repo.clone_from(git_url, temp_dir, branch=git_ref, depth=1)
                    
                    # Walk through files
                    for root, dirs, files in os.walk(temp_dir):
                        # Skip .git directory
                        if '.git' in root:
                            continue
                            
                        for file in files:
                            file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(file_path, temp_dir)
                            
                            # Determine file type
                            file_type = None
                            if file.endswith('.robot'):
                                file_type = 'robot'
                            elif file.endswith(('.yaml', '.yml')):
                                file_type = 'yaml'
                            elif file.endswith('.json'):
                                file_type = 'json'
                            elif file.endswith('.md'):
                                file_type = 'markdown'
                            else:
                                continue  # Skip other file types
                            
                            try:
                                # Read file content
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                
                                # Check if file already exists
                                existing = db.query(RawRepositoryData).filter(
                                    RawRepositoryData.collection_slug == collection_slug,
                                    RawRepositoryData.file_path == relative_path
                                ).first()
                                
                                if existing:
                                    existing.file_content = content
                                    existing.file_type = file_type
                                    existing.is_processed = False
                                else:
                                    raw_file = RawRepositoryData(
                                        collection_slug=collection_slug,
                                        repository_path=temp_dir,
                                        file_path=relative_path,
                                        file_content=content,
                                        file_type=file_type,
                                        is_processed=False
                                    )
                                    db.add(raw_file)
                                
                                total_files += 1
                                
                            except Exception as e:
                                logger.warning(f"Failed to read file {relative_path}: {e}")
                                continue
                
                logger.info(f"Completed cloning {collection_slug}")
                
            except Exception as e:
                logger.error(f"Failed to clone collection {collection_data.get('slug', 'unknown')}: {e}")
                continue
        
        db.commit()
        
        return {
            'status': 'success',
            'files_stored': total_files,
            'collections_processed': len(collections_data),
            'message': f'Successfully stored {total_files} files from {len(collections_data)} collections'
        }
        
    except Exception as e:
        logger.error(f"Failed to clone repositories: {e}")
        raise
    finally:
        db.close()

@celery_app.task(bind=True)
def parse_stored_data_task(self):
    """Parse stored raw data into structured records"""
    try:
        db = SessionLocal()
        
        # Parse Robot Framework files
        codebundles_data = parse_all_robot_files(db)
        
        codebundles_created = 0
        codebundles_updated = 0
        
        for codebundle_data in codebundles_data:
            try:
                # Get the collection
                collection = db.query(CodeCollection).filter(
                    CodeCollection.slug == codebundle_data['collection_slug']
                ).first()
                
                if not collection:
                    logger.warning(f"Collection not found: {codebundle_data['collection_slug']}")
                    continue
                
                # Check if codebundle already exists
                existing_codebundle = db.query(Codebundle).filter(
                    Codebundle.slug == codebundle_data['slug']
                ).first()
                
                if existing_codebundle:
                    # Update existing
                    existing_codebundle.name = codebundle_data['name']
                    existing_codebundle.display_name = codebundle_data['display_name']
                    existing_codebundle.description = codebundle_data['description']
                    existing_codebundle.doc = codebundle_data['doc']
                    existing_codebundle.tasks = codebundle_data['tasks']
                    existing_codebundle.support_tags = codebundle_data['support_tags']
                    existing_codebundle.slis = codebundle_data['slis']
                    codebundles_updated += 1
                else:
                    # Create new
                    codebundle = Codebundle(
                        name=codebundle_data['name'],
                        slug=codebundle_data['slug'],
                        display_name=codebundle_data['display_name'],
                        description=codebundle_data['description'],
                        doc=codebundle_data['doc'],
                        author=codebundle_data['author'],
                        support_tags=codebundle_data['support_tags'],
                        tasks=codebundle_data['tasks'],
                        slis=codebundle_data['slis'],
                        codecollection_id=collection.id
                    )
                    db.add(codebundle)
                    codebundles_created += 1
                
            except Exception as e:
                logger.error(f"Failed to process codebundle {codebundle_data.get('name', 'unknown')}: {e}")
                continue
        
        db.commit()
        
        return {
            'status': 'success',
            'codebundles_created': codebundles_created,
            'codebundles_updated': codebundles_updated,
            'total_processed': codebundles_created + codebundles_updated,
            'message': f'Successfully parsed {codebundles_created + codebundles_updated} codebundles'
        }
        
    except Exception as e:
        logger.error(f"Failed to parse stored data: {e}")
        raise
    finally:
        db.close()

@celery_app.task(bind=True)
def populate_registry_task(self, collection_slugs: List[str] = None):
    """Orchestrate full registry population using Celery chains"""
    try:
        # Use Celery chain to sequence tasks without .get()
        from celery import chain
        
        # Create a chain of tasks that will execute sequentially
        workflow = chain(
            store_yaml_data_task.s(),
            clone_repositories_task.s(collection_slugs),
            parse_stored_data_task.s()
        )
        
        # Apply the chain and return the result
        result = workflow.apply_async()
        
        return {
            'status': 'success',
            'message': 'Registry population workflow started',
            'workflow_id': result.id,
            'steps_planned': ['yaml_storage', 'repository_cloning', 'data_parsing']
        }
        
    except Exception as e:
        logger.error(f"Failed to start registry population workflow: {e}")
        raise
