#!/bin/bash
# Documentation Cleanup Script
# Run this to remove stale docs and keep only clean documentation in docs/

cd "$(dirname "$0")/.."

echo "Creating docs/archive folder..."
mkdir -p docs/archive

echo "Moving stale documentation to archive..."

# Stale migration and fix documentation
mv AI_ENHANCEMENT_README.md docs/archive/ 2>/dev/null
mv CELERY_FIXES_FINAL.md docs/archive/ 2>/dev/null
mv CELERY_TASK_FIXES.md docs/archive/ 2>/dev/null
mv CONFIG_UPDATE_SUMMARY.md docs/archive/ 2>/dev/null
mv GCR_MIGRATION_SUMMARY.md docs/archive/ 2>/dev/null
mv GCR_SETUP.md docs/archive/ 2>/dev/null
mv MCP_SERVER_ADDED.md docs/archive/ 2>/dev/null
mv RESET_ENHANCEMENT_FIX.md docs/archive/ 2>/dev/null
mv WORKFLOWS_SEPARATED.md docs/archive/ 2>/dev/null
mv WORKFLOW_UPDATED.md docs/archive/ 2>/dev/null
mv YAML_SCHEDULES_MIGRATION.md docs/archive/ 2>/dev/null
mv SCHEDULE_MANAGEMENT_FEATURE.md docs/archive/ 2>/dev/null

# Redundant schedule docs (consolidated into docs/SCHEDULES.md)
mv QUICK_START_SCHEDULES.md docs/archive/ 2>/dev/null
mv WORKFLOW_SCHEDULES.md docs/archive/ 2>/dev/null
mv README_SCHEDULES.md docs/archive/ 2>/dev/null

# Move remaining useful docs to docs/
mv AZURE_OPENAI_SETUP.md docs/ 2>/dev/null
mv DATABASE_REDIS_CONFIG.md docs/archive/ 2>/dev/null  # Consolidated into CONFIGURATION.md
mv SECRETS_UPDATED.md docs/archive/ 2>/dev/null  # Stale
mv MCP_SERVER_INTEGRATION.md docs/archive/ 2>/dev/null  # Historical
mv HELM_VERSION_MANAGEMENT.md docs/ 2>/dev/null  # Keep - useful
mv debug_jobs.md docs/archive/ 2>/dev/null  # Consolidated into TROUBLESHOOTING.md

# Keep these in root
# - README.md (main project readme)
# - DEPLOYMENT_GUIDE.md (or move to docs/)
# - QUICK_REFERENCE.md (or move to docs/)

echo "Optionally move to docs/ (decide if you want them in root or docs/):"
echo "  - DEPLOYMENT_GUIDE.md"
echo "  - QUICK_REFERENCE.md"

echo ""
echo "✓ Cleanup complete!"
echo ""
echo "Documentation structure:"
echo "  docs/README.md         - Main documentation index"
echo "  docs/SCHEDULES.md      - Schedule configuration guide"
echo "  docs/CONFIGURATION.md  - Environment and config"
echo "  docs/TROUBLESHOOTING.md - Debug and troubleshooting"
echo "  docs/archive/          - Historical/stale docs"
echo ""
echo "Root files remaining:"
ls -1 *.md 2>/dev/null | head -10
