#!/usr/bin/env python
"""
Run database migrations before starting the application.
This ensures the database schema is up-to-date.

On a fresh database, Base.metadata.create_all() creates all tables first,
then Alembic migrations run (with IF NOT EXISTS guards) to stamp the
migration version so subsequent starts only run incremental migrations.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from alembic.config import Config
from alembic import command
from app.core.config import settings


def ensure_base_tables():
    """Create all tables from SQLAlchemy models if they don't exist yet.
    
    This handles a fresh database where no tables exist at all.
    create_all() is safe to call on an existing DB — it only creates
    tables that are missing and never alters existing ones.
    """
    from sqlalchemy import text
    from app.core.database import Base, engine
    # Import all models so they are registered on Base.metadata
    from app.models import CodeCollection, Codebundle, CodeCollectionVersion, AIEnhancementLog, TaskGrowthMetric  # noqa: F401

    # pgvector extension must exist before creating vector tables
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    print("Ensuring base tables exist...")
    Base.metadata.create_all(bind=engine)
    print("✅ Base tables ready")


def run_migrations():
    """Run all pending database migrations"""
    try:
        print("=" * 60)
        print("Running database migrations...")
        print("=" * 60)

        # Step 1: Ensure base tables exist (safe on existing DBs)
        ensure_base_tables()

        # Step 2: Run Alembic migrations for incremental changes
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
