# MCP Server Deployment Fix

## Issue

The MCP server was crashing in Kubernetes with `CrashLoopBackOff` and exit code 0:

```
Last State:     Terminated
  Reason:       Completed
  Exit Code:    0
  Started:      Wed, 14 Jan 2026 15:36:31 -0500
  Finished:     Wed, 14 Jan 2026 15:36:33 -0500
```

## Root Cause

The MCP server has two different server implementations:

1. **`server.py`** - stdio-based MCP server
   - Designed for desktop integration (Claude Desktop, ChatGPT)
   - Communicates over stdin/stdout using the MCP protocol
   - Exits immediately when no stdin is available

2. **`server_http.py`** - HTTP/REST API server
   - Designed for production/Kubernetes deployments
   - Provides HTTP endpoints on port 8000
   - Includes `/health` endpoint for liveness/readiness probes

The Dockerfile was configured to run `server.py` by default, which is the stdio version. In Kubernetes, there's no stdin connected, so the server would start and immediately exit gracefully (exit code 0), causing the CrashLoopBackOff.

## Solution

Updated the Dockerfile to use `server_http.py` instead of `server.py`:

```dockerfile
# Before
CMD ["python", "server.py"]

# After
CMD ["python", "server_http.py"]
```

## Next Steps

### 1. Rebuild the Container Image

You need to rebuild the MCP server image with the updated Dockerfile:

```bash
# Using the GitHub Actions workflow (recommended)
# Push changes to trigger the build-mcp-server.yaml workflow
git add mcp-server/Dockerfile
git commit -m "fix: Use server_http.py for Kubernetes deployments"
git push

# Or build locally if needed
cd mcp-server
docker build -t your-registry/runwhen-mcp-server:fixed .
docker push your-registry/runwhen-mcp-server:fixed
```

### 2. Update the Deployment

If you built a new image tag, update the Kubernetes deployment to use it:

```bash
kubectl set image deployment/mcp-server \
  mcp-server=us-docker.pkg.dev/runwhen-nonprod-shared/public-images/runwhen-mcp-server:NEW_TAG \
  -n registry-test
```

Or update via kustomize and reapply:

```bash
cd cc-registry-v2/k8s
# Edit kustomization.yaml to set new image tag
kubectl apply -k .
```

### 3. Verify the Fix

Check that the pod starts successfully:

```bash
# Check pod status
kubectl get pods -n registry-test -l component=mcp-server

# Should show Running status
NAME                          READY   STATUS    RESTARTS   AGE
mcp-server-xxxxx-yyyyy       1/1     Running   0          30s

# Check logs
kubectl logs -n registry-test -l component=mcp-server --tail=50

# Should show FastAPI/uvicorn startup messages:
# INFO:     Started server process [1]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000

# Test health endpoint
kubectl port-forward -n registry-test svc/mcp-server 8000:8000

# In another terminal:
curl http://localhost:8000/health
```

Expected health response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-14T20:36:31.123456",
  "data_stats": {
    "codebundles": 150,
    "collections": 6,
    "libraries": 25,
    "documentation": 100
  },
  "semantic_search": {
    "is_available": true,
    "vector_count": 500
  }
}
```

## Server Modes

Going forward, be aware of the two server modes:

### Production/Kubernetes Mode (HTTP)
```bash
python server_http.py
# or
docker run -p 8000:8000 mcp-server:latest
```

- Provides HTTP REST API on port 8000
- Endpoints: `/health`, `/tools`, `/tools/call`, `/api/*`
- Used by: Web clients, Kubernetes services, backend integration

### Desktop Integration Mode (stdio)
```bash
python server.py
# or configure in Claude Desktop/ChatGPT settings
```

- Uses stdio communication (MCP protocol)
- No HTTP server, communicates via stdin/stdout
- Used by: Claude Desktop, ChatGPT desktop apps

## Configuration Requirements

Make sure your Kubernetes deployment has:

1. **Azure OpenAI Credentials** (for semantic search)
   ```bash
   kubectl get secret -n registry-test azure-openai-credentials
   ```

2. **CodeCollections Config**
   ```bash
   kubectl get configmap -n registry-test codecollections-config
   ```

3. **Persistent Volume** (for vector database)
   ```bash
   kubectl get pvc -n registry-test mcp-server-data
   ```

See `cc-registry-v2/k8s/secrets-example.yaml` for required secret configuration.

## Troubleshooting

### Pod still crashing after fix

1. Check the actual command being run:
   ```bash
   kubectl describe pod -n registry-test -l component=mcp-server | grep Command
   ```

2. View container logs:
   ```bash
   kubectl logs -n registry-test -l component=mcp-server --previous
   ```

3. Check if image was actually rebuilt:
   ```bash
   kubectl describe pod -n registry-test -l component=mcp-server | grep Image:
   ```

### Missing Azure OpenAI credentials

If semantic search is failing, check that embedding credentials are configured:

```bash
kubectl get secret -n registry-test azure-openai-credentials -o jsonpath='{.data}' | jq
```

Should include: `AZURE_OPENAI_EMBEDDING_API_KEY`, `AZURE_OPENAI_EMBEDDING_ENDPOINT`, etc.

### Data loading errors

Check that data files are present in the image:

```bash
kubectl exec -n registry-test -it deploy/mcp-server -- ls -la /app/data/
```

Should contain: `codebundles.json`, `codecollections.json`, `libraries.json`, `repos/`

## Related Documentation

- `cc-registry-v2/MCP_SERVER_INTEGRATION.md` - Backend integration
- `cc-registry-v2/k8s/secrets-example.yaml` - Required secrets
- `cc-registry-v2/AZURE_OPENAI_SETUP.md` - Azure OpenAI configuration
- `.github/workflows/build-mcp-server.yaml` - Automated build workflow
