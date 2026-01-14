# CodeCollection Registry v2 - Microservices Architecture

A modern, scalable registry for RunWhen CodeCollections with AI-powered enhancement capabilities.

## Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │    │   Backend   │    │   Worker    │
│   (React)   │◄──►│  (FastAPI)  │◄──►│  (Celery)   │
│   Port 3000 │    │  Port 8001  │    │             │
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │                   │
                          │                   │
             ┌────────────┴────┬──────────────┘
             │                 │
             ▼                 ▼
    ┌─────────────┐    ┌─────────────┐
    │ MCP Server  │    │    Redis    │
    │ (Semantic   │    │ (Message    │
    │  Search)    │    │  Broker)    │
    │  Port 8000  │    │  Port 6379  │
    └─────────────┘    └─────────────┘
             │
             ▼
    ┌─────────────┐
    │  Database   │
    │(PostgreSQL) │
    │  Port 5432  │
    └─────────────┘
```

## Services

### 🎨 Frontend Service (`/frontend`)
- **Technology**: React + TypeScript + Material-UI
- **Purpose**: User interface for registry browsing and management
- **Port**: 3000
- **Features**: Registry browsing, admin panel, task monitoring

### ⚡ Backend Service (`/backend`)
- **Technology**: FastAPI + SQLAlchemy + Pydantic
- **Purpose**: REST API server and business logic
- **Port**: 8001
- **Features**: CRUD operations, authentication, task orchestration

### 🔄 Worker Service (`/worker`)
- **Technology**: Celery + Redis
- **Purpose**: Background task processing
- **Features**: Data population, AI enhancement, scheduled jobs

### 🗄️ Database Service (`/database`)
- **Technology**: PostgreSQL 15
- **Purpose**: Persistent data storage
- **Port**: 5432
- **Features**: CodeCollections, Codebundles, metrics, task history

### 📨 Redis Service
- **Technology**: Redis 7
- **Purpose**: Message broker for Celery
- **Port**: 6379
- **Features**: Task queuing, caching, session storage

### 🔍 MCP Server Service (`/mcp-server`)
- **Technology**: FastAPI + Vector Store
- **Purpose**: Semantic search and knowledge base
- **Port**: 8000
- **Features**: CodeBundle search, library lookup, AI-powered search

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git
- [Task](https://taskfile.dev/installation/) (recommended)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd codecollection-registry/cc-registry-v2
   ```

2. **Start all services**
   ```bash
   # Using Taskfile (recommended)
   task setup    # Initial setup
   task start    # Start all services
   
   # Or using the startup script
   ./start.sh
   
   # Or using docker-compose directly
   docker-compose up -d --build
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8001
   - API Documentation: http://localhost:8001/docs
   - Task Monitor (Flower): http://localhost:5555
   - MCP Server: http://localhost:8000 (optional - see [MCP Server Integration](MCP_SERVER_INTEGRATION.md))

### Service Management

```bash
# Using Taskfile (recommended)
task --list           # Show all available commands
task start           # Start all services
task stop            # Stop all services
task restart         # Restart all services
task logs            # View logs for all services
task status          # Check service status
task health          # Health check all services

# Development commands
task dev             # Start dev environment (backend + frontend)
task backend         # Start only backend services
task frontend        # Start only frontend
task workers         # Start only worker services

# Using docker-compose directly
docker-compose up -d                    # Start all services
docker-compose up -d database redis backend  # Start specific services
docker-compose logs -f backend          # View logs
docker-compose down                     # Stop all services
docker-compose build                    # Rebuild services
docker-compose up -d --build            # Rebuild and start
```

## Development Workflow

### Backend Development
```bash
# Enter backend container
docker-compose exec backend bash

# Run migrations
alembic upgrade head

# Run tests
pytest

# Format code
black app/
isort app/
```

### Frontend Development
```bash
# Enter frontend container
docker-compose exec frontend sh

# Install new packages
npm install <package-name>

# Run tests
npm test

# Build for production
npm run build
```

### Worker Development
```bash
# Monitor worker logs
docker-compose logs -f worker

# Monitor task queue
docker-compose logs -f flower
# Then visit http://localhost:5555
```

## Project Structure

```
codecollection-registry/
├── docker-compose.yml              # Service orchestration
├── README.md                       # This file
│
├── backend/                        # FastAPI Backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                # FastAPI app
│   │   ├── core/                  # Configuration
│   │   ├── models/                # Database models
│   │   ├── routers/               # API endpoints
│   │   ├── services/              # Business logic
│   │   └── tasks/                 # Celery tasks
│   └── tests/
│
├── frontend/                       # React Frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── components/            # Reusable components
│   │   ├── pages/                 # Page components
│   │   └── services/              # API clients
│   └── public/
│
├── worker/                         # Celery Workers
│   ├── Dockerfile
│   └── requirements.txt
│
└── database/                       # Database Setup
    └── init/
        └── 01-init.sql            # Initialization script
