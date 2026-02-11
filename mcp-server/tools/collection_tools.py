"""
CodeCollection Tools

Tools for finding and listing CodeCollections.
All data is fetched from the Registry API.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class FindCodeCollectionTool(BaseTool):
    """Search for codecollections matching a query."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_codecollection",
            description="Find the right codecollection for your use case.",
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
        """Find codecollections via the Registry API."""
        try:
            collections = await self._client.list_collections()
        except Exception as e:
            logger.error(f"Registry API failed: {e}")
            return f"Search unavailable: {e}"
        
        # Client-side keyword matching until backend has semantic search
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for coll in collections:
            score = 0
            name = (coll.get('name') or '').lower()
            desc = (coll.get('description') or '').lower()
            slug = (coll.get('slug') or '').lower()
            text = f"{name} {desc} {slug}"
            
            if query_lower in name:
                score += 5
            if query_lower in desc:
                score += 3
            for word in query_words:
                if word in text:
                    score += 1
            
            if score > 0:
                scored.append((score, coll))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [coll for _, coll in scored[:max_results]]
        
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
            output += "---\n\n"
        
        return output


class ListCodeCollectionsTool(BaseTool):
    """List all available codecollections."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
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
        """List all codecollections from the Registry API."""
        try:
            collections = await self._client.list_collections()
        except Exception as e:
            logger.error(f"Registry API failed: {e}")
            return f"Failed to list collections: {e}"
        
        if format == "json":
            return json.dumps({"collections": collections}, indent=2, default=str)
        
        output = f"# CodeCollections ({len(collections)})\n\n"
        
        for coll in collections:
            slug = coll.get('slug', '')
            cb_count = coll.get('codebundle_count', 0)
            
            output += f"## **{coll.get('name')}**\n\n"
            output += f"**Slug:** {slug}\n\n"
            output += f"**CodeBundles:** {cb_count}\n\n"
            
            if coll.get('description'):
                output += f"**Description:** {coll['description']}\n\n"
            if coll.get('git_url'):
                output += f"**Repository:** {coll['git_url']}\n\n"
            output += "---\n\n"
        
        return output
