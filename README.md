# CodeCollection Registry

A registry for RunWhen CodeCollections -- browsing, searching, and configuring automation CodeBundles.

## Repository Structure

This repository contains two active projects:

### [cc-registry-v2/](cc-registry-v2/) -- Registry Application

The production registry application. A microservices architecture with 8 Docker services:

- **Frontend** -- React 19 + TypeScript + MUI v7 (port 3000)
- **Backend** -- FastAPI + SQLAlchemy 2.0 REST API (port 8001)
- **MCP Server** -- Stateless MCP tool server (port 8000)
- **Worker / Scheduler** -- Celery background tasks and cron scheduling
- **Database** -- PostgreSQL 15 + pgvector
- **Redis** -- Message broker for Celery

```bash
cd cc-registry-v2/
task start    # Start all services
task --list   # See all available commands
```

See [cc-registry-v2/README.md](cc-registry-v2/README.md) for setup, configuration, and deployment docs.

### [mcp-server/](mcp-server/) -- MCP Server

A standalone FastAPI server that exposes MCP tools for querying the CodeCollection Registry. Delegates all data access to the backend API. Includes an offline indexer for generating vector embeddings.

```bash
cd mcp-server/
docker-compose up mcp-http
```

See [mcp-server/README.md](mcp-server/README.md) for details.

## Requesting or Tracking CodeBundles

- Request new CodeBundles via [Issues templates](https://github.com/runwhen-contrib/codecollection-registry/issues/new/choose)
- Track development status in the [GitHub Project](https://github.com/orgs/runwhen-contrib/projects/1)

## Documentation

| Topic | Location |
|---|---|
| Architecture | [cc-registry-v2/docs/ARCHITECTURE.md](cc-registry-v2/docs/ARCHITECTURE.md) |
| Configuration | [cc-registry-v2/docs/CONFIGURATION.md](cc-registry-v2/docs/CONFIGURATION.md) |
| Indexing pipeline | [cc-registry-v2/docs/MCP_WORKFLOW.md](cc-registry-v2/docs/MCP_WORKFLOW.md) |
| Deployment | [cc-registry-v2/docs/DEPLOYMENT_GUIDE.md](cc-registry-v2/docs/DEPLOYMENT_GUIDE.md) |
| All docs index | [cc-registry-v2/docs/README.md](cc-registry-v2/docs/README.md) |

## Legacy Static Site (Deprecated)

The original static site generator (`generate_registry.py`, `cc-registry/`, `rebuild.sh`) is deprecated and no longer deployed. The GitHub Pages deployment workflow has been removed. These files remain in the repository for historical reference but are not maintained.

The v2 application fully replaces the static site with a database-driven registry, AI-powered search, and an admin interface.
