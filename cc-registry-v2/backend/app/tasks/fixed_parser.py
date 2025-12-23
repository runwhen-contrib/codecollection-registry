import tempfile
import os
import re
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from robot.api import TestSuite
import logging

logger = logging.getLogger(__name__)


def parse_generation_rules(runwhen_dir: Path) -> Dict[str, Any]:
    """
    Parse .runwhen/generation-rules/*.yaml files to extract discovery configuration.
    
    Returns a dict with:
    - has_genrules: bool
    - is_discoverable: bool  
    - discovery_platform: str (kubernetes, aws, azure, gcp, etc.)
    - discovery_resource_types: List[str]
    - discovery_match_patterns: List[dict]
    - discovery_output_items: List[str]
    - discovery_level_of_detail: str
    - discovery_templates: List[str]
    """
    result = {
        'has_genrules': False,
        'is_discoverable': False,
        'discovery_platform': None,
        'discovery_resource_types': [],
        'discovery_match_patterns': [],
        'discovery_output_items': [],
        'discovery_level_of_detail': None,
        'discovery_templates': [],
    }
    
    gen_rules_dir = runwhen_dir / 'generation-rules'
    templates_dir = runwhen_dir / 'templates'
    
    if not gen_rules_dir.exists():
        return result
    
    result['has_genrules'] = True
    result['is_discoverable'] = True
    
    # Parse all generation rule files
    all_resource_types = []
    all_match_patterns = []
    all_output_items = set()
    level_of_detail = None
    
    for yaml_file in gen_rules_dir.glob('*.yaml'):
        try:
            with open(yaml_file, 'r') as f:
                content = yaml.safe_load(f)
            
            if not content or 'spec' not in content:
                continue
            
            spec = content.get('spec', {})
            rules = spec.get('generationRules', [])
            
            for rule in rules:
                # Extract resource types
                resource_types = rule.get('resourceTypes', [])
                all_resource_types.extend(resource_types)
                
                # Extract match rules
                match_rules = rule.get('matchRules', [])
                for match in match_rules:
                    all_match_patterns.append({
                        'type': match.get('type'),
                        'pattern': match.get('pattern'),
                        'properties': match.get('properties', []),
                        'mode': match.get('mode')
                    })
                
                # Extract SLX definitions
                slxs = rule.get('slxs', [])
                for slx in slxs:
                    # Get level of detail
                    if slx.get('levelOfDetail'):
                        level_of_detail = slx.get('levelOfDetail')
                    
                    # Get output items
                    output_items = slx.get('outputItems', [])
                    for item in output_items:
                        if isinstance(item, dict):
                            all_output_items.add(item.get('type', ''))
                        else:
                            all_output_items.add(str(item))
                    
        except Exception as e:
            logger.warning(f"Failed to parse generation rules file {yaml_file}: {e}")
            continue
    
    # Determine platform from resource types
    platform = _detect_platform_from_resources(all_resource_types)
    
    # Get template files
    templates = []
    if templates_dir.exists():
        templates = [f.name for f in templates_dir.glob('*.yaml')]
    
    result['discovery_resource_types'] = list(set(all_resource_types))
    result['discovery_match_patterns'] = all_match_patterns
    result['discovery_output_items'] = list(all_output_items)
    result['discovery_level_of_detail'] = level_of_detail
    result['discovery_platform'] = platform
    result['discovery_templates'] = templates
    
    return result


def _detect_platform_from_resources(resource_types: List[str]) -> str:
    """Detect platform from resource types. Defaults to Kubernetes."""
    if not resource_types:
        return 'Kubernetes'  # Default platform
    
    resource_str = ' '.join(resource_types).lower()
    
    # Azure patterns
    if any(x in resource_str for x in ['azure', 'microsoft.']):
        return 'Azure'
    
    # AWS patterns  
    if any(x in resource_str for x in ['aws_', 'amazon']):
        return 'AWS'
    
    # GCP patterns
    if any(x in resource_str for x in ['gcp', 'google']):
        return 'GCP'
    
    # Default to Kubernetes for everything else
    return 'Kubernetes'

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
            # Slug should NOT include collection prefix - URL is /collections/{collection}/codebundles/{slug}
            path_parts = file_path.split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'codebundles':
                codebundle_dir = path_parts[1]
                name = codebundle_dir
                slug = codebundle_dir.lower().replace(' ', '-').replace('_', '-')
            else:
                name = os.path.splitext(os.path.basename(file_path))[0]
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

