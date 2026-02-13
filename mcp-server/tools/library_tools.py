"""
Library Tools

Tools for finding and getting help with Robot Framework libraries.
All data is fetched from the Registry API.
"""
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class KeywordUsageHelpTool(BaseTool):
    """
    Get help on using RunWhen Robot Framework keywords.
    Searches via the Registry API.
    """
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="keyword_usage_help",
            description="Get help on how to use RunWhen Robot Framework keywords in your codebundles. Ask questions like 'How do I run kubectl commands?' or 'How do I parse JSON output?'",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Your question about using keywords",
                    required=True
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Library category filter",
                    required=False,
                    default="all",
                    enum=["cli", "kubernetes", "aws", "azure", "gcp", "prometheus", "database", "all"]
                )
            ]
        )
    
    async def execute(self, query: str, category: str = "all") -> str:
        """Get keyword usage help via the Registry API."""
        try:
            # Use codebundle search as a proxy — backend can add a dedicated
            # library search endpoint later for better results.
            results = await self._client.search_codebundles(
                search=query,
                max_results=5,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Library search unavailable: {e}"
        
        if not results:
            return f"No library information found for: {query}\n\nTry searching for specific keywords like 'kubectl', 'AWS CLI', or 'HTTP request'."
        
        output = f"# Library Help: {query}\n\n"
        
        for cb in results:
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"## **{display_name}**\n\n"
            
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"**Description:** {desc[:300]}\n\n"
            
            tags = cb.get('support_tags', [])
            if tags:
                output += f"**Tags:** {', '.join(tags)}\n\n"
            
            output += "---\n\n"
        
        return output


class FindLibraryInfoTool(BaseTool):
    """Find information about libraries using keyword search."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_library_info",
            description="Find information about libraries (keyword search). For more natural queries, use keyword_usage_help instead.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Library category filter",
                    required=False,
                    default="all",
                    enum=["cli", "python", "shell", "all"]
                )
            ]
        )
    
    async def execute(self, query: str, category: str = "all") -> str:
        """Find library info via the Registry API."""
        try:
            results = await self._client.search_codebundles(
                search=query,
                max_results=10,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Library search unavailable: {e}"
        
        if not results:
            return f"No libraries found matching: {query}"
        
        output = f"# Library Search: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for cb in results:
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"## **{display_name}**\n\n"
            
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"**Description:** {desc[:300]}\n\n"
            
            output += "---\n\n"
        
        return output
