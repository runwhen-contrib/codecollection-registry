import tempfile
import os
import re
from typing import Optional, Dict, Any
from robot.api import TestSuite
import logging

logger = logging.getLogger(__name__)

def _create_display_name(name: str) -> str:
    """Create a display name from a codebundle name"""
    # Convert snake_case and kebab-case to Title Case
    display_words = []
    
    # Split by underscores and hyphens
    words = re.split(r'[-_]', name)
    
    for word in words:
        if word:
            # Handle camelCase within words
            camel_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', word)
            if camel_words:
                display_words.extend([w.capitalize() for w in camel_words])
            else:
                display_words.append(word.capitalize())
    
    return ' '.join(display_words)

def parse_robot_file_content(content: str, file_path: str, collection_slug: str = None) -> Optional[Dict[str, Any]]:
    """
    Parse Robot Framework file content using the EXACT logic from generate_registry.py
    This is the working parser that extracts 191 codebundles with 767 tasks
    """
    try:
        # Create temporary file for robot parser (same as generate_registry.py)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.robot', delete=False) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Use TestSuite.from_file_system EXACTLY like generate_registry.py
            suite = TestSuite.from_file_system(temp_file_path)
            
            # Use the EXACT parsing logic from generate_registry.py
            ret = {}
            ret["doc"] = suite.doc  # The doc string
            ret["type"] = suite.name.lower()
            ret["tags"] = []

            # Extract metadata EXACTLY like generate_registry.py
            for k, v in suite.metadata.items():
                if k.lower() in ["author", "name"]:
                    ret[k.lower()] = v
                if k.lower() in ["display name", "name"]:
                    ret["display_name"] = v
                if k.lower() in ["supports"]:
                    support_tags = re.split(r'\s*,\s*|\s+', v.strip().upper())
                    ret["support_tags"] = support_tags
            
            # Extract tasks EXACTLY like generate_registry.py
            tasks = []
            for task in suite.tests:
                tags = [str(tag) for tag in task.tags if tag not in ["skipped"]]
                tasks.append({
                    "id": task.id,
                    "name": task.name,
                    "doc": str(task.doc),
                    "keywords": task.body
                })
                ret["tags"] = list(set(ret["tags"] + tags))
            ret["tasks"] = tasks
            
            # Extract imports like generate_registry.py
            resourcefile = suite.resource
            ret["imports"] = []
            for i in resourcefile.imports:
                ret["imports"].append(i.name)
            
            # Extract codebundle name from path
            path_parts = file_path.split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'codebundles':
                codebundle_dir = path_parts[1]
                name = codebundle_dir
                if collection_slug:
                    slug = f"{collection_slug}-{codebundle_dir}".lower().replace(' ', '-').replace('_', '-')
                else:
                    slug = codebundle_dir.lower().replace(' ', '-').replace('_', '-')
            else:
                name = os.path.splitext(os.path.basename(file_path))[0]
                if collection_slug:
                    slug = f"{collection_slug}-{name}".lower().replace(' ', '-').replace('_', '-')
                else:
                    slug = name.lower().replace(' ', '-').replace('_', '-')
            
            # Return data in the format expected by the microservices
            return {
                'name': name,
                'slug': slug,
                'display_name': ret.get("display_name", _create_display_name(name)),
                'description': ret["doc"].split('\n')[0] if ret["doc"] else f"Codebundle for {_create_display_name(name)}",
                'doc': ret["doc"],
                'author': ret.get("author", ""),
                'tasks': [task["name"] for task in tasks],  # Task names for backward compatibility
                'detailed_tasks': tasks,  # Full task objects
                'support_tags': ret.get("support_tags", []),
                'runbook_path': file_path,
                'task_count': len(tasks),
                'collection_slug': collection_slug,
                'imports': ret["imports"]
            }
            
        finally:
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Failed to parse robot file content: {e}")
        return None

