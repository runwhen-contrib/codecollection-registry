#!/bin/bash
set -e

echo "============================================================"
echo "Starting CodeCollection Registry Backend"
echo "============================================================"

# Run database migrations
echo "Running database migrations..."
python run_migrations.py

if [ $? -eq 0 ]; then
    echo "✅ Migrations completed successfully"
else
    echo "❌ Migrations failed - exiting"
    exit 1
fi

echo "============================================================"
echo "Starting Uvicorn server..."
echo "============================================================"

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8001 "$@"
