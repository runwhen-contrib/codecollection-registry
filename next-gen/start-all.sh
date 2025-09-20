#!/bin/bash

echo "🚀 Starting CodeCollection Registry - Complete Stack"
echo "=================================================="

# Build and start all services
echo "📦 Building and starting all services..."
docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "🔍 Checking service health..."

# Check database
echo "📊 Database:"
docker-compose exec db pg_isready -U user -d codecollection_registry && echo "✅ Database is ready" || echo "❌ Database not ready"

# Check Redis
echo "🔴 Redis:"
docker-compose exec redis redis-cli ping && echo "✅ Redis is ready" || echo "❌ Redis not ready"

# Check FastAPI app
echo "🌐 FastAPI App:"
curl -s http://localhost:8001/api/v1/health | jq -r '.status' && echo "✅ FastAPI is ready" || echo "❌ FastAPI not ready"

# Check Celery worker
echo "👷 Celery Worker:"
docker-compose exec celery-worker celery -A app.tasks.data_population_tasks inspect ping && echo "✅ Celery Worker is ready" || echo "❌ Celery Worker not ready"

# Check Celery beat
echo "⏰ Celery Beat:"
docker-compose ps celery-beat | grep "Up" && echo "✅ Celery Beat is ready" || echo "❌ Celery Beat not ready"

# Check Flower
echo "🌸 Flower:"
curl -s http://localhost:5555 > /dev/null && echo "✅ Flower is ready" || echo "❌ Flower not ready"

echo ""
echo "🎉 All services started!"
echo ""
echo "📋 Service URLs:"
echo "  • FastAPI App:     http://localhost:8001"
echo "  • API Docs:        http://localhost:8001/docs"
echo "  • Flower Monitor:  http://localhost:5555"
echo "  • Frontend:        http://localhost:3000"
echo ""
echo "🔧 Management Commands:"
echo "  • View logs:       docker-compose logs -f [service]"
echo "  • Stop all:        docker-compose down"
echo "  • Restart:         docker-compose restart [service]"
echo ""
echo "📊 Task Management:"
echo "  • Admin Panel:     http://localhost:3000/admin"
echo "  • Task Manager:    http://localhost:3000/tasks"
echo "  • Flower Monitor:  http://localhost:5555"

