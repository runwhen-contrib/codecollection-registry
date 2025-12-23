#!/usr/bin/env python3
"""
RunWhen Registry MCP Server - HTTP/REST API Version

Provides HTTP endpoints for MCP tools to enable client-server separation.
This is the primary server for production deployments.

Tools are now organized in the tools/ directory:
- tools/base.py - Base classes and registry
- tools/codebundle_tools.py - CodeBundle search/list/details
- tools/collection_tools.py - CodeCollection tools
- tools/library_tools.py - Library and keyword help
- tools/documentation_tools.py - Documentation search
- tools/github_issue.py - GitHub issue creation
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from utils.data_loader import DataLoader
from utils.search import SearchEngine
from utils.semantic_search import get_semantic_search, SemanticSearch

# Import the tool registry
from tools import register_all_tools, get_tool_registry
from tools.github_issue import get_github_client, CodeBundleRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RunWhen Registry MCP Server",
    description="HTTP API for querying RunWhen codecollection data, libraries, and documentation",
    version="2.0.0"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data loader and search engine
data_loader = DataLoader()
search_engine = SearchEngine()

# Initialize semantic search (lazy loading)
semantic_search: SemanticSearch = None

def get_semantic_search_instance() -> SemanticSearch:
    """Get or create semantic search instance"""
    global semantic_search
    if semantic_search is None:
        semantic_search = get_semantic_search()
    return semantic_search


# Initialize tool registry on startup
@app.on_event("startup")
async def startup_event():
    """Register all tools on startup"""
    logger.info("Registering MCP tools...")
    registry = register_all_tools(
        semantic_search_getter=get_semantic_search_instance,
        data_loader=data_loader,
        search_engine=search_engine
    )
    logger.info(f"Registered {registry.count} tools")


# ============================================================================
# Request/Response Models
# ============================================================================

class ToolListResponse(BaseModel):
    tools: List[Dict[str, Any]]
    count: int


class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolCallResponse(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    data_stats: Dict[str, int]
    semantic_search: Optional[Dict[str, Any]] = None


# ============================================================================
# Health and Info Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "RunWhen Registry MCP Server",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "tools": "/tools"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Load data to verify it's accessible
        codebundles = data_loader.load_codebundles()
        collections = data_loader.load_codecollections()
        libraries = data_loader.load_libraries()
        docs = data_loader.load_documentation_resources()
        
        # Check semantic search status
        semantic_stats = None
        try:
            ss = get_semantic_search_instance()
            semantic_stats = ss.get_stats()
        except Exception as e:
            semantic_stats = {"error": str(e), "is_available": False}
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.utcnow().isoformat(),
            data_stats={
                "codebundles": len(codebundles),
                "collections": len(collections),
                "libraries": len(libraries),
                "documentation": len(docs)
            },
            semantic_search=semantic_stats
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# ============================================================================
# MCP Tool Endpoints
# ============================================================================

@app.get("/tools", response_model=ToolListResponse)
async def list_tools():
    """List all available MCP tools from the registry"""
    registry = get_tool_registry()
    tools = registry.list_tools()
    return ToolListResponse(tools=tools, count=len(tools))


@app.get("/tools/by-category/{category}", response_model=ToolListResponse)
async def list_tools_by_category(category: str):
    """List tools filtered by category (search, info, action)"""
    registry = get_tool_registry()
    tools = registry.list_by_category(category)
    return ToolListResponse(tools=tools, count=len(tools))


@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """Call a specific MCP tool using the registry"""
    try:
        tool_name = request.tool_name
        arguments = request.arguments
        
        logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")
        
        # Use the tool registry
        registry = get_tool_registry()
        
        try:
            result = await registry.execute(tool_name, arguments)
            return ToolCallResponse(
                success=True,
                result=result,
                metadata={"tool": tool_name, "timestamp": datetime.utcnow().isoformat()}
            )
        except ValueError as e:
            # Unknown tool
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return ToolCallResponse(
                success=False,
                error=str(e),
                metadata={"tool": tool_name}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling tool {request.tool_name}: {e}", exc_info=True)
        return ToolCallResponse(
            success=False,
            error=str(e),
            metadata={"tool": request.tool_name}
        )


# =============================================================================
# Legacy Tool Handlers (for backward compatibility with existing handler functions)
# These will be removed once all code uses the registry directly
# =============================================================================

# Legacy handler imports for REST endpoints that don't use the registry yet
async def _legacy_call_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Legacy tool call - uses registry"""
    registry = get_tool_registry()
    return await registry.execute(tool_name, arguments)


