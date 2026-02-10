"""
Documentation Tools

Tools for finding documentation, guides, and development resources.
Uses the managed docs.yaml for accurate URLs.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# =============================================================================
# Documentation Data Management
# =============================================================================

@dataclass
class DocEntry:
    """A documentation entry"""
    name: str
    url: str
    description: str
    keywords: List[str]
    category: str
    examples: Optional[List[str]] = None


class DocumentationManager:
    """
    Manages documentation from docs.yaml.
    Provides accurate, managed URLs for documentation resources.
    """
    
    def __init__(self, docs_file: str = None):
        if docs_file is None:
            docs_file = Path(__file__).parent.parent / "docs.yaml"
        self.docs_file = Path(docs_file)
        self._docs: Optional[Dict] = None
        self._entries: List[DocEntry] = []
    
    def _load(self) -> None:
        """Load and parse docs.yaml"""
        if self._docs is not None:
            return
        
        if not self.docs_file.exists():
            logger.warning(f"docs.yaml not found at {self.docs_file}")
            self._docs = {}
            return
        
        try:
            with open(self.docs_file, 'r') as f:
                self._docs = yaml.safe_load(f) or {}
            
            # Parse all entries
            docs = self._docs.get("documentation", {})
            for category, items in docs.items():
                if isinstance(items, list):
                    for item in items:
                        if "name" in item:
                            self._entries.append(DocEntry(
                                name=item.get("name", ""),
                                url=item.get("url", ""),
                                description=item.get("description", ""),
                                keywords=item.get("keywords", []),
                                category=category,
                                examples=item.get("examples")
                            ))
                        elif "question" in item:
                            # FAQ entry
                            self._entries.append(DocEntry(
                                name=item.get("question", ""),
                                url="",
                                description=item.get("answer", ""),
                                keywords=item.get("keywords", []),
                                category="faq"
                            ))
        except Exception as e:
            logger.error(f"Failed to load docs.yaml: {e}")
            self._docs = {}
    
    def search(self, query: str, category: str = None, limit: int = 5) -> List[DocEntry]:
        """Search documentation entries"""
        self._load()
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for entry in self._entries:
            if category and entry.category != category:
                continue
            
            score = 0
            
            # Name match (highest priority)
            if query_lower in entry.name.lower():
                score += 5
            
            # Keyword match
            for kw in entry.keywords:
                if kw.lower() in query_lower or query_lower in kw.lower():
                    score += 3
            
            # Description match
            if query_lower in entry.description.lower():
                score += 2
            
            # Word-level matching
            all_text = f"{entry.name} {entry.description} {' '.join(entry.keywords)}".lower()
            for word in query_words:
                if word in all_text:
                    score += 0.5
            
            if score > 0:
                scored.append((score, entry))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]
    
    def get_by_category(self, category: str) -> List[DocEntry]:
        """Get all docs in a category"""
        self._load()
        return [e for e in self._entries if e.category == category]
    
    def list_categories(self) -> List[str]:
        """List all documentation categories"""
        self._load()
        return list(set(e.category for e in self._entries))
    
    def get_all_urls(self) -> Dict[str, str]:
        """Get mapping of all doc names to URLs"""
        self._load()
        return {e.name: e.url for e in self._entries if e.url}


# Global instance
_doc_manager: Optional[DocumentationManager] = None

def get_doc_manager() -> DocumentationManager:
    """Get or create the documentation manager"""
    global _doc_manager
    if _doc_manager is None:
        _doc_manager = DocumentationManager()
    return _doc_manager


# =============================================================================
# Documentation Tools
# =============================================================================

class FindDocumentationTool(BaseTool):
    """
    Find documentation, guides, and FAQs.
    Uses managed docs.yaml for accurate URLs.
    """
    
    def __init__(self, semantic_search_getter=None):
        """
        Args:
            semantic_search_getter: Optional fallback to semantic search
        """
        self._get_semantic_search = semantic_search_getter
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_documentation",
            description="Find documentation, guides, examples, and FAQs for CodeBundle development. Ask how-to questions or search for specific topics.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="What documentation to find",
                    required=True
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Documentation category filter",
                    required=False,
                    default="all",
                    enum=["codebundle_development", "libraries", "platform", "faq", "all"]
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results",
                    required=False,
                    default=10
                )
            ]
        )
    
    async def execute(
        self,
        query: str,
        category: str = "all",
        max_results: int = 10
    ) -> str:
        """
        Find documentation using a two-layer approach:
        1. Semantic search (pgvector with crawled page content) - PRIMARY
        2. docs.yaml keyword matching - for URL enrichment and fallback
        
        Semantic search uses actual crawled page content with embeddings,
        so it can answer detailed questions. docs.yaml provides curated
        URLs and descriptions for enrichment.
        """
        doc_manager = get_doc_manager()
        semantic_results = []
        keyword_results = []
        
        # Layer 1: Semantic search against crawled documentation content (PRIMARY)
        if self._get_semantic_search:
            try:
                ss = self._get_semantic_search()
                if ss.is_available:
                    semantic_results = ss.search_documentation(
                        query=query,
                        category=category if category != "all" else None,
                        max_results=max_results
                    ) or []
            except Exception as e:
                logger.warning(f"Semantic documentation search failed: {e}")
        
        # Layer 2: Keyword search against docs.yaml (for URLs and curated descriptions)
        keyword_results = doc_manager.search(
            query=query,
            category=category if category != "all" else None,
            limit=max_results
        )
        
        # Build a URL lookup from keyword results for enrichment
        url_lookup = {}
        for entry in keyword_results:
            name_key = entry.name.lower().strip()
            url_lookup[name_key] = entry
        
        # Merge results: semantic results first (richer content), enriched with docs.yaml URLs
        output_parts = []
        seen_names = set()
        
        # Add semantic results (these have actual page content from crawling)
        for doc in semantic_results:
            name = doc.get('name', doc.get('question', 'Untitled'))
            seen_names.add(name.lower().strip())
            
            part = f"## **{name}**\n\n"
            part += f"**Category:** {doc.get('category', 'documentation')}\n\n"
            
            # Use crawled content if available (much richer than docs.yaml descriptions)
            if doc.get('crawled_content'):
                # Include actual page content - this is the gold
                content = doc['crawled_content'][:3000]
                part += f"**Content:**\n{content}\n\n"
            elif doc.get('description'):
                part += f"**Description:** {doc['description']}\n\n"
            
            # Enrich with URL from docs.yaml if available
            url = doc.get('url', '')
            name_key = name.lower().strip()
            if name_key in url_lookup and url_lookup[name_key].url:
                url = url_lookup[name_key].url
            if url:
                part += f"**Link:** [{url}]({url})\n\n"
            
            part += f"**Relevance:** {doc.get('score', 0):.0%}\n\n"
            part += "---\n\n"
            output_parts.append(part)
        
        # Add keyword-only results that weren't in semantic results
        for entry in keyword_results:
            if entry.name.lower().strip() not in seen_names:
                seen_names.add(entry.name.lower().strip())
                
                part = f"## **{entry.name}**\n\n"
                part += f"**Category:** {entry.category}\n\n"
                
                if entry.description:
                    part += f"**Description:** {entry.description}\n\n"
                
                if entry.url:
                    part += f"**Link:** [{entry.url}]({entry.url})\n\n"
                
                if entry.examples:
                    part += "**Examples:**\n"
                    for ex in entry.examples[:2]:
                        part += f"```robot\n{ex}\n```\n\n"
                
                part += "---\n\n"
                output_parts.append(part)
        
        if output_parts:
            output = f"# Documentation: {query}\n\n"
            output += f"Found {len(output_parts)} resource(s):\n\n"
            output += "".join(output_parts[:max_results])
            return output
        
        return f"No documentation found matching: {query}\n\nCheck the official RunWhen documentation at https://docs.runwhen.com"


class GetDevelopmentRequirementsTool(BaseTool):
    """Get development requirements and best practices."""
    
    def __init__(self, data_loader):
        self._data_loader = data_loader
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_development_requirements",
            description="Get development requirements, best practices, and documentation for specific features",
            category="info",
            parameters=[
                ToolParameter(
                    name="feature",
                    type="string",
                    description="Feature to get requirements for (e.g., 'secrets', 'tasks', 'slis')",
                    required=True
                )
            ]
        )
    
    async def execute(self, feature: str) -> str:
        """Get development requirements"""
        feature_lower = feature.lower()
        
        # Search documentation manager for the feature
        doc_manager = get_doc_manager()
        results = doc_manager.search(feature, limit=3)
        
        output = f"# Development Requirements: {feature}\n\n"
        
        if results:
            for entry in results:
                output += f"## **{entry.name}**\n\n"
                if entry.description:
                    output += f"{entry.description}\n\n"
                if entry.url:
                    output += f"**Documentation:** [{entry.url}]({entry.url})\n\n"
                if entry.examples:
                    output += "**Examples:**\n"
                    for ex in entry.examples:
                        output += f"```robot\n{ex}\n```\n\n"
                output += "---\n\n"
        else:
            output += f"No specific documentation found for '{feature}'.\n\n"
            output += "Check the official RunWhen documentation at https://docs.runwhen.com/public/runwhen-authors\n"
        
        return output


