"""
Celery tasks for AI-powered CodeBundle enhancement
"""
import logging
from typing import List, Optional
from datetime import datetime

from celery import current_task
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Codebundle, AIConfiguration
from app.tasks.registry_tasks import celery_app

logger = logging.getLogger(__name__)

# Try to import AI service, but handle gracefully if not available
try:
    from app.services.enhanced_ai_service import get_enhanced_ai_service
    AI_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Enhanced AI service not available: {e}")
    AI_SERVICE_AVAILABLE = False
    
    def get_enhanced_ai_service(db):
        return None


@celery_app.task(bind=True)
def enhance_codebundle_task(self, codebundle_id: int):
    """
    Enhance a single CodeBundle with AI-generated content
    """
    try:
        db = next(get_db())
        
        # Get the codebundle
        codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
        if not codebundle:
            raise ValueError(f"CodeBundle with id {codebundle_id} not found")
        
        # Update status to processing
        codebundle.enhancement_status = "processing"
        db.commit()
        
        # Get AI service
        if not AI_SERVICE_AVAILABLE:
            codebundle.enhancement_status = "failed"
            db.commit()
            raise ValueError("AI service is not available - missing dependencies")
            
        ai_service = get_enhanced_ai_service(db)
        
        if not ai_service or not ai_service.is_enabled():
            codebundle.enhancement_status = "failed"
            db.commit()
            raise ValueError("AI enhancement is not enabled or configured")
        
        # Perform enhancement with full logging
        self.update_state(state='PROGRESS', meta={'status': 'Enhancing with AI...'})
        
        enhancement_result = ai_service.enhance_codebundle_with_logging(codebundle)
        
        # Update codebundle with enhanced data
        codebundle.ai_enhanced_description = enhancement_result["enhanced_description"]
        codebundle.access_level = enhancement_result["access_level"]
        codebundle.minimum_iam_requirements = enhancement_result["iam_requirements"]
        
        # Store enhanced tasks in AI metadata for now
        if enhancement_result.get("enhanced_tasks"):
            if not codebundle.ai_enhanced_metadata:
                codebundle.ai_enhanced_metadata = {}
            codebundle.ai_enhanced_metadata["enhanced_tasks"] = enhancement_result["enhanced_tasks"]
        
        # Update AI metadata
        codebundle.ai_enhanced_metadata = enhancement_result["enhancement_metadata"]
        codebundle.enhancement_status = "completed"
        codebundle.last_enhanced = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Successfully enhanced CodeBundle {codebundle.slug}")
        
        return {
            'status': 'completed',
            'codebundle_id': codebundle_id,
            'codebundle_slug': codebundle.slug,
            'enhanced_description': enhancement_result["enhanced_description"],
            'access_level': enhancement_result["access_level"],
            'iam_requirements': enhancement_result["iam_requirements"]
        }
        
    except Exception as e:
        logger.error(f"Error enhancing CodeBundle {codebundle_id}: {e}")
        
        # Update status to failed
        try:
            db = next(get_db())
            codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
            if codebundle:
                codebundle.enhancement_status = "failed"
                db.commit()
        except Exception as db_error:
            logger.error(f"Error updating failed status: {db_error}")
        
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise


