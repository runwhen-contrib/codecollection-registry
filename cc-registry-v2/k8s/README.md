# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying CC-Registry-V2.

## 📋 Files

- `backend-deployment.yaml` - FastAPI backend service
- `frontend-deployment.yaml` - React frontend with Ingress
- `worker-deployment.yaml` - Celery workers with HPA
- `scheduler-deployment.yaml` - Celery beat scheduler and Flower
- `database-deployment.yaml` - PostgreSQL database
- `redis-deployment.yaml` - Redis message broker
- `secrets-example.yaml` - Example secrets (DO NOT USE IN PRODUCTION)
- `kustomization.yaml` - Kustomize configuration
- `CONTAINER_BUILD.md` - Documentation for building container images

## 🚀 Quick Start

### Prerequisites

1. Kubernetes cluster (v1.24+)
2. `kubectl` configured to access your cluster
3. Container images built and pushed to registry (see `CONTAINER_BUILD.md`)
4. GitHub Personal Access Token for pulling images from GHCR

### Option 1: Using Kustomize (Recommended)

```bash
# 1. Edit kustomization.yaml to set your image registry and tags
# Replace OWNER/REPO with your GitHub org/repo

# 2. Create namespace
kubectl create namespace codecollection-registry

# 3. Create image pull secret
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace=codecollection-registry

# 4. Update secrets
# Copy secrets-example.yaml and update with real values
kubectl apply -f secrets-example.yaml

# 5. Deploy using kustomize
kubectl apply -k .
```

### Option 2: Manual Deployment

```bash
# 1. Create namespace
kubectl create namespace codecollection-registry

# 2. Update image references in all deployment files
# Replace ghcr.io/OWNER/REPO with your registry

# 3. Create secrets
kubectl apply -f secrets-example.yaml  # Update with real values first!

# 4. Deploy infrastructure
kubectl apply -f database-deployment.yaml
kubectl apply -f redis-deployment.yaml

# Wait for database and redis to be ready
kubectl wait --for=condition=ready pod -l component=database -n codecollection-registry --timeout=300s
kubectl wait --for=condition=ready pod -l component=redis -n codecollection-registry --timeout=300s

# 5. Deploy application
kubectl apply -f backend-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f worker-deployment.yaml
kubectl apply -f scheduler-deployment.yaml

# 6. Check deployment status
kubectl get all -n codecollection-registry
```

## 🔧 Configuration

### Update Image References

Before deploying, replace `OWNER/REPO` in all deployment files:

```bash
# Find and replace in all files
find . -type f -name "*.yaml" -exec sed -i 's|ghcr.io/OWNER/REPO|ghcr.io/your-org/your-repo|g' {} +
```

### Secrets Configuration

**IMPORTANT:** Never commit actual secrets to git!

1. Copy `secrets-example.yaml` to `secrets.yaml`
2. Update with your actual credentials:
   - Database credentials
   - Azure OpenAI API keys
   - Admin passwords
3. Apply: `kubectl apply -f secrets.yaml`

For production, use:
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- Cloud provider secret managers (Azure Key Vault, AWS Secrets Manager, etc.)

### Update Ingress Domain

Edit `frontend-deployment.yaml` and replace `cc-registry.example.com` with your domain:

```yaml
spec:
  tls:
  - hosts:
    - your-domain.com  # Update this
  rules:
  - host: your-domain.com  # Update this
```

### Environment-Specific Configuration

Create overlays for different environments:

```bash
# Directory structure
k8s/
├── base/           # Base configuration (current files)
├── overlays/
│   ├── dev/
│   │   └── kustomization.yaml
│   ├── staging/
│   │   └── kustomization.yaml
│   └── production/
│       └── kustomization.yaml
```

Example `overlays/production/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

bases:
  - ../../base

replicas:
  - name: cc-registry-backend
    count: 5
  - name: cc-registry-worker
    count: 10

images:
  - name: ghcr.io/OWNER/REPO/cc-registry-v2-backend
    newTag: v1.0.0
```

## 📊 Monitoring

### Check Deployment Status

```bash
# Get all resources
kubectl get all -n codecollection-registry

# Check pod logs
kubectl logs -f deployment/cc-registry-backend -n codecollection-registry
kubectl logs -f deployment/cc-registry-worker -n codecollection-registry

# Check pod status
kubectl describe pod <pod-name> -n codecollection-registry
```

### Access Flower (Celery Monitoring)

```bash
# Port-forward to Flower
kubectl port-forward svc/cc-registry-flower 5555:5555 -n codecollection-registry

# Access at http://localhost:5555
```

### Horizontal Pod Autoscaling

Workers have HPA configured. Monitor with:

```bash
kubectl get hpa -n codecollection-registry
kubectl describe hpa cc-registry-worker -n codecollection-registry
```

## 🔍 Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n codecollection-registry

# Describe pod to see events
kubectl describe pod <pod-name> -n codecollection-registry

# Check logs
kubectl logs <pod-name> -n codecollection-registry
```

### Image Pull Errors

```bash
# Verify image pull secret
kubectl get secret ghcr-pull-secret -n codecollection-registry -o yaml

# Test image pull manually
kubectl run test-pull --image=ghcr.io/OWNER/REPO/cc-registry-v2-backend:latest \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"ghcr-pull-secret"}]}}' \
  -n codecollection-registry
```

### Database Connection Issues

```bash
# Check database logs
kubectl logs deployment/postgres -n codecollection-registry

# Test connection from backend pod
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  psql $DATABASE_URL -c "SELECT 1"
```

### Redis Connection Issues

```bash
# Check Redis logs
kubectl logs deployment/redis -n codecollection-registry

# Test connection
kubectl exec -it deployment/redis -n codecollection-registry -- redis-cli ping
```

## 🔄 Updates and Rollouts

### Update to New Image Version

```bash
# Using kubectl set image
kubectl set image deployment/cc-registry-backend \
  backend=ghcr.io/OWNER/REPO/cc-registry-v2-backend:v1.1.0 \
  -n codecollection-registry

# Or edit kustomization.yaml and reapply
kubectl apply -k .

# Monitor rollout
kubectl rollout status deployment/cc-registry-backend -n codecollection-registry
```

### Rollback Deployment

```bash
# View rollout history
kubectl rollout history deployment/cc-registry-backend -n codecollection-registry

# Rollback to previous version
kubectl rollout undo deployment/cc-registry-backend -n codecollection-registry

# Rollback to specific revision
kubectl rollout undo deployment/cc-registry-backend --to-revision=2 -n codecollection-registry
```

### Restart Deployments

```bash
# Restart a deployment (useful for config changes)
kubectl rollout restart deployment/cc-registry-backend -n codecollection-registry
```

## 💾 Database Migrations

### Automatic Migration on Deployment

Database migrations run **automatically** when the backend container starts. This is handled by:

**File:** `backend/scripts/start.sh`
```bash
#!/bin/bash
# Run migrations before starting the app
python run_migrations.py
# Then start FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Migration Script:** `backend/scripts/run_migrations.py`
- Checks if database is ready
- Runs `alembic upgrade head`
- Retries on connection failures

### Worker/Scheduler Pattern

Workers and schedulers use an **initContainer** to wait for migrations:

```yaml
initContainers:
  - name: wait-for-migrations
    image: backend-image:tag
    command: ['python', '/app/scripts/run_migrations.py']
```

This ensures:
1. Backend starts and runs migrations
2. Workers/schedulers wait for migrations to complete
3. All pods start with correct schema

### Adding a New Migration

```bash
# 1. Create migration file in backend/alembic/versions/
# Example: 003_add_new_feature.py

# 2. Build and push new backend image
docker build -t your-registry/backend:v1.2.3 ./backend
docker push your-registry/backend:v1.2.3

# 3. Update image tag in kustomization.yaml or deployment manifests

# 4. Deploy (migrations run automatically on backend restart)
kubectl apply -k .

# 5. Monitor migration
kubectl logs -f deployment/cc-registry-backend -n codecollection-registry
# Look for: "Running migrations..." and "Migrations completed successfully"

# 6. Verify schema
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  alembic current
```

### Migration Safety

- **Idempotent:** Migrations use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, etc.
- **Atomic:** Each migration runs in a transaction
- **Logged:** All migration attempts are logged
- **Resilient:** Retries on connection failures

### Troubleshooting Migrations

```bash
# Check if migrations ran
kubectl logs deployment/cc-registry-backend -n codecollection-registry | grep -i migration

# Check current schema version
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  alembic current

# View migration history
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  alembic history

# Manually run migrations (if needed)
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  alembic upgrade head

# View pending migrations
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  alembic upgrade head --sql
```

### Migration Files Location

- **Local:** `backend/alembic/versions/`
- **Container:** `/app/alembic/versions/`
- **Pattern:** `{revision_id}_{description}.py`

### Recent Migrations

- `001_add_user_variables.py` - Added user_variables column to codebundles
- `002_add_task_growth_metrics.py` - Created task_growth_metrics table for analytics

## 🧹 Cleanup

### Delete All Resources

```bash
# Using kustomize
kubectl delete -k .

# Or manually
kubectl delete namespace codecollection-registry

# Delete PVCs (if namespace deletion hangs)
kubectl delete pvc --all -n codecollection-registry --force --grace-period=0
```

## 📚 Additional Resources

- [Container Build Documentation](CONTAINER_BUILD.md)
- [Kustomize Documentation](https://kustomize.io/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

## 🏗️ Architecture

```
┌─────────────────┐
│   Ingress       │
│  (TLS/HTTPS)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌───▼───┐
│Frontend│  │Backend│◄─────┐
└───┬───┘  └───┬───┘      │
    │          │          │
    │      ┌───▼───┐      │
    │      │ Redis │      │
    │      └───┬───┘      │
    │          │          │
    │      ┌───▼────┐     │
    │      │Worker  ├─────┘
    │      │(HPA)   │
    │      └────────┘
    │      ┌────────┐
    │      │Scheduler│
    │      └────────┘
    │
┌───▼────┐
│Postgres│
└────────┘
```

## 🔐 Security Considerations

1. **Secrets Management**: Use external secret management solutions
2. **Network Policies**: Implement network policies to restrict traffic
3. **RBAC**: Configure appropriate RBAC for service accounts
4. **Pod Security**: Use Pod Security Standards/Policies
5. **Image Scanning**: Scan images for vulnerabilities before deployment
6. **TLS**: Always use TLS/HTTPS for external access
7. **Resource Limits**: Set appropriate resource limits to prevent resource exhaustion

## 📈 Performance Tuning

### Backend
- Increase replicas for high traffic
- Adjust resource requests/limits based on usage
- Consider using a connection pooler for database (PgBouncer)

### Workers
- HPA will scale based on CPU/memory
- Adjust concurrency per worker (currently 4)
- Monitor queue length and adjust min/max replicas

### Database
- Consider using a managed database service for production
- Implement backup and restore procedures
- Monitor disk usage and adjust PVC size as needed

### Redis
- Monitor memory usage
- Adjust maxmemory policy based on use case
- Consider Redis clustering for high availability
