"""
MCP Server Tools Package

This package contains all the tools available in the MCP server, organized
following a standard MCP tool pattern.

Tools are organized by category:
- codebundle_tools: Finding, listing, searching CodeBundles
- collection_tools: Finding and listing CodeCollections  
- library_tools: Help with Robot Framework libraries
- documentation_tools: Documentation, guides, and FAQs
- github_issue: Creating GitHub issues for new CodeBundle requests

Usage:
    from tools import get_tool_registry, register_all_tools
    
    # Register all tools
    registry = register_all_tools(semantic_search_getter, data_loader, search_engine)
    
    # List available tools
    tools = registry.list_tools()
    
    # Execute a tool
    result = await registry.execute("find_codebundle", {"query": "kubernetes health"})
"""

from typing import Callable, Any

# Base classes
from .base import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolRegistry,
    get_tool_registry
)

# CodeBundle tools
from .codebundle_tools import (
    FindCodeBundleTool,
    ListCodeBundlesTool,
    SearchCodeBundlesTool,
    GetCodeBundleDetailsTool
)

# Collection tools
from .collection_tools import (
    FindCodeCollectionTool,
    ListCodeCollectionsTool
)

# Library tools
from .library_tools import (
    KeywordUsageHelpTool,
    FindLibraryInfoTool
)

# Documentation tools
from .documentation_tools import (
    FindDocumentationTool,
    GetDevelopmentRequirementsTool,
    DocumentationManager,
    get_doc_manager
)

# GitHub issue tools
from .github_issue import (
    RequestCodeBundleTool,
    CheckExistingRequestsTool,
    GitHubIssueClient,
    CodeBundleRequest,
    get_github_client,
    get_github_tool  # Legacy alias
)


def register_all_tools(
    semantic_search_getter: Callable,
    data_loader: Any,
    search_engine: Any
) -> ToolRegistry:
    """
    Register all available MCP tools with the registry.
    
    Args:
        semantic_search_getter: Callable that returns SemanticSearch instance
        data_loader: DataLoader instance for loading data
        search_engine: SearchEngine instance for keyword search
    
    Returns:
        Configured ToolRegistry with all tools registered
    """
    registry = get_tool_registry()
    
    # Clear existing tools if re-registering
    registry._tools.clear()
    
    # Register CodeBundle tools
    registry.register(FindCodeBundleTool(semantic_search_getter))
    registry.register(ListCodeBundlesTool(data_loader))
    registry.register(SearchCodeBundlesTool(search_engine))
    registry.register(GetCodeBundleDetailsTool(data_loader))
    
    # Register Collection tools
    registry.register(FindCodeCollectionTool(semantic_search_getter))
    registry.register(ListCodeCollectionsTool(data_loader))
    
    # Register Library tools
    registry.register(KeywordUsageHelpTool(semantic_search_getter))
    registry.register(FindLibraryInfoTool(search_engine))
    
    # Register Documentation tools
    registry.register(FindDocumentationTool(semantic_search_getter))
    registry.register(GetDevelopmentRequirementsTool(data_loader))
    
    # Register GitHub Issue tools
    registry.register(RequestCodeBundleTool())
    registry.register(CheckExistingRequestsTool())
    
    return registry


__all__ = [
    # Base classes
    'BaseTool',
    'ToolDefinition',
    'ToolParameter',
    'ToolRegistry',
    'get_tool_registry',
    
    # Registration
    'register_all_tools',
    
    # CodeBundle tools
    'FindCodeBundleTool',
    'ListCodeBundlesTool',
    'SearchCodeBundlesTool',
    'GetCodeBundleDetailsTool',
    
    # Collection tools
    'FindCodeCollectionTool',
    'ListCodeCollectionsTool',
    
    # Library tools
    'KeywordUsageHelpTool',
    'FindLibraryInfoTool',
    
    # Documentation tools
    'FindDocumentationTool',
    'GetDevelopmentRequirementsTool',
    'DocumentationManager',
    'get_doc_manager',
    
    # GitHub tools
    'RequestCodeBundleTool',
    'CheckExistingRequestsTool',
    'GitHubIssueClient',
    'CodeBundleRequest',
    'get_github_client',
    'get_github_tool',
]
