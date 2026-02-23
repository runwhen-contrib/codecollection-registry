"""
Vector indexing tasks — native Celery tasks that generate embeddings
and store them in pgvector.

Replaces the old mcp_tasks.py which shelled out to the MCP server's
indexer.py subprocess. All indexing now runs inside the backend worker.
"""
import logging
from typing import Any, Dict, List

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.embedding_service import get_embedding_service
from app.services.vector_service import get_vector_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows, collection_slug_map: Dict[int, str]) -> List[Dict[str, Any]]:
    """Convert SQLAlchemy Codebundle rows to plain dicts for the vector service."""
    results = []
    for cb in rows:
        d = {
            "id": cb.id,
            "slug": cb.slug,
            "name": cb.name,
            "display_name": cb.display_name,
            "description": cb.description,
            "ai_enhanced_description": cb.ai_enhanced_description,
            "readme": cb.readme,
            "support_tags": cb.support_tags or [],
            "tasks": cb.tasks or [],
            "discovery_platform": cb.discovery_platform,
            "collection_slug": collection_slug_map.get(cb.codecollection_id, ""),
        }
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Index codebundles + codecollections
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.tasks.indexing_tasks.index_codebundles_task")
def index_codebundles_task(self) -> Dict[str, Any]:
    """Generate embeddings for all codebundles and codecollections, store in pgvector."""
    try:
        logger.info(f"Starting codebundle embedding indexing (task {self.request.id})")
        embed_svc = get_embedding_service()
        vec_svc = get_vector_service()

        if not embed_svc.available:
            return {"status": "skipped", "reason": "embedding service unavailable"}

        db = SessionLocal()
        try:
            from app.models.code_collection import CodeCollection
            from app.models.codebundle import Codebundle

            collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            slug_map = {c.id: c.slug for c in collections}

            codebundles = db.query(Codebundle).filter(Codebundle.is_active == True).all()
            cb_dicts = _rows_to_dicts(codebundles, slug_map)
        finally:
            db.close()

        if not cb_dicts:
            logger.info("No codebundles to index")
            return {"status": "success", "codebundles": 0, "codecollections": 0}

        # --- Codebundle embeddings ---
        documents = [vec_svc.codebundle_to_document(cb) for cb in cb_dicts]
        embeddings = embed_svc.embed_texts(documents)
        ids = [f"{cb['collection_slug']}/{cb['slug']}" for cb in cb_dicts]
        metadatas = [vec_svc.codebundle_metadata(cb) for cb in cb_dicts]

        vec_svc.upsert_vectors(
            "codebundles", ids, embeddings, documents, metadatas, clear_existing=True
        )

        # --- Codecollection embeddings ---
        db2 = SessionLocal()
        try:
            cc_rows = db2.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            cc_dicts = [
                {"slug": c.slug, "name": c.name, "description": c.description,
                 "git_url": c.git_url, "owner": c.owner}
                for c in cc_rows
            ]
        finally:
            db2.close()

        if cc_dicts:
            cc_docs = [vec_svc.collection_to_document(cc) for cc in cc_dicts]
            cc_embs = embed_svc.embed_texts(cc_docs)
            cc_ids = [cc["slug"] for cc in cc_dicts]
            cc_metas = [vec_svc.collection_metadata(cc) for cc in cc_dicts]
            vec_svc.upsert_vectors(
                "codecollections", cc_ids, cc_embs, cc_docs, cc_metas, clear_existing=True
            )

        logger.info(f"Codebundle indexing complete: {len(cb_dicts)} codebundles, {len(cc_dicts)} collections")
        return {
            "status": "success",
            "codebundles": len(cb_dicts),
            "codecollections": len(cc_dicts),
        }

    except Exception as e:
        logger.error(f"Codebundle indexing failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Index documentation from sources.yaml
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.tasks.indexing_tasks.index_documentation_task")
def index_documentation_task(self, crawl: bool = True) -> Dict[str, Any]:
    """Crawl documentation URLs from sources.yaml, embed, and store in pgvector."""
    try:
        logger.info(f"Starting documentation indexing (task {self.request.id})")
        embed_svc = get_embedding_service()
        vec_svc = get_vector_service()

        if not embed_svc.available:
            return {"status": "skipped", "reason": "embedding service unavailable"}

        from app.services.documentation_source_loader import DocumentationSourceLoader
        loader = DocumentationSourceLoader()
        docs = loader.get_all_docs(crawl=crawl)

        if not docs:
            logger.info("No documentation sources found")
            return {"status": "success", "documentation": 0}

        documents = [vec_svc.doc_to_document(d) for d in docs]
        embeddings = embed_svc.embed_texts(documents)

        seen: set = set()
        ids: List[str] = []
        for doc in docs:
            name = doc.get("name", "unknown")
            base_id = f"{doc.get('category', 'general')}/{name}".lower().replace(" ", "-")
            final_id = base_id
            counter = 1
            while final_id in seen:
                final_id = f"{base_id}_{counter}"
                counter += 1
            seen.add(final_id)
            ids.append(final_id)

        metadatas = [vec_svc.doc_metadata(d) for d in docs]
        vec_svc.upsert_vectors(
            "documentation", ids, embeddings, documents, metadatas, clear_existing=True
        )

        logger.info(f"Documentation indexing complete: {len(docs)} entries")
        return {"status": "success", "documentation": len(docs)}

    except Exception as e:
        logger.error(f"Documentation indexing failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Full reindex (all tables)
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name="app.tasks.indexing_tasks.reindex_all_task")
def reindex_all_task(self) -> Dict[str, Any]:
    """Full reindex: codebundles + codecollections + documentation."""
    logger.info(f"Starting full reindex (task {self.request.id})")

    cb_result = index_codebundles_task()
    doc_result = index_documentation_task(crawl=True)

    return {
        "status": "success",
        "codebundles": cb_result,
        "documentation": doc_result,
    }
