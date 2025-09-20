# CodeCollection Registry v2 - Microservices Architecture

A modern, scalable registry for RunWhen CodeCollections with AI-powered enhancement capabilities.

## Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │    │   Backend   │    │   Worker    │
│   (React)   │◄──►│  (FastAPI)  │◄──►│  (Celery)   │
│   Port 3000 │    │  Port 8001  │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  Database   │    │    Redis    │
                   │(PostgreSQL) │    │ (Message    │
                   │  Port 5432  │    │  Broker)    │
                   └─────────────┘    │  Port 6379  │
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

