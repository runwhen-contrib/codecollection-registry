# Configuration Update Summary

## Changes Made

### 1. MCP Server Deployment Fix

**Issue:** MCP server was crashing with `CrashLoopBackOff` (exit code 0)

**Root Cause:** Dockerfile was running `server.py` (stdio mode for desktop integration) instead of `server_http.py` (HTTP server for Kubernetes)

**Fix:** Updated `mcp-server/Dockerfile` to use `server_http.py`

**Impact:** MCP server will now start properly in Kubernetes and expose HTTP endpoints on port 8000

**Documentation:** `mcp-server/DEPLOYMENT_FIX.md`

---

### 2. Database Configuration - Component-Based Support

**Issue:** Need to support managed database services that provide individual connection parameters

**Changes:**
- Updated `backend/app/core/config.py` to support both:
  - Complete `DATABASE_URL` (simple)
  - Individual components: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- Added `@model_validator` to automatically construct `DATABASE_URL` from components
- Updated deployment manifests to use `envFrom` for all secrets

**Benefits:**
- Works with managed database services (Azure Database for PostgreSQL, AWS RDS)
- Easier integration with secret management systems
- More flexible credential rotation

**Example:**
```yaml
stringData:
  DB_HOST: "myserver.postgres.database.azure.com"
  DB_PORT: "5432"
  DB_USER: "admin@myserver"
  DB_PASSWORD: "SecurePassword"
  DB_NAME: "codecollection_registry"
```

---

### 3. Redis Sentinel Support

**Issue:** Need to support Redis Sentinel for high availability deployments

**Changes:**
- Updated `backend/app/core/config.py` to support:
  - Complete `REDIS_URL` (simple)
  - Redis Sentinel: `REDIS_SENTINEL_HOSTS`, `REDIS_SENTINEL_MASTER`, `REDIS_PASSWORD`, `REDIS_DB`
- Updated `backend/app/tasks/celery_app.py` to configure Celery for Sentinel:
  - Converts host format (comma to semicolon)
  - Sets `broker_transport_options` with Sentinel parameters
  - Configures connection timeouts and keepalive
- Updated Flower deployment to construct broker URL from environment

**Benefits:**
- High availability with automatic Redis failover
- Production-ready deployment architecture
- No application code changes needed for Sentinel switch

**Example:**
```yaml
stringData:
  REDIS_SENTINEL_HOSTS: "sentinel-1:26379,sentinel-2:26379,sentinel-3:26379"
  REDIS_SENTINEL_MASTER: "mymaster"
  REDIS_PASSWORD: "RedisPassword"
  REDIS_DB: "0"
```

---

### 4. Deployment Manifest Updates

**Changes:**
- `backend-deployment.yaml`: Use `envFrom` for all secrets
- `worker-deployment.yaml`: Use `envFrom` for all secrets
- `scheduler-deployment.yaml`: Use `envFrom` for all secrets and updated Flower command
- `secrets-example.yaml`: Updated with both URL and component-based examples

**Benefits:**
- Simplified secret management
- Supports both configuration methods
- No manifest changes needed when switching config methods

---

## Files Modified

### Backend Code
- `cc-registry-v2/backend/app/core/config.py` - Added component-based config support
- `cc-registry-v2/backend/app/tasks/celery_app.py` - Added Redis Sentinel support

### MCP Server
- `mcp-server/Dockerfile` - Changed CMD to use `server_http.py`

### Kubernetes Manifests
- `cc-registry-v2/k8s/secrets-example.yaml` - Updated with new configuration options
- `cc-registry-v2/k8s/backend-deployment.yaml` - Use envFrom for secrets
- `cc-registry-v2/k8s/worker-deployment.yaml` - Use envFrom for secrets
- `cc-registry-v2/k8s/scheduler-deployment.yaml` - Use envFrom for secrets, updated Flower

### Documentation
- `cc-registry-v2/DATABASE_REDIS_CONFIG.md` - **NEW** Comprehensive configuration guide
- `mcp-server/DEPLOYMENT_FIX.md` - **NEW** MCP server fix documentation
- `cc-registry-v2/README.md` - Added Configuration section with references

---

## Migration Path

### Immediate Actions Required

1. **Rebuild MCP Server Image:**
   ```bash
   cd /workspaces/codecollection-registry
   git add mcp-server/Dockerfile
   git commit -m "fix: Use server_http.py for Kubernetes deployments"
   git push
   ```
   The GitHub Actions workflow will automatically build and push the fixed image.

2. **Update MCP Server Deployment:**
   ```bash
   # Once new image is built
   kubectl set image deployment/mcp-server \
     mcp-server=us-docker.pkg.dev/runwhen-nonprod-shared/public-images/runwhen-mcp-server:NEW_TAG \
     -n registry-test
   ```

3. **Update Secrets (Optional but Recommended):**
   
   For component-based configuration:
   ```bash
   kubectl create secret generic cc-registry-secrets \
     --from-literal=DB_HOST=your-host \
     --from-literal=DB_PORT=5432 \
     --from-literal=DB_USER=your-user \
     --from-literal=DB_PASSWORD=your-password \
     --from-literal=DB_NAME=codecollection_registry \
     --from-literal=REDIS_SENTINEL_HOSTS=sentinel-1:26379,sentinel-2:26379,sentinel-3:26379 \
     --from-literal=REDIS_SENTINEL_MASTER=mymaster \
     --from-literal=REDIS_PASSWORD=redis-password \
     --from-literal=REDIS_DB=0 \
     -n registry-test \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

4. **Apply Updated Manifests:**
   ```bash
   cd cc-registry-v2/k8s
   kubectl apply -k .
   ```

5. **Restart Deployments:**
   ```bash
   kubectl rollout restart deployment/cc-registry-backend -n registry-test
   kubectl rollout restart deployment/cc-registry-worker -n registry-test
   kubectl rollout restart deployment/cc-registry-scheduler -n registry-test
   ```

### Backward Compatibility

✅ **All changes are backward compatible:**

- If you're using `DATABASE_URL`, it continues to work
- If you're using `REDIS_URL`, it continues to work
- New component-based config is optional
- MCP server fix is self-contained

### Testing

1. **Verify MCP Server:**
   ```bash
   kubectl get pods -n registry-test -l component=mcp-server
   # Should show: Running
   
   kubectl logs -n registry-test -l component=mcp-server
   # Should show: Uvicorn running on http://0.0.0.0:8000
   
   kubectl port-forward -n registry-test svc/mcp-server 8000:8000
   curl http://localhost:8000/health
   # Should return: {"status":"healthy",...}
   ```

2. **Verify Database Connection:**
   ```bash
   kubectl port-forward -n registry-test svc/cc-registry-backend 8001:8001
   curl http://localhost:8001/api/v1/health
   # Should return: {"status":"healthy","database":"connected",...}
   ```

3. **Verify Redis/Celery:**
   ```bash
   kubectl logs -n registry-test deployment/cc-registry-worker --tail=50
   # Should show: celery@worker ready.
   
   kubectl port-forward -n registry-test svc/cc-registry-flower 5555:5555
   # Open http://localhost:5555 - should show workers
   ```

---

## Benefits

### Operational
- ✅ Support for managed database services (Azure, AWS)
- ✅ High availability with Redis Sentinel
- ✅ Easier secret rotation and management
- ✅ MCP server now works correctly in Kubernetes

### Developer Experience
- ✅ Flexible configuration options
- ✅ Clear separation of concerns
- ✅ Better documentation
- ✅ No code changes needed for config switches

### Production Readiness
- ✅ HA-ready Redis configuration
- ✅ Managed database support
- ✅ Proper health checks for MCP server
- ✅ Comprehensive troubleshooting guides

---

## Related Documentation

- **[DATABASE_REDIS_CONFIG.md](DATABASE_REDIS_CONFIG.md)** - Complete configuration guide
- **[AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md)** - Azure OpenAI configuration
- **[mcp-server/DEPLOYMENT_FIX.md](../mcp-server/DEPLOYMENT_FIX.md)** - MCP server fix details
- **[k8s/secrets-example.yaml](k8s/secrets-example.yaml)** - Secret configuration examples
- **[README.md](README.md)** - Main documentation

---

## Questions or Issues?

1. Check the comprehensive guides in `DATABASE_REDIS_CONFIG.md`
2. Review troubleshooting sections in each documentation file
3. Verify your secret configuration matches the examples
4. Check pod logs for specific error messages

---

**Date:** 2026-01-14  
**Author:** Automated configuration update for production readiness
