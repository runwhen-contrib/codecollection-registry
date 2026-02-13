# Database Migrations with Alembic

This directory contains database migrations managed by Alembic.

## Automatic Migrations on Startup

The backend automatically runs pending migrations when it starts:
- **Production/Kubernetes**: The `start.sh` script runs migrations before starting Uvicorn
- **Development**: docker-compose runs migrations before starting the dev server

## Creating New Migrations

### Manual Migration (Recommended for complex changes)

```bash
# Run inside the backend container
docker exec -it registry-backend bash

# Create a new migration file
python -m alembic revision -m "describe_your_changes"

# Edit the generated file in alembic/versions/
# Add your upgrade() and downgrade() logic

# Test the migration
python run_migrations.py
```

### Auto-generated Migration (for simple schema changes)

```bash
# Run inside the backend container
docker exec -it registry-backend bash

# Auto-generate migration from model changes
python -m alembic revision --autogenerate -m "describe_your_changes"

# ALWAYS review the generated migration file!
# Auto-generate doesn't catch everything

# Test the migration
python run_migrations.py
```

## Migration Commands

```bash
# Run all pending migrations
python run_migrations.py

# Or use alembic directly:
python -m alembic upgrade head

# Show current version
python -m alembic current

# Show migration history
python -m alembic history

# Rollback one migration
python -m alembic downgrade -1

# Rollback to specific version
python -m alembic downgrade <revision_id>
```

## Naming Convention

Migrations use a simple numeric prefix:
- `001_add_user_variables.py`
- `002_add_enhanced_metadata.py`
- etc.

## Important Notes

1. **Migrations run automatically** on container startup
2. **Always test migrations locally** before pushing to production
3. **Migrations are idempotent** - safe to run multiple times
4. **Never edit applied migrations** - create a new migration to fix issues
5. **Backup production database** before applying major schema changes
