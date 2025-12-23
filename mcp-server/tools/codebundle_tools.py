"""
CodeBundle Tools

Tools for finding, listing, and getting details about CodeBundles.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class FindCodeBundleTool(BaseTool):
    """
    Semantic search to find codebundles matching natural language queries.
    Uses AI embeddings for intelligent matching.
    """
    
    def __init__(self, semantic_search_getter):
        """
        Args:
            semantic_search_getter: Callable that returns SemanticSearch instance
        """
        self._get_semantic_search = semantic_search_getter
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_codebundle",
            description="Find codebundles for your use case. Describe what you need in natural language. Examples: 'troubleshoot Kubernetes pods', 'monitor AWS EKS', 'check database health'",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Natural language description of what you're looking for",
                    required=True
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Optional platform filter",
                    required=False,
                    enum=["Kubernetes", "AWS", "Azure", "GCP", "Linux", "Database"]
                ),
                ToolParameter(
                    name="collection",
                    type="string",
                    description="Optional collection filter",
                    required=False
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results to return",
                    required=False,
                    default=10
                )
            ]
        )
    
    async def execute(
        self,
        query: str,
        platform: Optional[str] = None,
        collection: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Find codebundles using semantic search"""
        ss = self._get_semantic_search()
        
        if not ss.is_available:
            return "Semantic search is not available. Please ensure the vector database is initialized."
        
        recommendations = ss.recommend_codebundles(
            query=query,
            platform=platform,
            collection=collection,
            max_results=max_results
        )
        
        if not recommendations:
            return f"No codebundles found matching: {query}\n\nTry rephrasing your query or using broader terms."
        
        output = f"# CodeBundles for: {query}\n\n"
        output += f"Found {len(recommendations)} matching codebundle(s):\n\n"
        
        for i, rec in enumerate(recommendations, 1):
            output += f"## {i}. **{rec.display_name}**\n\n"
            output += f"**Collection:** {rec.collection_slug}\n\n"
            output += f"**Platform:** {rec.platform}\n\n"
            output += f"**Relevance:** {rec.score:.0%}\n\n"
            
            if rec.description:
                output += f"**Description:** {rec.description}\n\n"
            
            if rec.tasks:
                output += "**Tasks:**\n"
                for task in rec.tasks[:8]:
                    output += f"- {task}\n"
                output += "\n"
            
            if rec.capabilities:
                output += "**Capabilities:**\n"
                for cap in rec.capabilities[:5]:
                    output += f"- {cap}\n"
                output += "\n"
            
            if rec.tags:
                output += f"**Tags:** {', '.join(rec.tags)}\n\n"
            
            output += f"**Source:** [{rec.slug}]({rec.git_url})\n\n"
            output += "---\n\n"
        
        return output


class ListCodeBundlesTool(BaseTool):
    """List all codebundles, optionally filtered by collection."""
    
    def __init__(self, data_loader):
        self._data_loader = data_loader
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_codebundles",
            description="List all codebundles and codecollections. Supports filtering by collection and output formatting.",
            category="info",
            parameters=[
                ToolParameter(
                    name="format",
                    type="string",
                    description="Output format",
                    required=False,
                    default="markdown",
                    enum=["markdown", "json", "summary"]
                ),
                ToolParameter(
                    name="collection_slug",
                    type="string",
                    description="Filter by collection slug",
                    required=False
                )
            ]
        )
    
    async def execute(
        self,
        format: str = "markdown",
        collection_slug: Optional[str] = None
    ) -> str:
        """List codebundles"""
        codebundles = self._data_loader.load_codebundles()
        
        if collection_slug:
            codebundles = [cb for cb in codebundles if cb.get('collection_slug') == collection_slug]
        
        if format == "json":
            return json.dumps({"codebundles": codebundles, "count": len(codebundles)}, indent=2)
        
        if format == "summary":
            # Group by collection
            by_collection = {}
            for cb in codebundles:
                coll = cb.get('collection_slug', 'unknown')
                if coll not in by_collection:
                    by_collection[coll] = []
                by_collection[coll].append(cb)
            
            output = f"# CodeBundle Summary\n\n"
            output += f"Total: {len(codebundles)} codebundles in {len(by_collection)} collections\n\n"
            
            for coll, cbs in sorted(by_collection.items()):
                output += f"## {coll} ({len(cbs)} codebundles)\n\n"
            
            return output
        
        # Markdown format
        output = f"# Available CodeBundles ({len(codebundles)})\n\n"
        
        for cb in codebundles[:50]:  # Limit for readability
            output += f"### **{cb.get('display_name', cb.get('name'))}**\n"
            output += f"- Collection: {cb.get('collection_slug')}\n"
            output += f"- Platform: {cb.get('platform', 'Unknown')}\n"
            if cb.get('description'):
                output += f"- {cb['description'][:200]}\n"
            output += "\n"
        
        if len(codebundles) > 50:
            output += f"\n*... and {len(codebundles) - 50} more*\n"
        
        return output


