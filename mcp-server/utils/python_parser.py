"""
Python file parser for extracting functions, classes, and documentation.
"""
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PythonFunction:
    """Represents a Python function"""
    name: str
    docstring: str = ""
    signature: str = ""
    arguments: List[str] = field(default_factory=list)
    return_type: str = ""
    decorators: List[str] = field(default_factory=list)
    is_async: bool = False


@dataclass
class PythonClass:
    """Represents a Python class"""
    name: str
    docstring: str = ""
    bases: List[str] = field(default_factory=list)
    methods: List[PythonFunction] = field(default_factory=list)


@dataclass
class PythonModule:
    """Represents a parsed Python module"""
    path: str
    name: str
    docstring: str = ""
    imports: List[str] = field(default_factory=list)
    functions: List[PythonFunction] = field(default_factory=list)
    classes: List[PythonClass] = field(default_factory=list)
    constants: Dict[str, str] = field(default_factory=dict)


class PythonParser:
    """
    Parser for Python source files.
    
    Extracts:
    - Module docstrings
    - Function signatures and docstrings
    - Class definitions and methods
    - Import statements
    """
    
    def parse_file(self, filepath: str) -> Optional[PythonModule]:
        """Parse a Python file and extract structured information"""
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix != '.py':
                return None
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            return self._parse_source(source, str(path))
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
            return None
    
    def _parse_source(self, source: str, filepath: str) -> PythonModule:
        """Parse Python source code"""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {filepath}: {e}")
            return PythonModule(path=filepath, name=Path(filepath).stem)
        
        module = PythonModule(
            path=filepath,
            name=Path(filepath).stem,
            docstring=ast.get_docstring(tree) or ""
        )
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module.imports.append(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    module.imports.append(f"{module_name}.{alias.name}")
            
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func = self._parse_function(node)
                module.functions.append(func)
            
            elif isinstance(node, ast.ClassDef):
                cls = self._parse_class(node)
                module.classes.append(cls)
            
            elif isinstance(node, ast.Assign):
                # Capture top-level constants
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        try:
                            value = ast.literal_eval(node.value)
                            module.constants[target.id] = str(value)[:100]
                        except:
                            pass
        
        return module
    
    def _parse_function(self, node) -> PythonFunction:
        """Parse a function definition"""
        is_async = isinstance(node, ast.AsyncFunctionDef)
        
        # Get arguments
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._annotation_to_str(arg.annotation)}"
            args.append(arg_str)
        
        # Get return type
        return_type = ""
        if node.returns:
            return_type = self._annotation_to_str(node.returns)
        
        # Build signature
        sig = f"{'async ' if is_async else ''}def {node.name}({', '.join(args)})"
        if return_type:
            sig += f" -> {return_type}"
        
        # Get decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
        
        return PythonFunction(
            name=node.name,
            docstring=ast.get_docstring(node) or "",
            signature=sig,
            arguments=args,
            return_type=return_type,
            decorators=decorators,
            is_async=is_async
        )
    
    def _parse_class(self, node: ast.ClassDef) -> PythonClass:
        """Parse a class definition"""
        bases = []
        for base in node.bases:
            bases.append(self._annotation_to_str(base))
        
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._parse_function(item))
        
        return PythonClass(
            name=node.name,
            docstring=ast.get_docstring(node) or "",
            bases=bases,
            methods=methods
        )
    
    def _annotation_to_str(self, node) -> str:
        """Convert an annotation AST node to string"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            return f"{self._annotation_to_str(node.value)}[{self._annotation_to_str(node.slice)}]"
        elif isinstance(node, ast.Attribute):
            return f"{self._annotation_to_str(node.value)}.{node.attr}"
        elif isinstance(node, ast.Tuple):
            return ", ".join(self._annotation_to_str(e) for e in node.elts)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return f"{self._annotation_to_str(node.left)} | {self._annotation_to_str(node.right)}"
        else:
            return "..."
    
    def to_text(self, module: PythonModule) -> str:
        """Convert parsed module to searchable text"""
        parts = []
        
        # Module info
        parts.append(f"Module: {module.name}")
        if module.docstring:
            parts.append(f"Description: {module.docstring[:500]}")
        
        # Functions
        for func in module.functions:
            if not func.name.startswith('_'):  # Skip private
                func_text = f"Function: {func.signature}"
                if func.docstring:
                    func_text += f"\n  {func.docstring[:200]}"
                parts.append(func_text)
        
        # Classes
        for cls in module.classes:
            cls_text = f"Class: {cls.name}"
            if cls.docstring:
                cls_text += f"\n  {cls.docstring[:200]}"
            
            # Public methods
            public_methods = [m for m in cls.methods if not m.name.startswith('_')]
            if public_methods:
                cls_text += "\n  Methods: " + ", ".join(m.name for m in public_methods[:10])
            
            parts.append(cls_text)
        
        return "\n\n".join(parts)
    
    def extract_keywords(self, module: PythonModule) -> List[str]:
        """Extract Robot Framework keyword names from module"""
        keywords = []
        
        # Functions that look like keywords (no leading underscore, has docstring)
        for func in module.functions:
            if not func.name.startswith('_') and func.docstring:
                # Convert function_name to "Function Name" style
                keyword = func.name.replace('_', ' ').title()
                keywords.append(keyword)
        
        return keywords

