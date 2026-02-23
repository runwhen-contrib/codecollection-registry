"""
DEPRECATED — MCP indexing tasks have moved to indexing_tasks.py.

The old tasks shelled out to mcp-server/indexer.py as a subprocess.
The new tasks in indexing_tasks.py run natively inside the backend worker,
generating embeddings and storing them directly in pgvector.

These stubs remain only so that any in-flight Celery messages referencing
the old task names don't cause import errors. They redirect to the new tasks.
"""
import logging
from typing import Dict, Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.mcp_tasks.index_documentation_task')
def index_documentation_task(self) -> Dict[str, Any]:
    """Deprecated — redirects to indexing_tasks.index_documentation_task."""
    logger.warning("mcp_tasks.index_documentation_task is deprecated; use indexing_tasks.index_documentation_task")
    from app.tasks.indexing_tasks import index_documentation_task as new_task
    return new_task()


@celery_app.task(bind=True, name='app.tasks.mcp_tasks.reindex_all_task')
def reindex_all_task(self) -> Dict[str, Any]:
    """Deprecated — redirects to indexing_tasks.reindex_all_task."""
    logger.warning("mcp_tasks.reindex_all_task is deprecated; use indexing_tasks.reindex_all_task")
    from app.tasks.indexing_tasks import reindex_all_task as new_task
    return new_task()
