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
        yaml_path = settings.CODECOLLECTIONS_FILE
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
        clone_cache: Dict[Any, str] = {}
        
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
                
                git_ref = collection_data.get('git_ref', 'main')
                cache_key = (repo_url, git_ref)
                try:
                    # Clone once per (git_url, git_ref): V13 plugins share a
                    # monorepo, so six collections clone a single repository.
                    if cache_key not in clone_cache:
                        import git
                        repo_path = os.path.join(temp_dir, f"repo-{abs(hash(cache_key))}")
                        git.Repo.clone_from(repo_url, repo_path, branch=git_ref, depth=1)
                        clone_cache[cache_key] = repo_path
                    repo_path = clone_cache[cache_key]
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
                    plugin_path = collection_data.get('plugin_path')
                    if not plugin_path and os.path.isdir(os.path.join(repo_path, 'plugins', collection_data['slug'])):
                        plugin_path = f"plugins/{collection_data['slug']}"
                    files_stored = _store_repository_files(
                        db, collection_data['slug'], repo_path, plugin_path
                    )
                    
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

def _store_repository_files(db: Session, collection_slug: str, repo_path: str, plugin_path: str = None) -> int:
    """Store all relevant files from repository in database.

    When `plugin_path` is set (a V13 plugin inside a shared monorepo), only
    files under that path are stored for this collection.
    """
    files_stored = 0
    prefix = f"{plugin_path.rstrip('/')}/" if plugin_path else None

    # Find all .robot files and other relevant files (`.md` covers SKILL.md)
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(('.robot', '.yaml', '.yml', '.json', '.md')):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, repo_path)

                # Scope a shared monorepo checkout to this collection's plugin.
                if prefix and not (relative_path + "/").startswith(prefix):
                    continue

                try:
                    existing = db.query(RawRepositoryData).filter(
                        RawRepositoryData.collection_slug == collection_slug,
                        RawRepositoryData.file_path == relative_path,
                    ).first()
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if existing:
                        existing.file_content = content
                        existing.repository_path = repo_path
                        existing.file_type = file.split('.')[-1]
                        existing.is_processed = False
                    else:
                        db.add(RawRepositoryData(
                            collection_slug=collection_slug,
                            repository_path=repo_path,
                            file_path=relative_path,
                            file_content=content,
                            file_type=file.split('.')[-1],
                            is_processed=False
                        ))
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

        # --- V13 plugins: reconstruct skills from stored raw files ---
        from app.tasks.plugin_sync import (
            parse_collection_plugin_from_files,
            sync_plugin_collection,
        )

        all_rows = db.query(RawRepositoryData).all()
        plugin_files_by_collection: Dict[str, Dict[str, str]] = {}
        plugin_rows_by_collection: Dict[str, list] = {}
        for raw_file in all_rows:
            path = raw_file.file_path or ""
            if not (path.startswith("plugins/") or path in ("plugin.yaml", "integration/integration.yaml")):
                continue
            plugin_files_by_collection.setdefault(raw_file.collection_slug, {})[path] = raw_file.file_content or ""
            plugin_rows_by_collection.setdefault(raw_file.collection_slug, []).append(raw_file)

        plugin_skills_created = 0
        plugin_skills_updated = 0
        for collection_slug, files in plugin_files_by_collection.items():
            collection = db.query(CodeCollection).filter(
                CodeCollection.slug == collection_slug
            ).first()
            if not collection:
                logger.warning(f"Collection not found for plugin files: {collection_slug}")
                continue
            parsed_plugin = parse_collection_plugin_from_files(
                collection_slug, files,
                git_url=collection.git_url,
                git_ref=collection.git_ref,
            )
            if parsed_plugin and parsed_plugin.get("skills"):
                created, updated, _ = sync_plugin_collection(db, collection, "", parsed_plugin)
                plugin_skills_created += created
                plugin_skills_updated += updated
            for raw_file in plugin_rows_by_collection.get(collection_slug, []):
                raw_file.is_processed = True
        db.commit()

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
            'codebundles_created': codebundles_created + plugin_skills_created,
            'codebundles_updated': codebundles_updated + plugin_skills_updated,
            'total_processed': codebundles_created + codebundles_updated + plugin_skills_created + plugin_skills_updated,
            'message': f'Successfully parsed {codebundles_created + codebundles_updated} codebundles and {plugin_skills_created + plugin_skills_updated} plugin skills'
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
