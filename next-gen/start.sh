#!/bin/bash

# Start the CodeCollection Registry development environment

echo "🚀 Starting CodeCollection Registry development environment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://user:password@db:5432/codecollection_registry

# GitHub Integration
GITHUB_TOKEN=your_github_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# Security
SECRET_KEY=dev-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_URL=redis://redis:6379/0

# Environment
ENVIRONMENT=development
DEBUG=True
EOF
    echo "⚠️  Please update .env file with your GitHub token and other secrets"
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose up -d db redis

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Populate database with sample data
echo "📦 Populating database with sample data..."
docker-compose run --rm app python scripts/populate_data.py

# Start the application
echo "🎯 Starting application..."
docker-compose up app

echo "✅ Development environment started!"
echo "📖 API Documentation: http://localhost:8000/docs"
echo "🏥 Health Check: http://localhost:8000/api/v1/health"
