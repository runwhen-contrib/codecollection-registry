# CodeCollection Registry v2 Documentation

All project documentation, organized by topic.

## Architecture and Design

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture: services, data flow, PostgreSQL + pgvector, MCP server, Celery tasks
- **[MCP_WORKFLOW.md](MCP_WORKFLOW.md)** - Document indexing pipeline, embedding generation, vector store, and search flow
- **[CHAT.md](CHAT.md)** - Chat system architecture, dual search pipeline, LLM synthesis, follow-up detection

## Setup and Configuration

- **[CONFIGURATION.md](CONFIGURATION.md)** - Environment variables, secrets, and configuration files
- **[AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md)** - Azure OpenAI integration (GPT + Embeddings)
- **[DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md)** - PostgreSQL and Redis configuration options
- **[SCHEDULES.md](SCHEDULES.md)** - Celery Beat schedule management and format reference
- **[MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md)** - Automated documentation indexing schedules

## Deployment

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide (Docker Compose and Kubernetes)
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick commands and common operations

## Feature Documentation

- **[ANALYTICS_FEATURES.md](ANALYTICS_FEATURES.md)** - Task growth chart and Google Analytics integration
- **[CHAT_DEBUG.md](CHAT_DEBUG.md)** - Chat debug console, quality analysis, testing workflows
- **[HELM_VERSION_MANAGEMENT.md](HELM_VERSION_MANAGEMENT.md)** - Helm chart version tracking
- **[USER_VARIABLES_FEATURE.md](USER_VARIABLES_FEATURE.md)** - User variables parsing and display

## Troubleshooting

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

## Kubernetes

See the [`../k8s/`](../k8s/) directory:

- `k8s/README.md` - Kubernetes deployment overview
- `k8s/INGRESS_SETUP.md` - Ingress and TLS configuration
- `k8s/CONTAINER_BUILD.md` - Container image build workflow
- `k8s/ZALANDO_POSTGRES_CONFIG.md` - Zalando Postgres Operator setup

## Quick Start

1. Review [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
2. Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for setup
3. Configure with [CONFIGURATION.md](CONFIGURATION.md)
4. Use [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for day-to-day commands

## Contributing to Documentation

- All docs go in this `docs/` directory (not the project root)
- Use clear, descriptive names (e.g., `FEATURE_NAME.md`)
- Update this README index when adding new docs
- Do not create temporary files (`*-FIX.md`, `*-SUMMARY.md`, `*-UPDATE.md`)
