"""
MCP Server Tasks - Manage MCP server indexing and maintenance
"""
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any

from app.tasks.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.mcp_tasks.index_documentation_task')
def index_documentation_task(self) -> Dict[str, Any]:
    """
    Re-index documentation sources and update embeddings in the MCP server.
    
    This task:
    1. Calls the MCP server's indexer to process docs.yaml/sources.yaml
    2. Crawls documentation pages for content
    3. Generates embeddings
    4. Updates the vector database
    
    Returns:
        Dict with indexing results
    """
    try:
        logger.info(f"Starting documentation indexing (task {self.request.id})")
        
        # Find the mcp-server directory
        # Assuming structure: /workspaces/codecollection-registry/mcp-server
        workspace_root = Path(__file__).parent.parent.parent.parent.parent
        mcp_server_path = workspace_root / "mcp-server"
        indexer_script = mcp_server_path / "indexer.py"
        
        if not indexer_script.exists():
            error_msg = f"MCP indexer script not found at {indexer_script}"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': self.request.id
            }
        
        # Run the indexer with --docs-only flag
        # This will only re-index documentation, not codebundles
        logger.info(f"Running indexer: python {indexer_script} --docs-only")
        
        result = subprocess.run(
            ['python', str(indexer_script), '--docs-only'],
            cwd=str(mcp_server_path),
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Documentation indexing completed successfully")
            logger.info(f"Indexer output:\n{result.stdout}")
            
            return {
                'status': 'success',
                'message': 'Documentation indexed successfully',
                'task_id': self.request.id,
                'stdout': result.stdout[-1000:],  # Last 1000 chars
                'stderr': result.stderr[-500:] if result.stderr else None
            }
        else:
            error_msg = f"Indexer failed with exit code {result.returncode}"
            logger.error(error_msg)
            logger.error(f"Stderr: {result.stderr}")
            
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': self.request.id,
                'stdout': result.stdout[-1000:],
                'stderr': result.stderr[-500:]
            }
            
    except subprocess.TimeoutExpired:
        error_msg = "Documentation indexing timed out after 10 minutes"
        logger.error(error_msg)
        return {
            'status': 'failed',
            'error': error_msg,
            'task_id': self.request.id
        }
    except Exception as e:
        error_msg = f"Documentation indexing failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }


@celery_app.task(bind=True, name='app.tasks.mcp_tasks.reindex_all_task')
def reindex_all_task(self) -> Dict[str, Any]:
    """
    Full re-index of all MCP server data (codebundles + documentation).
    
    This is a more comprehensive task that rebuilds the entire vector database.
    Use sparingly as it can take several minutes.
    
    Returns:
        Dict with indexing results
    """
    try:
        logger.info(f"Starting full MCP re-index (task {self.request.id})")
        
        # Find the mcp-server directory
        workspace_root = Path(__file__).parent.parent.parent.parent.parent
        mcp_server_path = workspace_root / "mcp-server"
        indexer_script = mcp_server_path / "indexer.py"
        
        if not indexer_script.exists():
            error_msg = f"MCP indexer script not found at {indexer_script}"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': self.request.id
            }
        
        # Run the full indexer
        logger.info(f"Running full indexer: python {indexer_script}")
        
        result = subprocess.run(
            ['python', str(indexer_script)],
            cwd=str(mcp_server_path),
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout for full index
        )
        
        if result.returncode == 0:
            logger.info("Full re-index completed successfully")
            logger.info(f"Indexer output:\n{result.stdout}")
            
            return {
                'status': 'success',
                'message': 'Full MCP re-index completed successfully',
                'task_id': self.request.id,
                'stdout': result.stdout[-1000:],
                'stderr': result.stderr[-500:] if result.stderr else None
            }
        else:
            error_msg = f"Full indexer failed with exit code {result.returncode}"
            logger.error(error_msg)
            logger.error(f"Stderr: {result.stderr}")
            
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': self.request.id,
                'stdout': result.stdout[-1000:],
                'stderr': result.stderr[-500:]
            }
            
    except subprocess.TimeoutExpired:
        error_msg = "Full re-index timed out after 30 minutes"
        logger.error(error_msg)
        return {
            'status': 'failed',
            'error': error_msg,
            'task_id': self.request.id
        }
    except Exception as e:
        error_msg = f"Full re-index failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }
