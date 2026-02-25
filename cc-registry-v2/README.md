# CodeCollection Registry v2 - Microservices Architecture

A modern, scalable registry for RunWhen CodeCollections with AI-powered enhancement capabilities.

## Architecture Overview

8 Docker services orchestrated by `docker-compose.yml`:

```
                ┌──────────────────────────────────────────────┐
                │               Frontend (React)                │
                │                   :3000                       │
                └────────────────────┬─────────────────────────┘
                                     │ HTTP
                                     ▼
┌────────────────┐          ┌────────────────────┐         ┌──────────────┐
│   MCP Server   │◄─────────│     Backend        │────────►│    Worker    │
│  (stateless)   │  HTTP    │    (FastAPI)       │  Celery │   (Celery)   │
│    :8000       │  /tools/ │     :8001          │  tasks  │              │
└────────────────┘  call    └────────┬───────────┘         └──────┬───────┘
        │                            │                            │
        │  REGISTRY_API_URL          │                            │
        │  (all data queries         │                            │
        │   delegate to backend)     │                            │
        └───────────►────────────────┘                            │
                                     │                            │
                       ┌─────────────┼────────────────────────────┘
                       │             │
                       ▼             ▼
              ┌──────────────┐  ┌──────────┐  ┌───────────┐
              │  PostgreSQL  │  │  Redis   │  │ Scheduler │
              │  + pgvector  │  │  :6379   │  │  (Beat)   │
              │    :5432     │  └──────────┘  └───────────┘
              └──────────────┘
```

| Service | Stack | Port | Purpose |
|---------|-------|------|---------|
| **frontend** | React 19 + TypeScript + MUI v7 | 3000 | SPA for browsing and managing CodeBundles |
| **backend** | FastAPI + SQLAlchemy 2.0 + pgvector | 8001 | REST API, business logic, AI enhancement, embedding generation, vector search |
| **mcp-server** | FastAPI (separate repo: `../mcp-server`) | 8000 | Stateless MCP tool server, delegates all queries to backend API |
| **worker** | Celery (shares backend image) | -- | Background tasks: sync, parse, enhance, embed |
| **scheduler** | Celery Beat (shares backend image) | -- | Cron-driven task scheduling |
| **database** | PostgreSQL 15 + pgvector | 5432 | Primary data store with vector extension |
| **redis** | Redis 7 Alpine | 6379 | Celery broker and result backend |
| **flower** | Flower 2.0 | 5555 | Celery monitoring dashboard |

For full architecture details, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

## Configuration

### Database and Redis

The application supports flexible configuration for both database and Redis connections:

- **Database**: Standalone PostgreSQL or managed services (Azure Database, AWS RDS)
  - Option 1: Complete `DATABASE_URL`
  - Option 2: Individual components (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, etc.)

- **Redis**: Standalone Redis or Redis Sentinel for high availability
  - Option 1: Complete `REDIS_URL`
  - Option 2: Redis Sentinel (`REDIS_SENTINEL_HOSTS`, `REDIS_SENTINEL_MASTER`, etc.)

**See [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) for complete configuration guide.**

### Azure OpenAI

The application requires Azure OpenAI credentials for two purposes:

- **GPT/Chat**: Used by backend for AI enhancement features
- **Embeddings**: Used by MCP server for semantic search

**See [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) for configuration details.**

### Secrets Configuration

All secrets are managed via Kubernetes secrets. See [k8s/secrets-example.yaml](k8s/secrets-example.yaml) for examples.

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

### Architecture and Design
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, services, data flow
- **[docs/MCP_WORKFLOW.md](docs/MCP_WORKFLOW.md)** - Document indexing pipeline and search flow
- **[docs/CHAT.md](docs/CHAT.md)** - Chat system architecture

### Setup and Configuration
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** - Environment variables and secrets
- **[docs/AZURE_OPENAI_SETUP.md](docs/AZURE_OPENAI_SETUP.md)** - Azure OpenAI configuration
- **[docs/DATABASE_REDIS_CONFIG.md](docs/DATABASE_REDIS_CONFIG.md)** - Database and Redis setup
- **[docs/SCHEDULES.md](docs/SCHEDULES.md)** - Schedule management
- **[docs/MCP_INDEXING_SCHEDULE.md](docs/MCP_INDEXING_SCHEDULE.md)** - Automated indexing setup

### Deployment
- **[docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** - Complete deployment guide
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Quick command reference
- **[k8s/README.md](k8s/README.md)** - Kubernetes deployment details
- **[k8s/CONTAINER_BUILD.md](k8s/CONTAINER_BUILD.md)** - Container build workflow

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

