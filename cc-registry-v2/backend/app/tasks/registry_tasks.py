"""
Minimal Registry Task System - Working Version
"""
import os
import yaml
import tempfile
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import Celery
from git import Repo

from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawRepositoryData
from app.models.version import CodeCollectionVersion
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    'registry_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

def _create_display_name(name: str) -> str:
    """Create a display name from a codebundle name"""
    import re
    display_words = []
    words = re.split(r'[-_]', name)
    
    for word in words:
        if word:
            camel_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', word)
            if camel_words:
                display_words.extend([w.capitalize() for w in camel_words])
            else:
                display_words.append(word.capitalize())
    
    return ' '.join(display_words)

def _parse_robot_file_content(content: str, file_path: str, collection_slug: str = None) -> Optional[Dict[str, Any]]:
    """Parse Robot Framework file content using the WORKING parser from generate_registry.py"""
    from app.tasks.fixed_parser import parse_robot_file_content
    return parse_robot_file_content(content, file_path, collection_slug)

# DISABLED: These stub functions were creating fake data and are not allowed
@celery_app.task(bind=True)
def seed_database_from_yaml_task(self, yaml_file_path: str = "/app/codecollections.yaml"):
    """DISABLED: This task was creating fake data"""
    logger.error("seed_database_from_yaml_task is DISABLED - it creates fake demo data")
    return {"status": "error", "message": "DISABLED: This task creates fake demo data and has been disabled"}

@celery_app.task(bind=True) 
def sync_all_collections_task(self):
    """DISABLED: This task was creating fake data"""
    logger.error("sync_all_collections_task is DISABLED - it creates fake demo data")
    return {"status": "error", "message": "DISABLED: This task creates fake demo data and has been disabled"}

@celery_app.task(bind=True)
def parse_all_codebundles_task(self):
    """DISABLED: This task was creating fake data"""
    logger.error("parse_all_codebundles_task is DISABLED - it creates fake demo data")
    return {"status": "error", "message": "DISABLED: This task creates fake demo data and has been disabled"}

@celery_app.task(bind=True)
def enhance_all_codebundles_task(self):
    """DISABLED: This task was creating fake data"""
    logger.error("enhance_all_codebundles_task is DISABLED - it creates fake demo data")
    return {"status": "error", "message": "DISABLED: This task creates fake demo data and has been disabled"}

@celery_app.task(bind=True)
def generate_metrics_task(self):
    """DISABLED: This task was creating fake data"""
    logger.error("generate_metrics_task is DISABLED - it creates fake demo data")
    return {"status": "error", "message": "DISABLED: This task creates fake demo data and has been disabled"}

def _parse_runwhen_discovery(db, collection_slug: str, codebundle_name: str) -> Dict[str, Any]:
    """Parse .runwhen directory for discovery configuration"""
    return {}