```

## Key Features

### 🔄 Database-Driven Architecture
- YAML files are used only for seeding
- Database is the single source of truth
- All operations read from database

### 🚀 Async Task Processing
- Background data population
- AI-powered enhancement
- Scheduled maintenance tasks

### 📊 Real-time Monitoring
- Task progress tracking
- System metrics
- Performance monitoring

### 🛡️ Security
- Token-based authentication
- CORS protection
- Input validation

## API Documentation

Visit http://localhost:8001/docs for interactive API documentation.

## Deployment

### Container Images

Container images are automatically built via GitHub Actions workflows on:
- Pull requests (build only, not pushed)
- Manual dispatch with custom options
- Push to main branch

**Two separate workflows:**

1. **CC-Registry-V2 Workflow** - Builds 3 images:
   ```
   us-docker.pkg.dev/<project>/<repo>/cc-registry-v2-backend:<tag>
   us-docker.pkg.dev/<project>/<repo>/cc-registry-v2-frontend:<tag>
   us-docker.pkg.dev/<project>/<repo>/cc-registry-v2-worker:<tag>
   ```

2. **MCP Server Workflow** - Builds 1 image:
   ```
   us-docker.pkg.dev/<project>/<repo>/runwhen-mcp-server:<tag>
   ```

**Why separate?** MCP server is a standalone component with its own release cycle. See [WORKFLOWS_SEPARATED.md](WORKFLOWS_SEPARATED.md) for details.

**Build and push images:**
```bash
# Build cc-registry-v2 images
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.1.0

# Build MCP server separately
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=v1.3.0
```

### Kubernetes Deployment

Deploy to Kubernetes test cluster:

```bash
# Update image references
task k8s:update-images REGISTRY=ghcr.io/your-org/your-repo TAG=v1.0.0

# Deploy to cluster
task k8s:deploy

# Check status
task k8s:status

# View logs
task k8s:logs SERVICE=backend
```

For detailed deployment instructions, see:
- 📚 [Deployment Guide](DEPLOYMENT_GUIDE.md) - Complete deployment walkthrough
- 🚀 [Quick Reference](QUICK_REFERENCE.md) - Command cheat sheet
- ☸️ [Kubernetes Manifests](k8s/README.md) - K8s deployment details
- 🐳 [Container Build](k8s/CONTAINER_BUILD.md) - Image build workflow

## Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick command reference
- **[WORKFLOWS_SEPARATED.md](WORKFLOWS_SEPARATED.md)** - Why workflows are separate
- **[MCP_SERVER_INTEGRATION.md](MCP_SERVER_INTEGRATION.md)** - MCP server integration guide
- **[k8s/README.md](k8s/README.md)** - Kubernetes deployment details
- **[k8s/CONTAINER_BUILD.md](k8s/CONTAINER_BUILD.md)** - Container build workflow
- **[GCR_SETUP.md](GCR_SETUP.md)** - Google Cloud Registry setup
- **[Taskfile.yml](Taskfile.yml)** - Available task commands
- **[docker-compose.yml](docker-compose.yml)** - Local development setup

## Available Commands

```bash
task --list                  # Show all available commands

# Local Development
task start                   # Start all services
task stop                    # Stop all services
task logs                    # View logs
task status                  # Check status
task health                  # Health check

# Container Images
task image:build             # Build all images
task image:publish           # Build, tag, and push images

# Kubernetes
task k8s:deploy              # Deploy to K8s
task k8s:status              # Check K8s status
task k8s:logs                # View K8s logs
task k8s:restart             # Restart K8s deployment
task k8s:rollback            # Rollback K8s deployment
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request
6. Wait for CI/CD checks to pass

The GitHub Actions workflow will automatically build container images for your PR.

## Troubleshooting

### Common Issues

**Services not starting:**
```bash
task status          # Check service status
task logs            # View logs
docker-compose ps    # Check container status
```

**Port conflicts:**
```bash
# Stop services using the ports
lsof -i :3000        # Check what's using port 3000
lsof -i :8001        # Check what's using port 8001
```

**Database issues:**
```bash
# Reset database
docker-compose down -v
docker-compose up -d database
```

**Image build failures:**
```bash
# Clean docker cache
docker system prune -af
task clean:all
```

For more troubleshooting help, see the [Deployment Guide](DEPLOYMENT_GUIDE.md).

## License

[Your License Here]

