# RunWhen Registry MCP Server

A minimal HTTP/REST API server for querying RunWhen codecollection data.

## Quick Start

**Prerequisites:** Docker and Docker Compose (+ optional: Azure OpenAI for LLM features)

```bash
cd /workspaces/codecollection-registry/hack/mcp

# Configure Azure OpenAI (create az.secret file)
cp env.example az.secret
# Edit az.secret with your Azure OpenAI credentials

# Build and start
task build
task start

# Access services:
# - Web Client (AI-powered): http://localhost:8080
# - API Server: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

## Commands

| Command | What it does |
|---------|--------------|
| `task build` | Build Docker image |
| `task start` | Start HTTP API server + Web Client |
| `task stop` | Stop all services |
| `task logs` | View server logs |
| `task test` | Run tests |
| `task clean` | Clean up everything |

Use `make` instead of `task` if you prefer.

## Using the API

### Interactive Documentation
Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

### Example API Calls

**Health Check:**
```bash
curl http://localhost:8000/health
```

**List Tools:**
```bash
curl http://localhost:8000/tools
```

**Search CodeBundles:**
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "search_codebundles",
    "arguments": {
      "query": "kubernetes troubleshooting",
      "max_results": 5
    }
  }'
```

**Direct REST Endpoint:**
```bash
curl "http://localhost:8000/api/codebundles/search?query=kubernetes&max_results=5"
```

## API Endpoints

### Core Endpoints
- `GET /` - API information
- `GET /health` - Health check with stats
- `GET /docs` - Interactive API documentation
- `GET /tools` - List available MCP tools
- `POST /tools/call` - Call any MCP tool

### REST Endpoints
- `GET /api/codebundles` - List all codebundles
- `GET /api/codebundles/search` - Search codebundles
- `GET /api/codebundles/{slug}` - Get specific codebundle
- `GET /api/collections` - List codecollections
- `GET /api/libraries/search` - Search libraries
- `GET /api/docs/requirements` - Get development requirements

## Available Tools

1. **`list_codebundles`** - List all codebundles and codecollections
2. **`search_codebundles`** - Search for codebundles by keywords/tags
3. **`get_codebundle_details`** - Get detailed codebundle information
4. **`list_codecollections`** - List all codecollections
5. **`find_library_info`** - Find library documentation and usage
6. **`get_development_requirements`** - Get development guides

## Data

Sample data included in `data/`:
- **8 CodeBundles** - Kubernetes, AWS, GCP, Azure examples
- **5 CodeCollections** - RunWhen collections
- **8 Libraries** - RW.CLI, RW.Core, etc.
- **10 Documentation Resources** - Development guides

## Architecture

```
┌─────────────────┐
│   Web Client    │ (client_web.py) :8080
│ + Azure OpenAI  │ AI-powered search
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│   HTTP Clients  │ (Any REST client)
└────────┬────────┘
         │ HTTP :8000
         ▼
┌─────────────────┐
│    FastAPI      │ (server_http.py)
│   MCP Server    │
└────────┬────────┘
         │
┌────────▼────────┐
│   JSON Data     │ (data/*.json)
└─────────────────┘
```

## 🔧 Azure OpenAI Configuration (Optional)

For AI-powered search via the web client:

1. **Copy the example config:**
   ```bash
   cp env.example az.secret
   ```

2. **Edit `az.secret` with your credentials:**
   ```bash
   export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   export AZURE_OPENAI_API_KEY=your-api-key-here
   export AZURE_OPENAI_DEPLOYMENT=gpt-4
   export AZURE_OPENAI_API_VERSION=2024-02-15-preview
   ```

3. **Restart services:**
   ```bash
   task stop
   task start
   ```

The Taskfile automatically sources `az.secret` if it exists, and Docker Compose loads it via `env_file`. The web client will still work without Azure OpenAI configured, but LLM features will be disabled.

**Note:** `az.secret` is git-ignored for security.

## Client Examples

### Python
```python
import requests

response = requests.post(
    "http://localhost:8000/tools/call",
    json={
        "tool_name": "search_codebundles",
        "arguments": {"query": "kubernetes"}
    }
)
print(response.json()["result"])
```

### JavaScript
```javascript
const response = await fetch('http://localhost:8000/tools/call', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    tool_name: 'search_codebundles',
    arguments: { query: 'kubernetes' }
  })
});
const data = await response.json();
console.log(data.result);
```

### curl
```bash
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name":"search_codebundles","arguments":{"query":"kubernetes"}}'
```

## Files

### Core Files
- `server_http.py` - FastAPI HTTP server (primary)
- `client_web.py` - Web-based test client with Azure OpenAI
- `server.py` - MCP stdio server (legacy)
- `docker-compose.yml` - Docker services
- `Dockerfile` - Container definition
- `requirements.txt` - Python dependencies

### Clients & Tests
- `client_web.py` - Web UI with AI search (http://localhost:8080)
- `client_test.py` - Automated test suite
- `interactive_client.py` - Interactive CLI client
- `demo_first_query.py` - Demo script

### Utilities
- `utils/data_loader.py` - Data loading
- `utils/search.py` - Search engine

### Data
- `data/codebundles.json` - CodeBundle data
- `data/codecollections.json` - CodeCollection metadata
- `data/libraries.json` - Library documentation
- `data/documentation_resources.json` - Dev guides

## Development

### View Logs
```bash
task logs
```

### Run Tests
```bash
task test
```

### Shell Access
```bash
docker-compose exec mcp-http /bin/bash
```

### Restart
```bash
docker-compose restart mcp-http
```

## Integration with cc-registry-v2

Both services use HTTP and can run together:

```bash
# Terminal 1: Start cc-registry-v2
cd ../../cc-registry-v2
task start

# Terminal 2: Start MCP server
cd ../../hack/mcp
task start
```

Access both:
- cc-registry-v2: http://localhost:8001
- MCP server: http://localhost:8000

## Production Considerations

For production deployments, consider adding:
- Authentication (API keys, OAuth)
- HTTPS/TLS (reverse proxy or uvicorn SSL)
- Rate limiting
- Monitoring and logging
- Load balancing (multiple containers)

## Troubleshooting

**Server won't start:**
```bash
docker-compose logs mcp-http
```

**Port already in use:**
```bash
# Stop any existing containers
task stop
# Or change port in docker-compose.yml
```

**Build fails:**
```bash
# Force rebuild
docker-compose build --no-cache
```

## License

MIT

## Documentation

- **README.md** (this file) - Main documentation
- **QUICKREF.md** - Quick command reference
- **INDEX.md** - Documentation index
