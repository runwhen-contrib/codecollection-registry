"""
DEPRECATED — Local vector store (in-memory / JSON file).

Vector storage and search have moved to the backend, which uses pgvector
in PostgreSQL. See:
  - cc-registry-v2/backend/app/services/vector_service.py
  - cc-registry-v2/backend/app/tasks/indexing_tasks.py

This file is kept for reference only.
"""
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# =========================================================================
# Shared types
# =========================================================================

@dataclass
class SearchResult:
    """A search result with metadata and score"""
    id: str
    content: str
    metadata: Dict[str, Any]
    distance: float  # Lower is better (closer match)

    @property
    def score(self) -> float:
        """Convert distance to similarity score (higher is better)"""
        return 1.0 / (1.0 + self.distance)


# Table / collection names
TABLE_CODEBUNDLES = "vector_codebundles"
TABLE_CODECOLLECTIONS = "vector_codecollections"
TABLE_LIBRARIES = "vector_libraries"
TABLE_DOCUMENTATION = "vector_documentation"

ALL_TABLES = [TABLE_CODEBUNDLES, TABLE_CODECOLLECTIONS, TABLE_LIBRARIES, TABLE_DOCUMENTATION]


# =========================================================================
# Abstract base
# =========================================================================

class BaseVectorStore(ABC):
    """Interface that both backends implement."""

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def add_codebundles(self, codebundles: List[Dict[str, Any]], embeddings: List[List[float]], clear_existing: bool = True): ...

    @abstractmethod
    def search_codebundles(self, query_embedding: List[float], n_results: int = 10, platform_filter: str = None, collection_filter: str = None) -> List[SearchResult]: ...

    @abstractmethod
    def add_codecollections(self, collections: List[Dict[str, Any]], embeddings: List[List[float]], clear_existing: bool = True): ...

    @abstractmethod
    def search_codecollections(self, query_embedding: List[float], n_results: int = 10) -> List[SearchResult]: ...

    @abstractmethod
    def add_libraries(self, libraries: List[Dict[str, Any]], embeddings: List[List[float]], clear_existing: bool = True): ...

    @abstractmethod
    def search_libraries(self, query_embedding: List[float], n_results: int = 10, category_filter: str = None) -> List[SearchResult]: ...

    @abstractmethod
    def add_documentation(self, docs: List[Dict[str, Any]], embeddings: List[List[float]], clear_existing: bool = True): ...

    @abstractmethod
    def search_documentation(self, query_embedding: List[float], n_results: int = 10, category_filter: str = None) -> List[SearchResult]: ...

    @abstractmethod
    def get_stats(self) -> Dict[str, int]: ...

    # Shared helpers

    def _codebundle_to_document(self, cb: Dict[str, Any]) -> str:
        """Convert a codebundle to searchable document text."""
        parts = []
        if cb.get("display_name"):
            parts.append(cb["display_name"])
        if cb.get("name"):
            parts.append(cb["name"])
        if cb.get("description"):
            parts.append(cb["description"])
        if cb.get("platform"):
            parts.append(f"Platform: {cb['platform']}")
        if cb.get("support_tags"):
            parts.append(f"Tags: {', '.join(cb['support_tags'])}")
        if cb.get("tasks"):
            parts.append(f"Tasks: {', '.join(cb['tasks'][:10])}")
        if cb.get("capabilities"):
            parts.append(f"Capabilities: {', '.join(cb['capabilities'][:10])}")
        if cb.get("readme"):
            parts.append(cb["readme"][:1000])
        return "\n".join(parts)

    def _build_codebundle_metadata(self, cb: Dict[str, Any]) -> Dict[str, Any]:
        tasks = cb.get("tasks", [])
        capabilities = cb.get("capabilities", [])
        return {
            "slug": cb.get("slug", ""),
            "collection_slug": cb.get("collection_slug", ""),
            "name": cb.get("name", ""),
            "display_name": cb.get("display_name", ""),
            "description": (cb.get("description", "") or "")[:500],
            "platform": cb.get("platform", ""),
            "author": cb.get("author", ""),
            "tags": ",".join(cb.get("support_tags", [])[:10]),
            "tasks": json.dumps(tasks[:15]),
            "capabilities": json.dumps(capabilities[:10]),
        }

    def _build_library_document(self, lib: Dict[str, Any]) -> str:
        doc_parts = [lib.get("name", ""), lib.get("description", "")]
        if lib.get("functions"):
            func_names = [f.get("name", "") for f in lib["functions"][:20]]
            doc_parts.append("Functions: " + ", ".join(func_names))
        if lib.get("keywords"):
            doc_parts.append("Keywords: " + ", ".join(lib["keywords"][:20]))
        return " ".join(doc_parts)

    def _build_library_metadata(self, lib: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": lib.get("name", ""),
            "description": (lib.get("description", "") or "")[:500],
            "category": lib.get("category", ""),
            "import_path": lib.get("import_path", lib.get("import_name", "")),
            "collection_slug": lib.get("collection_slug", ""),
            "git_url": lib.get("git_url", ""),
        }

    def _build_doc_document(self, doc: Dict[str, Any]) -> str:
        doc_parts = [f"# {doc.get('name', '')}", doc.get("description", "")]
        if doc.get("crawled_content"):
            doc_parts.append(doc["crawled_content"][:12000])
        else:
            if doc.get("topics"):
                doc_parts.append(f"Topics: {', '.join(doc['topics'])}")
            if doc.get("key_points"):
                doc_parts.append(f"Key points: {', '.join(doc['key_points'])}")
            if doc.get("usage_examples"):
                doc_parts.append(f"Examples: {', '.join(doc['usage_examples'])}")
            if doc.get("answer"):
                doc_parts.append(f"Answer: {doc['answer'][:500]}")
        return "\n\n".join(doc_parts)

    def _build_doc_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": doc.get("name", doc.get("question", "")),
            "description": (doc.get("description", doc.get("answer", "")) or "")[:500],
            "url": doc.get("url", ""),
            "category": doc.get("category", "general"),
            "topics": ",".join(doc.get("topics", [])),
            "priority": doc.get("priority", "medium"),
            "has_crawled_content": "true" if doc.get("crawled_content") else "false",
        }

    def _dedup_id(self, base_id: str, seen: set) -> str:
        """Generate a unique ID, appending _N if needed."""
        doc_id = base_id
        counter = 1
        while doc_id in seen:
            doc_id = f"{base_id}_{counter}"
            counter += 1
        seen.add(doc_id)
        return doc_id


