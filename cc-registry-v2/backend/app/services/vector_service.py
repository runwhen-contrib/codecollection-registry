"""
Vector storage and similarity search service backed by pgvector.

Provides CRUD operations and cosine-similarity search across all four
vector tables (codebundles, codecollections, libraries, documentation).
"""
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import text, delete
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.vector_models import (
    VectorCodebundle,
    VectorCodecollection,
    VectorDocumentation,
    VectorLibrary,
)

logger = logging.getLogger(__name__)

TABLE_MAP = {
    "codebundles": VectorCodebundle,
    "codecollections": VectorCodecollection,
    "libraries": VectorLibrary,
    "documentation": VectorDocumentation,
}


@dataclass
class VectorSearchResult:
    id: str
    document: str
    metadata: Dict[str, Any]
    distance: float

    @property
    def score(self) -> float:
        return 1.0 / (1.0 + self.distance)


class VectorService:
    """Read / write pgvector tables and run similarity search."""

    # ------------------------------------------------------------------
    # Upsert helpers
    # ------------------------------------------------------------------

    def upsert_vectors(
        self,
        table_key: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        clear_existing: bool = True,
        db: Session = None,
    ) -> int:
        """Upsert embedding rows into a vector table.

        If *clear_existing* is True the table is truncated first (full rebuild).
        Returns the number of rows written.
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            model = TABLE_MAP[table_key]

            if clear_existing:
                db.execute(delete(model))
                db.flush()

            table_name = model.__tablename__
            stmt = text(
                f"INSERT INTO {table_name} (id, embedding, document, metadata, updated_at) "
                f"VALUES (:id, CAST(:emb AS vector), :doc, CAST(:meta AS jsonb), NOW()) "
                f"ON CONFLICT (id) DO UPDATE SET "
                f"  embedding = EXCLUDED.embedding, "
                f"  document = EXCLUDED.document, "
                f"  metadata = EXCLUDED.metadata, "
                f"  updated_at = NOW()"
            )
            for i in range(len(ids)):
                emb = embeddings[i]
                if not emb:
                    continue
                emb_literal = "[" + ",".join(str(v) for v in emb) + "]"
                meta_json = json.dumps(metadatas[i]) if metadatas[i] else "{}"
                db.execute(
                    stmt,
                    {"id": ids[i], "emb": emb_literal, "doc": documents[i], "meta": meta_json},
                )

            db.commit()
            logger.info(f"Upserted {len(ids)} rows into {table_name}")
            return len(ids)
        except Exception:
            if own_session:
                db.rollback()
            raise
        finally:
            if own_session:
                db.close()

    # ------------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------------

    def search(
        self,
        table_key: str,
        query_embedding: List[float],
        n_results: int = 10,
        metadata_filters: Optional[Dict[str, str]] = None,
        db: Session = None,
    ) -> List[VectorSearchResult]:
        """Cosine-similarity search against a vector table.

        *metadata_filters* is a dict of key-value pairs that are ANDed
        together, e.g. ``{"platform": "kubernetes"}``.
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            model = TABLE_MAP[table_key]
            table_name = model.__tablename__
            emb_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

            where_clauses = ["embedding IS NOT NULL"]
            params: Dict[str, Any] = {
                "emb": emb_literal,
                "limit": n_results,
            }

            if metadata_filters:
                for idx, (key, value) in enumerate(metadata_filters.items()):
                    param_name = f"mf_{idx}"
                    where_clauses.append(f"metadata->>'{key}' = :{param_name}")
                    params[param_name] = value

            where_sql = " AND ".join(where_clauses)

            sql = text(
                f"SELECT id, document, metadata, "
                f"  (embedding <=> CAST(:emb AS vector)) AS distance "
                f"FROM {table_name} "
                f"WHERE {where_sql} "
                f"ORDER BY distance "
                f"LIMIT :limit"
            )

            rows = db.execute(sql, params).fetchall()
            results = []
            for row in rows:
                meta = row[2] if isinstance(row[2], dict) else json.loads(row[2])
                results.append(
                    VectorSearchResult(
                        id=row[0],
                        document=row[1] or "",
                        metadata=meta,
                        distance=float(row[3]),
                    )
                )
            return results
        finally:
            if own_session:
                db.close()

    # ------------------------------------------------------------------
    # Multi-table search (unified semantic search)
    # ------------------------------------------------------------------

    def search_all(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        table_keys: Optional[List[str]] = None,
        db: Session = None,
    ) -> Dict[str, List[VectorSearchResult]]:
        """Run similarity search across multiple vector tables."""
        keys = table_keys or list(TABLE_MAP.keys())
        results: Dict[str, List[VectorSearchResult]] = {}
        for key in keys:
            results[key] = self.search(key, query_embedding, n_results=n_results, db=db)
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self, db: Session = None) -> Dict[str, int]:
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            stats = {}
            for key, model in TABLE_MAP.items():
                count = db.query(model).count()
                stats[key] = count
            return stats
        finally:
            if own_session:
                db.close()

    # ------------------------------------------------------------------
    # Document builders (shared logic, mirrors mcp-server helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def codebundle_to_document(cb: Dict[str, Any]) -> str:
        parts = []
        for field in ("display_name", "name"):
            if cb.get(field):
                parts.append(cb[field])
        if cb.get("description"):
            parts.append(cb["description"])
        if cb.get("ai_enhanced_description"):
            parts.append(cb["ai_enhanced_description"])
        if cb.get("discovery_platform"):
            parts.append(f"Platform: {cb['discovery_platform']}")
        tags = cb.get("support_tags") or []
        if tags:
            parts.append(f"Tags: {', '.join(tags[:15])}")
        tasks = cb.get("tasks") or []
        if tasks:
            parts.append(f"Tasks: {', '.join(tasks[:20])}")
        readme = cb.get("readme") or ""
        if readme:
            parts.append(readme[:2000])
        return "\n".join(parts)

    @staticmethod
    def codebundle_metadata(cb: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "slug": cb.get("slug", ""),
            "collection_slug": cb.get("collection_slug", ""),
            "name": cb.get("name", ""),
            "display_name": cb.get("display_name", ""),
            "description": (cb.get("description") or "")[:500],
            "platform": cb.get("discovery_platform") or cb.get("platform", ""),
            "tags": ",".join((cb.get("support_tags") or [])[:10]),
        }

    @staticmethod
    def collection_to_document(cc: Dict[str, Any]) -> str:
        return f"{cc.get('name', '')} — {cc.get('description', '')}"

    @staticmethod
    def collection_metadata(cc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "slug": cc.get("slug", ""),
            "name": cc.get("name", ""),
            "description": (cc.get("description") or "")[:500],
            "git_url": cc.get("git_url", ""),
            "owner": cc.get("owner", ""),
        }

    @staticmethod
    def doc_to_document(doc: Dict[str, Any]) -> str:
        parts = [f"# {doc.get('name', '')}"]
        if doc.get("description"):
            parts.append(doc["description"])
        if doc.get("crawled_content"):
            parts.append(doc["crawled_content"][:12000])
        else:
            for field in ("topics", "key_points", "usage_examples"):
                items = doc.get(field) or []
                if items:
                    parts.append(f"{field.replace('_', ' ').title()}: {', '.join(items)}")
        return "\n\n".join(parts)

    @staticmethod
    def doc_metadata(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": doc.get("name", doc.get("question", "")),
            "description": (doc.get("description", doc.get("answer", "")) or "")[:500],
            "url": doc.get("url", ""),
            "category": doc.get("category", "general"),
            "topics": ",".join(doc.get("topics") or []),
            "has_crawled_content": "true" if doc.get("crawled_content") else "false",
        }


_instance: Optional[VectorService] = None


def get_vector_service() -> VectorService:
    global _instance
    if _instance is None:
        _instance = VectorService()
    return _instance
