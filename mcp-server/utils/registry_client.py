"""
Registry API Client

Thin HTTP client for the CodeCollection Registry backend API.
All data access goes through the API — the MCP server never
touches the database directly.

Configure via REGISTRY_API_URL environment variable.
"""
import os
import logging
from typing import Dict, Any, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_URL = "http://localhost:8001"
TIMEOUT = 30.0


class RegistryClient:
    """
    HTTP client for the CodeCollection Registry API.
    
    Wraps the backend endpoints that the MCP server tools need.
    """

    def __init__(self, base_url: str = None):
        self.base_url = (base_url or os.getenv("REGISTRY_API_URL", DEFAULT_REGISTRY_URL)).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=TIMEOUT)
        logger.info(f"RegistryClient initialized: {self.base_url}")

    async def health(self) -> Dict[str, Any]:
        """Check backend API health."""
        resp = await self._client.get("/api/v1/health")
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------
    # CodeBundles
    # -----------------------------------------------------------------

    async def search_codebundles(
        self,
        search: str = None,
        platform: str = None,
        tags: str = None,
        collection_slug: str = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search codebundles via the backend text search."""
        params: Dict[str, Any] = {"limit": max_results}
        if search:
            params["search"] = search
        if platform:
            params["platform"] = platform
        if tags:
            params["tags"] = tags
        if collection_slug:
            params["collection_slug"] = collection_slug
        
        resp = await self._client.get("/api/v1/codebundles", params=params)
        resp.raise_for_status()
        data = resp.json()
        # The endpoint returns a list or a paginated object
        if isinstance(data, list):
            return data
        return data.get("items", data.get("codebundles", []))

    async def get_codebundle(
        self, collection_slug: str, codebundle_slug: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single codebundle by collection + codebundle slug."""
        resp = await self._client.get(
            f"/api/v1/collections/{collection_slug}/codebundles/{codebundle_slug}"
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------
    # Collections
    # -----------------------------------------------------------------

    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all codecollections with statistics."""
        resp = await self._client.get("/api/v1/registry/collections")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("collections", data.get("items", []))

    async def get_collection(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a single collection by slug."""
        resp = await self._client.get(f"/api/v1/registry/collections/{slug}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------
    # Tasks
    # -----------------------------------------------------------------

    async def search_tasks(
        self,
        search: str = None,
        support_tags: str = None,
        collection_slug: str = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search tasks across codebundles."""
        params: Dict[str, Any] = {"limit": max_results}
        if search:
            params["search"] = search
        if support_tags:
            params["support_tags"] = support_tags
        if collection_slug:
            params["collection_slug"] = collection_slug

        resp = await self._client.get("/api/v1/registry/tasks", params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("items", data.get("tasks", []))

    # -----------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------

    async def get_stats(self) -> Dict[str, Any]:
        """Get registry-wide statistics."""
        resp = await self._client.get("/api/v1/registry/stats")
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------
    # Vector / semantic search (backed by pgvector in the backend)
    # -----------------------------------------------------------------

    async def vector_search(
        self,
        query: str,
        tables: str = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """Unified semantic search across vector tables."""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if tables:
            params["tables"] = tables
        resp = await self._client.get("/api/v1/vector/search", params=params)
        resp.raise_for_status()
        return resp.json()

    async def vector_search_codebundles(
        self,
        query: str,
        max_results: int = 10,
        platform: str = None,
        collection_slug: str = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over codebundle embeddings."""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if platform:
            params["platform"] = platform
        if collection_slug:
            params["collection_slug"] = collection_slug
        resp = await self._client.get("/api/v1/vector/search/codebundles", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    async def vector_search_documentation(
        self,
        query: str,
        max_results: int = 10,
        category: str = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over documentation embeddings."""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if category:
            params["category"] = category
        resp = await self._client.get("/api/v1/vector/search/documentation", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    async def vector_search_libraries(
        self,
        query: str,
        max_results: int = 10,
        category: str = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over library embeddings."""
        params: Dict[str, Any] = {"query": query, "max_results": max_results}
        if category:
            params["category"] = category
        resp = await self._client.get("/api/v1/vector/search/libraries", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    async def vector_stats(self) -> Dict[str, int]:
        """Return row counts for each vector table."""
        resp = await self._client.get("/api/v1/vector/stats")
        resp.raise_for_status()
        return resp.json()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    async def close(self):
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: Optional[RegistryClient] = None


def get_registry_client() -> RegistryClient:
    """Get or create the singleton RegistryClient."""
    global _client
    if _client is None:
        _client = RegistryClient()
    return _client