# =========================================================================
# Backend 1: Local (in-memory numpy + JSON file persistence)
# =========================================================================

class LocalVectorStore(BaseVectorStore):
    """
    Zero-infrastructure vector store. Stores embeddings in a local JSON file,
    loads them into memory, and searches with brute-force cosine similarity.

    Fast enough for thousands of vectors. No database required.
    """

    def __init__(self, persist_path: str = None):
        self._persist_path = persist_path or str(
            Path(__file__).parent.parent / "data" / "vector_index.json"
        )
        # In-memory store: {table_name: {id: {embedding, document, metadata}}}
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {t: {} for t in ALL_TABLES}
        self._load()
        logger.info(f"LocalVectorStore initialized (file: {self._persist_path})")

    @property
    def available(self) -> bool:
        return True

    def _load(self):
        """Load persisted data from JSON file."""
        try:
            if Path(self._persist_path).exists():
                with open(self._persist_path, "r") as f:
                    raw = json.load(f)
                for table in ALL_TABLES:
                    if table in raw:
                        self._data[table] = raw[table]
                total = sum(len(v) for v in self._data.values())
                logger.info(f"Loaded {total} vectors from {self._persist_path}")
        except Exception as e:
            logger.warning(f"Could not load local vector index: {e}")

    def _save(self):
        """Persist data to JSON file."""
        try:
            Path(self._persist_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w") as f:
                json.dump(self._data, f)
        except Exception as e:
            logger.error(f"Failed to save local vector index: {e}")

    def _cosine_search(
        self,
        table: str,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, str]] = None,
    ) -> List[SearchResult]:
        """Brute-force cosine distance search."""
        entries = self._data.get(table, {})
        if not entries:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec = query_vec / query_norm

        scored = []
        for entry_id, entry in entries.items():
            # Apply metadata filters
            if where:
                meta = entry.get("metadata", {})
                if not all(meta.get(k) == v for k, v in where.items()):
                    continue

            emb = np.array(entry["embedding"], dtype=np.float32)
            emb_norm = np.linalg.norm(emb)
            if emb_norm == 0:
                continue
            # Cosine distance = 1 - cosine_similarity
            cosine_sim = float(np.dot(query_vec, emb / emb_norm))
            distance = 1.0 - cosine_sim
            scored.append((entry_id, entry, distance))

        # Sort by distance (ascending = most similar first)
        scored.sort(key=lambda x: x[2])

        results = []
        for entry_id, entry, distance in scored[:n_results]:
            results.append(SearchResult(
                id=entry_id,
                content=entry.get("document", ""),
                metadata=entry.get("metadata", {}),
                distance=distance,
            ))
        return results

    def _add_entries(
        self,
        table: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        clear_existing: bool = True,
    ):
        if clear_existing:
            self._data[table] = {}
        for i in range(len(ids)):
            self._data[table][ids[i]] = {
                "embedding": embeddings[i],
                "document": documents[i],
                "metadata": metadatas[i],
            }
        self._save()

    # -- Codebundles --

    def add_codebundles(self, codebundles, embeddings, clear_existing=True):
        if not codebundles:
            return
        ids, docs, metas = [], [], []
        for cb in codebundles:
            ids.append(f"{cb.get('collection_slug', 'unknown')}/{cb.get('slug', 'unknown')}")
            docs.append(self._codebundle_to_document(cb))
            metas.append(self._build_codebundle_metadata(cb))
        self._add_entries(TABLE_CODEBUNDLES, ids, embeddings, docs, metas, clear_existing)
        logger.info(f"Added {len(codebundles)} codebundles to local vector store")

    def search_codebundles(self, query_embedding, n_results=10, platform_filter=None, collection_filter=None):
        where = {}
        if platform_filter:
            where["platform"] = platform_filter
        if collection_filter:
            where["collection_slug"] = collection_filter
        return self._cosine_search(TABLE_CODEBUNDLES, query_embedding, n_results, where or None)

    # -- Codecollections --

    def add_codecollections(self, collections, embeddings, clear_existing=True):
        if not collections:
            return
        ids, docs, metas = [], [], []
        for cc in collections:
            ids.append(cc.get("slug", "unknown"))
            docs.append(f"{cc.get('name', '')} - {cc.get('description', '')}")
            metas.append({
                "slug": cc.get("slug", ""), "name": cc.get("name", ""),
                "description": (cc.get("description", "") or "")[:500],
                "git_url": cc.get("git_url", ""), "owner": cc.get("owner", ""),
            })
        self._add_entries(TABLE_CODECOLLECTIONS, ids, embeddings, docs, metas, clear_existing)
        logger.info(f"Added {len(collections)} codecollections to local vector store")

    def search_codecollections(self, query_embedding, n_results=10):
        return self._cosine_search(TABLE_CODECOLLECTIONS, query_embedding, n_results)

    # -- Libraries --

    def add_libraries(self, libraries, embeddings, clear_existing=True):
        if not libraries:
            return
        ids, docs, metas = [], [], []
        seen: set = set()
        for lib in libraries:
            base_id = f"{lib.get('collection_slug', 'unknown')}/{lib.get('module_path', lib.get('import_path', lib.get('name', 'unknown')))}"
            ids.append(self._dedup_id(base_id, seen))
            docs.append(self._build_library_document(lib))
            metas.append(self._build_library_metadata(lib))
        self._add_entries(TABLE_LIBRARIES, ids, embeddings, docs, metas, clear_existing)
        logger.info(f"Added {len(libraries)} libraries to local vector store")

    def search_libraries(self, query_embedding, n_results=10, category_filter=None):
        where = {}
        if category_filter and category_filter != "all":
            where["category"] = category_filter
        return self._cosine_search(TABLE_LIBRARIES, query_embedding, n_results, where or None)

    # -- Documentation --

    def add_documentation(self, docs_list, embeddings, clear_existing=True):
        if not docs_list:
            return
        ids, docs, metas = [], [], []
        seen: set = set()
        for i, doc in enumerate(docs_list):
            name = doc.get("name", doc.get("question", f"doc-{i}"))
            base_id = f"{doc.get('category', 'general')}/{name}".lower().replace(" ", "-")
            ids.append(self._dedup_id(base_id, seen))
            docs.append(self._build_doc_document(doc))
            metas.append(self._build_doc_metadata(doc))
        self._add_entries(TABLE_DOCUMENTATION, ids, embeddings, docs, metas, clear_existing)
        logger.info(f"Added {len(docs_list)} documentation resources to local vector store")

    def search_documentation(self, query_embedding, n_results=10, category_filter=None):
        where = {}
        if category_filter and category_filter != "all":
            where["category"] = category_filter
        return self._cosine_search(TABLE_DOCUMENTATION, query_embedding, n_results, where or None)

    # -- Stats --

    def get_stats(self):
        return {
            "codebundles": len(self._data.get(TABLE_CODEBUNDLES, {})),
            "codecollections": len(self._data.get(TABLE_CODECOLLECTIONS, {})),
            "libraries": len(self._data.get(TABLE_LIBRARIES, {})),
            "documentation": len(self._data.get(TABLE_DOCUMENTATION, {})),
        }


def VectorStore() -> LocalVectorStore:
    """Create the vector store."""
    return LocalVectorStore()
