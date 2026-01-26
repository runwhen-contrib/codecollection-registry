#!/usr/bin/env python
"""
Run database migrations before starting the application.
This ensures the database schema is up-to-date.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from alembic.config import Config
from alembic import command
from app.core.config import settings

def run_migrations():
    """Run all pending database migrations"""
    try:
        print("=" * 60)
        print("Running database migrations...")
        print("=" * 60)
        
        # Create Alembic configuration
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option('sqlalchemy.url', settings.DATABASE_URL)
        
        # Run migrations to head
        command.upgrade(alembic_cfg, "head")
        
        print("=" * 60)
        print("✅ Database migrations completed successfully")
        print("=" * 60)
        return True
    except Exception as e:
        print("=" * 60)
        print(f"❌ Migration failed: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
