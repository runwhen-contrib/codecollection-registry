#!/usr/bin/env python3
"""
Test script for helm chart synchronization functionality.
Run this to test the helm chart version sync without starting the full application.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.database import SessionLocal, engine, Base
from app.services.helm_sync import sync_runwhen_local_chart
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_helm_sync():
    """Test the helm chart synchronization."""
    logger.info("Starting helm chart sync test...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Sync the runwhen-local chart
        result = sync_runwhen_local_chart(db)
        
        logger.info("Helm chart sync completed successfully!")
        logger.info(f"Result: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Helm chart sync failed: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    test_helm_sync()
