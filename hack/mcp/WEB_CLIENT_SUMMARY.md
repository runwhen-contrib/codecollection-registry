# Web Client with Azure OpenAI Integration

## What Was Added

### 1. Web Client (`client_web.py`)
A beautiful, AI-powered web interface for testing the MCP server with Azure OpenAI integration.

**Features:**
- **Modern Web UI**: Clean, responsive interface with gradient design
- **AI-Powered Search**: Uses Azure OpenAI (GPT-4) to provide intelligent responses
- **Real-time Status**: Shows MCP server and Azure OpenAI connection status
- **Example Queries**: One-click examples to get started
- **Dual Display**: Shows both AI response and raw search results
- **REST Proxy**: Acts as a proxy to the MCP HTTP server

**Architecture:**
```
User Browser
     ↓
Web Client :8080 (client_web.py)
     ↓
Azure OpenAI (GPT-4) + MCP Server :8000
     ↓
CodeBundle Data
```

### 2. Configuration Files

**`env.example`**: Template for Azure OpenAI credentials
**`az.secret`**: Your actual credentials (git-ignored)

```bash
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_API_KEY=your-api-key-here
export AZURE_OPENAI_DEPLOYMENT=gpt-4
export AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### 3. Docker Integration

**Updated `docker-compose.yml`:**
- New `web-client` service on port 8080
- Environment variable support for Azure OpenAI
- Depends on `mcp-http` service
- Shared network for inter-service communication

### 4. Dependencies

**Updated `requirements.txt`:**
- `httpx>=0.25.0` - Async HTTP client
- `openai>=1.12.0` - Azure OpenAI Python SDK

### 5. Documentation Updates

Updated all docs to include web client:
- **README.md**: Added configuration section, updated architecture diagram
- **QUICKREF.md**: Added quick access links
- **Taskfile.yml**: Updated to start both services
- **Makefile**: Updated to start both services

## How to Use

### Step 1: Configure Azure OpenAI (Optional)
```bash
cd /workspaces/codecollection-registry/hack/mcp
cp env.example az.secret
# Edit az.secret with your Azure OpenAI credentials
```

### Step 2: Build and Start
```bash
task build
task start
```

### Step 3: Access the Web Client
Open http://localhost:8080 in your browser

### Step 4: Ask Questions!
Try queries like:
- "Which codebundle is best for Kubernetes troubleshooting?"
- "How do I monitor AWS EKS clusters?"
- "Show me tools for database health checks"
- "What libraries do I use to run shell scripts?"

## How It Works

1. **User enters a question** in the web interface
2. **Web client searches** the MCP server for relevant codebundles
3. **Search results are sent** to Azure OpenAI with context
4. **GPT-4 generates** an intelligent, helpful response
5. **Both AI response and raw data** are displayed to the user

## Features Without Azure OpenAI

The web client works even without Azure OpenAI configured:
- ✅ Health checks
- ✅ List MCP tools
- ✅ Direct MCP tool calls
- ❌ AI-powered search (disabled)

## Endpoints

### Web Client (Port 8080)
- `GET /` - Web interface (HTML)
- `GET /health` - Health check
- `GET /api/mcp/tools` - List MCP tools
- `POST /api/mcp/call` - Call MCP tool directly
- `POST /api/query` - AI-powered search (requires Azure OpenAI)

### MCP Server (Port 8000)
- All existing endpoints remain unchanged
- See README.md for full API documentation

## Example Usage

### Via Web Interface (Recommended)
1. Open http://localhost:8080
2. Type or click an example question
3. Click "Search with AI"
4. View AI response and raw data

### Via API (Programmatic)
```bash
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Which codebundle is best for Kubernetes troubleshooting?"
  }'
```

## Architecture Diagram

```
┌────────────────┐
│  User Browser  │
└───────┬────────┘
        │ HTTP :8080
        ▼
┌────────────────┐
│  Web Client    │  client_web.py
│  (FastAPI)     │  - Serves HTML UI
└────┬──────┬────┘  - Proxies MCP calls
     │      │        - Calls Azure OpenAI
     │      │
     │      └───────────────────┐
     │                          │
     │ HTTP :8000               │ HTTPS
     ▼                          ▼
┌────────────────┐     ┌────────────────┐
│  MCP Server    │     │ Azure OpenAI   │
│  (FastAPI)     │     │    (GPT-4)     │
└───────┬────────┘     └────────────────┘
        │
        ▼
┌────────────────┐
│  JSON Data     │
│  data/*.json   │
└────────────────┘
```

## Security Notes

- **API Keys**: Store in `.env`, never commit
- **HTTPS**: In production, use a reverse proxy (nginx/traefik)
- **Rate Limiting**: Consider adding for production use
- **Authentication**: Add API key auth for public deployments

## Next Steps

1. **Test it**: Try the example queries
2. **Customize**: Modify the system prompt in `client_web.py`
3. **Extend**: Add more tools or data sources
4. **Deploy**: Add HTTPS and authentication for production

## Files Changed/Added

### New Files:
- `client_web.py` - Web client implementation
- `env.example` - Configuration template
- `WEB_CLIENT_SUMMARY.md` - This file

### Modified Files:
- `requirements.txt` - Added httpx, openai
- `docker-compose.yml` - Added web-client service with env_file
- `Taskfile.yml` - Updated to source az.secret
- `Makefile` - Updated start command
- `README.md` - Added configuration docs
- `QUICKREF.md` - Added web client URLs
- `.gitignore` - Added .env and az.secret

## Troubleshooting

**Web client shows "Azure OpenAI not configured":**
- Copy `env.example` to `az.secret` and add your credentials
- Restart: `task stop && task start`

**Can't connect to MCP server:**
- Check MCP server is running: `curl http://localhost:8000/health`
- Check logs: `task logs`

**Azure OpenAI errors:**
- Verify endpoint URL and API key
- Check deployment name matches your Azure resource
- Ensure API version is supported

## Benefits

1. **Better Testing**: Visual, interactive way to test the MCP server
2. **AI-Powered**: Intelligent responses using GPT-4
3. **User-Friendly**: No CLI or curl commands needed
4. **Portable**: Works in any browser
5. **Extensible**: Easy to add new features or customize

---

**Ready to use!** Just run `task start` and open http://localhost:8080

