"""
Library Tools

Tools for finding and getting help with Robot Framework libraries.
"""
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


class KeywordUsageHelpTool(BaseTool):
    """
    Get help on using RunWhen Robot Framework keywords.
    Uses semantic search to find relevant library documentation.
    """
    
    def __init__(self, semantic_search_getter):
        self._get_semantic_search = semantic_search_getter
    
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
        """Get keyword usage help"""
        ss = self._get_semantic_search()
        
        if not ss.is_available:
            return "Library search is not available."
        
        results = ss.search_libraries(
            query=query,
            category=category if category != "all" else None,
            max_results=5
        )
        
        if not results:
            return f"No library information found for: {query}\n\nTry searching for specific keywords like 'kubectl', 'AWS CLI', or 'HTTP request'."
        
        output = f"# Library Help: {query}\n\n"
        
        for lib in results:
            output += f"## **{lib['name']}**\n\n"
            output += f"**Import:** `{lib.get('import_path', lib['name'])}`\n\n"
            output += f"**Category:** {lib.get('category', 'general')}\n\n"
            
            if lib.get('description'):
                output += f"**Description:** {lib['description']}\n\n"
            
            if lib.get('functions'):
                output += "**Functions:**\n"
                for func in lib['functions'][:5]:
                    output += f"- `{func.get('signature', func.get('name'))}`"
                    if func.get('docstring'):
                        output += f"\n  {func['docstring'][:150]}"
                    output += "\n"
                output += "\n"
            
            if lib.get('keywords'):
                output += f"**Robot Keywords:** {', '.join(lib['keywords'][:10])}\n\n"
            
            output += f"**Relevance:** {lib.get('score', 0):.0%}\n\n"
            output += "---\n\n"
        
        return output


class FindLibraryInfoTool(BaseTool):
    """Find information about libraries using keyword search."""
    
    def __init__(self, search_engine):
        self._search_engine = search_engine
    
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
        """Find library info by keyword"""
        results = self._search_engine.search_libraries(
            query=query,
            category=category if category != "all" else None,
            max_results=10
        )
        
        if not results:
            return f"No libraries found matching: {query}"
        
        output = f"# Library Search: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for lib in results:
            output += f"## **{lib.get('name')}**\n\n"
            output += f"**Import:** {lib.get('import_path', 'N/A')}\n\n"
            output += f"**Category:** {lib.get('category', 'general')}\n\n"
            
            if lib.get('description'):
                output += f"**Description:** {lib['description'][:300]}\n\n"
            
            if lib.get('keywords'):
                output += f"**Keywords:** {', '.join(lib['keywords'][:8])}\n\n"
            
            output += "---\n\n"
        
        return output

