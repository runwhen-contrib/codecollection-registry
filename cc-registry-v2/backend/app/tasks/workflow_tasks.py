"""
Workflow orchestration tasks — chain multiple tasks in sequence.

Pipeline: Sync → Parse → AI Enhance → Generate Embeddings
"""
import logging
from typing import Dict, Any

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def sync_parse_enhance_workflow_task(self, limit: int = None):
    """
    Complete workflow: Sync → Parse → Enhance → Embed

    1. Sync all codecollections from their git repos
    2. Parse codebundles (extract tasks, SLIs, metadata)
    3. AI enhance ONLY NEW codebundles (pending/NULL status)
    4. Generate embeddings and store in pgvector

    Subtasks are called directly in this worker process to avoid the
    "never call result.get() inside a task" anti-pattern.
    """
    try:
        logger.info(f"Starting sync-parse-enhance-embed workflow (task {self.request.id})")

        from app.tasks.registry_tasks import sync_all_collections_task, parse_all_codebundles_task
        from app.tasks.ai_enhancement_tasks import enhance_pending_codebundles_task
        from app.tasks.indexing_tasks import index_codebundles_task

        # Step 1: Sync collections
        self.update_state(state='PROGRESS', meta={
            'step': 1, 'total_steps': 4,
            'current_step': 'Syncing codecollections from repos',
        })
        logger.info("Step 1/4: Syncing collections...")
        try:
            sync_result = sync_all_collections_task()
            logger.info(f"Sync completed: {sync_result}")
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            sync_result = {'status': 'failed', 'error': str(e)}

        # Step 2: Parse codebundles
        self.update_state(state='PROGRESS', meta={
            'step': 2, 'total_steps': 4,
            'current_step': 'Parsing codebundles',
        })
        logger.info("Step 2/4: Parsing codebundles...")
        try:
            parse_result = parse_all_codebundles_task()
            logger.info(f"Parse completed: {parse_result}")
        except Exception as e:
            logger.error(f"Parse failed: {e}")
            parse_result = {'status': 'failed', 'error': str(e)}

        # Step 3: AI enhance NEW codebundles
        self.update_state(state='PROGRESS', meta={
            'step': 3, 'total_steps': 4,
            'current_step': 'AI enhancing new codebundles',
        })
        logger.info(f"Step 3/4: Enhancing NEW codebundles (limit={limit})...")
        try:
            enhance_result = enhance_pending_codebundles_task(limit=limit)
            logger.info(f"Enhancement completed: {enhance_result}")
        except Exception as e:
            logger.error(f"Enhancement failed: {e}")
            enhance_result = {'status': 'failed', 'error': str(e)}

        # Step 4: Generate embeddings and store in pgvector
        self.update_state(state='PROGRESS', meta={
            'step': 4, 'total_steps': 4,
            'current_step': 'Generating embeddings for vector search',
        })
        logger.info("Step 4/4: Generating embeddings...")
        try:
            embed_result = index_codebundles_task()
            logger.info(f"Embedding indexing completed: {embed_result}")
        except Exception as e:
            logger.error(f"Embedding indexing failed: {e}")
            embed_result = {'status': 'failed', 'error': str(e)}

        final_result = {
            'status': 'completed',
            'workflow_id': self.request.id,
            'steps': {
                '1_sync': sync_result,
                '2_parse': parse_result,
                '3_enhance': enhance_result,
                '4_embed': embed_result,
            },
            'message': 'Workflow completed: sync → parse → enhance → embed'
        }

        logger.info(f"Workflow completed: {final_result}")
        return final_result

    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'error_type': type(e).__name__,
            'workflow_id': self.request.id,
        }


@celery_app.task(bind=True)
def quick_update_workflow_task(self, ai_limit: int = 20):
    """Quick update workflow with a limit on AI enhancement to control costs."""
    return sync_parse_enhance_workflow_task(limit=ai_limit)
