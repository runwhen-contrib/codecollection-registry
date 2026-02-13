"""
Robot Framework file parser for extracting tasks, keywords, and documentation.
"""
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class RobotTask:
    """Represents a Robot Framework task"""
    name: str
    documentation: str = ""
    tags: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)


@dataclass
class RobotKeyword:
    """Represents a Robot Framework keyword"""
    name: str
    documentation: str = ""
    arguments: List[str] = field(default_factory=list)


@dataclass
class RobotFile:
    """Represents a parsed Robot Framework file"""
    path: str
    documentation: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
    libraries: List[str] = field(default_factory=list)
    tasks: List[RobotTask] = field(default_factory=list)
    keywords: List[RobotKeyword] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)


class RobotParser:
    """
    Parser for Robot Framework .robot files.
    
    Extracts structured information including tasks, keywords, documentation,
    and metadata for use in semantic search and explanation generation.
    """
    
    def __init__(self):
        self.section_pattern = re.compile(r'^\*\*\*\s*(.+?)\s*\*\*\*', re.IGNORECASE)
    
    def parse_file(self, filepath: str) -> Optional[RobotFile]:
        """Parse a .robot file and extract structured information"""
        try:
            path = Path(filepath)
            if not path.exists() or path.suffix != '.robot':
                return None
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_content(content, str(path))
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
            return None
    
    def _parse_content(self, content: str, filepath: str) -> RobotFile:
        """Parse robot file content"""
        robot_file = RobotFile(path=filepath)
        
        lines = content.split('\n')
        current_section = None
        current_item = None
        current_item_lines = []
        
        for line in lines:
            # Check for section header
            section_match = self.section_pattern.match(line)
            if section_match:
                # Save previous item if exists
                if current_item and current_item_lines:
                    self._process_item(robot_file, current_section, current_item, current_item_lines)
                
                current_section = section_match.group(1).lower().strip()
                current_item = None
                current_item_lines = []
                continue
            
            if current_section is None:
                continue
            
            # Process based on section
            if current_section in ('settings', 'setting'):
                self._parse_settings_line(robot_file, line)
            
            elif current_section in ('variables', 'variable'):
                self._parse_variable_line(robot_file, line)
            
            elif current_section in ('tasks', 'task', 'test cases', 'test case'):
                # Task names start at column 0 (not indented)
                if line and not line[0].isspace() and line.strip():
                    # Save previous task
                    if current_item and current_item_lines:
                        self._process_item(robot_file, current_section, current_item, current_item_lines)
                    current_item = line.strip()
                    current_item_lines = []
                elif current_item:
                    current_item_lines.append(line)
            
            elif current_section in ('keywords', 'keyword'):
                # Keyword names start at column 0
                if line and not line[0].isspace() and line.strip():
                    # Save previous keyword
                    if current_item and current_item_lines:
                        self._process_item(robot_file, current_section, current_item, current_item_lines)
                    current_item = line.strip()
                    current_item_lines = []
                elif current_item:
                    current_item_lines.append(line)
        
        # Process final item
        if current_item and current_item_lines:
            self._process_item(robot_file, current_section, current_item, current_item_lines)
        
        return robot_file
    
    def _parse_settings_line(self, robot_file: RobotFile, line: str):
        """Parse a settings section line"""
        stripped = line.strip()
        if not stripped:
            return
        
        # Split on multiple spaces or tabs
        parts = re.split(r'\s{2,}|\t', stripped, maxsplit=1)
        if len(parts) < 2:
            return
        
        key = parts[0].lower()
        value = parts[1].strip()
        
        if key == 'documentation':
            robot_file.documentation = value
        elif key == 'library':
            robot_file.libraries.append(value.split()[0])  # Just the library name
        elif key == 'metadata':
            # Metadata Author jon-funk
            meta_parts = value.split(None, 1)
            if len(meta_parts) == 2:
                robot_file.metadata[meta_parts[0]] = meta_parts[1]
    
    def _parse_variable_line(self, robot_file: RobotFile, line: str):
        """Parse a variable definition line"""
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            return
        
        # Variables look like: ${VAR_NAME}    value
        match = re.match(r'\$\{([^}]+)\}\s+(.+)', stripped)
        if match:
            robot_file.variables[match.group(1)] = match.group(2)
    
    def _process_item(self, robot_file: RobotFile, section: str, name: str, lines: List[str]):
        """Process a task or keyword with its body lines"""
        documentation = ""
        tags = []
        steps = []
        arguments = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # Check for [Documentation], [Tags], [Arguments]
            if stripped.startswith('[Documentation]'):
                doc_value = stripped[15:].strip()
                documentation = doc_value
            elif stripped.startswith('[Tags]'):
                tag_value = stripped[6:].strip()
                tags = [t.strip() for t in re.split(r'\s{2,}|\t', tag_value) if t.strip()]
            elif stripped.startswith('[Arguments]'):
                arg_value = stripped[11:].strip()
                arguments = [a.strip() for a in re.split(r'\s{2,}|\t', arg_value) if a.strip()]
            else:
                # It's a step/keyword call
                steps.append(stripped)
        
        if section in ('tasks', 'task', 'test cases', 'test case'):
            robot_file.tasks.append(RobotTask(
                name=name,
                documentation=documentation,
                tags=tags,
                steps=steps
            ))
        elif section in ('keywords', 'keyword'):
            robot_file.keywords.append(RobotKeyword(
                name=name,
                documentation=documentation,
                arguments=arguments
            ))
    
    def to_text(self, robot_file: RobotFile) -> str:
        """Convert parsed robot file to searchable text"""
        parts = []
        
        # Documentation
        if robot_file.documentation:
            parts.append(f"Documentation: {robot_file.documentation}")
        
        # Metadata
        for key, value in robot_file.metadata.items():
            parts.append(f"{key}: {value}")
        
        # Libraries used
        if robot_file.libraries:
            parts.append(f"Libraries: {', '.join(robot_file.libraries)}")
        
        # Tasks
        for task in robot_file.tasks:
            task_text = f"Task: {task.name}"
            if task.documentation:
                task_text += f" - {task.documentation}"
            if task.tags:
                task_text += f" [Tags: {', '.join(task.tags)}]"
            parts.append(task_text)
        
        # Keywords
        for keyword in robot_file.keywords:
            kw_text = f"Keyword: {keyword.name}"
            if keyword.documentation:
                kw_text += f" - {keyword.documentation}"
            parts.append(kw_text)
        
        return "\n".join(parts)
    
    def extract_capabilities(self, robot_file: RobotFile) -> List[str]:
        """Extract capability descriptions from tasks"""
        capabilities = []
        
        for task in robot_file.tasks:
            # Clean up task name (remove variable placeholders)
            name = re.sub(r'\$\{[^}]+\}', '<param>', task.name)
            
            if task.documentation:
                capabilities.append(f"{name}: {task.documentation}")
            else:
                capabilities.append(name)
        
        return capabilities

