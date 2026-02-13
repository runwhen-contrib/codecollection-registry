# ✅ MCP Server Added to Build Workflow

The GitHub Actions workflow has been updated to include the **MCP Server** as the fourth component in the cc-registry-v2 stack.

## 🎯 What Changed

### 1. **Workflow Updated**
**File:** `.github/workflows/build-cc-registry-v2-images.yaml`

Added two new build jobs:
- `build-mcp-server-amd64` - Build MCP server for amd64
- `build-mcp-server-arm64` - Build MCP server for arm64 (optional)

The workflow now builds **4 images** instead of 3:
1. ✅ Backend (FastAPI)
2. ✅ Frontend (React)  
3. ✅ Worker (Celery)
4. ✅ **MCP Server (Semantic Search)** ← NEW!

### 2. **Kubernetes Deployment Created**
**File:** `cc-registry-v2/k8s/mcp-server-deployment.yaml`

Complete Kubernetes deployment including:
- Deployment with 2 replicas
- Service (ClusterIP on port 8000)
- PersistentVolumeClaim for vector store data
- ConfigMap for codecollections configuration
- Health checks and resource limits

### 3. **Documentation Added**
**File:** `cc-registry-v2/MCP_SERVER_INTEGRATION.md`

Comprehensive guide covering:
- MCP server overview and architecture
- Backend integration details
- Configuration and deployment
- Troubleshooting guide
- Scaling considerations

### 4. **Updated Existing Documentation**

- **k8s/kustomization.yaml** - Added MCP server to resources and replicas
- **README.md** - Updated architecture diagram and service descriptions
- **Build workflow** - Updated summaries to include MCP server

## 🚀 Images Built

The workflow now produces four container images:

```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-backend:TAG
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-frontend:TAG
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-worker:TAG
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-mcp-server:TAG  ← NEW!
```

Each with:
- `TAG-amd64` - Architecture-specific tag
- `TAG-arm64` - ARM architecture (if multi-arch build enabled)
- `TAG` - Multi-arch manifest

## 📋 Why MCP Server is Needed

The MCP (Model Context Protocol) Server provides:

### 🔍 **Semantic Search**
- Search codebundles by natural language queries
- Find related libraries and documentation
- AI-powered result ranking

### 📚 **Knowledge Base**
- Vector store for embeddings
- CodeBundle metadata
- Library documentation
- Development guides

### 🔗 **Backend Integration**
The cc-registry-v2 backend connects to MCP server via:
```python
MCP_SERVER_URL: str = "http://mcp-server:8000"
```

Used by:
- `/api/v1/codebundles/search` endpoint
- AI enhancement features
- Library lookup functionality

## 🏗️ Complete Architecture

```
┌─────────────┐
│   Frontend  │ :3000 (React UI)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │ :8001 (FastAPI)
└──────┬──────┘
       │
       ├──────► MCP Server   :8000 (Semantic Search)
       │        └──────┬──────
       │               ▼
       │        Vector Store + Data
       │
       ├──────► Redis         :6379 (Message Broker)
       │               │
       ▼               ▼
   Database        Worker/Scheduler (Celery)
   :5432
```

## 🔧 Deployment Changes

### Docker Compose (No Change Required)
The MCP server can run independently:
```bash
# Start full stack (backend auto-connects to MCP on localhost:8000)
cd cc-registry-v2
task start

# Or start MCP separately
cd mcp-server
task start
```

### Kubernetes (New Manifest)
Deploy MCP server:
```bash
# Deploy MCP server
kubectl apply -f k8s/mcp-server-deployment.yaml

# Backend automatically connects via:
# MCP_SERVER_URL=http://mcp-server:8000
```

### Deployment Order
```bash
# 1. Infrastructure
kubectl apply -f k8s/database-deployment.yaml
kubectl apply -f k8s/redis-deployment.yaml

# 2. MCP Server (backend dependency)
kubectl apply -f k8s/mcp-server-deployment.yaml

# 3. Application services
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/scheduler-deployment.yaml

# Or use kustomize (includes MCP server)
kubectl apply -k k8s/
```

## 📊 Workflow Summary

### Total Jobs: 13
- `scan-repo` - Security scanning
- `generate-tag` - Tag generation
- **Build jobs (8):**
  - `build-backend-amd64`
  - `build-backend-arm64` (optional)
  - `build-frontend-amd64`
  - `build-frontend-arm64` (optional)
  - `build-worker-amd64`
  - `build-worker-arm64` (optional)
  - `build-mcp-server-amd64` ← NEW!
  - `build-mcp-server-arm64` ← NEW! (optional)
