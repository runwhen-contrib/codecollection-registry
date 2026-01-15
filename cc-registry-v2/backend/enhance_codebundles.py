#!/usr/bin/env python3
"""
Script to enhance codebundle descriptions using AI.

Usage:
    # Synchronous (blocking) - good for small batches or testing
    docker-compose exec backend python enhance_codebundles.py [--limit N] [--collection SLUG]
    
    # Async (queued to workers) - recommended for large batches
    docker-compose exec backend python enhance_codebundles.py --async [--limit N] [--collection SLUG]

This uses Azure OpenAI (configured via environment vars) to generate:
- Enhanced descriptions
- Access level classification (read-only, write, admin)
- IAM requirements

Options:
    --limit N           Process only N codebundles
    --collection SLUG   Process only codebundles from this collection
    --force             Re-enhance already enhanced codebundles
    --async             Queue tasks to Celery workers (recommended for large batches)
"""

import sys
import argparse
import logging

sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models import Codebundle, CodeCollection
from app.services.ai_service import AIEnhancementService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def enhance_codebundles(limit: int = None, collection_slug: str = None, force: bool = False, async_mode: bool = False):
    """
    Enhance codebundles with AI-generated descriptions
    
    Args:
        limit: Maximum number of codebundles to process
        collection_slug: Only process codebundles from this collection
        force: Re-enhance already enhanced codebundles
        async_mode: If True, queue tasks to Celery workers instead of processing synchronously
    """
    
    db = SessionLocal()
    
    try:
        # Check if AI is configured
        ai_service = AIEnhancementService(db)
        
        if not ai_service.is_enabled():
            logger.error("AI enhancement is not enabled. Check your environment variables:")
            logger.error("  - AI_SERVICE_PROVIDER=azure-openai")
            logger.error("  - AI_ENHANCEMENT_ENABLED=true")
            logger.error("  - AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME")
            return False
        
        logger.info(f"AI service enabled: {ai_service.config.service_provider} / {ai_service.config.model_name}")
        logger.info(f"Mode: {'Async (queued to workers)' if async_mode else 'Synchronous (blocking)'}")
        
        # Build query for codebundles
        query = db.query(Codebundle).filter(Codebundle.is_active == True)
        
        if collection_slug:
            collection = db.query(CodeCollection).filter(CodeCollection.slug == collection_slug).first()
            if not collection:
                logger.error(f"Collection '{collection_slug}' not found")
                return False
            query = query.filter(Codebundle.codecollection_id == collection.id)
            logger.info(f"Filtering to collection: {collection.name}")
        
        if not force:
            # Only enhance those without existing enhancement
            query = query.filter(
                (Codebundle.enhancement_status == None) | 
                (Codebundle.enhancement_status == 'pending') |
                (Codebundle.enhancement_status == 'failed')
            )
        
        if limit:
            query = query.limit(limit)
        
        codebundles = query.all()
        logger.info(f"Found {len(codebundles)} codebundles to enhance")
        
        if not codebundles:
            logger.info("No codebundles need enhancement")
            return True
        
        # Process based on mode
        if async_mode:
            # Queue tasks to Celery workers
            from app.tasks.ai_enhancement_tasks import enhance_codebundle_task
            
            queued_count = 0
            for i, cb in enumerate(codebundles, 1):
                try:
                    logger.info(f"[{i}/{len(codebundles)}] Queuing: {cb.name} ({cb.codecollection.name})")
                    
                    cb.enhancement_status = "pending"
                    db.commit()
                    
                    task = enhance_codebundle_task.apply_async(args=[cb.id])
                    logger.info(f"  ✓ Queued as task {task.id}")
                    queued_count += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to queue {cb.name}: {e}")
            
            logger.info(f"\n=== COMPLETE ===")
            logger.info(f"Queued: {queued_count}/{len(codebundles)} tasks")
            logger.info("Tasks will be processed by Celery workers")
            return True
        
        else:
            # Synchronous processing (original behavior)
            success_count = 0
            error_count = 0
            
            for i, cb in enumerate(codebundles, 1):
                try:
                    logger.info(f"[{i}/{len(codebundles)}] Enhancing: {cb.name} ({cb.codecollection.name})")
                    
                    # Update status
                    cb.enhancement_status = "processing"
                    db.commit()
                    
                    # Perform enhancement
                    result = ai_service.enhance_codebundle(cb)
                    
                    # Update codebundle
                    cb.ai_enhanced_description = result["enhanced_description"]
                    cb.access_level = result["access_level"]
                    cb.minimum_iam_requirements = result["iam_requirements"]
                    cb.ai_enhanced_metadata = result.get("enhancement_metadata", {})
                    cb.enhancement_status = "completed"
                    
                    from datetime import datetime
                    cb.last_enhanced = datetime.utcnow()
                    
                    db.commit()
                    success_count += 1
                    
                    logger.info(f"  ✓ Enhanced: {result['access_level']} access, {len(result.get('iam_requirements', []))} IAM reqs")
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to enhance {cb.name}: {e}")
                    cb.enhancement_status = "failed"
                    db.commit()
                    error_count += 1
            
            logger.info(f"\n=== COMPLETE ===")
            logger.info(f"Success: {success_count}")
            logger.info(f"Failed: {error_count}")
            
            return error_count == 0
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='Enhance codebundle descriptions with AI')
    parser.add_argument('--limit', type=int, help='Maximum number of codebundles to enhance')
    parser.add_argument('--collection', type=str, help='Only enhance codebundles from this collection (slug)')
    parser.add_argument('--force', action='store_true', help='Re-enhance already enhanced codebundles')
    parser.add_argument('--async', dest='async_mode', action='store_true', 
                       help='Queue tasks to Celery workers instead of processing synchronously (recommended for large batches)')
    
    args = parser.parse_args()
    
    success = enhance_codebundles(
        limit=args.limit,
        collection_slug=args.collection,
        force=args.force,
        async_mode=args.async_mode
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()






