"""
MCP Server Tools Package

Tools are organized by category:
- codebundle_tools: Finding, listing, searching CodeBundles
- collection_tools: Finding and listing CodeCollections  
- library_tools: Help with Robot Framework libraries
- documentation_tools: Documentation, guides, and FAQs
- github_issue: Creating GitHub issues for new CodeBundle requests

All data access goes through the Registry API via RegistryClient.
"""

from typing import Any

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


def register_all_tools(registry_client: Any) -> ToolRegistry:
    """
    Register all available MCP tools with the registry.
    
    Args:
        registry_client: RegistryClient instance for API access
    
    Returns:
        Configured ToolRegistry with all tools registered
    """
    registry = get_tool_registry()
    
    # Clear existing tools if re-registering
    registry._tools.clear()
    
    # Register CodeBundle tools
    registry.register(FindCodeBundleTool(registry_client))
    registry.register(ListCodeBundlesTool(registry_client))
    registry.register(SearchCodeBundlesTool(registry_client))
    registry.register(GetCodeBundleDetailsTool(registry_client))
    
    # Register Collection tools
    registry.register(FindCodeCollectionTool(registry_client))
    registry.register(ListCodeCollectionsTool(registry_client))
    
    # Register Library tools
    registry.register(KeywordUsageHelpTool(registry_client))
    registry.register(FindLibraryInfoTool(registry_client))
    
    # Register Documentation tools (uses local docs.yaml + optional API)
    registry.register(FindDocumentationTool(registry_client))
    registry.register(GetDevelopmentRequirementsTool(registry_client))
    
    # Register GitHub Issue tools (no API dependency)
    registry.register(RequestCodeBundleTool())
    registry.register(CheckExistingRequestsTool())
    
    return registry


__all__ = [
    'BaseTool', 'ToolDefinition', 'ToolParameter', 'ToolRegistry', 'get_tool_registry',
    'register_all_tools',
    'FindCodeBundleTool', 'ListCodeBundlesTool', 'SearchCodeBundlesTool', 'GetCodeBundleDetailsTool',
    'FindCodeCollectionTool', 'ListCodeCollectionsTool',
    'KeywordUsageHelpTool', 'FindLibraryInfoTool',
    'FindDocumentationTool', 'GetDevelopmentRequirementsTool', 'DocumentationManager', 'get_doc_manager',
    'RequestCodeBundleTool', 'CheckExistingRequestsTool',
    'GitHubIssueClient', 'CodeBundleRequest', 'get_github_client', 'get_github_tool',
]