# Backward compatibility aliases for direct handler calls
async def handle_find_codebundle(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("find_codebundle", arguments)

async def handle_find_codecollection(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("find_codecollection", arguments)

async def handle_keyword_usage_help(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("keyword_usage_help", arguments)

async def handle_find_documentation(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("find_documentation", arguments)

async def handle_list_codebundles(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("list_codebundles", arguments)

async def handle_search_codebundles(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("search_codebundles", arguments)

async def handle_get_codebundle_details(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("get_codebundle_details", arguments)

async def handle_list_codecollections(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("list_codecollections", arguments)

async def handle_find_library_info(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("find_library_info", arguments)

async def handle_get_development_requirements(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("get_development_requirements", arguments)

async def handle_request_codebundle(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("request_codebundle", arguments)

async def handle_check_existing_requests(arguments: Dict[str, Any]) -> str:
    return await _legacy_call_tool("check_existing_requests", arguments)




# ============================================================================
# Direct REST Endpoints (Alternative to tool calling pattern)
# ============================================================================

@app.get("/api/codebundles", response_model=Dict[str, Any])
async def get_codebundles(
    format: str = Query("json", enum=["markdown", "json", "summary"]),
    collection_slug: Optional[str] = None
):
    """Get all codebundles (REST endpoint)"""
    result = await handle_list_codebundles({"format": format, "collection_slug": collection_slug})
    
    if format == "json":
        return json.loads(result)
    else:
        return {"result": result, "format": format}


@app.get("/api/codebundles/search", response_model=Dict[str, Any])
async def search_codebundles_api(
    query: str,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    platform: Optional[str] = None,
    max_results: int = 10
):
    """Search codebundles (REST endpoint)"""
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    
    result = await handle_search_codebundles({
        "query": query,
        "tags": tag_list,
        "platform": platform,
        "max_results": max_results
    })
    
    return {"result": result, "query": query}


@app.get("/api/codebundles/{slug}", response_model=Dict[str, Any])
async def get_codebundle_by_slug(
    slug: str,
    collection_slug: Optional[str] = None
):
    """Get specific codebundle by slug (REST endpoint)"""
    result = await handle_get_codebundle_details({
        "slug": slug,
        "collection_slug": collection_slug
    })
    
    return {"result": result, "slug": slug}


@app.get("/api/collections", response_model=Dict[str, Any])
async def get_collections(
    format: str = Query("json", enum=["markdown", "json", "summary"])
):
    """Get all codecollections (REST endpoint)"""
    result = await handle_list_codecollections({"format": format})
    
    if format == "json":
        return json.loads(result)
    else:
        return {"result": result, "format": format}


@app.get("/api/libraries/search", response_model=Dict[str, Any])
async def search_libraries_api(
    query: str,
    category: str = Query("all", enum=["cli", "python", "shell", "all"])
):
    """Search libraries (REST endpoint)"""
    result = await handle_find_library_info({
        "query": query,
        "category": category
    })
    
    return {"result": result, "query": query}


@app.get("/api/docs/requirements", response_model=Dict[str, Any])
async def get_dev_requirements(feature: str):
    """Get development requirements (REST endpoint)"""
    result = await handle_get_development_requirements({"feature": feature})
    
    return {"result": result, "feature": feature}


@app.get("/api/docs/list", response_model=Dict[str, Any])
async def list_managed_docs():
    """List all managed documentation from docs.yaml"""
    try:
        from tools.documentation_tools import get_doc_manager
        
        doc_manager = get_doc_manager()
        categories = doc_manager.list_categories()
        all_urls = doc_manager.get_all_urls()
        
        # Group by category
        by_category = {}
        for cat in categories:
            docs = doc_manager.get_by_category(cat)
            by_category[cat] = [
                {"name": d.name, "url": d.url, "description": d.description[:100] + "..." if len(d.description) > 100 else d.description}
                for d in docs
            ]
        
        return {
            "total": len(all_urls),
            "categories": categories,
            "docs_by_category": by_category
        }
    except Exception as e:
        logger.error(f"Error listing docs: {e}")
        return {"error": str(e), "total": 0, "categories": []}


@app.get("/api/docs/search", response_model=Dict[str, Any])
async def search_docs_api(query: str, limit: int = 5):
    """Search managed documentation (REST endpoint)"""
    result = await handle_find_documentation({"query": query, "max_results": limit})
    return {"result": result, "query": query}


# ============================================================================
# Server Startup
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Default configuration
    host = "0.0.0.0"
    port = 8000
    
    # Allow configuration via command line
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    logger.info(f"Starting RunWhen Registry MCP Server on http://{host}:{port}")
    logger.info(f"API Documentation: http://{host}:{port}/docs")
    logger.info(f"Health Check: http://{host}:{port}/health")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )

