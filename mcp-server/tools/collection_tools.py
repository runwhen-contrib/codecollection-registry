"""
CodeCollection Tools

Tools for finding and listing CodeCollections.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class FindCodeCollectionTool(BaseTool):
    """Semantic search for codecollections."""
    
    def __init__(self, semantic_search_getter):
        self._get_semantic_search = semantic_search_getter
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_codecollection",
            description="Find the right codecollection for your use case using semantic search.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Description of what you're looking for",
                    required=True
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results",
                    required=False,
                    default=5
                )
            ]
        )
    
    async def execute(self, query: str, max_results: int = 5) -> str:
        """Find codecollections using semantic search"""
        ss = self._get_semantic_search()
        
        if not ss.is_available:
            return "Semantic search is not available."
        
        results = ss.search_codecollections(query=query, n_results=max_results)
        
        if not results:
            return f"No codecollections found matching: {query}"
        
        output = f"# CodeCollections for: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for i, coll in enumerate(results, 1):
            output += f"## {i}. **{coll.get('name')}**\n\n"
            output += f"**Slug:** {coll.get('slug')}\n\n"
            if coll.get('description'):
                output += f"**Description:** {coll['description']}\n\n"
            if coll.get('git_url'):
                output += f"**Repository:** [{coll['git_url']}]({coll['git_url']})\n\n"
            output += f"**Relevance:** {coll.get('score', 0):.0%}\n\n"
            output += "---\n\n"
        
        return output


class ListCodeCollectionsTool(BaseTool):
    """List all available codecollections."""
    
    def __init__(self, data_loader):
        self._data_loader = data_loader
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_codecollections",
            description="List all available codecollections",
            category="info",
            parameters=[
                ToolParameter(
                    name="format",
                    type="string",
                    description="Output format",
                    required=False,
                    default="markdown",
                    enum=["markdown", "json", "summary"]
                )
            ]
        )
    
    async def execute(self, format: str = "markdown") -> str:
        """List all codecollections"""
        collections = self._data_loader.load_codecollections()
        codebundles = self._data_loader.load_codebundles()
        
        # Count codebundles per collection
        cb_counts = {}
        for cb in codebundles:
            coll = cb.get('collection_slug', 'unknown')
            cb_counts[coll] = cb_counts.get(coll, 0) + 1
        
        if format == "json":
            for coll in collections:
                coll['codebundle_count'] = cb_counts.get(coll.get('slug', ''), 0)
            return json.dumps({"collections": collections}, indent=2)
        
        output = f"# CodeCollections ({len(collections)})\n\n"
        
        for coll in collections:
            slug = coll.get('slug', '')
            cb_count = cb_counts.get(slug, 0)
            
            output += f"## **{coll.get('name')}**\n\n"
            output += f"**Slug:** {slug}\n\n"
            output += f"**CodeBundles:** {cb_count}\n\n"
            
            if coll.get('description'):
                output += f"**Description:** {coll['description']}\n\n"
            
            if coll.get('git_url'):
                output += f"**Repository:** {coll['git_url']}\n\n"
            
            output += "---\n\n"
        
        return output

