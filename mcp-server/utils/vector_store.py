"""
Vector store for semantic search using ChromaDB.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


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


class VectorStore:
    """
    ChromaDB-based vector store for semantic search.
    
    Supports:
    - Codebundle embeddings
    - Codecollection embeddings  
    - Library embeddings
    """
    
    def __init__(self, persist_dir: str = None):
        """
        Initialize the vector store.
        
        Args:
            persist_dir: Directory to persist the database. 
                        Defaults to mcp-server/data/vectordb
        """
        if persist_dir is None:
            persist_dir = str(Path(__file__).parent.parent / "data" / "vectordb")
        
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Collection names
        self.CODEBUNDLES = "codebundles"
        self.CODECOLLECTIONS = "codecollections"
        self.LIBRARIES = "libraries"
        self.DOCUMENTATION = "documentation"
        
        logger.info(f"VectorStore initialized at {persist_dir}")
    
    def _get_or_create_collection(self, name: str):
        """Get or create a collection"""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
    
    def clear_collection(self, name: str):
        """Clear and recreate a collection"""
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        return self._get_or_create_collection(name)
    
    # =========================================================================
    # Codebundle operations
    # =========================================================================
    
    def add_codebundles(
        self,
        codebundles: List[Dict[str, Any]],
        embeddings: List[List[float]],
        clear_existing: bool = True
    ):
        """
        Add codebundles to the vector store.
        
        Args:
            codebundles: List of codebundle dicts with metadata
            embeddings: Corresponding embedding vectors
            clear_existing: Whether to clear existing data first
        """
        if clear_existing:
            collection = self.clear_collection(self.CODEBUNDLES)
        else:
            collection = self._get_or_create_collection(self.CODEBUNDLES)
        
        if not codebundles:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for cb in codebundles:
            # Create unique ID
            cb_id = f"{cb.get('collection_slug', 'unknown')}/{cb.get('slug', 'unknown')}"
            ids.append(cb_id)
            
            # Create searchable document text
            doc = self._codebundle_to_document(cb)
            documents.append(doc)
            
            # Store metadata (ChromaDB requires simple types)
            # Include tasks and capabilities as JSON strings
            import json
            tasks = cb.get("tasks", [])
            capabilities = cb.get("capabilities", [])
            
            metadatas.append({
                "slug": cb.get("slug", ""),
                "collection_slug": cb.get("collection_slug", ""),
                "name": cb.get("name", ""),
                "display_name": cb.get("display_name", ""),
                "description": cb.get("description", "")[:500],  # Truncate for storage
                "platform": cb.get("platform", ""),
                "author": cb.get("author", ""),
                "tags": ",".join(cb.get("support_tags", [])[:10]),  # Store as comma-separated
                "tasks": json.dumps(tasks[:15]),  # Store as JSON string (top 15 tasks)
                "capabilities": json.dumps(capabilities[:10]),  # Store as JSON string (top 10)
            })
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(codebundles)} codebundles to vector store")
    
    def search_codebundles(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        platform_filter: str = None,
        collection_filter: str = None
    ) -> List[SearchResult]:
        """
        Search codebundles by semantic similarity.
        
        Args:
            query_embedding: Embedding vector for the query
            n_results: Maximum number of results
            platform_filter: Optional platform to filter by
            collection_filter: Optional collection slug to filter by
            
        Returns:
            List of SearchResult objects
        """
        collection = self._get_or_create_collection(self.CODEBUNDLES)
        
        # Build where filter
        where_filter = None
        if platform_filter or collection_filter:
            conditions = []
            if platform_filter:
                conditions.append({"platform": platform_filter})
            if collection_filter:
                conditions.append({"collection_slug": collection_filter})
            
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        return self._format_results(results)
    
    # =========================================================================
    # Codecollection operations
    # =========================================================================
    
    def add_codecollections(
        self,
        collections: List[Dict[str, Any]],
        embeddings: List[List[float]],
        clear_existing: bool = True
    ):
        """Add codecollections to the vector store"""
        if clear_existing:
            collection = self.clear_collection(self.CODECOLLECTIONS)
        else:
            collection = self._get_or_create_collection(self.CODECOLLECTIONS)
        
        if not collections:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        for cc in collections:
            ids.append(cc.get("slug", "unknown"))
            
            # Create document text
            doc = f"{cc.get('name', '')} - {cc.get('description', '')}"
            documents.append(doc)
            
            metadatas.append({
                "slug": cc.get("slug", ""),
                "name": cc.get("name", ""),
                "description": cc.get("description", "")[:500],
                "git_url": cc.get("git_url", ""),
                "owner": cc.get("owner", ""),
            })
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(collections)} codecollections to vector store")
    
    def search_codecollections(
        self,
        query_embedding: List[float],
        n_results: int = 10
    ) -> List[SearchResult]:
        """Search codecollections by semantic similarity"""
        collection = self._get_or_create_collection(self.CODECOLLECTIONS)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        return self._format_results(results)
    
    # =========================================================================
    # Library operations
    # =========================================================================
    
    def add_libraries(
        self,
        libraries: List[Dict[str, Any]],
        embeddings: List[List[float]],
        clear_existing: bool = True
    ):
        """Add libraries to the vector store"""
        if clear_existing:
            collection = self.clear_collection(self.LIBRARIES)
        else:
            collection = self._get_or_create_collection(self.LIBRARIES)
        
        if not libraries:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        seen_ids = set()
        for lib in libraries:
            # Create unique ID from collection + module path (use full module_path for uniqueness)
            base_id = f"{lib.get('collection_slug', 'unknown')}/{lib.get('module_path', lib.get('import_path', lib.get('name', 'unknown')))}"
            lib_id = base_id
            # Handle duplicates by appending a counter
            counter = 1
            while lib_id in seen_ids:
                lib_id = f"{base_id}_{counter}"
                counter += 1
            seen_ids.add(lib_id)
            ids.append(lib_id)
            
            # Create document text
            doc_parts = [
                lib.get("name", ""),
                lib.get("description", ""),
            ]
            # Add function names for searchability
            if lib.get("functions"):
                func_names = [f.get("name", "") for f in lib["functions"][:20]]
                doc_parts.append("Functions: " + ", ".join(func_names))
            # Add keywords
            if lib.get("keywords"):
                doc_parts.append("Keywords: " + ", ".join(lib["keywords"][:20]))
            documents.append(" ".join(doc_parts))
            
            metadatas.append({
                "name": lib.get("name", ""),
                "description": lib.get("description", "")[:500],
                "category": lib.get("category", ""),
                "import_path": lib.get("import_path", lib.get("import_name", "")),
                "collection_slug": lib.get("collection_slug", ""),
                "git_url": lib.get("git_url", ""),
            })
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(libraries)} libraries to vector store")
    
    def search_libraries(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        category_filter: str = None
    ) -> List[SearchResult]:
        """Search libraries by semantic similarity"""
        collection = self._get_or_create_collection(self.LIBRARIES)
        
        where_filter = None
        if category_filter and category_filter != "all":
            where_filter = {"category": category_filter}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        return self._format_results(results)
    
    # =========================================================================
    # Helper methods
    # =========================================================================
    
    def _codebundle_to_document(self, cb: Dict[str, Any]) -> str:
        """Convert a codebundle to searchable document text"""
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
            # Include first 1000 chars of readme
            parts.append(cb["readme"][:1000])
        
        return "\n".join(parts)
    
    def _format_results(self, results: Dict) -> List[SearchResult]:
        """Format ChromaDB results into SearchResult objects"""
        formatted = []
        
        if not results or not results.get("ids") or not results["ids"][0]:
            return formatted
        
        ids = results["ids"][0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        for i, id_ in enumerate(ids):
            formatted.append(SearchResult(
                id=id_,
                content=documents[i] if i < len(documents) else "",
                metadata=metadatas[i] if i < len(metadatas) else {},
                distance=distances[i] if i < len(distances) else 1.0
            ))
        
        return formatted
    
    # =========================================================================
    # Documentation operations
    # =========================================================================
    
    def add_documentation(
        self,
        docs: List[Dict[str, Any]],
        embeddings: List[List[float]],
        clear_existing: bool = True
    ):
        """Add documentation resources to the vector store"""
        if clear_existing:
            collection = self.clear_collection(self.DOCUMENTATION)
        else:
            collection = self._get_or_create_collection(self.DOCUMENTATION)
        
        if not docs:
            return
        
        ids = []
        documents = []
        metadatas = []
        
        seen_ids = set()
        for i, doc in enumerate(docs):
            # Create unique ID from name and category
            name = doc.get('name', doc.get('question', f'doc-{i}'))
            base_id = f"{doc.get('category', 'general')}/{name}".lower().replace(' ', '-')
            doc_id = base_id
            # Handle duplicates
            counter = 1
            while doc_id in seen_ids:
                doc_id = f"{base_id}_{counter}"
                counter += 1
            seen_ids.add(doc_id)
            ids.append(doc_id)
            
            # Create document text for embedding
            doc_parts = [
                doc.get("name", ""),
                doc.get("description", ""),
            ]
            if doc.get("topics"):
                doc_parts.append(f"Topics: {', '.join(doc['topics'])}")
            if doc.get("key_points"):
                doc_parts.append(f"Key points: {', '.join(doc['key_points'])}")
            if doc.get("usage_examples"):
                doc_parts.append(f"Examples: {', '.join(doc['usage_examples'])}")
            if doc.get("answer"):
                doc_parts.append(f"Answer: {doc['answer'][:500]}")
            documents.append(" ".join(doc_parts))
            
            metadatas.append({
                "name": doc.get("name", doc.get("question", "")),
                "description": doc.get("description", doc.get("answer", ""))[:500],
                "url": doc.get("url", ""),
                "category": doc.get("category", "general"),
                "topics": ",".join(doc.get("topics", [])),
                "priority": doc.get("priority", "medium"),
            })
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(docs)} documentation resources to vector store")
    
    def search_documentation(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        category_filter: str = None
    ) -> List[SearchResult]:
        """Search documentation by semantic similarity"""
        collection = self._get_or_create_collection(self.DOCUMENTATION)
        
        where_filter = None
        if category_filter and category_filter != "all":
            where_filter = {"category": category_filter}
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        return self._format_results(results)
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about stored data"""
        stats = {}
        
        for name in [self.CODEBUNDLES, self.CODECOLLECTIONS, self.LIBRARIES, self.DOCUMENTATION]:
            try:
                collection = self._get_or_create_collection(name)
                stats[name] = collection.count()
            except Exception:
                stats[name] = 0
        
        return stats

