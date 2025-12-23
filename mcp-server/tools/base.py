"""
Base Tool Classes for MCP Server

Provides the base classes and registry for defining MCP tools
in a consistent, discoverable way.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Type
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Definition of a tool parameter"""
    name: str
    type: str  # "string", "integer", "boolean", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    items: Optional[str] = None  # For array types
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP parameter schema"""
        result = {
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            result["default"] = self.default
        if self.enum:
            result["enum"] = self.enum
        if self.items:
            result["items"] = self.items
        return result


@dataclass
class ToolDefinition:
    """Complete tool definition for MCP"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    category: str = "general"  # For grouping: search, action, info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {p.name: p.to_dict() for p in self.parameters},
            "category": self.category
        }


class BaseTool(ABC):
    """
    Base class for all MCP tools.
    
    Subclass this and implement:
    - definition: ToolDefinition with name, description, parameters
    - execute(): The tool's logic
    """
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool's definition"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        Execute the tool with the given arguments.
        
        Returns:
            Markdown-formatted string result
        """
        pass
    
    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize arguments against definition"""
        validated = {}
        
        for param in self.definition.parameters:
            if param.name in args:
                validated[param.name] = args[param.name]
            elif param.required:
                raise ValueError(f"Missing required parameter: {param.name}")
            elif param.default is not None:
                validated[param.name] = param.default
        
        return validated


class ToolRegistry:
    """
    Registry for managing MCP tools.
    
    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        
        # List all tools
        tools = registry.list_tools()
        
        # Execute a tool
        result = await registry.execute("tool_name", {"arg": "value"})
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        name = tool.definition.name
        if name in self._tools:
            logger.warning(f"Overwriting existing tool: {name}")
        self._tools[name] = tool
        logger.info(f"Registered tool: {name}")
    
    def register_all(self, tools: List[BaseTool]) -> None:
        """Register multiple tools"""
        for tool in tools:
            self.register(tool)
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools as MCP schema"""
        return [tool.definition.to_dict() for tool in self._tools.values()]
    
    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List tools in a specific category"""
        return [
            tool.definition.to_dict() 
            for tool in self._tools.values() 
            if tool.definition.category == category
        ]
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name"""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        
        try:
            validated_args = tool.validate_args(arguments)
            return await tool.execute(**validated_args)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}", exc_info=True)
            raise
    
    @property
    def count(self) -> int:
        """Number of registered tools"""
        return len(self._tools)


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry

