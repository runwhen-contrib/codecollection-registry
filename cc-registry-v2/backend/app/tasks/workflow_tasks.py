"""
Workflow orchestration tasks - Chain multiple tasks in sequence
"""
import logging
from typing import Dict, Any
from celery import chain

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def sync_parse_enhance_workflow_task(self, limit: int = None):
    """
    Complete workflow: Sync → Parse → Enhance New
    
    This task orchestrates the full update cycle:
    1. Sync all codecollections from their repos
    2. Parse all codebundles to find new ones
    3. AI enhance only NEW codebundles (pending/NULL status)
    
    Args:
        limit: Optional limit for AI enhancement (None = all pending)
    
    Returns:
        Dict with results from each step
    """
    try:
        logger.info(f"Starting sync-parse-enhance workflow (task {self.request.id})")
        
        # Step 1: Sync collections
        self.update_state(state='PROGRESS', meta={
            'step': 1,
            'total_steps': 3,
            'current_step': 'Syncing codecollections from repos',
            'status': 'Checking for updates in repositories...'
        })
        
        from app.tasks.registry_tasks import sync_all_collections_task
        logger.info("Step 1/3: Syncing collections...")
        
        try:
            # Use apply_async to properly dispatch to workers, then wait for result
            sync_result = sync_all_collections_task.apply_async().get(timeout=300)
            logger.info(f"Sync completed: {sync_result}")
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            sync_result = {'status': 'failed', 'error': str(e)}
        
        # Step 2: Parse codebundles
        self.update_state(state='PROGRESS', meta={
            'step': 2,
            'total_steps': 3,
            'current_step': 'Parsing codebundles',
            'status': 'Parsing Robot files from repositories...',
            'sync_result': sync_result
        })
        
        from app.tasks.registry_tasks import parse_all_codebundles_task
        logger.info("Step 2/3: Parsing codebundles...")
        
        try:
            # Use apply_async to properly dispatch to workers, then wait for result
            parse_result = parse_all_codebundles_task.apply_async().get(timeout=600)
            logger.info(f"Parse completed: {parse_result}")
        except Exception as e:
            logger.error(f"Parse failed: {e}")
            parse_result = {'status': 'failed', 'error': str(e)}
        
        # Step 3: Enhance only NEW codebundles
        self.update_state(state='PROGRESS', meta={
            'step': 3,
            'total_steps': 3,
            'current_step': 'AI enhancing new codebundles',
            'status': 'Enhancing codebundles with pending status...',
            'sync_result': sync_result,
            'parse_result': parse_result
        })
        
        from app.tasks.ai_enhancement_tasks import enhance_pending_codebundles_task
        logger.info(f"Step 3/3: Enhancing NEW codebundles (limit={limit})...")
        
        try:
            # Only enhance pending/new codebundles
            # Use apply_async to properly dispatch to workers, then wait for result
            enhance_result = enhance_pending_codebundles_task.apply_async(kwargs={'limit': limit}).get(timeout=1800)
            logger.info(f"Enhancement completed: {enhance_result}")
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            enhance_result = {'status': 'failed', 'error': str(e)}
        
        # Final result
        final_result = {
            'status': 'completed',
            'workflow_id': self.request.id,
            'steps': {
                '1_sync': sync_result,
                '2_parse': parse_result,
                '3_enhance': enhance_result
            },
            'message': 'Workflow completed: sync → parse → enhance new codebundles'
        }
        
        logger.info(f"Workflow completed: {final_result}")
        return final_result
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return {
            'status': 'failed',
            'error': str(e),
            'error_type': type(e).__name__,
            'workflow_id': self.request.id
        }


@celery_app.task(bind=True)
def quick_update_workflow_task(self, ai_limit: int = 20):
    """
    Quick update workflow with AI limit
    
    Same as sync_parse_enhance_workflow_task but with a default limit
    on AI enhancement to avoid large API costs.
    
    Args:
        ai_limit: Max number of codebundles to enhance (default: 20)
    """
    return sync_parse_enhance_workflow_task.apply_async(kwargs={'limit': ai_limit}).get(timeout=3600)
