#!/bin/bash

# CodeCollection Registry - Simple Startup Script
# Kubernetes-ready: Uses simple docker-compose commands

set -e

echo "🚀 Starting CodeCollection Registry..."

# Create .env file from example if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp env.example .env
    echo "⚠️  Please update .env file with your actual configuration values"
fi

# Simple docker-compose startup - let Docker handle the orchestration
echo "🏗️  Starting all services with docker-compose..."
docker-compose up -d --build

echo ""
echo "⏳ Services are starting up..."
echo "   Use 'docker-compose logs -f' to monitor startup progress"
echo ""
echo "📱 Once ready, access the application at:"
echo "   Frontend:        http://localhost:3000"
echo "   Backend API:     http://localhost:8001"
echo "   API Docs:        http://localhost:8001/docs"
echo "   Task Monitor:    http://localhost:5555"
echo ""
echo "🔧 Useful commands:"
echo "   Task runner:     task --list"
echo "   View logs:       task logs"
echo "   Stop services:   task stop"
echo "   Restart:         task restart"
echo "   Service status:  task status"
echo ""
echo "💡 Install task runner: https://taskfile.dev/installation/"

