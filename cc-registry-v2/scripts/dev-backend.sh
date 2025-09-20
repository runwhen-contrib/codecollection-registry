#!/bin/bash

# Development script for backend service only
echo "🔧 Starting backend development environment..."

# Start dependencies
docker-compose up -d database redis

# Wait for dependencies
echo "⏳ Waiting for dependencies..."
until docker-compose exec -T database pg_isready -U user -d codecollection_registry > /dev/null 2>&1; do
    sleep 1
done
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    sleep 1
done

echo "✅ Dependencies ready"

# Start backend in development mode
docker-compose up backend --build

