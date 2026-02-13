#!/usr/bin/env python3
"""
Complete database reset and population script
This script will:
1. Clear existing codebundles
2. Clone repositories if needed
3. Parse robot files with the working parser
4. Populate the database with real data
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle
from app.models.raw_data import RawRepositoryData
from app.tasks.fixed_parser import parse_robot_file_content

def clone_repository(git_url: str, clone_dir: str, ref: str = 'main'):
    """Clone a git repository"""
    print(f"Cloning {git_url} (ref: {ref}) to {clone_dir}")
    try:
        subprocess.run(['git', 'clone', '-b', ref, '--single-branch', git_url, clone_dir], 
                      check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cloning {git_url}: {e}")
        return False

def find_robot_files(directory: str):
    """Find all .robot files in a directory"""
    robot_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.robot'):
                robot_files.append(os.path.join(root, file))
    return robot_files

def store_robot_file(db, collection_slug: str, file_path: str, repo_path: str):
    """Store a robot file in the database"""
    relative_path = os.path.relpath(file_path, repo_path)
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already exists
    existing = db.query(RawRepositoryData).filter(
        RawRepositoryData.collection_slug == collection_slug,
        RawRepositoryData.file_path == relative_path
    ).first()
    
    if not existing:
        raw_data = RawRepositoryData(
            collection_slug=collection_slug,
            repository_path=repo_path,
            file_path=relative_path,
            file_content=content,
            file_type='robot',
            is_processed=False
        )
        db.add(raw_data)
        return True
    return False

def main():
    print("=== COMPLETE DATABASE RESET AND POPULATION ===")
    
    db = SessionLocal()
    
    try:
        # Step 1: Clear existing codebundles
        print("Step 1: Clearing existing codebundles...")
        codebundles_before = db.query(Codebundle).count()
        db.query(Codebundle).delete()
        db.commit()
        print(f"Cleared {codebundles_before} codebundles")
        
        # Step 2: Clear existing raw repository data
        print("Step 2: Clearing existing repository data...")
        raw_data_before = db.query(RawRepositoryData).count()
        db.query(RawRepositoryData).delete()
        db.commit()
        print(f"Cleared {raw_data_before} raw repository files")
        
        # Step 3: Get collections from database
        collections = db.query(CodeCollection).all()
        print(f"Step 3: Found {len(collections)} collections to process")
        
        if not collections:
            print("ERROR: No collections found. Make sure YAML data is stored first.")
            return
        
        # Step 4: Clone repositories and store robot files
        temp_dir = tempfile.mkdtemp()
        total_robot_files = 0
        
        try:
            for collection in collections:
                print(f"\\nProcessing collection: {collection.name}")
                
                # Clone repository
                repo_name = collection.git_url.split('/')[-1].replace('.git', '')
                repo_path = os.path.join(temp_dir, repo_name)
                
                if clone_repository(collection.git_url, repo_path, collection.git_ref):
                    # Find and store robot files
                    robot_files = find_robot_files(repo_path)
                    print(f"Found {len(robot_files)} robot files")
                    
                    files_stored = 0
                    for robot_file in robot_files:
                        if store_robot_file(db, collection.slug, robot_file, repo_path):
                            files_stored += 1
                    
                    print(f"Stored {files_stored} new robot files")
                    total_robot_files += files_stored
                    
                    # Commit after each collection
                    db.commit()
        
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print(f"\\nStep 4 Complete: Stored {total_robot_files} robot files total")
        
        # Step 5: Parse robot files with working parser
        print("\\nStep 5: Parsing robot files...")
        robot_files = db.query(RawRepositoryData).filter(RawRepositoryData.file_type == 'robot').all()
        
        codebundles_created = 0
        for i, robot_file in enumerate(robot_files):
            if i % 100 == 0:
                print(f"Processing file {i+1}/{len(robot_files)}...")
                
            try:
                result = parse_robot_file_content(robot_file.file_content, robot_file.file_path, robot_file.collection_slug)
                if result:
                    # Get the collection
                    collection = db.query(CodeCollection).filter(CodeCollection.slug == result['collection_slug']).first()
                    if collection:
                        # Check if codebundle already exists
                        existing = db.query(Codebundle).filter(Codebundle.slug == result['slug']).first()
                        if not existing:
                            # Create new codebundle
                            codebundle = Codebundle(
                                codecollection_id=collection.id,
                                name=result['name'],
                                slug=result['slug'],
                                display_name=result['display_name'],
                                description=result['description'],
                                doc=result['doc'],
                                author=result['author'],
                                support_tags=result['support_tags'],
                                tasks=result['tasks'],
                                task_count=result['task_count'],
                                runbook_path=result['runbook_path'],
                                is_active=True
                            )
                            db.add(codebundle)
                            codebundles_created += 1
                            
                            if codebundles_created % 50 == 0:
                                db.commit()
                                
                    # Mark as processed
                    robot_file.is_processed = True
                    
            except Exception as e:
                print(f"Error parsing {robot_file.file_path}: {e}")
        
        db.commit()
        
        # Final status
        final_codebundles = db.query(Codebundle).count()
        total_tasks = sum(cb.task_count for cb in db.query(Codebundle).all())
        
        print(f"\\n=== SUCCESS ===")
        print(f"Created {codebundles_created} codebundles")
        print(f"Final count: {final_codebundles} codebundles with {total_tasks} tasks")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

