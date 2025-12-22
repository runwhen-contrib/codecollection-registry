#!/usr/bin/env python3
"""
Script to update codebundles with .runwhen/generation-rules configuration.

This parses the .runwhen directories from the MCP cloned repos and updates
the codebundle records with configuration type info.

Usage:
    docker-compose exec backend python update_genrules.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models import Codebundle, CodeCollection
from app.tasks.fixed_parser import parse_generation_rules

# Path to MCP cloned repos (mounted from docker-compose)
MCP_REPOS_PATH = Path('/mcp-repos')
# Alternative path if running locally (outside container)
ALT_REPOS_PATH = Path('/workspaces/codecollection-registry/mcp-server/data/repos')


def find_repos_path():
    """Find the path to cloned repos"""
    if MCP_REPOS_PATH.exists():
        return MCP_REPOS_PATH
    if ALT_REPOS_PATH.exists():
        return ALT_REPOS_PATH
    return None


def get_collection_repo_name(collection_slug: str) -> str:
    """Convert collection slug to repo directory name"""
    # Common mappings
    mappings = {
        'rw-cli-codecollection': 'rw-cli-codecollection',
        'rw-public-codecollection': 'rw-public-codecollection',
        'rw-generic-codecollection': 'rw-generic-codecollection',
        'aws-c7n-codecollection': 'aws-c7n-codecollection',
        'azure-c7n-codecollection': 'azure-c7n-codecollection',
        'ternary-codecollection': 'ternary-codecollection',
        'rw-workspace-utils': 'rw-workspace-utils',
    }
    return mappings.get(collection_slug, collection_slug)


def main():
    print("=== UPDATE CODEBUNDLES WITH GENERATION RULES ===\n")
    
    repos_path = find_repos_path()
    if not repos_path:
        print("ERROR: Cannot find cloned repos. Run MCP indexer first.")
        print(f"Checked: {MCP_REPOS_PATH}")
        print(f"Checked: {ALT_REPOS_PATH}")
        return False
    
    print(f"Using repos from: {repos_path}\n")
    
    db = SessionLocal()
    
    try:
        # Get all collections and their codebundles
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        updated_count = 0
        auto_discovered = 0
        manual_count = 0
        
        for collection in collections:
            repo_name = get_collection_repo_name(collection.slug)
            repo_path = repos_path / repo_name
            
            if not repo_path.exists():
                print(f"⚠️  Repo not found for {collection.name}: {repo_path}")
                continue
            
            codebundles_path = repo_path / 'codebundles'
            if not codebundles_path.exists():
                continue
            
            # Get codebundles for this collection
            codebundles = db.query(Codebundle).filter(
                Codebundle.codecollection_id == collection.id,
                Codebundle.is_active == True
            ).all()
            
            for cb in codebundles:
                # Find the codebundle directory
                cb_dir = codebundles_path / cb.name
                if not cb_dir.exists():
                    # Try without collection prefix
                    parts = cb.name.split('-', 1)
                    if len(parts) > 1:
                        cb_dir = codebundles_path / parts[1]
                
                if not cb_dir.exists():
                    continue
                
                # Check for .runwhen directory
                runwhen_dir = cb_dir / '.runwhen'
                
                if runwhen_dir.exists():
                    # Parse generation rules
                    gen_rules = parse_generation_rules(runwhen_dir)
                    
                    # Update codebundle
                    cb.has_genrules = gen_rules.get('has_genrules', False)
                    cb.is_discoverable = gen_rules.get('is_discoverable', False)
                    cb.discovery_platform = gen_rules.get('discovery_platform')
                    cb.discovery_resource_types = gen_rules.get('discovery_resource_types', [])
                    cb.discovery_match_patterns = gen_rules.get('discovery_match_patterns', [])
                    cb.discovery_output_items = gen_rules.get('discovery_output_items', [])
                    cb.discovery_level_of_detail = gen_rules.get('discovery_level_of_detail')
                    cb.discovery_templates = gen_rules.get('discovery_templates', [])
                    cb.runwhen_directory_path = str(runwhen_dir.relative_to(repo_path))
                    
                    updated_count += 1
                    auto_discovered += 1
                    
                else:
                    # No .runwhen directory = Manual configuration
                    cb.has_genrules = False
                    cb.is_discoverable = False
                    manual_count += 1
                    updated_count += 1
            
            # Commit after each collection
            db.commit()
            print(f"✓ {collection.name}: {len(codebundles)} codebundles processed")
        
        print(f"\n=== COMPLETE ===")
        print(f"Updated: {updated_count} codebundles")
        print(f"Auto-discovered (has .runwhen): {auto_discovered}")
        print(f"Manual configuration: {manual_count}")
        
        return True
        
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

