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
        self.vector_store = VectorStore()
        
        # Auto-detect or use preference
        if prefer_local is None:
            # Use Azure if available, otherwise local
            prefer_local = not (
                os.getenv("AZURE_OPENAI_ENDPOINT") and 
                os.getenv("AZURE_OPENAI_API_KEY")
            )
        
        try:
            self.embedding_generator = get_embedding_generator(prefer_local=prefer_local)
            self._is_available = True
            logger.info(f"SemanticSearch initialized with {self.embedding_generator.provider_name}")
        except Exception as e:
            logger.warning(f"SemanticSearch unavailable: {e}")
            self._is_available = False
            self.embedding_generator = None
    
    @property
    def is_available(self) -> bool:
        """Check if semantic search is available"""
        return self._is_available and self.vector_store.get_stats().get('codebundles', 0) > 0
    
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
            recommendations.append(RecommendationResult(
                slug=meta.get('slug', ''),
                collection_slug=meta.get('collection_slug', ''),
                name=meta.get('name', ''),
                display_name=meta.get('display_name', meta.get('name', '')),
                description=meta.get('description', ''),
                platform=meta.get('platform', 'Unknown'),
                tags=meta.get('tags', '').split(',') if meta.get('tags') else [],
                score=result.score,
                git_url=f"https://github.com/runwhen-contrib/{meta.get('collection_slug', '')}/tree/main/codebundles/{meta.get('slug', '')}"
            ))
        
        return recommendations
    
    def recommend_codecollections(
        self,
        query: str,
        max_results: int = 5
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
        max_results: int = 5
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
    """Get the singleton SemanticSearch instance"""
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch()
    return _semantic_search

