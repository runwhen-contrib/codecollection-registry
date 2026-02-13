#!/bin/bash

# Development script for frontend service only
echo "🎨 Starting frontend development environment..."

# Start backend dependencies first
docker-compose up -d database redis backend

# Wait for backend
echo "⏳ Waiting for backend..."
until curl -s http://localhost:8001/api/v1/health > /dev/null 2>&1; do
    sleep 2
done

echo "✅ Backend ready"

# Start frontend in development mode
docker-compose up frontend --build

