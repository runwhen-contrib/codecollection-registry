# CodeCollection Registry v2 Documentation

Welcome to the CodeCollection Registry v2 documentation. This directory contains all project documentation organized by topic.

## 📚 Documentation Index

### Getting Started

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide for Docker Compose and Kubernetes
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick commands and common operations
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration options and environment variables

### Chat & AI

- **[CHAT.md](CHAT.md)** - Chat system architecture, dual search pipeline, LLM synthesis, follow-up detection
- **[CHAT_DEBUG.md](CHAT_DEBUG.md)** - Debug console features, quality analysis, API endpoints, testing workflows

### Core Features

- **[MCP_WORKFLOW.md](MCP_WORKFLOW.md)** - **Complete guide** to App → MCP → Indexing workflow
- **[SCHEDULES.md](SCHEDULES.md)** - Celery Beat schedule management and configuration
- **[MCP_INDEXING_SCHEDULE.md](MCP_INDEXING_SCHEDULE.md)** - Automated documentation indexing schedules
- **[WORKFLOW_FIX.md](WORKFLOW_FIX.md)** - Workflow orchestration and task chaining
- **[ANALYTICS_FEATURES.md](ANALYTICS_FEATURES.md)** - Task growth chart and Google Analytics integration

### Infrastructure Setup

- **[DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md)** - PostgreSQL and Redis configuration options
- **[AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md)** - Azure OpenAI integration for AI features
- **[HELM_VERSION_MANAGEMENT.md](HELM_VERSION_MANAGEMENT.md)** - Helm chart version tracking
- **[SECRETS_UPDATED.md](SECRETS_UPDATED.md)** - Secret management and environment variables

### Troubleshooting

- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Kubernetes Specific

See the [`../k8s/`](../k8s/) directory for Kubernetes-specific documentation:
- `k8s/README.md` - Kubernetes deployment overview
- `k8s/INGRESS_SETUP.md` - Ingress and TLS configuration
- `k8s/CONTAINER_BUILD.md` - Building container images
- `k8s/ZALANDO_POSTGRES_CONFIG.md` - Zalando Postgres Operator setup

### Archived Documentation

The [`archive/`](archive/) directory contains older documentation that may still be useful for historical reference:
- Previous migration guides
- Deprecated features
- Old troubleshooting notes

## 🏗️ Project Architecture

```
cc-registry-v2/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── routers/  # API endpoints
│   │   ├── services/ # Business logic
│   │   ├── models/   # Database models
│   │   ├── tasks/    # Celery tasks
│   │   └── core/     # Config & dependencies
│   └── alembic/      # Database migrations
├── frontend/         # React + TypeScript UI
│   ├── src/
│   │   ├── pages/    # Page components
│   │   ├── components/ # Reusable components
│   │   └── services/ # API clients
├── k8s/              # Kubernetes manifests
├── docs/             # Documentation (this directory)
├── database/         # DB init scripts
└── docker-compose.yml
```

## 🚀 Quick Start

1. **Setup:** Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
2. **Configure:** Review [CONFIGURATION.md](CONFIGURATION.md)
3. **Deploy:** Use [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for common commands
4. **Troubleshoot:** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if issues arise

## 🔗 External Resources

- **Main Repository:** https://github.com/runwhen-contrib/codecollection-registry
- **RunWhen Documentation:** https://docs.runwhen.com
- **MCP Server:** ../mcp-server/

## 📝 Contributing to Documentation

When adding new documentation:
1. Create files in `docs/` directory (not project root)
2. Use clear, descriptive names (e.g., `FEATURE_NAME.md`)
3. Update this README.md index
4. Follow existing documentation style

**Do NOT create:**
- Temporary fix files (`*-FIX.md`, `*-SUMMARY.md`, `*-UPDATE.md`)
- Duplicate documentation
- Documentation in project root (except `README.md`)

Old or deprecated docs should be moved to `docs/archive/`.

---

**Last Updated:** 2026-02-09
