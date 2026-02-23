# Configuration Guide

Environment variables, secrets, and configuration files for the CodeCollection Registry.

## Secrets File (`az.secret`)

All sensitive credentials live in `az.secret` at the project root (`cc-registry-v2/az.secret`). This file is not committed to git. Format:

```bash
export AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-key-here
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
export AZURE_OPENAI_API_VERSION=2024-02-15-preview
export AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-embedding-instance.openai.azure.com/
export AZURE_OPENAI_EMBEDDING_API_KEY=your-embedding-key
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

The file is loaded by `docker-compose.yml` as `env_file` for the backend, worker, scheduler, and frontend services.

## Service Ports

| Service | Port | URL |
|---|---|---|
| Frontend | 3000 | http://localhost:3000 |
| Backend API | 8001 | http://localhost:8001/api/v1/ |
| Backend Swagger | 8001 | http://localhost:8001/docs |
| MCP Server | 8000 | http://localhost:8000 |
| MCP Server Docs | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | `postgresql://user:password@localhost:5432/codecollection_registry` |
| Redis | 6379 | `redis://localhost:6379/0` |
| Flower | 5555 | http://localhost:5555 |

## Environment Variables

### Database

The backend supports two configuration modes:

**Option 1: Connection string**

```bash
DATABASE_URL=postgresql://user:password@database:5432/codecollection_registry
```

**Option 2: Individual components**

```bash
DB_HOST=database
DB_PORT=5432
DB_USER=user
DB_PASSWORD=password
DB_NAME=codecollection_registry
```

Local development defaults are set in `docker-compose.yml`. For managed databases (Azure, AWS RDS), use the individual component vars or a full connection string.

See [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) for advanced database configuration.

### Redis

**Option 1: Direct connection**

```bash
REDIS_URL=redis://redis:6379/0
```

**Option 2: Redis Sentinel** (for high-availability deployments)

```bash
REDIS_SENTINEL_HOSTS=redis-sentinel:26379
REDIS_SENTINEL_MASTER=mymaster
REDIS_PASSWORD=your-redis-password
REDIS_DB=0
```

See [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) for Sentinel configuration details.

### Azure OpenAI -- GPT (backend)

Used by the backend for AI enhancement of codebundles and chat LLM synthesis.

```bash
AI_SERVICE_PROVIDER=azure-openai
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AI_ENHANCEMENT_ENABLED=true
```

### Azure OpenAI -- Embeddings (indexer)

Used by the MCP indexer (`indexer.py`) for generating vector embeddings. Supports a dedicated embedding endpoint or falls back to the main Azure OpenAI endpoint.

**Dedicated embedding endpoint (preferred):**

```bash
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-embedding-instance.openai.azure.com/
AZURE_OPENAI_EMBEDDING_API_KEY=your-embedding-key
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_EMBEDDING_API_VERSION=2024-02-15-preview
```

**Fallback to main endpoint:**

If `AZURE_OPENAI_EMBEDDING_*` vars are not set, the backend's embedding service uses `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` instead.

**No Azure credentials:**

If neither set of credentials is available, the embedding step is silently skipped. Vector tables remain empty and keyword search continues to work normally.

See [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) for detailed setup instructions.

### MCP Server

```bash
# Backend sets this to reach the MCP server
MCP_SERVER_URL=http://mcp-server:8000

# MCP server sets this to reach the backend API
REGISTRY_API_URL=http://backend:8001
```

### GitHub Integration (MCP server)

Required for the `request_codebundle` tool to create GitHub issues:

```bash
GITHUB_TOKEN=ghp_your-personal-access-token
```

### Other

```bash
ENVIRONMENT=development    # or "production"
MCP_LOG_LEVEL=INFO         # DEBUG, INFO, WARNING, ERROR
```

## Configuration Files

### `schedules.yaml`

Defines all Celery Beat scheduled tasks. Located at `cc-registry-v2/schedules.yaml`, mounted read-only into the backend, worker, and scheduler containers.

See [SCHEDULES.md](SCHEDULES.md) for the schedule format reference.

### `codecollections.yaml`

Defines which git repositories to index. Located at the repo root (`codecollections.yaml`), used by the MCP indexer.

```yaml
codecollections:
  - name: "RunWhen CLI CodeCollection"
    slug: rw-cli-codecollection
    git_url: https://github.com/runwhen-contrib/rw-cli-codecollection
    owner: RunWhen
    description: "CLI-based automation codebundles"
```

### `mcp-server/sources.yaml`

Defines documentation URLs to crawl for indexing. See [MCP_WORKFLOW.md](MCP_WORKFLOW.md) for format details.

### `mcp-server/docs.yaml`

Managed documentation catalog used by the `find_documentation` and `get_development_requirements` tools at runtime.

### `map-tag-icons.yaml`

Maps support tag names to icon identifiers. Located at the repo root, mounted read-only into the backend.

## Admin Login

### Local development

Default credentials are set in `az.secret` or fall back to:

| Field | Value |
|---|---|
| Email | `dev@example.com` |
| Password | `password` |

### Kubernetes

Admin credentials are stored in the `azure-openai-credentials` Kubernetes secret and injected via `envFrom`.

## Docker Compose Overrides

For local development, `docker-compose.yml` sets sensible defaults:

```yaml
environment:
  - DATABASE_URL=postgresql://user:password@database:5432/codecollection_registry
  - REDIS_URL=redis://redis:6379/0
  - MCP_SERVER_URL=http://mcp-server:8000
  - AI_SERVICE_PROVIDER=azure-openai
  - REACT_APP_API_URL=http://localhost:8001/api/v1
```

Override these by setting values in `az.secret` or creating a `docker-compose.override.yml`.

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) -- System architecture
- [DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md) -- Database and Redis deep-dive
- [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md) -- Azure OpenAI setup guide
- [SECRETS_UPDATED.md](SECRETS_UPDATED.md) -- Secrets management reference
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) -- Production deployment
