import os
import yaml
import shutil
import subprocess
import tempfile
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import git
from robot.api import TestSuite
from collections import Counter, defaultdict

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle
from app.core.config import settings

logger = logging.getLogger(__name__)

class DataPopulationService:
    """Service to populate the new registry with data from the original generate_registry.py process"""
    
    def __init__(self):
        self.temp_dir = None
        self.all_support_tags = set()
        self.all_codebundle_tasks = []
        self.all_files_with_dates = []
        self.all_codecollection_stats = {}
        
    def populate_registry_data(self) -> Dict[str, Any]:
        """Main method to populate the registry with data from the original process"""
        try:
            logger.info("Starting registry data population...")
            
            # Read the original codecollections.yaml
            yaml_data = self._read_codecollections_yaml()
            
            # Create temporary directory for cloning
            self.temp_dir = tempfile.mkdtemp(prefix="registry_migration_")
            logger.info(f"Using temp directory: {self.temp_dir}")
            
            # Process each codecollection
            for collection_data in yaml_data.get('codecollections', []):
                logger.info(f"Processing collection: {collection_data['name']}")
                self._process_codecollection(collection_data)
            
            # Generate categories and tags
            self._generate_categories()
            
            # Update statistics
            self._update_collection_stats()
            
            logger.info("Registry data population completed successfully")
            return {
                "status": "success",
                "collections_processed": len(yaml_data.get('codecollections', [])),
                "total_codebundles": len(self.all_codebundle_tasks),
                "total_tags": len(self.all_support_tags),
                "temp_dir": self.temp_dir
            }
            
        except Exception as e:
            logger.error(f"Registry data population failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            # Cleanup temp directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
    
    def _read_codecollections_yaml(self) -> Dict[str, Any]:
        """Read the original codecollections.yaml file"""
        yaml_path = "/workspaces/codecollection-registry/codecollections.yaml"
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"codecollections.yaml not found at {yaml_path}")
        
        with open(yaml_path, 'r') as file:
            return yaml.safe_load(file)
    
    def _process_codecollection(self, collection_data: Dict[str, Any]):
        """Process a single codecollection - clone, parse, and save to database"""
        try:
            # Extract org and repo name from git_url
            git_url = collection_data['git_url']
            org = git_url.split("/")[-2]
            repo_name = git_url.split("/")[-1]
            ref = collection_data.get('git_ref', 'main')
            
            # Clone repository
            clone_path = os.path.join(self.temp_dir, org)
            self._clone_repository(git_url, clone_path, ref)
            
            # Generate GitHub stats
            self._generate_github_stats(collection_data)
            
            # Parse and save codebundles
            repo_path = os.path.join(clone_path, repo_name)
            self._parse_and_save_codebundles(collection_data, repo_path)
            
            # Get latest files for statistics
            latest_files = self._get_latest_files_by_pattern(repo_path, '*.robot', 5)
            self.all_files_with_dates.extend(latest_files)
            
        except Exception as e:
            logger.error(f"Error processing collection {collection_data['name']}: {e}")
    
    def _clone_repository(self, git_url: str, clone_directory: str, ref: str = 'main'):
        """Clone a git repository"""
        if not os.path.exists(clone_directory):
            os.makedirs(clone_directory)
        
        try:
            # Use gitpython for better error handling
            git.Repo.clone_from(git_url, os.path.join(clone_directory, git_url.split("/")[-1]), branch=ref)
        except Exception as e:
            logger.error(f"Failed to clone {git_url}: {e}")
            raise
    
    def _generate_github_stats(self, collection_data: Dict[str, Any]):
        """Generate GitHub statistics for a collection"""
        # This would integrate with GitHub API to get stats
        # For now, we'll use the data from the YAML
        self.all_codecollection_stats[collection_data['slug']] = {
            'name': collection_data['name'],
            'description': collection_data.get('description', ''),
            'owner': collection_data.get('owner', ''),
            'git_url': collection_data['git_url'],
            'git_ref': collection_data.get('git_ref', 'main'),
            'last_updated': datetime.now().isoformat()
        }
    
    def _parse_and_save_codebundles(self, collection_data: Dict[str, Any], repo_path: str):
        """Parse robot files and save codebundles to database"""
        db = SessionLocal()
        try:
            # Get or create the codecollection in database
            collection = db.query(CodeCollection).filter(
                CodeCollection.slug == collection_data['slug']
            ).first()
            
            if not collection:
                collection = CodeCollection(
                    name=collection_data['name'],
                    slug=collection_data['slug'],
                    git_url=collection_data['git_url'],
                    description=collection_data.get('description', ''),
                    owner=collection_data.get('owner', ''),
                    owner_email=collection_data.get('owner_email', ''),
                    owner_icon=collection_data.get('owner_icon', ''),
                    git_ref=collection_data.get('git_ref', 'main'),
                    is_active=True
                )
                db.add(collection)
                db.commit()
                db.refresh(collection)
            
            # Find and parse all robot files
            robot_files = self._find_robot_files(repo_path)
            
            for robot_file in robot_files:
                try:
                    codebundle_data = self._parse_robot_file(robot_file)
                    if codebundle_data:
                        self._save_codebundle(collection.id, codebundle_data, db)
                except Exception as e:
                    logger.error(f"Error parsing robot file {robot_file}: {e}")
                    continue
                    
        finally:
            db.close()
    
    def _find_robot_files(self, repo_path: str) -> List[str]:
        """Find all robot files in the repository"""
        robot_files = []
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.robot'):
                    robot_files.append(os.path.join(root, file))
        return robot_files
    
    def _parse_robot_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse a robot file and extract codebundle information"""
        try:
            suite = TestSuite.from_file_system(file_path)
            
            # Extract metadata
            metadata = suite.metadata if hasattr(suite, 'metadata') else {}
            
            # Get relative path for display
            relative_path = os.path.relpath(file_path, self.temp_dir)
            
            # Extract tasks
            tasks = []
            if hasattr(suite, 'tests'):
                for test in suite.tests:
                    task_data = {
                        'name': test.name if hasattr(test, 'name') else 'Unknown Task',
                        'description': getattr(test, 'doc', ''),
                        'tags': getattr(test, 'tags', []),
                        'steps': []
                    }
                    
                    # Extract test steps
                    if hasattr(test, 'body') and test.body:
                        for step in test.body:
                            if hasattr(step, 'name'):
                                task_data['steps'].append(step.name)
                    
                    tasks.append(task_data)
            
            # Extract support tags
            support_tags = []
            if hasattr(suite, 'tags'):
                support_tags = list(suite.tags)
            elif metadata.get('Tags'):
                support_tags = metadata.get('Tags', '').split(',')
            
            # Add to global tags
            self.all_support_tags.update(support_tags)
            
            # Create codebundle data
            codebundle_data = {
                'name': os.path.basename(file_path).replace('.robot', ''),
                'slug': os.path.basename(file_path).replace('.robot', '').lower().replace('_', '-'),
                'display_name': metadata.get('Name', os.path.basename(file_path).replace('.robot', '')),
                'description': metadata.get('Documentation', ''),
                'doc': metadata.get('Documentation', ''),
                'author': metadata.get('Author', ''),
                'support_tags': support_tags,
                'tasks': tasks,
                'task_count': len(tasks),
                'file_path': relative_path,
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            return codebundle_data
            
        except Exception as e:
            logger.error(f"Error parsing robot file {file_path}: {e}")
            return None
    
    def _save_codebundle(self, collection_id: int, codebundle_data: Dict[str, Any], db):
        """Save a codebundle to the database"""
        try:
            # Check if codebundle already exists
            existing = db.query(Codebundle).filter(
                Codebundle.slug == codebundle_data['slug'],
                Codebundle.codecollection_id == collection_id
            ).first()
            
            if existing:
                # Update existing
                for key, value in codebundle_data.items():
                    if key != 'tasks' and hasattr(existing, key):
                        setattr(existing, key, value)
                codebundle = existing
            else:
                # Create new
                codebundle = Codebundle(
                    name=codebundle_data['name'],
                    slug=codebundle_data['slug'],
                    display_name=codebundle_data['display_name'],
                    description=codebundle_data['description'],
                    doc=codebundle_data['doc'],
                    author=codebundle_data['author'],
                    support_tags=codebundle_data['support_tags'],
                    task_count=codebundle_data['task_count'],
                    codecollection_id=collection_id,
                    is_active=True
                )
                db.add(codebundle)
                db.commit()
                db.refresh(codebundle)
            
            # Tasks are stored as JSON in the codebundle model
            # No separate CodebundleTask table needed
            
            db.commit()
            logger.info(f"Saved codebundle: {codebundle_data['name']}")
            
        except Exception as e:
            logger.error(f"Error saving codebundle {codebundle_data['name']}: {e}")
            db.rollback()
            raise
    
    def _get_latest_files_by_pattern(self, directory: str, pattern: str, limit: int) -> List[Dict[str, Any]]:
        """Get the latest files matching a pattern"""
        files_with_dates = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(pattern.replace('*', '')):
                    file_path = os.path.join(root, file)
                    try:
                        # Get file modification time
                        mtime = os.path.getmtime(file_path)
                        files_with_dates.append({
                            'filepath': file_path,
                            'relative_path': os.path.relpath(file_path, directory),
                            'commit_date': datetime.fromtimestamp(mtime),
                            'mtime': mtime
                        })
                    except Exception as e:
                        logger.error(f"Error getting file date for {file_path}: {e}")
        
        # Sort by modification time and return top files
        files_with_dates.sort(key=lambda x: x['mtime'], reverse=True)
        return files_with_dates[:limit]
    
    def _generate_categories(self):
        """Generate category data from support tags"""
        # This would create category pages and metadata
        # For now, we'll just log the tags
        logger.info(f"Generated {len(self.all_support_tags)} unique support tags")
        logger.info(f"Tags: {sorted(self.all_support_tags)}")
    
    def _update_collection_stats(self):
        """Update collection statistics"""
        # This would update various statistics and metrics
        logger.info(f"Updated stats for {len(self.all_codecollection_stats)} collections")
