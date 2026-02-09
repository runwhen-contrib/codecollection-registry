from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
import logging
import yaml
import json
import os
import tempfile
import shutil
import git
import subprocess
from datetime import datetime

from app.services.helm_sync import sync_runwhen_local_chart
from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.models import CodeCollection, Codebundle, RawYamlData, RawRepositoryData
from app.services.robot_parser import parse_all_robot_files
from app.tasks.fixed_parser import parse_robot_file_content, parse_generation_rules
from pathlib import Path
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_git_last_commit_date(repo_path: str, folder_path: str) -> Optional[datetime]:
    """Get the last commit date for files in a folder using git log, excluding meta.yml/meta.yaml"""
    try:
        # Exclude meta.yml and meta.yaml files from git log to get real code update dates
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
            dt = datetime.fromtimestamp(timestamp)
            logger.info(f"Git date for {folder_path}: {dt}")
            return dt
        else:
            logger.warning(f"No git date found for {folder_path}: rc={result.returncode}, stderr={result.stderr}")
    except Exception as e:
        logger.warning(f"Could not get git date for {folder_path}: {e}")
    return None

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    # For development, accept any token that starts with 'admin-'
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

@router.post("/populate-data")
async def trigger_data_population(token: str = Depends(verify_admin_token)):
    """Trigger comprehensive data population: Load YAML, clone repos, parse codebundles"""
    db = SessionLocal()
    try:
        logger.info("Starting data population triggered by admin")
        
        # Step 1: Load YAML data
        yaml_path = "/app/codecollections.yaml"
        if not os.path.exists(yaml_path):
            raise HTTPException(status_code=404, detail=f"YAML file not found: {yaml_path}")
            
        with open(yaml_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        collections_data = yaml_data.get('codecollections', [])
        logger.info(f"Loaded {len(collections_data)} collections from YAML")
        
        # Step 2: Process each collection
        collections_synced = 0
        codebundles_created = 0
        codebundles_updated = 0
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            for collection_data in collections_data:
                try:
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
                        db.commit()
                        db.refresh(collection)
                        logger.info(f"Created collection: {collection_slug}")
                    else:
                        collection.name = collection_data.get('name', collection_slug)
                        collection.git_url = git_url
                        collection.description = collection_data.get('description', '')
                        collection.is_active = True
                        db.commit()
                        logger.info(f"Updated collection: {collection_slug}")
                    
                    collections_synced += 1
                    
                    # Clone repository
                    repo_path = os.path.join(tmp_dir, collection_slug)
                    logger.info(f"Cloning {git_url} to {repo_path}")
                    
                    try:
                        # Clone without depth limit to get full history for accurate git dates
                        git.Repo.clone_from(git_url, repo_path)
                    except Exception as clone_err:
                        logger.error(f"Failed to clone {git_url}: {clone_err}")
                        continue
                    
                    # Find and parse codebundles
                    codebundles_dir = os.path.join(repo_path, 'codebundles')
                    if not os.path.exists(codebundles_dir):
                        logger.warning(f"No codebundles directory in {collection_slug}")
                        continue
                    
                    for bundle_name in os.listdir(codebundles_dir):
                        bundle_path = os.path.join(codebundles_dir, bundle_name)
                        if not os.path.isdir(bundle_path):
                            continue
                        
                        # Check for runbook.robot and sli.robot separately
                        runbook_path = os.path.join(bundle_path, 'runbook.robot')
                        sli_path = os.path.join(bundle_path, 'sli.robot')
                        
                        has_runbook = os.path.exists(runbook_path)
                        has_sli = os.path.exists(sli_path)
                        
                        if not has_runbook and not has_sli:
                            continue
                        
                        try:
                            # Parse runbook.robot for TaskSet tasks
                            runbook_parsed = None
                            if has_runbook:
                                with open(runbook_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/runbook.robot"
                                runbook_parsed = parse_robot_file_content(content, relative_path, collection_slug)
                            
                            # Parse sli.robot for SLI tasks
                            sli_parsed = None
                            if has_sli:
                                with open(sli_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/sli.robot"
                                sli_parsed = parse_robot_file_content(content, relative_path, collection_slug)
                            
                            # Use runbook metadata as primary, fallback to sli
                            primary_parsed = runbook_parsed or sli_parsed
                            if not primary_parsed:
                                continue
                            
                            # Extract tasks and SLIs separately
                            taskset_tasks = runbook_parsed.get('tasks', []) if runbook_parsed else []
                            sli_tasks = sli_parsed.get('tasks', []) if sli_parsed else []
                            
                            # Combine support tags from both files
                            support_tags = list(set(
                                (runbook_parsed.get('support_tags', []) if runbook_parsed else []) +
                                (sli_parsed.get('support_tags', []) if sli_parsed else [])
                            ))
                            
                            # Determine codebundle type
                            if has_runbook and has_sli:
                                codebundle_type = "both"
                            elif has_runbook:
                                codebundle_type = "taskset"
                            else:
                                codebundle_type = "sli"
                            
                            # Read README if exists
                            readme_content = ""
                            readme_path_file = os.path.join(bundle_path, "README.md")
                            if os.path.exists(readme_path_file):
                                with open(readme_path_file, 'r', encoding='utf-8') as f:
                                    readme_content = f.read()
                            
                            # Parse .runwhen/generation-rules for discovery configuration
                            runwhen_dir = Path(bundle_path) / '.runwhen'
                            gen_rules = parse_generation_rules(runwhen_dir)
                            
                            # Create/update codebundle
                            existing = db.query(Codebundle).filter(
                                Codebundle.slug == primary_parsed['slug'],
                                Codebundle.codecollection_id == collection.id
                            ).first()
                            
                            # Build runbook source URL
                            runbook_source_url = f"{git_url.rstrip('.git')}/tree/main/codebundles/{bundle_name}"
                            
                            # Get last git commit date for this codebundle folder
                            git_date = get_git_last_commit_date(repo_path, f"codebundles/{bundle_name}")
                            
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
                                existing.runbook_path = f"codebundles/{bundle_name}/runbook.robot" if has_runbook else f"codebundles/{bundle_name}/sli.robot"
                                existing.sli_path = f"codebundles/{bundle_name}/sli.robot" if has_sli else None
                                # Discovery configuration from generation-rules
                                existing.has_genrules = gen_rules.get('has_genrules', False)
                                existing.is_discoverable = gen_rules.get('is_discoverable', False)
                                existing.discovery_platform = gen_rules.get('discovery_platform')
                                existing.discovery_resource_types = gen_rules.get('discovery_resource_types', [])
                                existing.discovery_match_patterns = gen_rules.get('discovery_match_patterns', [])
                                existing.discovery_output_items = gen_rules.get('discovery_output_items', [])
                                existing.discovery_level_of_detail = gen_rules.get('discovery_level_of_detail')
                                existing.discovery_templates = gen_rules.get('discovery_templates', [])
                                if runwhen_dir.exists():
                                    existing.runwhen_directory_path = f"codebundles/{bundle_name}/.runwhen"
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
                                    runbook_path=f"codebundles/{bundle_name}/runbook.robot" if has_runbook else f"codebundles/{bundle_name}/sli.robot",
                                    sli_path=f"codebundles/{bundle_name}/sli.robot" if has_sli else None,
                                    is_active=True,
                                    # Discovery configuration from generation-rules
                                    has_genrules=gen_rules.get('has_genrules', False),
                                    is_discoverable=gen_rules.get('is_discoverable', False),
                                    discovery_platform=gen_rules.get('discovery_platform'),
                                    discovery_resource_types=gen_rules.get('discovery_resource_types', []),
                                    discovery_match_patterns=gen_rules.get('discovery_match_patterns', []),
                                    discovery_output_items=gen_rules.get('discovery_output_items', []),
                                    discovery_level_of_detail=gen_rules.get('discovery_level_of_detail'),
                                    discovery_templates=gen_rules.get('discovery_templates', []),
                                    runwhen_directory_path=f"codebundles/{bundle_name}/.runwhen" if runwhen_dir.exists() else None,
                                    git_updated_at=git_date
                                )
                                db.add(codebundle)
                                codebundles_created += 1
                                    
                        except Exception as parse_err:
                            logger.error(f"Failed to parse codebundle {bundle_name}: {parse_err}")
                            continue
                    
                    db.commit()
                    
                except Exception as coll_err:
                    logger.error(f"Failed to process collection {collection_data.get('slug', 'unknown')}: {coll_err}")
                    continue
        
        db.commit()
        
        result = {
            "status": "success",
            "collections_synced": collections_synced,
            "codebundles_created": codebundles_created,
            "codebundles_updated": codebundles_updated,
            "total_codebundles": codebundles_created + codebundles_updated
        }
        
        logger.info(f"Data population completed: {result}")
        
        return {
            "message": "Registry data population completed successfully",
            "details": result
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Data population error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Population failed: {str(e)}")
    finally:
        db.close()

@router.get("/population-status")
async def get_population_status(token: str = Depends(verify_admin_token)):
    """Get current population status and statistics"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, Codebundle
        
        db = SessionLocal()
        try:
            from sqlalchemy import func
            
            collections_count = db.query(CodeCollection).count()
            codebundles_count = db.query(Codebundle).count()
            # Count tasks using authoritative integer fields (consistent with stats endpoint)
            stats = db.query(
                func.coalesce(func.sum(Codebundle.task_count), 0).label('total_tasks'),
                func.coalesce(func.sum(Codebundle.sli_count), 0).label('total_slis')
            ).first()
            tasks_count = int(stats.total_tasks) + int(stats.total_slis)
            
            return {
                "collections": collections_count,
                "codebundles": codebundles_count,
                "tasks": tasks_count,
                "status": "ready"
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/clear-data")
async def clear_all_data(token: str = Depends(verify_admin_token)):
    """Clear all data from the database (use with caution!)"""
    try:
        from app.core.database import SessionLocal
        from app.models import (
            CodeCollection, Codebundle, CodeCollectionVersion, VersionCodebundle,
            CodeCollectionMetrics, SystemMetrics, RawRepositoryData, RawYamlData, 
            HelmChart, HelmChartVersion, HelmChartTemplate, AIConfiguration, 
            AIEnhancementLog, TaskExecution
        )
        
        db = SessionLocal()
        try:
            # Delete in reverse order to respect foreign key constraints
            # Start with the most dependent tables first
            
            # AI and task execution tables
            db.query(AIEnhancementLog).delete()
            db.query(TaskExecution).delete()
            
            # Helm chart related tables
            db.query(HelmChartTemplate).delete()
            db.query(HelmChartVersion).delete()
            db.query(HelmChart).delete()
            
            # Raw data tables
            db.query(RawRepositoryData).delete()
            db.query(RawYamlData).delete()
            
            # Version-related tables
            db.query(VersionCodebundle).delete()
            db.query(CodeCollectionVersion).delete()
            
            # Metrics tables
            db.query(CodeCollectionMetrics).delete()
            db.query(SystemMetrics).delete()
            
            # AI configuration
            db.query(AIConfiguration).delete()
            
            # Main tables
            db.query(Codebundle).delete()
            db.query(CodeCollection).delete()
            
            db.commit()
            
            return {
                "message": "All data cleared successfully",
                "collections_deleted": True,
                "codebundles_deleted": True,
                "versions_deleted": True,
                "metrics_deleted": True,
                "raw_data_deleted": True,
                "helm_charts_deleted": True,
                "ai_data_deleted": True,
                "task_executions_deleted": True
            }
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=f"Clear data failed: {str(e)}")

@router.post("/sync-helm-charts")
async def sync_helm_charts(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Sync helm chart versions from repository"""
    try:
        logger.info("Starting helm chart sync triggered by admin")
        
        result = sync_runwhen_local_chart(db)
        
        logger.info(f"Helm chart sync completed: {result}")
        return {
            "status": "success",
            "message": "Helm chart versions synced successfully",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Helm chart sync failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Helm chart sync failed: {str(e)}")

@router.get("/releases/status")
async def get_releases_status(token: str = Depends(verify_admin_token)):
    """Get version management status and statistics (versions are now automatically synced during collection indexing)"""
    try:
        from app.core.database import SessionLocal
        from app.models import CodeCollection, CodeCollectionVersion, VersionCodebundle
        
        db = SessionLocal()
        try:
            # Get release statistics
            total_collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).count()
            collections_with_versions = db.query(CodeCollection).join(CodeCollectionVersion).distinct().count()
            total_versions = db.query(CodeCollectionVersion).filter(CodeCollectionVersion.is_active == True).count()
            total_version_codebundles = db.query(VersionCodebundle).count()
            
            # Get latest versions
            latest_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.is_latest == True,
                CodeCollectionVersion.is_active == True
            ).count()
            
            # Get prerelease count
            prereleases = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.is_prerelease == True,
                CodeCollectionVersion.is_active == True
            ).count()
            
            # Get version type counts
            main_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.version_type == 'main',
                CodeCollectionVersion.is_active == True
            ).count()
            
            tag_versions = db.query(CodeCollectionVersion).filter(
                CodeCollectionVersion.version_type == 'tag',
                CodeCollectionVersion.is_active == True
            ).count()
            
            return {
                "total_collections": total_collections,
                "collections_with_versions": collections_with_versions,
                "total_versions": total_versions,
                "latest_versions": latest_versions,
                "prereleases": prereleases,
                "main_versions": main_versions,
                "tag_versions": tag_versions,
                "total_version_codebundles": total_version_codebundles,
                "coverage_percentage": round((collections_with_versions / total_collections * 100) if total_collections > 0 else 0, 2)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting release status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get release status: {str(e)}")


@router.get("/ai-enhancement/status")
async def get_ai_enhancement_status(token: str = Depends(verify_admin_token)):
    """Get AI enhancement status and statistics"""
    try:
        from app.core.database import SessionLocal
        from app.models import Codebundle
        from app.services.ai_service import AIEnhancementService
        
        db = SessionLocal()
        try:
            # Check if AI is configured
            ai_service = AIEnhancementService(db)
            
            # Get enhancement statistics
            total = db.query(Codebundle).filter(Codebundle.is_active == True).count()
            enhanced = db.query(Codebundle).filter(
                Codebundle.is_active == True,
                Codebundle.enhancement_status == 'completed'
            ).count()
            pending = db.query(Codebundle).filter(
                Codebundle.is_active == True,
                (Codebundle.enhancement_status == None) | 
                (Codebundle.enhancement_status == 'pending')
            ).count()
            failed = db.query(Codebundle).filter(
                Codebundle.is_active == True,
                Codebundle.enhancement_status == 'failed'
            ).count()
            
            return {
                "ai_enabled": ai_service.is_enabled(),
                "ai_provider": ai_service.config.service_provider if ai_service.config else None,
                "ai_model": ai_service.config.model_name if ai_service.config else None,
                "total_codebundles": total,
                "enhanced": enhanced,
                "pending": pending,
                "failed": failed,
                "enhancement_percentage": round((enhanced / total * 100) if total > 0 else 0, 1)
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting AI enhancement status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI status: {str(e)}")


@router.post("/ai-enhancement/run")
async def run_ai_enhancement(
    token: str = Depends(verify_admin_token),
    limit: int = 10,
    collection_slug: str = None
):
    """Trigger AI enhancement for pending codebundles - queues tasks for workers"""
    try:
        from app.core.database import SessionLocal
        from app.models import Codebundle, CodeCollection
        from app.services.ai_service import AIEnhancementService
        from app.tasks.ai_enhancement_tasks import enhance_codebundle_task
        
        db = SessionLocal()
        try:
            ai_service = AIEnhancementService(db)
            
            if not ai_service.is_enabled():
                raise HTTPException(
                    status_code=400, 
                    detail="AI enhancement is not configured. Set AZURE_OPENAI_* environment variables."
                )
            
            # Build query
            query = db.query(Codebundle).filter(
                Codebundle.is_active == True,
                (Codebundle.enhancement_status == None) | 
                (Codebundle.enhancement_status == 'pending') |
                (Codebundle.enhancement_status == 'failed')
            )
            
            if collection_slug:
                collection = db.query(CodeCollection).filter(CodeCollection.slug == collection_slug).first()
                if collection:
                    query = query.filter(Codebundle.codecollection_id == collection.id)
            
            codebundles = query.limit(limit).all()
            
            if not codebundles:
                return {"message": "No codebundles need enhancement", "queued": 0}
            
            # Queue codebundles for async enhancement by workers
            queued_tasks = []
            
            for cb in codebundles:
                try:
                    # Mark as pending and queue the task to workers
                    cb.enhancement_status = "pending"
                    db.commit()
                    
                    # Delegate to Celery worker asynchronously
                    task = enhance_codebundle_task.apply_async(args=[cb.id])
                    queued_tasks.append({
                        "codebundle_id": cb.id,
                        "codebundle_name": cb.name,
                        "task_id": task.id
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to queue enhancement for {cb.name}: {e}")
            
            return {
                "message": f"Queued {len(queued_tasks)} codebundles for AI enhancement",
                "queued": len(queued_tasks),
                "tasks": queued_tasks,
                "remaining": query.count() - len(codebundles)
            }
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI enhancement error: {e}")
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")
