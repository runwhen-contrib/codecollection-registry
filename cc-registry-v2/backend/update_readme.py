#!/usr/bin/env python3
"""
Script to update codebundles with README.md content.

This parses README.md files from the MCP cloned repos and updates
the codebundle records.

Usage:
    docker-compose exec backend python update_readme.py
"""

import sys
from pathlib import Path

sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models import Codebundle, CodeCollection

# Path to MCP cloned repos (mounted from docker-compose)
MCP_REPOS_PATH = Path('/mcp-repos')
# Alternative path if running locally (outside container)
ALT_REPOS_PATH = Path('/workspaces/codecollection-registry/hack/mcp/data/repos')


def find_repos_path():
    """Find the path to cloned repos"""
    if MCP_REPOS_PATH.exists():
        return MCP_REPOS_PATH
    if ALT_REPOS_PATH.exists():
        return ALT_REPOS_PATH
    return None


def get_collection_repo_name(collection_slug: str) -> str:
    """Convert collection slug to repo directory name"""
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
    print("=== UPDATE CODEBUNDLES WITH README CONTENT ===\n")
    
    repos_path = find_repos_path()
    if not repos_path:
        print("ERROR: Cannot find cloned repos. Run MCP indexer first.")
        print(f"Checked: {MCP_REPOS_PATH}")
        print(f"Checked: {ALT_REPOS_PATH}")
        return False
    
    print(f"Using repos from: {repos_path}\n")
    
    db = SessionLocal()
    
    try:
        # Get all collections
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        updated_count = 0
        readme_found = 0
        
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
                
                # Look for README.md (case insensitive)
                readme_content = None
                for readme_name in ['README.md', 'readme.md', 'Readme.md', 'README.MD']:
                    readme_path = cb_dir / readme_name
                    if readme_path.exists():
                        try:
                            readme_content = readme_path.read_text(encoding='utf-8')
                            readme_found += 1
                            break
                        except Exception as e:
                            print(f"  Warning: Could not read {readme_path}: {e}")
                
                # Update codebundle
                if readme_content:
                    cb.readme = readme_content
                    updated_count += 1
            
            # Commit after each collection
            db.commit()
            
            collection_readmes = sum(1 for cb in codebundles if cb.readme)
            print(f"✓ {collection.name}: {collection_readmes}/{len(codebundles)} codebundles have READMEs")
        
        print(f"\n=== COMPLETE ===")
        print(f"Updated: {updated_count} codebundles with README content")
        print(f"README files found: {readme_found}")
        
        return True
        
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