class SearchCodeBundlesTool(BaseTool):
    """Keyword-based search for codebundles."""
    
    def __init__(self, search_engine):
        self._search_engine = search_engine
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_codebundles",
            description="Keyword-based search for codebundles by keywords, tags, or platform. For semantic search, use find_codebundle instead.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Filter by tags",
                    required=False,
                    items="string"
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Filter by platform",
                    required=False
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
        tags: Optional[List[str]] = None,
        platform: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Search codebundles by keyword"""
        results = self._search_engine.search_codebundles(
            query=query,
            tags=tags or [],
            platform=platform,
            max_results=max_results
        )
        
        if not results:
            return f"No codebundles found matching: {query}"
        
        output = f"# Search Results: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for i, cb in enumerate(results, 1):
            output += f"## {i}. **{cb.get('display_name', cb.get('name'))}**\n\n"
            output += f"**Collection:** {cb.get('collection_slug')}\n"
            output += f"**Platform:** {cb.get('platform', 'Unknown')}\n"
            if cb.get('description'):
                output += f"**Description:** {cb['description']}\n"
            if cb.get('support_tags'):
                output += f"**Tags:** {', '.join(cb['support_tags'])}\n"
            output += f"\n---\n\n"
        
        return output


class GetCodeBundleDetailsTool(BaseTool):
    """Get detailed information about a specific codebundle."""
    
    def __init__(self, data_loader):
        self._data_loader = data_loader
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_codebundle_details",
            description="Get detailed information about a specific codebundle",
            category="info",
            parameters=[
                ToolParameter(
                    name="slug",
                    type="string",
                    description="CodeBundle slug",
                    required=True
                ),
                ToolParameter(
                    name="collection_slug",
                    type="string",
                    description="Collection slug (optional, helps disambiguate)",
                    required=False
                )
            ]
        )
    
    async def execute(
        self,
        slug: str,
        collection_slug: Optional[str] = None
    ) -> str:
        """Get codebundle details"""
        codebundles = self._data_loader.load_codebundles()
        
        # Find matching codebundle
        matches = [cb for cb in codebundles if cb.get('slug') == slug or slug in cb.get('slug', '')]
        
        if collection_slug:
            matches = [cb for cb in matches if cb.get('collection_slug') == collection_slug]
        
        if not matches:
            return f"CodeBundle not found: {slug}"
        
        cb = matches[0]
        
        output = f"# **{cb.get('display_name', cb.get('name'))}**\n\n"
        output += f"**Slug:** {cb.get('slug')}\n\n"
        output += f"**Collection:** {cb.get('collection_slug')}\n\n"
        output += f"**Platform:** {cb.get('platform', 'Unknown')}\n\n"
        
        if cb.get('author'):
            output += f"**Author:** {cb['author']}\n\n"
        
        if cb.get('description'):
            output += f"## Description\n\n{cb['description']}\n\n"
        
        if cb.get('tasks'):
            output += f"## Tasks ({len(cb['tasks'])})\n\n"
            for task in cb['tasks']:
                output += f"- {task}\n"
            output += "\n"
        
        if cb.get('capabilities'):
            output += f"## Capabilities\n\n"
            for cap in cb['capabilities'][:10]:
                output += f"- {cap}\n"
            output += "\n"
        
        if cb.get('support_tags'):
            output += f"**Tags:** {', '.join(cb['support_tags'])}\n\n"
        
        if cb.get('git_url'):
            output += f"**Source:** [{cb['git_url']}]({cb['git_url']})\n\n"
        
        return output

