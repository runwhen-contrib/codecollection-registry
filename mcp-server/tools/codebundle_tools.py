"""
CodeBundle Tools

Tools for finding, listing, and getting details about CodeBundles.
All data is fetched from the Registry API.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class FindCodeBundleTool(BaseTool):
    """
    Search to find codebundles matching natural language queries.
    Delegates search to the Registry API.
    """
    
    def __init__(self, registry_client):
        self._client = registry_client
    
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
        """Find codebundles via the Registry API."""
        try:
            results = await self._client.search_codebundles(
                search=query,
                platform=platform,
                collection_slug=collection,
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Search unavailable: {e}"
        
        if not results:
            return f"No codebundles found matching: {query}\n\nTry rephrasing your query or using broader terms."
        
        output = f"# CodeBundles for: {query}\n\n"
        output += f"Found {len(results)} matching codebundle(s):\n\n"
        
        for i, cb in enumerate(results, 1):
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug', 'Unknown')
            output += f"## {i}. **{display_name}**\n\n"
            output += f"**Collection:** {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n\n"
            output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'N/A'))}\n\n"
            
            description = cb.get('description') or cb.get('doc') or ''
            if description:
                output += f"**Description:** {description[:500]}\n\n"
            
            tasks = cb.get('tasks', [])
            if tasks:
                output += "**Tasks:**\n"
                for task in tasks[:8]:
                    task_name = task if isinstance(task, str) else task.get('name', str(task))
                    output += f"- {task_name}\n"
                output += "\n"
            
            tags = cb.get('support_tags', [])
            if tags:
                output += f"**Tags:** {', '.join(tags)}\n\n"
            
            output += "---\n\n"
        
        return output


class ListCodeBundlesTool(BaseTool):
    """List all codebundles, optionally filtered by collection."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
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
        """List codebundles from the Registry API."""
        try:
            codebundles = await self._client.search_codebundles(
                collection_slug=collection_slug,
                max_results=200,
            )
        except Exception as e:
            logger.error(f"Registry API list failed: {e}")
            return f"Failed to list codebundles: {e}"
        
        if format == "json":
            return json.dumps({"codebundles": codebundles, "count": len(codebundles)}, indent=2, default=str)
        
        if format == "summary":
            by_collection = {}
            for cb in codebundles:
                coll = cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'unknown'))
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
        for cb in codebundles[:50]:
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"### **{display_name}**\n"
            output += f"- Collection: {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n"
            output += f"- Platform: {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n"
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"- {desc[:200]}\n"
            output += "\n"
        
        if len(codebundles) > 50:
            output += f"\n*... and {len(codebundles) - 50} more*\n"
        return output


class SearchCodeBundlesTool(BaseTool):
    """Keyword-based search for codebundles."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_codebundles",
            description="Search for codebundles by keywords, tags, or platform.",
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
        """Search codebundles via the Registry API."""
        try:
            results = await self._client.search_codebundles(
                search=query,
                platform=platform,
                tags=",".join(tags) if tags else None,
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Search unavailable: {e}"
        
        if not results:
            return f"No codebundles found matching: {query}"
        
        output = f"# Search Results: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for i, cb in enumerate(results, 1):
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"## {i}. **{display_name}**\n\n"
            output += f"**Collection:** {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n"
            output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n"
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"**Description:** {desc}\n"
            tags_list = cb.get('support_tags', [])
            if tags_list:
                output += f"**Tags:** {', '.join(tags_list)}\n"
            output += f"\n---\n\n"
        
        return output


class GetCodeBundleDetailsTool(BaseTool):
    """Get detailed information about a specific codebundle."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
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
                    description="Collection slug (helps disambiguate)",
                    required=False
                )
            ]
        )
    
    async def execute(
        self,
        slug: str,
        collection_slug: Optional[str] = None
    ) -> str:
        """Get codebundle details from the Registry API."""
        cb = None
        
        # Try direct lookup if we have both slugs
        if collection_slug:
            try:
                cb = await self._client.get_codebundle(collection_slug, slug)
            except Exception as e:
                logger.warning(f"Direct codebundle lookup failed: {e}")
        
        # Fall back to search
        if not cb:
            try:
                results = await self._client.search_codebundles(search=slug, max_results=5)
                for r in results:
                    if r.get('slug') == slug or slug in r.get('slug', ''):
                        cb = r
                        break
            except Exception as e:
                logger.error(f"Codebundle search failed: {e}")
                return f"Failed to fetch codebundle: {e}"
        
        if not cb:
            return f"CodeBundle not found: {slug}"
        
        display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
        output = f"# **{display_name}**\n\n"
        output += f"**Slug:** {cb.get('slug')}\n\n"
        output += f"**Collection:** {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n\n"
        output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n\n"
        
        if cb.get('author'):
            output += f"**Author:** {cb['author']}\n\n"
        
        description = cb.get('description') or cb.get('doc') or ''
        if description:
            output += f"## Description\n\n{description}\n\n"
        
        tasks = cb.get('tasks', [])
        if tasks:
            output += f"## Tasks ({len(tasks)})\n\n"
            for task in tasks:
                task_name = task if isinstance(task, str) else task.get('name', str(task))
                output += f"- {task_name}\n"
            output += "\n"
        
        tags = cb.get('support_tags', [])
        if tags:
            output += f"**Tags:** {', '.join(tags)}\n\n"
        
        return output
