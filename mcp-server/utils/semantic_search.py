"""
Semantic search utilities combining embeddings and vector store.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .vector_store import VectorStore, SearchResult
from .embeddings import get_embedding_generator, EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class RecommendationResult:
    """A recommendation result with full details"""
    slug: str
    collection_slug: str
    name: str
    display_name: str
    description: str
    platform: str
    tags: List[str]
    score: float
    git_url: str = ""
    tasks: List[str] = None  # List of task names
    capabilities: List[str] = None  # List of task:description strings
    
    def __post_init__(self):
        if self.tasks is None:
            self.tasks = []
        if self.capabilities is None:
            self.capabilities = []
    
    def to_markdown(self) -> str:
        """Convert to markdown format"""
        lines = [
            f"### {self.display_name}",
            f"",
            f"**Slug:** `{self.collection_slug}/{self.slug}`",
            f"",
            f"**Platform:** {self.platform}",
            f"",
            f"**Description:** {self.description}",
            f"",
        ]
        if self.tasks:
            lines.append("**Available Tasks:**")
            for task in self.tasks[:10]:
                lines.append(f"  - {task}")
            lines.append("")
        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")
            lines.append("")
        if self.git_url:
            lines.append(f"**Source:** [{self.git_url}]({self.git_url})")
            lines.append("")
        lines.append(f"**Relevance Score:** {self.score:.2f}")
        return "\n".join(lines)


class SemanticSearch:
    """
    High-level semantic search interface for MCP tools.
    
    Combines embedding generation with vector store queries
    to provide semantic search capabilities.
    """
    
    def __init__(self, prefer_local: bool = None):
        """
        Initialize semantic search.
        
        Args:
            prefer_local: If True, use local embeddings. If None, auto-detect.
        """
        try:
            self.vector_store = VectorStore()
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            self.vector_store = None
            self._is_available = False
            self.embedding_generator = None
            return
        
        # Auto-detect embedding provider
        if prefer_local is None:
            # Use Azure if available (embedding-specific or main credentials), otherwise local
            embedding_endpoint = os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
            embedding_key = os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
            prefer_local = not (embedding_endpoint and embedding_key)
        
        try:
            self.embedding_generator = get_embedding_generator(prefer_local=prefer_local)
            self._is_available = True
            backend = type(self.vector_store).__name__
            logger.info(f"SemanticSearch initialized with {self.embedding_generator.provider_name} + {backend}")
        except Exception as e:
            logger.warning(f"SemanticSearch unavailable: {e}")
            self._is_available = False
            self.embedding_generator = None
    
    @property
    def is_available(self) -> bool:
        """Check if semantic search is available"""
        if not self._is_available or not self.vector_store:
            return False
        try:
            return self.vector_store.get_stats().get('codebundles', 0) > 0
        except Exception:
            return False
    
    def recommend_codebundles(
        self,
        query: str,
        platform: str = None,
        collection: str = None,
        max_results: int = 10
    ) -> List[RecommendationResult]:
        """
        Recommend codebundles based on a natural language query.
        
        Args:
            query: Natural language query describing the use case
            platform: Optional platform filter (Kubernetes, AWS, Azure, etc.)
            collection: Optional collection slug filter
            max_results: Maximum number of recommendations
            
        Returns:
            List of RecommendationResult objects
        """
        if not self._is_available:
            logger.warning("Semantic search not available")
            return []
        
        # Generate query embedding
        query_embedding = self.embedding_generator.embed_text(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []
        
        # Search vector store
        results = self.vector_store.search_codebundles(
            query_embedding=query_embedding,
            n_results=max_results,
            platform_filter=platform,
            collection_filter=collection
        )
        
        # Convert to recommendations
        recommendations = []
        for result in results:
            meta = result.metadata
            # Parse tasks - may be stored as JSON string or list
            tasks = meta.get('tasks', [])
            if isinstance(tasks, str):
                import json
                try:
                    tasks = json.loads(tasks)
                except:
                    tasks = []
            
            # Parse capabilities - may be stored as JSON string or list  
            capabilities = meta.get('capabilities', [])
            if isinstance(capabilities, str):
                import json
                try:
                    capabilities = json.loads(capabilities)
                except:
                    capabilities = []
            
            # Use 'name' for URL path (codebundle folder name without collection prefix)
            codebundle_name = meta.get('name', meta.get('slug', ''))
            recommendations.append(RecommendationResult(
                slug=meta.get('slug', ''),
                collection_slug=meta.get('collection_slug', ''),
                name=codebundle_name,
                display_name=meta.get('display_name', codebundle_name),
                description=meta.get('description', ''),
                platform=meta.get('platform', 'Unknown'),
                tags=meta.get('tags', '').split(',') if meta.get('tags') else [],
                score=result.score,
                # Use registry URL with 'name' (folder name) not 'slug' (which has collection prefix)
                git_url=f"/collections/{meta.get('collection_slug', '')}/codebundles/{codebundle_name}",
                tasks=tasks,
                capabilities=capabilities
            ))
        
        return recommendations
    
    def recommend_codecollections(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recommend codecollections based on a natural language query.
        
        Args:
            query: Natural language query
            max_results: Maximum number of recommendations
            
        Returns:
            List of collection recommendations
        """
        if not self._is_available:
            return []
        
        query_embedding = self.embedding_generator.embed_text(query)
        if not query_embedding:
            return []
        
        results = self.vector_store.search_codecollections(
            query_embedding=query_embedding,
            n_results=max_results
        )
        
        recommendations = []
        for result in results:
            meta = result.metadata
            recommendations.append({
                'slug': meta.get('slug', ''),
                'name': meta.get('name', ''),
                'description': meta.get('description', ''),
                'git_url': meta.get('git_url', ''),
                'score': result.score
            })
        
        return recommendations
    
    def search_libraries(
        self,
        query: str,
        category: str = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for libraries based on a natural language query.
        
        Args:
            query: Natural language query about library usage
            category: Optional category filter (cli, python, shell)
            max_results: Maximum number of results
            
        Returns:
            List of library recommendations
        """
        if not self._is_available:
            return []
        
        query_embedding = self.embedding_generator.embed_text(query)
        if not query_embedding:
            return []
        
        results = self.vector_store.search_libraries(
            query_embedding=query_embedding,
            n_results=max_results,
            category_filter=category
        )
        
        recommendations = []
        for result in results:
            meta = result.metadata
            recommendations.append({
                'name': meta.get('name', ''),
                'description': meta.get('description', ''),
                'category': meta.get('category', ''),
                'import_path': meta.get('import_path', meta.get('import_name', '')),
                'collection_slug': meta.get('collection_slug', ''),
                'git_url': meta.get('git_url', ''),
                'score': result.score
            })
        
        return recommendations
    
    def search_documentation(
        self,
        query: str,
        category: str = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search documentation resources based on a natural language query.
        
        Args:
            query: Natural language query about how to do something
            category: Optional category filter (documentation, examples, faq, libraries)
            max_results: Maximum number of results
            
        Returns:
            List of documentation recommendations
        """
        if not self._is_available:
            return []
        
        query_embedding = self.embedding_generator.embed_text(query)
        if not query_embedding:
            return []
        
        results = self.vector_store.search_documentation(
            query_embedding=query_embedding,
            n_results=max_results,
            category_filter=category
        )
        
        recommendations = []
        for result in results:
            meta = result.metadata
            rec = {
                'name': meta.get('name', ''),
                'description': meta.get('description', ''),
                'url': meta.get('url', ''),
                'category': meta.get('category', ''),
                'topics': meta.get('topics', '').split(',') if meta.get('topics') else [],
                'priority': meta.get('priority', 'medium'),
                'score': result.score,
            }
            # Include the stored document content (crawled page content).
            # This is what makes documentation answers actually useful --
            # the LLM gets real page content, not just metadata summaries.
            if result.content and meta.get('has_crawled_content') == 'true':
                rec['crawled_content'] = result.content
            recommendations.append(rec)
        
        return recommendations
    
    def get_stats(self) -> Dict[str, Any]:
        """Get search statistics"""
        stats = self.vector_store.get_stats()
        stats['embedding_provider'] = (
            self.embedding_generator.provider_name if self.embedding_generator else 'None'
        )
        stats['is_available'] = self.is_available
        return stats


# Singleton instance for reuse
_semantic_search: Optional[SemanticSearch] = None


def get_semantic_search() -> SemanticSearch:
    """Get the singleton SemanticSearch instance.
    
    NOTE: This module is legacy — the MCP server now uses RegistryClient
    to fetch data from the backend API.  This helper remains for any
    standalone / indexer scripts that still rely on local vector search.
    """
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch()
    return _semantic_search

