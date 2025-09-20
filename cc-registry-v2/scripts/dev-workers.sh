#!/bin/bash

# Development script for worker services only
echo "🔄 Starting worker development environment..."

# Start dependencies
docker-compose up -d database redis backend

# Wait for dependencies
echo "⏳ Waiting for dependencies..."
until curl -s http://localhost:8001/api/v1/health > /dev/null 2>&1; do
    sleep 2
done

echo "✅ Dependencies ready"

# Start workers and monitoring
docker-compose up worker scheduler flower --build

