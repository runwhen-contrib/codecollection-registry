#!/usr/bin/env python3
"""
RunWhen Registry MCP Server - HTTP/REST API Version

Provides HTTP endpoints for MCP tools to enable client-server separation.
This is the primary server for production deployments.
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RunWhen Registry MCP Server",
    description="HTTP API for querying RunWhen codecollection data, libraries, and documentation",
    version="1.0.0"
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
    """List all available MCP tools"""
    tools = [
        # === Semantic Search Tools (AI-powered) ===
        {
            "name": "find_codebundle",
            "description": "Find codebundles for your use case. Describe what you need in natural language. Examples: 'troubleshoot Kubernetes pods', 'monitor AWS EKS', 'check database health'",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "What you want to do"},
                "platform": {"type": "string", "optional": True, "description": "Filter by platform: Kubernetes, AWS, Azure, GCP, Linux, Database"},
                "collection": {"type": "string", "optional": True, "description": "Filter by collection slug"},
                "max_results": {"type": "integer", "default": 5}
            }
        },
        {
            "name": "find_codecollection",
            "description": "Find the right codecollection for your use case.",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "What you're looking for"},
                "max_results": {"type": "integer", "default": 3}
            }
        },
        {
            "name": "keyword_usage_help",
            "description": "Get help on how to use RunWhen Robot Framework keywords in your codebundles. Ask questions like 'How do I run kubectl commands?' or 'How do I parse JSON output?'",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "Question about keyword/library usage"},
                "category": {"type": "string", "enum": ["cli", "kubernetes", "aws", "azure", "all"], "default": "all"}
            }
        },
        {
            "name": "find_documentation",
            "description": "Find documentation, guides, examples, and FAQs for CodeBundle development. Ask how-to questions or search for specific topics.",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "What you want to learn about (e.g., 'how to use secrets', 'meta.yaml format')"},
                "category": {"type": "string", "enum": ["documentation", "examples", "libraries", "faq", "all"], "default": "all"},
                "max_results": {"type": "integer", "default": 5}
            }
        },
        # === Basic Search Tools (keyword-based) ===
        {
            "name": "list_codebundles",
            "description": "List all codebundles and codecollections. Supports filtering by collection and output formatting.",
            "parameters": {
                "format": {"type": "string", "enum": ["markdown", "json", "summary"], "default": "markdown"},
                "collection_slug": {"type": "string", "optional": True}
            }
        },
        {
            "name": "search_codebundles",
            "description": "Keyword-based search for codebundles by keywords, tags, or platform. For semantic search, use recommend_codebundle instead.",
            "parameters": {
                "query": {"type": "string", "required": True},
                "tags": {"type": "array", "items": "string", "optional": True},
                "platform": {"type": "string", "optional": True},
                "max_results": {"type": "integer", "default": 10}
            }
        },
        {
            "name": "get_codebundle_details",
            "description": "Get detailed information about a specific codebundle",
            "parameters": {
                "slug": {"type": "string", "required": True},
                "collection_slug": {"type": "string", "optional": True}
            }
        },
        {
            "name": "list_codecollections",
            "description": "List all available codecollections",
            "parameters": {
                "format": {"type": "string", "enum": ["markdown", "json", "summary"], "default": "markdown"}
            }
        },
        {
            "name": "find_library_info",
            "description": "Find information about libraries (keyword search). For more natural queries, use library_usage_help.",
            "parameters": {
                "query": {"type": "string", "required": True},
                "category": {"type": "string", "enum": ["cli", "python", "shell", "all"], "default": "all"}
            }
        },
        {
            "name": "get_development_requirements",
            "description": "Get development requirements, best practices, and documentation for specific features",
            "parameters": {
                "feature": {"type": "string", "required": True}
            }
        }
    ]
    
    return ToolListResponse(tools=tools, count=len(tools))


@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """Call a specific MCP tool"""
    try:
        tool_name = request.tool_name
        arguments = request.arguments
        
        logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")
        
        # Route to appropriate handler
        # Semantic search tools (AI-powered)
        if tool_name == "find_codebundle":
            result = await handle_find_codebundle(arguments)
        elif tool_name == "find_codecollection":
            result = await handle_find_codecollection(arguments)
        elif tool_name == "keyword_usage_help":
            result = await handle_keyword_usage_help(arguments)
        elif tool_name == "find_documentation":
            result = await handle_find_documentation(arguments)
        # Basic search tools (keyword-based)
        elif tool_name == "list_codebundles":
            result = await handle_list_codebundles(arguments)
        elif tool_name == "search_codebundles":
            result = await handle_search_codebundles(arguments)
        elif tool_name == "get_codebundle_details":
            result = await handle_get_codebundle_details(arguments)
        elif tool_name == "list_codecollections":
            result = await handle_list_codecollections(arguments)
        elif tool_name == "find_library_info":
            result = await handle_find_library_info(arguments)
        elif tool_name == "get_development_requirements":
            result = await handle_get_development_requirements(arguments)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
        
        return ToolCallResponse(
            success=True,
            result=result,
            metadata={"tool": tool_name, "timestamp": datetime.utcnow().isoformat()}
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


# ============================================================================
# Semantic Search Tool Handlers (AI-powered)
# ============================================================================

async def handle_find_codebundle(arguments: Dict[str, Any]) -> str:
    """Handle find_codebundle tool call"""
    query = arguments.get("query", "")
    platform = arguments.get("platform")
    collection = arguments.get("collection")
    max_results = arguments.get("max_results", 5)
    
    if not query:
        return "Error: query is required"
    
    ss = get_semantic_search_instance()
    
    if not ss.is_available:
        # Fall back to keyword search
        logger.info("Semantic search unavailable, falling back to keyword search")
        return await handle_search_codebundles({
            "query": query,
            "platform": platform,
            "max_results": max_results
        })
    
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
        output += f"## {i}. {rec.display_name}\n\n"
        output += f"**Collection:** `{rec.collection_slug}`\n\n"
        output += f"**Platform:** {rec.platform}\n\n"
        output += f"**Description:** {rec.description}\n\n"
        if rec.tags:
            output += f"**Tags:** {', '.join(rec.tags)}\n\n"
        output += f"**Relevance:** {rec.score:.0%}\n\n"
        output += f"**Source:** [View on GitHub]({rec.git_url})\n\n"
        output += "---\n\n"
    
    return output


async def handle_find_codecollection(arguments: Dict[str, Any]) -> str:
    """Handle find_codecollection tool call"""
    query = arguments.get("query", "")
    max_results = arguments.get("max_results", 3)
    
    if not query:
        return "Error: query is required"
    
    ss = get_semantic_search_instance()
    
    if not ss.is_available:
        # Fall back to listing all collections
        return await handle_list_codecollections({"format": "markdown"})
    
    recommendations = ss.recommend_codecollections(
        query=query,
        max_results=max_results
    )
    
    if not recommendations:
        return f"No codecollections found matching: {query}"
    
    output = f"# CodeCollections for: {query}\n\n"
    
    for i, rec in enumerate(recommendations, 1):
        output += f"## {i}. {rec['name']}\n\n"
        output += f"**Slug:** `{rec['slug']}`\n\n"
        output += f"**Description:** {rec['description']}\n\n"
        output += f"**Repository:** [{rec['git_url']}]({rec['git_url']})\n\n"
        output += f"**Relevance:** {rec['score']:.0%}\n\n"
        output += "---\n\n"
    
    return output


async def handle_keyword_usage_help(arguments: Dict[str, Any]) -> str:
    """Handle keyword_usage_help tool call"""
    query = arguments.get("query", "")
    category = arguments.get("category", "all")
    
    if not query:
        return "Error: query is required"
    
    ss = get_semantic_search_instance()
    
    if not ss.is_available:
        # Fall back to keyword search
        return await handle_find_library_info({
            "query": query,
            "category": category
        })
    
    results = ss.search_libraries(
        query=query,
        category=category if category != "all" else None,
        max_results=5
    )
    
    if not results:
        return f"No keyword libraries found matching: {query}\n\nTry different keywords or browse all keyword libraries."
    
    output = f"# Keyword Usage Help: {query}\n\n"
    output += f"Found {len(results)} relevant keyword library/libraries:\n\n"
    
    for i, lib in enumerate(results, 1):
        output += f"## {i}. {lib['name']}\n\n"
        output += f"**Category:** {lib['category']}\n\n"
        if lib.get('import_path'):
            output += f"**Import:** `from {lib['import_path']} import {lib['name']}`\n\n"
        if lib.get('collection_slug'):
            output += f"**Collection:** `{lib['collection_slug']}`\n\n"
        output += f"**Description:** {lib['description']}\n\n"
        if lib.get('git_url'):
            output += f"**Source:** [View on GitHub]({lib['git_url']})\n\n"
        output += f"**Relevance:** {lib['score']:.0%}\n\n"
        output += "---\n\n"
    
    return output


async def handle_find_documentation(arguments: Dict[str, Any]) -> str:
    """Handle find_documentation tool call"""
    query = arguments.get("query", "")
    category = arguments.get("category", "all")
    max_results = arguments.get("max_results", 5)
    
    if not query:
        return "Error: query is required"
    
    ss = get_semantic_search_instance()
    
    if not ss.is_available:
        return "Documentation search is not available. Vector store not initialized."
    
    results = ss.search_documentation(
        query=query,
        category=category if category != "all" else None,
        max_results=max_results
    )
    
    if not results:
        return f"No documentation found matching: {query}\n\nTry different keywords or check the official RunWhen documentation at https://docs.runwhen.com"
    
    output = f"# Documentation: {query}\n\n"
    output += f"Found {len(results)} relevant resource(s):\n\n"
    
    for i, doc in enumerate(results, 1):
        output += f"## {i}. {doc['name']}\n\n"
        output += f"**Category:** {doc['category']}\n\n"
        if doc.get('description'):
            output += f"**Description:** {doc['description']}\n\n"
        if doc.get('topics'):
            output += f"**Topics:** {', '.join(doc['topics'])}\n\n"
        if doc.get('url'):
            output += f"**Link:** [{doc['url']}]({doc['url']})\n\n"
        output += f"**Relevance:** {doc['score']:.0%}\n\n"
        output += "---\n\n"
    
    return output


# ============================================================================
# Tool Handler Functions (keyword-based)
# ============================================================================

async def handle_list_codebundles(arguments: Dict[str, Any]) -> str:
    """Handle list_codebundles tool call"""
    format_type = arguments.get("format", "markdown")
    collection_slug = arguments.get("collection_slug")
    
    # Load data
    codebundles = data_loader.load_codebundles()
    collections = data_loader.load_codecollections()
    
    # Filter by collection if specified
    if collection_slug:
        codebundles = [cb for cb in codebundles if cb.get("collection_slug") == collection_slug]
    
    # Format output
    if format_type == "json":
        result = json.dumps({
            "codecollections": collections,
            "codebundles": codebundles,
            "total_collections": len(collections),
            "total_codebundles": len(codebundles)
        }, indent=2)
    
    elif format_type == "summary":
        result = f"# RunWhen Registry Summary\n\n"
        result += f"**Total CodeCollections:** {len(collections)}\n"
        result += f"**Total CodeBundles:** {len(codebundles)}\n\n"
        
        for cc in collections:
            cc_bundles = [cb for cb in codebundles if cb.get("collection_slug") == cc["slug"]]
            result += f"- **{cc['name']}** ({cc['slug']}): {len(cc_bundles)} codebundles\n"
    
    else:  # markdown
        result = "# RunWhen CodeCollections and CodeBundles\n\n"
        
        for cc in collections:
            cc_bundles = [cb for cb in codebundles if cb.get("collection_slug") == cc["slug"]]
            
            result += f"## {cc['name']}\n\n"
            result += f"**Slug:** `{cc['slug']}`\n\n"
            result += f"**Description:** {cc.get('description', 'N/A')}\n\n"
            result += f"**CodeBundles ({len(cc_bundles)}):**\n\n"
            
            if cc_bundles:
                for cb in cc_bundles:
                    result += f"### {cb.get('display_name', cb.get('name'))}\n\n"
                    result += f"- **Slug:** `{cb['slug']}`\n"
                    result += f"- **Description:** {cb.get('description', 'N/A')}\n"
                    result += f"- **Platform:** {cb.get('platform', 'N/A')}\n\n"
    
    return result


async def handle_search_codebundles(arguments: Dict[str, Any]) -> str:
    """Handle search_codebundles tool call"""
    query = arguments.get("query", "")
    tags = arguments.get("tags", [])
    platform = arguments.get("platform")
    max_results = arguments.get("max_results", 10)
    
    codebundles = data_loader.load_codebundles()
    
    results = search_engine.search_codebundles(
        codebundles=codebundles,
        query=query,
        tags=tags,
        platform=platform,
        max_results=max_results
    )
    
    if not results:
        return f"No codebundles found matching query: {query}"
    
    output = f"# Search Results for: {query}\n\nFound {len(results)} relevant codebundle(s):\n\n"
    
    for i, cb in enumerate(results, 1):
        output += f"## {i}. {cb.get('display_name', cb.get('name'))}\n\n"
        output += f"- **Slug:** `{cb['slug']}`\n"
        output += f"- **Collection:** {cb.get('collection_slug', 'N/A')}\n"
        output += f"- **Description:** {cb.get('description', 'N/A')}\n"
        output += f"- **Platform:** {cb.get('platform', 'N/A')}\n\n"
    
    return output


async def handle_get_codebundle_details(arguments: Dict[str, Any]) -> str:
    """Handle get_codebundle_details tool call"""
    slug = arguments.get("slug")
    collection_slug = arguments.get("collection_slug")
    
    cb = data_loader.get_codebundle_by_slug(slug, collection_slug)
    
    if not cb:
        return f"Codebundle not found: {slug}"
    
    output = f"# {cb.get('display_name', cb.get('name'))}\n\n"
    output += f"**Slug:** `{cb['slug']}`\n\n"
    output += f"## Description\n\n{cb.get('description', 'No description available')}\n\n"
    
    return output


async def handle_list_codecollections(arguments: Dict[str, Any]) -> str:
    """Handle list_codecollections tool call"""
    format_type = arguments.get("format", "markdown")
    collections = data_loader.load_codecollections()
    
    if format_type == "json":
        return json.dumps({"codecollections": collections}, indent=2)
    
    result = "# RunWhen CodeCollections\n\n"
    for cc in collections:
        result += f"## {cc['name']}\n\n"
        result += f"- **Slug:** `{cc['slug']}`\n"
        result += f"- **Description:** {cc.get('description', 'N/A')}\n\n"
    
    return result


async def handle_find_library_info(arguments: Dict[str, Any]) -> str:
    """Handle find_library_info tool call"""
    query = arguments.get("query", "")
    category = arguments.get("category", "all")
    
    libraries = data_loader.load_libraries()
    results = search_engine.search_libraries(
        libraries=libraries,
        query=query,
        category=category,
        max_results=5
    )
    
    if not results:
        return f"No libraries found matching: {query}"
    
    output = f"# Library Search Results: {query}\n\n"
    for i, lib in enumerate(results, 1):
        output += f"## {i}. {lib['name']}\n\n"
        output += f"**Description:** {lib.get('description', 'N/A')}\n\n"
    
    return output


async def handle_get_development_requirements(arguments: Dict[str, Any]) -> str:
    """Handle get_development_requirements tool call"""
    feature = arguments.get("feature", "").lower()
    
    resources = data_loader.load_documentation_resources()
    results = search_engine.search_documentation(resources, feature, max_results=5)
    
    if not results:
        return f"No documentation found for feature: {feature}"
    
    output = f"# Development Requirements: {feature}\n\n"
    for i, doc in enumerate(results, 1):
        output += f"## {i}. {doc['title']}\n\n"
        output += f"**Description:** {doc.get('description', 'N/A')}\n\n"
    
    return output


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

