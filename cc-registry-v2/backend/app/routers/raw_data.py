"""
Raw Data API endpoints - Direct data storage without Celery
"""
import os
import yaml
import json
import tempfile
import shutil
import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawYamlData, RawRepositoryData
from app.services.robot_parser import parse_all_robot_files
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["raw-data"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/store-yaml-data")
async def store_yaml_data(db: Session = Depends(get_db)):
    """Store raw YAML data in database"""
    try:
        logger.info("Starting store_yaml_data endpoint")
        
        # Load YAML data
        yaml_path = "/app/codecollections.yaml"
        logger.info(f"Reading YAML file from: {yaml_path}")
        
        if not os.path.exists(yaml_path):
            logger.error(f"YAML file not found: {yaml_path}")
            raise HTTPException(status_code=404, detail=f"YAML file not found: {yaml_path}")
        
        with open(yaml_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        collections_count = len(yaml_data.get('codecollections', []))
        logger.info(f"YAML loaded successfully, found {collections_count} collections")
        
        # Store raw YAML data in database
        logger.info("Checking for existing YAML data in database")
        raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
        
        if raw_yaml:
            # Update existing
            logger.info(f"Updating existing RawYamlData record (id={raw_yaml.id})")
            raw_yaml.content = yaml.dump(yaml_data)
            raw_yaml.parsed_data = json.dumps(yaml_data)
            raw_yaml.is_processed = False
        else:
            # Create new
            logger.info("Creating new RawYamlData record")
            raw_yaml = RawYamlData(
                source="codecollections.yaml",
                content=yaml.dump(yaml_data),
                parsed_data=json.dumps(yaml_data),
                is_processed=False
            )
            db.add(raw_yaml)
        
        logger.info("Committing database changes")
        db.commit()
        logger.info(f"Successfully stored YAML data (id={raw_yaml.id})")
        
        return {
            'status': 'success',
            'message': 'YAML data stored successfully',
            'yaml_id': raw_yaml.id,
            'collections_count': collections_count
        }
        
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to store YAML data: {e}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clone-repositories")
async def clone_repositories(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Clone repositories and store raw file data"""
    try:
        # Load YAML data from database
        raw_yaml = db.query(RawYamlData).filter(RawYamlData.source == "codecollections.yaml").first()
        if not raw_yaml:
            raise HTTPException(status_code=404, detail="No YAML data found in database")
        
        yaml_data = json.loads(raw_yaml.parsed_data)
        collection_slugs = request.get('collection_slugs', [])
        
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
        
        return {
            'status': 'success',
            'collections_processed': collections_processed,
            'message': f'Successfully processed {collections_processed} collections'
        }
        
    except Exception as e:
        logger.error(f"Failed to clone repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _store_repository_files(db: Session, collection_slug: str, repo_path: str) -> int:
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

@router.post("/parse-stored-data")
async def parse_stored_data(db: Session = Depends(get_db)):
    """Parse stored raw data and create structured records"""
    try:
        logger.info("Starting parsing of stored raw data")
        
        # Parse all Robot Framework files
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
        
        logger.info(f"Parsing completed: {codebundles_created} created, {codebundles_updated} updated")
        
        return {
            'status': 'success',
            'codebundles_created': codebundles_created,
            'codebundles_updated': codebundles_updated,
            'total_processed': codebundles_created + codebundles_updated,
            'message': f'Successfully parsed {codebundles_created + codebundles_updated} codebundles'
        }
        
    except Exception as e:
        logger.error(f"Failed to parse stored data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/raw-data-status")
async def get_raw_data_status(db: Session = Depends(get_db)):
    """Get status of raw data storage"""
    try:
        yaml_count = db.query(RawYamlData).count()
        repository_files = db.query(RawRepositoryData).count()
        processed_files = db.query(RawRepositoryData).filter(RawRepositoryData.is_processed == True).count()
        codebundles_count = db.query(Codebundle).count()
        
        return {
            'yaml_data_stored': yaml_count > 0,
            'repository_files_stored': repository_files,
            'processed_files': processed_files,
            'unprocessed_files': repository_files - processed_files,
            'codebundles_created': codebundles_count
        }
        
    except Exception as e:
        logger.error(f"Failed to get raw data status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