@celery_app.task(bind=True)
def enhance_multiple_codebundles_task(self, codebundle_ids: List[int]):
    """
    Enhance multiple CodeBundles with AI-generated content
    """
    try:
        db = next(get_db())
        
        total_bundles = len(codebundle_ids)
        completed = 0
        failed = 0
        results = []
        
        for i, codebundle_id in enumerate(codebundle_ids):
            self.update_state(
                state='PROGRESS', 
                meta={
                    'current': i + 1,
                    'total': total_bundles,
                    'status': f'Processing CodeBundle {codebundle_id}...'
                }
            )
            
            try:
                # Get the codebundle
                codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
                if not codebundle:
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle_id,
                        'error': f"CodeBundle with id {codebundle_id} not found"
                    })
                    continue
                
                # Update status to processing
                codebundle.enhancement_status = "processing"
                db.commit()
                
                # Check AI service availability
                if not AI_SERVICE_AVAILABLE:
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle_id,
                        'error': "AI service is not available - missing dependencies"
                    })
                    continue
                    
                ai_service = get_enhanced_ai_service(db)
                
                if not ai_service or not ai_service.is_enabled():
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle_id,
                        'error': "AI enhancement is not enabled or configured"
                    })
                    continue
                
                # Perform enhancement with full logging
                enhancement_result = ai_service.enhance_codebundle_with_logging(codebundle)
                
                # Update codebundle with enhanced data
                codebundle.ai_enhanced_description = enhancement_result["enhanced_description"]
                codebundle.access_level = enhancement_result["access_level"]
                codebundle.minimum_iam_requirements = enhancement_result["iam_requirements"]
                
                # Store enhanced tasks in AI metadata
                if enhancement_result.get("enhanced_tasks"):
                    if not codebundle.ai_enhanced_metadata:
                        codebundle.ai_enhanced_metadata = {}
                    codebundle.ai_enhanced_metadata["enhanced_tasks"] = enhancement_result["enhanced_tasks"]
                
                # Update AI metadata
                codebundle.ai_enhanced_metadata = enhancement_result["enhancement_metadata"]
                codebundle.enhancement_status = "completed"
                codebundle.last_enhanced = datetime.utcnow()
                
                db.commit()
                
                completed += 1
                results.append({
                    'status': 'success',
                    'codebundle_id': codebundle_id,
                    'codebundle_slug': codebundle.slug
                })
                
                logger.info(f"Successfully enhanced CodeBundle {codebundle.slug}")
                
            except Exception as e:
                logger.error(f"Failed to enhance CodeBundle {codebundle_id}: {e}")
                
                # Update status to failed
                try:
                    codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
                    if codebundle:
                        codebundle.enhancement_status = "failed"
                        db.commit()
                except Exception as db_error:
                    logger.error(f"Error updating failed status: {db_error}")
                
                failed += 1
                results.append({
                    'status': 'failed',
                    'codebundle_id': codebundle_id,
                    'error': str(e)
                })
        
        self.update_state(
            state='SUCCESS', 
            meta={
                'current': total_bundles,
                'total': total_bundles,
                'status': 'Completed',
                'completed': completed,
                'failed': failed
            }
        )
        
        return {
            'status': 'completed',
            'total_processed': total_bundles,
            'completed': completed,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in batch enhancement: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise


@celery_app.task(bind=True)
def enhance_collection_codebundles_task(self, collection_slug: str):
    """
    Enhance all CodeBundles in a specific collection
    """
    try:
        db = next(get_db())
        
        # Get all codebundles in the collection
        codebundles = db.query(Codebundle).join(Codebundle.codecollection).filter(
            Codebundle.codecollection.has(slug=collection_slug),
            Codebundle.is_active == True
        ).all()
        
        if not codebundles:
            return {
                'status': 'completed',
                'message': f'No active CodeBundles found in collection {collection_slug}'
            }
        
        # Process codebundles directly in this task (no nested tasks)
        completed = 0
        failed = 0
        results = []
        
        for codebundle in codebundles:
            try:
                # Update status to processing
                codebundle.enhancement_status = "processing"
                db.commit()
                
                # Check AI service availability
                if not AI_SERVICE_AVAILABLE:
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle.id,
                        'error': "AI service is not available - missing dependencies"
                    })
                    continue
                    
                ai_service = get_enhanced_ai_service(db)
                
                if not ai_service or not ai_service.is_enabled():
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle.id,
                        'error': "AI enhancement is not enabled or configured"
                    })
                    continue
                
                # Perform enhancement with full logging
                enhancement_result = ai_service.enhance_codebundle_with_logging(codebundle)
                
                # Update codebundle with enhanced data
                codebundle.ai_enhanced_description = enhancement_result["enhanced_description"]
                codebundle.access_level = enhancement_result["access_level"]
                codebundle.minimum_iam_requirements = enhancement_result["iam_requirements"]
                
                # Store enhanced tasks in AI metadata
                if enhancement_result.get("enhanced_tasks"):
                    if not codebundle.ai_enhanced_metadata:
                        codebundle.ai_enhanced_metadata = {}
                    codebundle.ai_enhanced_metadata["enhanced_tasks"] = enhancement_result["enhanced_tasks"]
                
                # Update AI metadata
                codebundle.ai_enhanced_metadata = enhancement_result["enhancement_metadata"]
                codebundle.enhancement_status = "completed"
                codebundle.last_enhanced = datetime.utcnow()
                
                db.commit()
                
                completed += 1
                results.append({
                    'status': 'success',
                    'codebundle_id': codebundle.id,
                    'codebundle_slug': codebundle.slug
                })
                
                logger.info(f"Successfully enhanced CodeBundle {codebundle.slug}")
                
            except Exception as e:
                logger.error(f"Failed to enhance CodeBundle {codebundle.id}: {e}")
                
                # Update status to failed
                try:
                    codebundle.enhancement_status = "failed"
                    db.commit()
                except Exception as db_error:
                    logger.error(f"Error updating failed status: {db_error}")
                
                failed += 1
                results.append({
                    'status': 'failed',
                    'codebundle_id': codebundle.id,
                    'error': str(e)
                })
        
        return {
            'status': 'completed',
            'collection_slug': collection_slug,
            'total_processed': len(codebundles),
            'completed': completed,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error enhancing collection {collection_slug}: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise


@celery_app.task(bind=True)
def enhance_pending_codebundles_task(self, limit: Optional[int] = None):
    """
    Enhance all CodeBundles with pending enhancement status
    """
    try:
        db = next(get_db())
        
        # Get pending codebundles (including NULL values)
        query = db.query(Codebundle).filter(
            (Codebundle.enhancement_status == "pending") | (Codebundle.enhancement_status.is_(None)),
            Codebundle.is_active == True
        )
        
        if limit:
            query = query.limit(limit)
        
        codebundles = query.all()
        
        if not codebundles:
            return {
                'status': 'completed',
                'message': 'No pending CodeBundles found'
            }
        
        # Process codebundles directly in this task (no nested tasks)
        completed = 0
        failed = 0
        results = []
        
        for codebundle in codebundles:
            try:
                # Update status to processing
                codebundle.enhancement_status = "processing"
                db.commit()
                
                # Check AI service availability
                if not AI_SERVICE_AVAILABLE:
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle.id,
                        'error': "AI service is not available - missing dependencies"
                    })
                    continue
                    
                ai_service = get_enhanced_ai_service(db)
                
                if not ai_service or not ai_service.is_enabled():
                    codebundle.enhancement_status = "failed"
                    db.commit()
                    failed += 1
                    results.append({
                        'status': 'failed',
                        'codebundle_id': codebundle.id,
                        'error': "AI enhancement is not enabled or configured"
                    })
                    continue
                
                # Perform enhancement with full logging
                enhancement_result = ai_service.enhance_codebundle_with_logging(codebundle)
                
                # Update codebundle with enhanced data
                codebundle.ai_enhanced_description = enhancement_result["enhanced_description"]
                codebundle.access_level = enhancement_result["access_level"]
                codebundle.minimum_iam_requirements = enhancement_result["iam_requirements"]
                
                # Store enhanced tasks in AI metadata
                if enhancement_result.get("enhanced_tasks"):
                    if not codebundle.ai_enhanced_metadata:
                        codebundle.ai_enhanced_metadata = {}
                    codebundle.ai_enhanced_metadata["enhanced_tasks"] = enhancement_result["enhanced_tasks"]
                
                # Update AI metadata
                codebundle.ai_enhanced_metadata = enhancement_result["enhancement_metadata"]
                codebundle.enhancement_status = "completed"
                codebundle.last_enhanced = datetime.utcnow()
                
                db.commit()
                
                completed += 1
                results.append({
                    'status': 'success',
                    'codebundle_id': codebundle.id,
                    'codebundle_slug': codebundle.slug
                })
                
                logger.info(f"Successfully enhanced CodeBundle {codebundle.slug}")
                
            except Exception as e:
                logger.error(f"Failed to enhance CodeBundle {codebundle.id}: {e}")
                
                # Update status to failed
                try:
                    codebundle.enhancement_status = "failed"
                    db.commit()
                except Exception as db_error:
                    logger.error(f"Error updating failed status: {db_error}")
                
                failed += 1
                results.append({
                    'status': 'failed',
                    'codebundle_id': codebundle.id,
                    'error': str(e)
                })
        
        return {
            'status': 'completed',
            'total_processed': len(codebundles),
            'completed': completed,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error enhancing pending CodeBundles: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise


