# MCP Server Integration

This document explains the Model Context Protocol (MCP) Server integration with cc-registry-v2.

## 📋 Overview

The MCP Server is a **semantic search and knowledge base server** that provides:
- 🔍 **Semantic search** for codebundles, libraries, and documentation
- 📚 **Knowledge base queries** using vector embeddings
- 🤖 **AI-powered** search with Azure OpenAI integration
- 📊 **REST API** for integration with the registry backend

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend      │ :3000
│   (React)       │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│   Backend       │ :8001
│   (FastAPI)     │
└────────┬────────┘
         │ HTTP :8000
         ▼
┌─────────────────┐
│  MCP Server     │ :8000
│  (Semantic      │
│   Search)       │
└────────┬────────┘
         │
┌────────▼────────┐
│  Vector Store   │
│  + JSON Data    │
└─────────────────┘
```

## 🔗 Backend Integration

The cc-registry-v2 backend connects to the MCP server via the `MCP_SERVER_URL` environment variable.

### Configuration

**In cc-registry-v2/backend/app/core/config.py:**
```python
MCP_SERVER_URL: str = "http://mcp-http:8000"
```

**Docker Compose:**
```yaml
backend:
  environment:
    - MCP_SERVER_URL=http://host.docker.internal:8000
```

**Kubernetes:**
```yaml
backend:
  env:
    - name: MCP_SERVER_URL
      value: "http://mcp-server:8000"
```

### Usage in Backend

The backend uses the MCP client (`app/services/mcp_client.py`) to:
1. Search for codebundles semantically
2. Find related libraries and documentation
3. Get codebundle details
4. Enhance search results with AI

## 🚀 Container Images

The MCP server is now built alongside the other cc-registry-v2 components:

```
us-docker.pkg.dev/PROJECT/REPO/cc-registry-v2-backend:TAG
us-docker.pkg.dev/PROJECT/REPO/cc-registry-v2-frontend:TAG
us-docker.pkg.dev/PROJECT/REPO/cc-registry-v2-worker:TAG
us-docker.pkg.dev/PROJECT/REPO/cc-registry-v2-mcp-server:TAG  ← New!
```

### Build Process

The GitHub Actions workflow builds all four images:
- **Backend** - FastAPI application
- **Frontend** - React application
- **Worker** - Celery worker/scheduler
- **MCP Server** - Semantic search server

## 🔧 Deployment

### Docker Compose (Local Development)

The MCP server can run independently:

```bash
# Start MCP server only
cd mcp-server
task start

# Or start full stack
cd ../cc-registry-v2
task start
# Backend will connect to MCP server on localhost:8000
```

### Kubernetes Deployment

#### 1. Deploy MCP Server

```bash
kubectl apply -f k8s/mcp-server-deployment.yaml
```

This creates:
- **Deployment**: 2 replicas of MCP server
- **Service**: ClusterIP service on port 8000
- **PVC**: Persistent storage for vector store data
- **ConfigMap**: CodeCollections configuration

#### 2. Backend Automatically Connects

The backend deployment already has the MCP_SERVER_URL configured:

```yaml
env:
  - name: MCP_SERVER_URL
    value: "http://mcp-server:8000"
```

## 📊 MCP Server Features

### REST API Endpoints

The MCP server provides these endpoints:

```bash
# Health check
GET http://mcp-server:8000/health

# List available tools
GET http://mcp-server:8000/tools

# Search codebundles
GET http://mcp-server:8000/api/codebundles/search?query=kubernetes

# Get codebundle details
GET http://mcp-server:8000/api/codebundles/{slug}

# Search libraries
GET http://mcp-server:8000/api/libraries/search?query=aws

# MCP tool call (generic)
POST http://mcp-server:8000/tools/call
{
  "tool_name": "search_codebundles",
  "arguments": {"query": "troubleshooting"}
}
```

### Data Structure

The MCP server maintains:
- **Codebundles** - Task automation scripts
- **CodeCollections** - Collections of codebundles
- **Libraries** - RW libraries and dependencies
- **Documentation** - Development guides and docs
- **Vector Store** - Embeddings for semantic search

## 🔐 Configuration

### Required Secrets

#### Azure OpenAI (Optional - for AI features)

If using AI-powered search, configure Azure OpenAI:

**Docker Compose:**
```bash
# Create az.secret file
cp mcp-server/env.example mcp-server/az.secret
# Edit with your Azure OpenAI credentials
```

**Kubernetes:**
```yaml
# Already included in azure-openai-credentials secret
apiVersion: v1
kind: Secret
metadata:
  name: azure-openai-credentials
stringData:
  AZURE_OPENAI_API_KEY: "your-key"
  AZURE_OPENAI_ENDPOINT: "https://your-instance.openai.azure.com/"
  AZURE_OPENAI_DEPLOYMENT_NAME: "gpt-4"
  AZURE_OPENAI_API_VERSION: "2024-02-15-preview"
```

### Data Initialization

The MCP server needs initial data to function:

**Option 1: Pre-populated data (Recommended)**
```bash
# The container includes sample data in mcp-server/data/
# This data is automatically loaded on startup
```

**Option 2: Run indexer**
```bash
# In local development
cd mcp-server
task index

# Or with Docker Compose
docker-compose --profile index up indexer
```

**Option 3: Mount existing data**
```yaml
# In Kubernetes
volumes:
  - name: data
    persistentVolumeClaim:
      claimName: mcp-server-data
```

## 📈 Scaling Considerations

### Horizontal Scaling

The MCP server is stateless for reads and can scale horizontally:

```bash
# Scale in Kubernetes
kubectl scale deployment mcp-server --replicas=5 -n codecollection-registry
```

**Notes:**
- Read operations can scale indefinitely
- Vector store is read from persistent volume
- Write operations (indexing) should be single-instance

### Performance

Typical resource usage:
- **CPU**: 250m-1000m per pod
- **Memory**: 512Mi-2Gi per pod (depends on vector store size)
- **Storage**: 5-10Gi for vector store and data

Response times:
- **Simple queries**: 50-200ms
- **Semantic search**: 200-500ms
- **AI-enhanced search**: 1-3s (depends on Azure OpenAI)

## 🐛 Troubleshooting

### Backend Can't Connect to MCP Server

**Symptoms:**
- Backend logs show "Connection refused" to MCP server
- Search features don't work

**Solutions:**

**Docker Compose:**
```bash
# Check MCP server is running
docker ps | grep mcp

# Check MCP server logs
docker logs runwhen-mcp-http

# Verify network connectivity
docker exec registry-backend curl http://host.docker.internal:8000/health
```

**Kubernetes:**
```bash
# Check MCP server pods
kubectl get pods -n codecollection-registry -l component=mcp-server

# Check logs
kubectl logs -l component=mcp-server -n codecollection-registry

# Test connectivity from backend
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- \
  curl http://mcp-server:8000/health
```

### MCP Server Returns Empty Results

**Symptoms:**
- API returns `[]` or empty results
- Health check passes but queries fail

**Solutions:**

1. **Check data is loaded:**
   ```bash
   # Docker
   docker exec runwhen-mcp-http ls -la /app/data/
   
   # Kubernetes
   kubectl exec deployment/mcp-server -n codecollection-registry -- \
     ls -la /app/data/
   ```

2. **Verify vector store:**
   ```bash
   # Check vector database exists
   kubectl exec deployment/mcp-server -n codecollection-registry -- \
     ls -la /app/data/vectordb/
   ```

3. **Run indexer to rebuild:**
   ```bash
   # Docker
   docker-compose --profile index up indexer
   
   # Kubernetes (create a job)
   kubectl create job mcp-indexer --image=us-docker.pkg.dev/.../cc-registry-v2-mcp-server:TAG \
     -n codecollection-registry
   ```

### High Memory Usage

**Symptoms:**
- MCP server pods being OOMKilled
- Slow query responses

**Solutions:**

1. **Increase memory limits:**
   ```yaml
   resources:
     limits:
       memory: "4Gi"  # Increase from 2Gi
   ```

2. **Reduce vector store size:**
   - Limit the number of indexed documents
   - Use dimensionality reduction
   - Index fewer collections

3. **Use local embeddings:**
   ```bash
   # Reduces memory by not loading Azure OpenAI models
   python indexer.py --local
   ```

## 🔄 Updates and Maintenance

### Updating MCP Server

**Rolling update in Kubernetes:**
```bash
# Update image
kubectl set image deployment/mcp-server \
  mcp-server=us-docker.pkg.dev/.../cc-registry-v2-mcp-server:new-tag \
  -n codecollection-registry

# Monitor rollout
kubectl rollout status deployment/mcp-server -n codecollection-registry
```

### Reindexing Data

When codebundle data changes, reindex:

```bash
# Docker
docker-compose --profile index up indexer

# Kubernetes
kubectl create job mcp-reindex-$(date +%s) \
  --from=deployment/mcp-server \
  -n codecollection-registry
```

### Backup Vector Store

```bash
# From Kubernetes
kubectl exec deployment/mcp-server -n codecollection-registry -- \
  tar czf /tmp/vectordb-backup.tar.gz /app/data/vectordb

kubectl cp codecollection-registry/mcp-server-pod:/tmp/vectordb-backup.tar.gz \
  ./vectordb-backup-$(date +%Y%m%d).tar.gz
```

## 📚 Additional Resources

- **MCP Server README**: [mcp-server/README.md](../mcp-server/README.md)
- **MCP Server Dockerfile**: [mcp-server/Dockerfile](../mcp-server/Dockerfile)
- **Backend MCP Client**: [backend/app/services/mcp_client.py](backend/app/services/mcp_client.py)
- **K8s Deployment**: [k8s/mcp-server-deployment.yaml](k8s/mcp-server-deployment.yaml)

## 🎯 Quick Commands

```bash
# Build MCP server image
cd mcp-server && docker build -t mcp-server:latest .

# Run locally
cd mcp-server && task start

# Test health
curl http://localhost:8000/health

# Test search
curl "http://localhost:8000/api/codebundles/search?query=kubernetes&max_results=5"

# Deploy to Kubernetes
kubectl apply -f cc-registry-v2/k8s/mcp-server-deployment.yaml

# Scale up
kubectl scale deployment/mcp-server --replicas=5 -n codecollection-registry

# View logs
kubectl logs -f deployment/mcp-server -n codecollection-registry

# Port forward for testing
kubectl port-forward svc/mcp-server 8000:8000 -n codecollection-registry
```

## ✅ Deployment Checklist

- [ ] MCP server image built and pushed to registry
- [ ] Kubernetes manifest applied
- [ ] PVC created and data initialized
- [ ] Azure OpenAI credentials configured (if using AI features)
- [ ] Backend deployment has MCP_SERVER_URL configured
- [ ] Service DNS resolves: `nslookup mcp-server` from backend pod
- [ ] Health check passes: `curl http://mcp-server:8000/health`
- [ ] Search returns results: Test query via API
- [ ] Backend can successfully call MCP server
- [ ] Logs show no connection errors
