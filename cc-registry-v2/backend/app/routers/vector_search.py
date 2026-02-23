"""
Vector search API endpoints.

Exposes semantic (embedding-based) search over codebundles, codecollections,
libraries, and documentation. Used by the MCP server and the frontend chat.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.embedding_service import get_embedding_service
from app.services.vector_service import VectorSearchResult, get_vector_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vector", tags=["vector-search"])


def _result_to_dict(r: VectorSearchResult) -> Dict[str, Any]:
    return {
        "id": r.id,
        "document": r.document[:500],
        "metadata": r.metadata,
        "score": round(r.score, 4),
        "distance": round(r.distance, 4),
    }


# --------------------------------------------------------------------------
# Unified semantic search
# --------------------------------------------------------------------------

@router.get("/search")
async def semantic_search(
    query: str,
    tables: Optional[str] = Query(
        None,
        description="Comma-separated table keys to search (codebundles,codecollections,libraries,documentation). Default: all.",
    ),
    max_results: int = Query(10, ge=1, le=50),
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Run a semantic similarity search across one or more vector tables."""
    embed_svc = get_embedding_service()
    vec_svc = get_vector_service()

    if not embed_svc.available:
        raise HTTPException(
            status_code=503,
            detail="Embedding service is not configured. Set AZURE_OPENAI_EMBEDDING_* environment variables.",
        )

    query_embedding = embed_svc.embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding")

    table_keys = [t.strip() for t in tables.split(",")] if tables else None

    if table_keys:
        valid_keys = {"codebundles", "codecollections", "libraries", "documentation"}
        invalid = set(table_keys) - valid_keys
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid table keys: {invalid}")

    results_map = vec_svc.search_all(
        query_embedding, n_results=max_results, table_keys=table_keys, db=db
    )

    output: Dict[str, Any] = {}
    for key, results in results_map.items():
        output[key] = [_result_to_dict(r) for r in results]

    return output


# --------------------------------------------------------------------------
# Per-table endpoints
# --------------------------------------------------------------------------

@router.get("/search/codebundles")
async def search_codebundles(
    query: str,
    max_results: int = Query(10, ge=1, le=50),
    platform: Optional[str] = None,
    collection_slug: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Semantic search over codebundles."""
    embed_svc = get_embedding_service()
    vec_svc = get_vector_service()

    if not embed_svc.available:
        raise HTTPException(status_code=503, detail="Embedding service not configured")

    query_embedding = embed_svc.embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    filters: Optional[Dict[str, str]] = {}
    if platform:
        filters["platform"] = platform
    if collection_slug:
        filters["collection_slug"] = collection_slug

    results = vec_svc.search(
        "codebundles", query_embedding, n_results=max_results,
        metadata_filters=filters or None, db=db,
    )
    return {"results": [_result_to_dict(r) for r in results], "query": query}


@router.get("/search/documentation")
async def search_documentation(
    query: str,
    max_results: int = Query(10, ge=1, le=50),
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Semantic search over documentation."""
    embed_svc = get_embedding_service()
    vec_svc = get_vector_service()

    if not embed_svc.available:
        raise HTTPException(status_code=503, detail="Embedding service not configured")

    query_embedding = embed_svc.embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    filters = {"category": category} if category else None
    results = vec_svc.search(
        "documentation", query_embedding, n_results=max_results,
        metadata_filters=filters, db=db,
    )
    return {"results": [_result_to_dict(r) for r in results], "query": query}


@router.get("/search/libraries")
async def search_libraries(
    query: str,
    max_results: int = Query(10, ge=1, le=50),
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Semantic search over libraries."""
    embed_svc = get_embedding_service()
    vec_svc = get_vector_service()

    if not embed_svc.available:
        raise HTTPException(status_code=503, detail="Embedding service not configured")

    query_embedding = embed_svc.embed_text(query)
    if not query_embedding:
        raise HTTPException(status_code=500, detail="Embedding generation failed")

    filters = {"category": category} if category else None
    results = vec_svc.search(
        "libraries", query_embedding, n_results=max_results,
        metadata_filters=filters, db=db,
    )
    return {"results": [_result_to_dict(r) for r in results], "query": query}


# --------------------------------------------------------------------------
# Stats / health
# --------------------------------------------------------------------------

@router.get("/stats")
async def vector_stats(db: Session = Depends(get_db)):
    """Return row counts for each vector table."""
    vec_svc = get_vector_service()
    return vec_svc.get_stats(db=db)


@router.post("/reindex")
async def trigger_reindex():
    """Trigger a full reindex (async Celery task)."""
    from app.tasks.indexing_tasks import reindex_all_task

    task = reindex_all_task.apply_async()
    return {"task_id": task.id, "status": "queued"}


@router.post("/reindex/codebundles")
async def trigger_reindex_codebundles():
    """Trigger codebundle reindexing."""
    from app.tasks.indexing_tasks import index_codebundles_task

    task = index_codebundles_task.apply_async()
    return {"task_id": task.id, "status": "queued"}


@router.post("/reindex/documentation")
async def trigger_reindex_documentation():
    """Trigger documentation reindexing."""
    from app.tasks.indexing_tasks import index_documentation_task

    task = index_documentation_task.apply_async()
    return {"task_id": task.id, "status": "queued"}
