"""
Data loading utilities for RunWhen MCP Server
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Any


class DataLoader:
    """Loads and caches data from JSON files"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Default to data/ directory relative to this file
            self.data_dir = Path(__file__).parent.parent / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self._cache = {}
    
    def load_codebundles(self) -> List[Dict[str, Any]]:
        """Load codebundles data"""
        return self._load_json_file("codebundles.json").get("codebundles", [])
    
    def load_codecollections(self) -> List[Dict[str, Any]]:
        """Load codecollections data"""
        return self._load_json_file("codecollections.json").get("codecollections", [])
    
    def load_libraries(self) -> List[Dict[str, Any]]:
        """Load libraries data"""
        return self._load_json_file("libraries.json").get("libraries", [])
    
    def load_documentation_resources(self) -> List[Dict[str, Any]]:
        """Load documentation resources"""
        return self._load_json_file("documentation_resources.json").get("resources", [])
    
    def _load_json_file(self, filename: str) -> Dict[str, Any]:
        """Load a JSON file from the data directory"""
        filepath = self.data_dir / filename
        
        # Simple caching - reload on each call for MVP
        # In production, implement proper cache invalidation
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: {filepath} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing {filepath}: {e}")
            return {}
    
    def get_codebundle_by_slug(self, slug: str, collection_slug: str = None) -> Dict[str, Any] | None:
        """Find a codebundle by slug"""
        codebundles = self.load_codebundles()
        
        for cb in codebundles:
            if cb.get("slug") == slug:
                if collection_slug is None or cb.get("collection_slug") == collection_slug:
                    return cb
        
        return None
    
    def get_codecollection_by_slug(self, slug: str) -> Dict[str, Any] | None:
        """Find a codecollection by slug"""
        collections = self.load_codecollections()
        
        for cc in collections:
            if cc.get("slug") == slug:
                return cc
        
        return None

