"""
MCP Client Service

Provides a client interface to the MCP (Model Context Protocol) server
for semantic search of codebundles, codecollections, and keywords.
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CodeBundleResult:
    """A codebundle search result"""
    slug: str
    collection_slug: str
    name: str
    display_name: str
    description: str
    platform: str
    tags: List[str]
    score: float
    git_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "collection_slug": self.collection_slug,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "platform": self.platform,
            "tags": self.tags,
            "score": self.score,
            "git_url": self.git_url
        }


@dataclass  
class KeywordResult:
    """A keyword/library search result"""
    name: str
    import_path: str
    collection_slug: str
    description: str
    category: str
    score: float
    git_url: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "import_path": self.import_path,
            "collection_slug": self.collection_slug,
            "description": self.description,
            "category": self.category,
            "score": self.score,
            "git_url": self.git_url
        }


class MCPClient:
    """
    Client for the RunWhen MCP Server.
    
    Provides semantic search capabilities for:
    - Codebundles (find_codebundle)
    - Codecollections (find_codecollection)
    - Keywords/Libraries (keyword_usage_help)
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.MCP_SERVER_URL
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MCP server health"""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"MCP health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def is_available(self) -> bool:
        """Check if MCP server is available"""
        health = await self.health_check()
        return health.get("status") == "healthy"
    
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool"""
        try:
            client = await self._get_client()
            response = await client.post(
                "/tools/call",
                json={
                    "tool_name": tool_name,
                    "arguments": arguments
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"MCP tool call failed: {e}")
            raise MCPError(f"Failed to call MCP tool {tool_name}: {e}")
    
    async def find_codebundle(
        self,
        query: str,
        platform: str = None,
        collection: str = None,
        max_results: int = 5
    ) -> str:
        """
        Find codebundles matching a natural language query.
        
        Args:
            query: Natural language description of what you want to do
            platform: Optional platform filter (Kubernetes, AWS, Azure, etc.)
            collection: Optional collection slug filter
            max_results: Maximum number of results
            
        Returns:
            Markdown formatted response with matching codebundles
        """
        arguments = {
            "query": query,
            "max_results": max_results
        }
        if platform:
            arguments["platform"] = platform
        if collection:
            arguments["collection"] = collection
        
        result = await self._call_tool("find_codebundle", arguments)
        
        if result.get("success"):
            return result.get("result", "No results found")
        else:
            raise MCPError(result.get("error", "Unknown error"))
    
    async def find_codecollection(
        self,
        query: str,
        max_results: int = 3
    ) -> str:
        """
        Find codecollections matching a natural language query.
        
        Args:
            query: Natural language description of what you're looking for
            max_results: Maximum number of results
            
        Returns:
            Markdown formatted response with matching codecollections
        """
        result = await self._call_tool("find_codecollection", {
            "query": query,
            "max_results": max_results
        })
        
        if result.get("success"):
            return result.get("result", "No results found")
        else:
            raise MCPError(result.get("error", "Unknown error"))
    
    async def keyword_usage_help(
        self,
        query: str,
        category: str = "all"
    ) -> str:
        """
        Get help on using RunWhen Robot Framework keywords.
        
        Args:
            query: Question about keyword/library usage
            category: Category filter (cli, kubernetes, aws, azure, all)
            
        Returns:
            Markdown formatted response with keyword help
        """
        result = await self._call_tool("keyword_usage_help", {
            "query": query,
            "category": category
        })
        
        if result.get("success"):
            return result.get("result", "No results found")
        else:
            raise MCPError(result.get("error", "Unknown error"))
    
    async def search_codebundles_raw(
        self,
        query: str,
        platform: str = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search codebundles and return raw structured data (for API responses).
        
        This calls the underlying search_codebundles tool and parses the response.
        """
        try:
            result = await self._call_tool("search_codebundles", {
                "query": query,
                "platform": platform,
                "max_results": max_results
            })
            
            if result.get("success"):
                # Parse the markdown response to extract codebundles
                # For now, return an empty list - the markdown response is meant for display
                return []
            return []
        except Exception as e:
            logger.error(f"Raw search failed: {e}")
            return []


class MCPError(Exception):
    """Exception raised for MCP client errors"""
    pass


# Singleton instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get the singleton MCP client instance"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client



