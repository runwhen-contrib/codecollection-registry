#!/usr/bin/env python3
"""
Script to create sample release data for testing the release system
"""

import sys
import os
from datetime import datetime, timedelta
from random import choice, randint

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models import CodeCollection, CodeCollectionRelease, ReleaseCodebundle


def create_sample_releases():
    """Create sample release data for existing collections"""
    
    db = SessionLocal()
    try:
        # Get existing collections
        collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
        
        if not collections:
            print("No collections found. Please populate collections first.")
            return
        
        print(f"Creating sample releases for {len(collections)} collections...")
        
        # Sample release data
        version_patterns = [
            ["v1.0.0", "v1.1.0", "v1.2.0", "v2.0.0", "v2.1.0"],
            ["v0.1.0", "v0.2.0", "v0.3.0", "v1.0.0", "v1.0.1"],
            ["v2.0.0", "v2.1.0", "v2.2.0", "v3.0.0-beta", "v3.0.0"],
            ["v1.5.0", "v1.6.0", "v2.0.0-alpha", "v2.0.0-beta", "v2.0.0"],
        ]
        
        release_names = [
            "Initial Release",
            "Bug Fixes and Improvements", 
            "New Features",
            "Performance Updates",
            "Security Patches",
            "Major Update",
            "Beta Release",
            "Stable Release"
        ]
        
        descriptions = [
            "This release includes bug fixes and performance improvements.",
            "Major new features and enhancements added.",
            "Security updates and stability improvements.",
            "Performance optimizations and bug fixes.",
            "New codebundles and task improvements.",
            "Breaking changes and API updates.",
            "Beta version with experimental features.",
            "Stable release with comprehensive testing."
        ]
        
        total_releases = 0
        
        for collection in collections:
            print(f"Creating releases for collection: {collection.name}")
            
            # Choose a version pattern
            versions = choice(version_patterns)
            base_date = datetime.utcnow() - timedelta(days=randint(30, 365))
            
            for i, version in enumerate(versions):
                # Create release
                release_date = base_date + timedelta(days=i * randint(15, 45))
                is_prerelease = any(pre in version.lower() for pre in ['alpha', 'beta', 'rc'])
                is_latest = (i == len(versions) - 1) and not is_prerelease
                
                release = CodeCollectionRelease(
                    codecollection_id=collection.id,
                    tag_name=version,
                    git_ref=version,
                    release_name=choice(release_names),
                    description=choice(descriptions),
                    is_latest=is_latest,
                    is_prerelease=is_prerelease,
                    release_date=release_date,
                    synced_at=datetime.utcnow(),
                    is_active=True
                )
                
                db.add(release)
                db.flush()  # Get the release ID
                
                # Create sample codebundles for this release
                codebundle_count = randint(3, 8)
                for j in range(codebundle_count):
                    codebundle = ReleaseCodebundle(
                        release_id=release.id,
                        name=f"sample-codebundle-{j+1}",
                        slug=f"sample-codebundle-{j+1}",
                        display_name=f"Sample CodeBundle {j+1}",
                        description=f"Sample codebundle for testing release {version}",
                        author="Sample Author",
                        support_tags=["KUBERNETES", "TROUBLESHOOTING", "MONITORING"][:randint(1, 3)],
                        categories=["Infrastructure", "Monitoring"][:randint(1, 2)],
                        task_count=randint(1, 5),
                        sli_count=randint(0, 2),
                        runbook_path=f"codebundles/sample-codebundle-{j+1}/runbook.robot",
                        runbook_source_url=f"{collection.git_url}/blob/{version}/codebundles/sample-codebundle-{j+1}/runbook.robot",
                        added_in_release=i == 0 or randint(0, 100) < 20,  # 20% chance of being new
                        modified_in_release=i > 0 and randint(0, 100) < 30,  # 30% chance of being modified
                        removed_in_release=False,
                        discovery_info={"is_discoverable": choice([True, False])}
                    )
                    
                    db.add(codebundle)
                
                total_releases += 1
                print(f"  Created release {version} with {codebundle_count} codebundles")
        
        db.commit()
        print(f"\nSuccessfully created {total_releases} sample releases!")
        
        # Print summary
        print("\nSummary:")
        for collection in collections:
            release_count = db.query(CodeCollectionRelease).filter(
                CodeCollectionRelease.codecollection_id == collection.id
            ).count()
            latest_release = db.query(CodeCollectionRelease).filter(
                CodeCollectionRelease.codecollection_id == collection.id,
                CodeCollectionRelease.is_latest == True
            ).first()
            
            print(f"  {collection.name}: {release_count} releases" + 
                  (f" (latest: {latest_release.tag_name})" if latest_release else ""))
        
    except Exception as e:
        print(f"Error creating sample releases: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_releases()


