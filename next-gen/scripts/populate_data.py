#!/usr/bin/env python3
"""
Populate database with sample data
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine, Base
from app.models import CodeCollection, Codebundle

def populate_data():
    """Populate database with sample data"""
    print("🗄️  Creating database tables...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    db = SessionLocal()
    try:
        # Check if data already exists
        existing_collections = db.query(CodeCollection).count()
        if existing_collections > 0:
            print(f"⚠️  Database already has {existing_collections} collections")
            return
        
        # Create sample codecollections
        collections_data = [
            {
                "name": "RunWhen Public CodeCollection",
                "slug": "rw-public-codecollection",
                "git_url": "https://github.com/runwhen-contrib/rw-public-codecollection",
                "description": "Python based CodeCollections that do not leverage a command line binary or bash script",
                "owner": "RunWhen",
                "owner_email": "shea.stewart@runwhen.com",
                "owner_icon": "https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg",
                "git_ref": "main"
            },
            {
                "name": "RunWhen CLI CodeCollection",
                "slug": "rw-cli-codecollection",
                "git_url": "https://github.com/runwhen-contrib/rw-cli-codecollection",
                "description": "CodeCollections based on command line binaries and bash scripts",
                "owner": "RunWhen",
                "owner_email": "shea.stewart@runwhen.com",
                "owner_icon": "https://assets-global.website-files.com/64f9646ad0f39e9ee5c116c4/659f80c7391d64a0ec2a840e_icon_rw-platform.svg",
                "git_ref": "main"
            }
        ]
        
        # Create codecollections
        for cc_data in collections_data:
            collection = CodeCollection(**cc_data)
            db.add(collection)
            print(f"➕ Added: {cc_data['name']}")
        
        db.commit()
        
        # Create sample codebundles
        codebundles_data = [
            {
                "codecollection_id": 1,
                "name": "kubernetes-pod-health",
                "slug": "kubernetes-pod-health",
                "display_name": "Kubernetes Pod Health Check",
                "description": "Monitor pod health and readiness in Kubernetes clusters",
                "doc": "This codebundle provides comprehensive pod health monitoring including readiness, liveness, and resource utilization checks.",
                "author": "RunWhen Team",
                "support_tags": ["KUBERNETES", "PODS", "HEALTH", "MONITORING"],
                "tasks": ["Check Pod Readiness", "Verify Pod Liveness", "Monitor Resource Usage", "Check Pod Events", "Validate Pod Status"],
                "task_count": 5
            },
            {
                "codecollection_id": 1,
                "name": "azure-nsg-validation",
                "slug": "azure-nsg-validation",
                "display_name": "Azure NSG Validation",
                "description": "Validate Network Security Group rules and configurations",
                "doc": "Comprehensive NSG validation including rule analysis, security group integrity, and traffic flow verification.",
                "author": "RunWhen Team",
                "support_tags": ["AZURE", "NSG", "NETWORK", "SECURITY"],
                "tasks": ["Validate NSG Rules", "Check Security Group Integrity", "Verify Traffic Flow", "Audit NSG Changes", "Monitor Network Access"],
                "task_count": 5
            },
            {
                "codecollection_id": 2,
                "name": "aws-s3-bucket-audit",
                "slug": "aws-s3-bucket-audit",
                "display_name": "AWS S3 Bucket Audit",
                "description": "Audit S3 buckets for security and compliance",
                "doc": "Comprehensive S3 bucket auditing including access policies, encryption status, and compliance checks.",
                "author": "RunWhen Team",
                "support_tags": ["AWS", "S3", "SECURITY", "COMPLIANCE"],
                "tasks": ["Check Bucket Encryption", "Validate Access Policies", "Audit Public Access", "Verify Compliance", "Monitor Bucket Changes"],
                "task_count": 5
            }
        ]
        
        # Create codebundles
        for cb_data in codebundles_data:
            codebundle = Codebundle(**cb_data)
            db.add(codebundle)
            print(f"➕ Added: {cb_data['display_name']}")
        
        db.commit()
        print("✅ Sample data created successfully")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    populate_data()