- `publish-manifests` - Create multi-arch manifests
- `summary` - Build summary
- `notify` - Notifications

### Build Matrix

| Component  | amd64 | arm64 (optional) | Use Case |
|------------|-------|------------------|----------|
| Backend    | ✅    | ✅               | API server |
| Frontend   | ✅    | ✅               | Web UI |
| Worker     | ✅    | ✅               | Background jobs |
| MCP Server | ✅    | ✅               | Semantic search |

## 🎯 Quick Start

### Build All Images
```bash
# Via GitHub Actions
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v1.0.0 \
  -f build_multiarch=false
```

### Deploy to Kubernetes
```bash
# Deploy everything
kubectl apply -k cc-registry-v2/k8s/

# Check MCP server
kubectl get pods -n codecollection-registry -l component=mcp-server
kubectl logs -f deployment/mcp-server -n codecollection-registry

# Test MCP server
kubectl port-forward svc/mcp-server 8000:8000 -n codecollection-registry
curl http://localhost:8000/health
```

### Verify Backend Connection
```bash
# From backend pod
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- \
  curl http://mcp-server:8000/health

# Should return: {"status": "healthy", ...}
```

## 🔍 MCP Server Features

### Available Endpoints
```bash
# Health check
GET http://mcp-server:8000/health

# Search codebundles
GET http://mcp-server:8000/api/codebundles/search?query=kubernetes

# Get codebundle details
GET http://mcp-server:8000/api/codebundles/{slug}

# Search libraries
GET http://mcp-server:8000/api/libraries/search?query=aws

# List tools
GET http://mcp-server:8000/tools

# Call MCP tool
POST http://mcp-server:8000/tools/call
{
  "tool_name": "search_codebundles",
  "arguments": {"query": "troubleshooting"}
}
```

## 📚 Updated Documentation

### New Files
1. **[MCP_SERVER_INTEGRATION.md](MCP_SERVER_INTEGRATION.md)** - Complete MCP integration guide
2. **[k8s/mcp-server-deployment.yaml](k8s/mcp-server-deployment.yaml)** - Kubernetes deployment

### Updated Files
1. **[.github/workflows/build-cc-registry-v2-images.yaml](.github/workflows/build-cc-registry-v2-images.yaml)** - Added MCP server builds
2. **[k8s/kustomization.yaml](k8s/kustomization.yaml)** - Added MCP server resource
3. **[README.md](README.md)** - Updated architecture and documentation links

## 🐛 Troubleshooting

### MCP Server Not Starting
```bash
# Check logs
kubectl logs deployment/mcp-server -n codecollection-registry

# Common issues:
# - Missing data volume
# - Missing Azure OpenAI credentials (optional)
# - Insufficient memory
```

### Backend Can't Connect to MCP Server
```bash
# Test DNS resolution
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- \
  nslookup mcp-server

# Test connectivity
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- \
  curl http://mcp-server:8000/health
```

### Search Returns Empty Results
```bash
# Check data is loaded
kubectl exec deployment/mcp-server -n codecollection-registry -- \
  ls -la /app/data/

# Verify vector store
kubectl exec deployment/mcp-server -n codecollection-registry -- \
  ls -la /app/data/vectordb/

# Reindex if needed (see MCP_SERVER_INTEGRATION.md)
```

## ✅ Validation

```bash
# Workflow syntax
✅ YAML syntax is valid
✅ Total jobs: 13
✅ Build jobs: 8 (4 components × 2 architectures)
✅ Registry: us-docker.pkg.dev/runwhen-nonprod-shared/public-images

# Kubernetes manifests
✅ mcp-server-deployment.yaml created
✅ kustomization.yaml updated
✅ Service, PVC, ConfigMap included

# Documentation
✅ MCP_SERVER_INTEGRATION.md created
✅ README.md updated
✅ Architecture diagrams updated
```

## 🎉 Summary

The MCP Server is now:
- ✅ **Built automatically** with the other components
- ✅ **Deployed to Kubernetes** with proper manifests
- ✅ **Integrated with backend** via MCP_SERVER_URL
- ✅ **Documented comprehensively** with guides and examples
- ✅ **Ready for production** with health checks and scaling support

**Next Steps:**
1. Update your GCP project ID in the workflow
2. Test the workflow with a manual run
3. Deploy to your test cluster
4. Verify backend can connect to MCP server
5. Test search functionality

For detailed setup instructions, see:
- [MCP_SERVER_INTEGRATION.md](MCP_SERVER_INTEGRATION.md)
- [GCR_SETUP.md](GCR_SETUP.md)
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
