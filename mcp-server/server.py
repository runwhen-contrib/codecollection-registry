#!/usr/bin/env python3
"""
RunWhen Registry MCP Server

A Model Context Protocol server for querying RunWhen codecollection data,
libraries, and documentation resources.
"""
import asyncio
import json
import sys
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from utils.data_loader import DataLoader
from utils.search import SearchEngine


# Initialize data loader
data_loader = DataLoader()
search_engine = SearchEngine()

# Create MCP server
app = Server("runwhen-registry")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="list_codebundles",
            description=(
                "List all codebundles and codecollections. "
                "Supports filtering by collection and output formatting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json", "summary"],
                        "default": "markdown",
                        "description": "Output format"
                    },
                    "collection_slug": {
                        "type": "string",
                        "description": "Filter by codecollection slug (optional)"
                    }
                }
            }
        ),
        Tool(
            name="search_codebundles",
            description=(
                "Search for codebundles by keywords, tags, or use case. "
                "Returns relevant codebundles with relevance scoring."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query or keywords"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by support tags (optional)"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Filter by platform (kubernetes, aws, gcp, azure, generic)"
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_codebundle_details",
            description="Get detailed information about a specific codebundle",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Codebundle slug"
                    },
                    "collection_slug": {
                        "type": "string",
                        "description": "CodeCollection slug (optional)"
                    }
                },
                "required": ["slug"]
            }
        ),
        Tool(
            name="list_codecollections",
            description="List all available codecollections",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json", "summary"],
                        "default": "markdown",
                        "description": "Output format"
                    }
                }
            }
        ),
        Tool(
            name="find_library_info",
            description=(
                "Find information about libraries and how to use them. "
                "Useful for questions like 'which library do I use to run shell scripts?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query about library usage"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["cli", "python", "shell", "all"],
                        "default": "all",
                        "description": "Library category"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_development_requirements",
            description=(
                "Get development requirements, best practices, and documentation "
                "for specific features (e.g., secrets, environment variables, IAM)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "feature": {
                        "type": "string",
                        "description": "Feature name (e.g., 'secrets', 'environment variables', 'iam')"
                    }
                },
                "required": ["feature"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "list_codebundles":
            return await handle_list_codebundles(arguments)
        elif name == "search_codebundles":
            return await handle_search_codebundles(arguments)
        elif name == "get_codebundle_details":
            return await handle_get_codebundle_details(arguments)
        elif name == "list_codecollections":
            return await handle_list_codecollections(arguments)
        elif name == "find_library_info":
            return await handle_find_library_info(arguments)
        elif name == "get_development_requirements":
            return await handle_get_development_requirements(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]


async def handle_list_codebundles(arguments: Dict[str, Any]) -> List[TextContent]:
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
        
        # Group codebundles by collection
        for cc in collections:
            cc_bundles = [cb for cb in codebundles if cb.get("collection_slug") == cc["slug"]]
            
            result += f"## {cc['name']}\n\n"
            result += f"**Slug:** `{cc['slug']}`\n\n"
            result += f"**Description:** {cc.get('description', 'N/A')}\n\n"
            result += f"**Repository:** {cc.get('git_url', 'N/A')}\n\n"
            result += f"**CodeBundles ({len(cc_bundles)}):**\n\n"
            
            if cc_bundles:
                for cb in cc_bundles:
                    result += f"### {cb.get('display_name', cb.get('name'))}\n\n"
                    result += f"- **Slug:** `{cb['slug']}`\n"
                    result += f"- **Description:** {cb.get('description', 'N/A')}\n"
                    result += f"- **Tags:** {', '.join(cb.get('support_tags', []))}\n"
                    result += f"- **Platform:** {cb.get('platform', 'N/A')}\n"
                    result += f"- **Use Cases:** {', '.join(cb.get('use_cases', []))}\n"
                    
                    if cb.get('tasks'):
                        result += f"- **Tasks:** {len(cb['tasks'])} task(s)\n"
                    
                    if cb.get('documentation_url'):
                        result += f"- **Documentation:** {cb['documentation_url']}\n"
                    
                    result += "\n"
            else:
                result += "*No codebundles found*\n\n"
    
    return [TextContent(type="text", text=result)]


async def handle_search_codebundles(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle search_codebundles tool call"""
    query = arguments.get("query", "")
    tags = arguments.get("tags", [])
    platform = arguments.get("platform")
    max_results = arguments.get("max_results", 10)
    
    # Load codebundles
    codebundles = data_loader.load_codebundles()
    
    # Search
    results = search_engine.search_codebundles(
        codebundles=codebundles,
        query=query,
        tags=tags,
        platform=platform,
        max_results=max_results
    )
    
    # Format results
    if not results:
        return [TextContent(type="text", text=f"No codebundles found matching query: {query}")]
    
    output = f"# Search Results for: {query}\n\n"
    output += f"Found {len(results)} relevant codebundle(s):\n\n"
    
    for i, cb in enumerate(results, 1):
        output += f"## {i}. {cb.get('display_name', cb.get('name'))}\n\n"
        output += f"- **Slug:** `{cb['slug']}`\n"
        output += f"- **Collection:** {cb.get('collection_slug', 'N/A')}\n"
        output += f"- **Description:** {cb.get('description', 'N/A')}\n"
        output += f"- **Platform:** {cb.get('platform', 'N/A')}\n"
        output += f"- **Tags:** {', '.join(cb.get('support_tags', []))}\n"
        output += f"- **Use Cases:** {', '.join(cb.get('use_cases', []))}\n"
        output += f"- **Access Level:** {cb.get('access_level', 'unknown')}\n"
        
        if cb.get('tasks'):
            output += f"- **Tasks ({len(cb['tasks'])}):**\n"
            for task in cb['tasks'][:3]:  # Show first 3 tasks
                task_name = task.get('name', task) if isinstance(task, dict) else task
                output += f"  - {task_name}\n"
            if len(cb['tasks']) > 3:
                output += f"  - ... and {len(cb['tasks']) - 3} more\n"
        
        if cb.get('libraries_used'):
            output += f"- **Libraries Used:** {', '.join(cb['libraries_used'])}\n"
        
        if cb.get('documentation_url'):
            output += f"- **Documentation:** {cb['documentation_url']}\n"
        
        output += "\n"
    
    return [TextContent(type="text", text=output)]


async def handle_get_codebundle_details(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle get_codebundle_details tool call"""
    slug = arguments.get("slug")
    collection_slug = arguments.get("collection_slug")
    
    # Find codebundle
    cb = data_loader.get_codebundle_by_slug(slug, collection_slug)
    
    if not cb:
        return [TextContent(type="text", text=f"Codebundle not found: {slug}")]
    
    # Format detailed output
    output = f"# {cb.get('display_name', cb.get('name'))}\n\n"
    output += f"**Slug:** `{cb['slug']}`\n\n"
    output += f"**Collection:** {cb.get('collection_slug', 'N/A')}\n\n"
    output += f"**Platform:** {cb.get('platform', 'N/A')}\n\n"
    
    output += f"## Description\n\n{cb.get('description', 'No description available')}\n\n"
    
    output += f"## Metadata\n\n"
    output += f"- **Access Level:** {cb.get('access_level', 'unknown')}\n"
    output += f"- **Support Tags:** {', '.join(cb.get('support_tags', []))}\n"
    output += f"- **Use Cases:** {', '.join(cb.get('use_cases', []))}\n\n"
    
    if cb.get('tasks'):
        output += f"## Tasks ({len(cb['tasks'])})\n\n"
        for task in cb['tasks']:
            if isinstance(task, dict):
                output += f"### {task.get('name')}\n\n"
                output += f"{task.get('description', 'No description')}\n\n"
                if task.get('tags'):
                    output += f"**Tags:** {', '.join(task['tags'])}\n\n"
            else:
                output += f"- {task}\n"
        output += "\n"
    
    if cb.get('slis'):
        output += f"## SLIs (Service Level Indicators)\n\n"
        for sli in cb['slis']:
            output += f"- {sli}\n"
        output += "\n"
    
    if cb.get('libraries_used'):
        output += f"## Libraries Used\n\n"
        for lib in cb['libraries_used']:
            output += f"- `{lib}`\n"
        output += "\n"
    
    if cb.get('iam_requirements'):
        output += f"## IAM Requirements\n\n"
        for req in cb['iam_requirements']:
            output += f"- {req}\n"
        output += "\n"
    
    if cb.get('documentation_url'):
        output += f"## Documentation\n\n{cb['documentation_url']}\n\n"
    
    return [TextContent(type="text", text=output)]


async def handle_list_codecollections(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle list_codecollections tool call"""
    format_type = arguments.get("format", "markdown")
    
    # Load collections
    collections = data_loader.load_codecollections()
    
    if format_type == "json":
        result = json.dumps({"codecollections": collections}, indent=2)
    
    elif format_type == "summary":
        result = f"# RunWhen CodeCollections\n\n"
        result += f"**Total:** {len(collections)}\n\n"
        for cc in collections:
            result += f"- **{cc['name']}** (`{cc['slug']}`): {cc.get('description', 'N/A')}\n"
    
    else:  # markdown
        result = "# RunWhen CodeCollections\n\n"
        for cc in collections:
            result += f"## {cc['name']}\n\n"
            result += f"- **Slug:** `{cc['slug']}`\n"
            result += f"- **Description:** {cc.get('description', 'N/A')}\n"
            result += f"- **Repository:** {cc.get('git_url', 'N/A')}\n"
            result += f"- **Branch:** {cc.get('git_ref', 'main')}\n"
            result += f"- **Owner:** {cc.get('owner', 'N/A')}\n"
            result += f"- **Primary Language:** {cc.get('primary_language', 'N/A')}\n"
            result += f"- **Tags:** {', '.join(cc.get('tags', []))}\n"
            result += f"- **Codebundle Count:** {cc.get('codebundle_count', 0)}\n\n"
    
    return [TextContent(type="text", text=result)]


async def handle_find_library_info(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle find_library_info tool call"""
    query = arguments.get("query", "")
    category = arguments.get("category", "all")
    
    # Load libraries
    libraries = data_loader.load_libraries()
    
    # Search
    results = search_engine.search_libraries(
        libraries=libraries,
        query=query,
        category=category,
        max_results=5
    )
    
    if not results:
        return [TextContent(type="text", text=f"No libraries found matching: {query}")]
    
    # Format results
    output = f"# Library Search Results: {query}\n\n"
    output += f"Found {len(results)} relevant library/libraries:\n\n"
    
    for i, lib in enumerate(results, 1):
        output += f"## {i}. {lib['name']}\n\n"
        output += f"**Category:** {lib.get('category', 'N/A')}\n\n"
        output += f"**Description:** {lib.get('description', 'N/A')}\n\n"
        
        if lib.get('common_use_cases'):
            output += f"### Common Use Cases\n\n"
            for use_case in lib['common_use_cases']:
                output += f"- {use_case}\n"
            output += "\n"
        
        if lib.get('usage_example'):
            output += f"### Usage Example\n\n```python\n{lib['usage_example']}\n```\n\n"
        
        if lib.get('parameters'):
            output += f"### Parameters\n\n"
            for param, desc in lib['parameters'].items():
                output += f"- **{param}:** {desc}\n"
            output += "\n"
        
        if lib.get('requirements'):
            output += f"### Requirements\n\n"
            for req in lib['requirements']:
                output += f"- {req}\n"
            output += "\n"
        
        if lib.get('documentation_url'):
            output += f"### Documentation\n\n{lib['documentation_url']}\n\n"
        
        output += "---\n\n"
    
    return [TextContent(type="text", text=output)]


async def handle_get_development_requirements(arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle get_development_requirements tool call"""
    feature = arguments.get("feature", "").lower()
    
    # Load documentation resources
    resources = data_loader.load_documentation_resources()
    
    # Search for relevant documentation
    results = search_engine.search_documentation(resources, feature, max_results=5)
    
    if not results:
        return [TextContent(type="text", text=f"No documentation found for feature: {feature}")]
    
    # Format results
    output = f"# Development Requirements: {feature}\n\n"
    output += f"Found {len(results)} relevant documentation resource(s):\n\n"
    
    for i, doc in enumerate(results, 1):
        output += f"## {i}. {doc['title']}\n\n"
        output += f"**URL:** {doc.get('url', 'N/A')}\n\n"
        output += f"**Description:** {doc.get('description', 'N/A')}\n\n"
        
        if doc.get('topics'):
            output += f"**Topics:** {', '.join(doc['topics'])}\n\n"
        
        if doc.get('key_points'):
            output += f"### Key Points\n\n"
            for point in doc['key_points']:
                output += f"- {point}\n"
            output += "\n"
        
        if doc.get('requirements'):
            output += f"### Requirements\n\n"
            reqs = doc['requirements']
            if isinstance(reqs, dict):
                for key, value in reqs.items():
                    if isinstance(value, list):
                        output += f"**{key}:** {', '.join(value)}\n\n"
                    else:
                        output += f"**{key}:** {value}\n\n"
            output += "\n"
        
        if doc.get('platforms'):
            output += f"### Platform-Specific Information\n\n"
            for platform, info in doc['platforms'].items():
                output += f"#### {platform.upper()}\n\n"
                if isinstance(info, dict):
                    for key, value in info.items():
                        output += f"**{key}:**\n"
                        if isinstance(value, list):
                            for item in value:
                                output += f"- `{item}`\n"
                        output += "\n"
        
        output += "---\n\n"
    
    return [TextContent(type="text", text=output)]


async def main():
    """Main entry point for the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

