# ✅ Workflows Separated: MCP Server Now Independent

The build workflows have been reorganized to properly separate concerns. The MCP Server now has its own dedicated workflow.

## 🎯 Why Separate Workflows?

### 1. **Independent Release Cycles**
- MCP server can be versioned independently (e.g., `mcp-v1.2.0`)
- cc-registry-v2 can be versioned independently (e.g., `registry-v2.5.0`)
- Updates to one don't require rebuilding the other

### 2. **Different Trigger Paths**
- **MCP Server**: Triggers on changes to `mcp-server/**`
- **CC-Registry-V2**: Triggers on changes to `cc-registry-v2/**`
- No unnecessary rebuilds when only one component changes

### 3. **Cleaner Separation of Concerns**
- MCP server is a standalone component with its own codebase
- Can be reused by other projects beyond cc-registry-v2
- Easier to maintain and understand

### 4. **Flexibility**
- Can deploy MCP server updates without touching registry
- Can test MCP server independently
- Different teams can own different workflows

## 📂 Workflow Files

### 1. **CC-Registry-V2 Workflow**
**File:** `.github/workflows/build-cc-registry-v2-images.yaml`

**Builds 3 images:**
- `cc-registry-v2-backend` - FastAPI backend
- `cc-registry-v2-frontend` - React frontend
- `cc-registry-v2-worker` - Celery worker/scheduler

**Triggers:**
- Push to `main` branch affecting `cc-registry-v2/**`
- Pull requests affecting `cc-registry-v2/**`
- Manual workflow dispatch

**Total jobs:** 11
- scan-repo
- generate-tag
- build-backend-amd64 / build-backend-arm64
- build-frontend-amd64 / build-frontend-arm64
- build-worker-amd64 / build-worker-arm64
- publish-manifests
- summary
- notify

### 2. **MCP Server Workflow**
**File:** `.github/workflows/build-mcp-server.yaml`

**Builds 1 image:**
- `runwhen-mcp-server` - Semantic search server

**Triggers:**
- Push to `main` branch affecting `mcp-server/**`
- Pull requests affecting `mcp-server/**`
- Manual workflow dispatch

**Total jobs:** 6
- scan-repo
- generate-tag
- build-amd64 / build-arm64
- publish-manifest
- summary
- notify

## 🏷️ Image Naming

### CC-Registry-V2 Images
```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-backend:<tag>
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-frontend:<tag>
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-worker:<tag>
```

### MCP Server Image
```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/runwhen-mcp-server:<tag>
```

Note: MCP Server uses a different naming convention (`runwhen-mcp-server` vs `cc-registry-v2-mcp-server`) because:
- It's a standalone component
- Can be used by multiple projects
- Has its own identity

## 🚀 Usage Examples

### Build Everything

```bash
# Build cc-registry-v2 components
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.1.0 \
  -f build_multiarch=false

# Build MCP server
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=v1.3.0 \
  -f build_multiarch=false
```

### Version Independently

```bash
# Release new registry version (without changing MCP server)
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.2.0

# Release new MCP server version (without changing registry)
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=v1.4.0
```

### Automatic Triggers

**When you push changes to cc-registry-v2:**
```bash
git add cc-registry-v2/backend/
git commit -m "Update backend API"
git push origin feature-branch
# Only cc-registry-v2 workflow runs
```

**When you push changes to mcp-server:**
```bash
git add mcp-server/
git commit -m "Improve search algorithm"
git push origin feature-branch
# Only mcp-server workflow runs
```

**When you push changes to both:**
```bash
git add cc-registry-v2/ mcp-server/
git commit -m "Update both components"
git push origin feature-branch
# Both workflows run
```

## 📊 Workflow Comparison

| Feature | CC-Registry-V2 | MCP Server |
|---------|----------------|------------|
| **Components** | 3 (backend, frontend, worker) | 1 (mcp-server) |
| **Jobs** | 11 | 6 |
| **Build time** | ~15-20 min | ~5-8 min |
| **Trigger path** | `cc-registry-v2/**` | `mcp-server/**` |
| **Image prefix** | `cc-registry-v2-*` | `runwhen-mcp-server` |
| **Use case** | Full registry stack | Semantic search service |

## 🔄 Deployment Scenarios

### Scenario 1: Deploy Full Stack
```bash
# Deploy all components including MCP server
kubectl apply -k cc-registry-v2/k8s/

# This includes:
# - Backend (connects to MCP server)
# - Frontend
# - Worker
# - MCP Server
# - Database
# - Redis
```

### Scenario 2: Update Only Registry
```bash
# Build new registry images
gh workflow run build-cc-registry-v2-images.yaml -f tag=v2.2.0

# Deploy only registry components
kubectl set image deployment/cc-registry-backend \
  backend=us-docker.pkg.dev/.../cc-registry-v2-backend:v2.2.0

# MCP server continues running on old version
```

### Scenario 3: Update Only MCP Server
```bash
# Build new MCP server
gh workflow run build-mcp-server.yaml -f tag=v1.5.0

# Deploy only MCP server
kubectl set image deployment/mcp-server \
  mcp-server=us-docker.pkg.dev/.../runwhen-mcp-server:v1.5.0

# Registry components continue running
```

### Scenario 4: Update Both Independently
```bash
# Build both
gh workflow run build-cc-registry-v2-images.yaml -f tag=v2.3.0
gh workflow run build-mcp-server.yaml -f tag=v1.6.0

# Deploy both
kubectl set image deployment/cc-registry-backend \
  backend=...cc-registry-v2-backend:v2.3.0
kubectl set image deployment/mcp-server \
  mcp-server=...runwhen-mcp-server:v1.6.0
```

## 🔗 Integration Points

Even though workflows are separate, the components still integrate:

### Backend → MCP Server Connection

**Environment Variable:**
```yaml
# cc-registry-v2/backend
env:
  - name: MCP_SERVER_URL
    value: "http://mcp-server:8000"
```

**Kubernetes Service:**
```yaml
# Both components in same namespace
apiVersion: v1
kind: Service
metadata:
  name: mcp-server
  namespace: codecollection-registry
spec:
  ports:
  - port: 8000
```

The backend can connect to MCP server via DNS: `http://mcp-server:8000`

## 📚 Documentation Updates

### Updated Files
- **`.github/workflows/build-cc-registry-v2-images.yaml`** - Removed MCP server builds
- **`.github/workflows/build-mcp-server.yaml`** - New MCP server workflow (created)
- **`WORKFLOWS_SEPARATED.md`** - This document (created)

### Existing Documentation Still Valid
- **`MCP_SERVER_INTEGRATION.md`** - Integration guide
- **`GCR_SETUP.md`** - GCP setup
- **`DEPLOYMENT_GUIDE.md`** - Deployment guide
- **`k8s/mcp-server-deployment.yaml`** - K8s manifest

## ✅ Benefits Achieved

### 1. **Faster CI/CD**
- ✅ Only affected components rebuild
- ✅ Smaller workflows run faster
- ✅ Parallel development possible

### 2. **Better Organization**
- ✅ Clear ownership boundaries
- ✅ Easier to maintain
- ✅ Less cognitive overhead

### 3. **Independent Versioning**
- ✅ MCP server can have v1.x, v2.x versions
- ✅ Registry can have independent versions
- ✅ No forced coupling

### 4. **Reusability**
- ✅ MCP server can be used by other projects
- ✅ Cleaner dependency graph
- ✅ Standalone testing

## 🎯 When to Build Each

### Build CC-Registry-V2 When:
- ✅ Backend API changes
- ✅ Frontend UI updates
- ✅ Worker task changes
- ✅ Docker compose updates
- ✅ Kubernetes manifests change (registry-specific)

### Build MCP Server When:
- ✅ Search algorithm improvements
- ✅ Vector store updates
- ✅ New MCP tools added
- ✅ Data parsing changes
- ✅ Indexer modifications

### Build Both When:
- ✅ Breaking API changes between components
- ✅ Major version updates
- ✅ Full stack releases

## 🐛 Troubleshooting

### "MCP Server not found" in cc-registry-v2 workflow
**This is expected!** MCP server is built separately. If you need both:
```bash
# Trigger both workflows
gh workflow run build-cc-registry-v2-images.yaml -f tag=latest
gh workflow run build-mcp-server.yaml -f tag=latest
```

### PR Comments Mention "MCP Server built separately"
**This is intentional!** The cc-registry-v2 workflow notes that MCP server has its own workflow.

### Want to build everything at once?
**Create a meta-workflow:**
```yaml
name: Build All Components
on:
  workflow_dispatch:
jobs:
  build-registry:
    uses: ./.github/workflows/build-cc-registry-v2-images.yaml
  build-mcp:
    uses: ./.github/workflows/build-mcp-server.yaml
```

## 📝 Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Workflows** | 1 mega workflow | 2 focused workflows |
| **Images** | 4 in one workflow | 3 + 1 separate |
| **Jobs** | 13 total | 11 + 6 separate |
| **Triggers** | Any change rebuilds all | Only affected components |
| **Versioning** | Coupled | Independent |
| **Maintenance** | Complex | Simple |

**Result:** ✅ Cleaner, faster, more maintainable CI/CD pipeline!
