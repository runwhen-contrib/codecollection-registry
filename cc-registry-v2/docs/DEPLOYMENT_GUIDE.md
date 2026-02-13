# CC-Registry-V2 Deployment Guide

This guide covers the complete deployment process for CC-Registry-V2, from building container images to deploying to a Kubernetes test cluster.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Container Image Workflow](#container-image-workflow)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **Docker** (v20.10+) - For building container images
- **kubectl** (v1.24+) - For Kubernetes deployments
- **task** - Task runner (install: `brew install go-task/tap/go-task` or see [taskfile.dev](https://taskfile.dev))
- **GitHub Account** - With access to GitHub Container Registry (GHCR)

### Optional Tools

- **kustomize** (v4.5+) - For advanced Kubernetes configurations
- **k9s** - Terminal-based Kubernetes UI (recommended for monitoring)
- **helm** - For managing Kubernetes applications

### Kubernetes Cluster Access

You need access to a Kubernetes cluster:
- **Local**: Docker Desktop, Minikube, Kind, k3d
- **Cloud**: AKS, EKS, GKE
- **On-premise**: Any Kubernetes cluster

Verify access:
```bash
kubectl cluster-info
kubectl get nodes
```

## Quick Start

### 1. Build and Test Locally

```bash
# Navigate to project directory
cd cc-registry-v2

# Start local development environment
task start

# Check services are running
task status

# View logs
task logs
```

### 2. Build Container Images

```bash
# Build all images
task image:build

# Or build individually
task image:build:backend
task image:build:frontend
task image:build:worker
```

### 3. Push to Registry

```bash
# Set your registry (replace with your GitHub org/repo)
export REGISTRY="ghcr.io/your-org/your-repo"
export TAG="v1.0.0"

# Build, tag, and push all images
task image:publish REGISTRY=$REGISTRY TAG=$TAG
```

### 4. Deploy to Kubernetes

```bash
# Update image references in k8s manifests
task k8s:update-images REGISTRY=$REGISTRY TAG=$TAG

# Setup namespace and secrets
task k8s:setup

# Deploy
task k8s:deploy

# Check status
task k8s:status
```

## Container Image Workflow

### GitHub Actions Workflow

The project includes a GitHub Actions workflow that automatically builds container images.

#### Workflow File Location
`.github/workflows/build-cc-registry-v2-images.yaml`

#### Automatic Triggers

1. **Pull Requests** - Builds images when PRs are opened (images not pushed)
2. **Manual Dispatch** - Manually trigger builds with custom tags

#### Manual Trigger from GitHub UI

1. Go to **Actions** tab in GitHub
2. Select "Build CC-Registry-V2 Container Images"
3. Click "Run workflow"
4. Configure options:
   - **Branch**: Select branch to build from
   - **Push images**: `true` to push to registry
   - **Tag**: Custom tag (e.g., `v1.0.0`, `test-123`)
5. Click "Run workflow"

#### Image Naming Convention

```
ghcr.io/<owner>/<repo>/cc-registry-v2-backend:<tag>
ghcr.io/<owner>/<repo>/cc-registry-v2-frontend:<tag>
ghcr.io/<owner>/<repo>/cc-registry-v2-worker:<tag>
```

Tags:
- `latest` - Latest build from main branch
- `pr-<number>` - Pull request builds
- `<branch>-<sha>` - Branch name + commit SHA
- Custom tags from manual dispatch

### Local Image Build

#### Build All Images

```bash
task image:build
```

#### Build with Custom Tag

```bash
task image:build TAG=v1.0.0
```

#### Build Individual Components

```bash
task image:build:backend TAG=v1.0.0
task image:build:frontend TAG=v1.0.0
task image:build:worker TAG=v1.0.0
```

### Push Images to Registry

#### Setup GitHub Container Registry Authentication

```bash
# Create GitHub Personal Access Token with:
# - read:packages
# - write:packages
# - delete:packages (optional)

# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin
```

#### Tag and Push

```bash
# Set variables
export REGISTRY="ghcr.io/your-org/your-repo"
export TAG="v1.0.0"

# Tag images
task image:tag REGISTRY=$REGISTRY TAG=$TAG

# Push images
task image:push REGISTRY=$REGISTRY TAG=$TAG
```

#### One-Command Publish

```bash
# Build, tag, and push in one command
task image:publish REGISTRY=ghcr.io/your-org/your-repo TAG=v1.0.0
```

## Kubernetes Deployment

### Pre-Deployment Setup

#### 1. Update Configuration Files

**Update image registry:**
```bash
cd k8s
# Replace OWNER/REPO with your GitHub org/repo
find . -type f -name "*.yaml" ! -name "secrets-example.yaml" -exec sed -i \
  's|ghcr.io/OWNER/REPO|ghcr.io/your-org/your-repo|g' {} +
```

Or use the task:
```bash
task k8s:update-images REGISTRY=ghcr.io/your-org/your-repo TAG=v1.0.0
```

**Update domain in ingress:**
```bash
# Edit k8s/frontend-deployment.yaml
# Replace cc-registry.example.com with your domain
```

#### 2. Create Secrets

**Important:** Never commit real secrets to git!

```bash
# Copy example secrets
cp k8s/secrets-example.yaml k8s/secrets.yaml

# Edit secrets.yaml with real values
# - Database credentials
# - Azure OpenAI API keys
# - Admin passwords

# Apply secrets
kubectl apply -f k8s/secrets.yaml
```

**Production Recommendation:** Use external secret management:
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/)
- Cloud provider secret managers

#### 3. Create Image Pull Secret

```bash
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace=codecollection-registry
```

### Deployment Methods

#### Method 1: Using Task Commands (Recommended)

```bash
# Validate manifests
task k8s:validate

# Deploy
task k8s:deploy

# Check status
task k8s:status
```

#### Method 2: Using kubectl with Kustomize

```bash
# Apply using kustomize
kubectl apply -k k8s/

# Check status
kubectl get all -n codecollection-registry
```

#### Method 3: Manual kubectl apply

```bash
# Create namespace
kubectl create namespace codecollection-registry

# Apply manifests in order
kubectl apply -f k8s/secrets-example.yaml
kubectl apply -f k8s/database-deployment.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/scheduler-deployment.yaml
```

### Post-Deployment Verification

#### Check Pod Status

```bash
# Using task
task k8s:status

# Using kubectl
kubectl get pods -n codecollection-registry

# Watch pods
kubectl get pods -n codecollection-registry -w
```

#### Check Logs

```bash
# Using task
task k8s:logs SERVICE=backend
task k8s:logs SERVICE=frontend
task k8s:logs SERVICE=worker

# Using kubectl
kubectl logs -f deployment/cc-registry-backend -n codecollection-registry
```

#### Test Services

```bash
# Port-forward backend
kubectl port-forward svc/cc-registry-backend 8001:8001 -n codecollection-registry

# Test health endpoint
curl http://localhost:8001/api/v1/health

# Port-forward frontend
kubectl port-forward svc/cc-registry-frontend 3000:3000 -n codecollection-registry

# Access at http://localhost:3000
```

#### Access Flower (Celery Monitoring)

```bash
kubectl port-forward svc/cc-registry-flower 5555:5555 -n codecollection-registry
# Access at http://localhost:5555
```

## Common Tasks

### Update to New Version

```bash
# Build and push new version
task image:publish REGISTRY=ghcr.io/your-org/your-repo TAG=v1.1.0

# Update k8s manifests
task k8s:update-images REGISTRY=ghcr.io/your-org/your-repo TAG=v1.1.0

# Deploy update
task k8s:deploy

# Or use kubectl set image
kubectl set image deployment/cc-registry-backend \
  backend=ghcr.io/your-org/your-repo/cc-registry-v2-backend:v1.1.0 \
  -n codecollection-registry
```

### Restart Services

```bash
# Restart specific service
task k8s:restart SERVICE=backend

# Restart all services
task k8s:restart SERVICE=all
```

### Rollback Deployment

```bash
# Rollback specific service
task k8s:rollback SERVICE=backend

# Or using kubectl
kubectl rollout undo deployment/cc-registry-backend -n codecollection-registry
```

### Scale Services

```bash
# Scale backend
kubectl scale deployment/cc-registry-backend --replicas=5 -n codecollection-registry

# Scale workers (or let HPA handle it)
kubectl scale deployment/cc-registry-worker --replicas=10 -n codecollection-registry
```

### View Logs

```bash
# Specific service
task k8s:logs SERVICE=backend

# Multiple pods
kubectl logs -l component=worker -n codecollection-registry --tail=100 -f

# Previous container logs (for crashed pods)
kubectl logs <pod-name> --previous -n codecollection-registry
```

### Database Operations

```bash
# Connect to database
kubectl exec -it deployment/postgres -n codecollection-registry -- \
  psql -U user -d codecollection_registry

# Backup database
kubectl exec deployment/postgres -n codecollection-registry -- \
  pg_dump -U user codecollection_registry > backup_$(date +%Y%m%d).sql

# Restore database
cat backup.sql | kubectl exec -i deployment/postgres -n codecollection-registry -- \
  psql -U user -d codecollection_registry
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n codecollection-registry

# Describe pod to see events
kubectl describe pod <pod-name> -n codecollection-registry

# Check logs
kubectl logs <pod-name> -n codecollection-registry

# Check previous logs if crashed
kubectl logs <pod-name> --previous -n codecollection-registry
```

### Image Pull Errors

```bash
# Verify secret exists
kubectl get secret ghcr-pull-secret -n codecollection-registry

# Check secret contents
kubectl get secret ghcr-pull-secret -n codecollection-registry -o yaml

# Recreate secret
kubectl delete secret ghcr-pull-secret -n codecollection-registry
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_USERNAME \
  --docker-password=YOUR_TOKEN \
  --namespace=codecollection-registry
```

### Service Not Accessible

```bash
# Check service
kubectl get svc -n codecollection-registry

# Check endpoints
kubectl get endpoints -n codecollection-registry

# Check ingress
kubectl get ingress -n codecollection-registry
kubectl describe ingress cc-registry-frontend -n codecollection-registry
```

### Database Connection Issues

```bash
# Check database pod
kubectl logs deployment/postgres -n codecollection-registry

# Test connection from backend pod
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  bash -c 'apt-get update && apt-get install -y postgresql-client && psql $DATABASE_URL -c "SELECT 1"'
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -n codecollection-registry
kubectl top nodes

# Check HPA status
kubectl get hpa -n codecollection-registry
kubectl describe hpa cc-registry-worker -n codecollection-registry

# Increase resources
# Edit deployment and update resource limits/requests
kubectl edit deployment/cc-registry-backend -n codecollection-registry
```

### Complete Cleanup

```bash
# Delete all resources
task k8s:undeploy

# Or manually
kubectl delete namespace codecollection-registry

# If namespace stuck in terminating state
kubectl delete pvc --all -n codecollection-registry --force --grace-period=0
kubectl get namespace codecollection-registry -o json | \
  jq '.spec = {"finalizers":[]}' | \
  kubectl replace --raw /api/v1/namespaces/codecollection-registry/finalize -f -
```

## CI/CD Integration

### Deploy on Git Push

Add to your GitHub Actions workflow:

```yaml
deploy:
  needs: [build-backend, build-frontend, build-worker]
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - name: Setup kubectl
      uses: azure/setup-kubectl@v3
    
    - name: Set context
      uses: azure/k8s-set-context@v3
      with:
        kubeconfig: ${{ secrets.KUBECONFIG }}
    
    - name: Deploy to cluster
      run: |
        kubectl set image deployment/cc-registry-backend \
          backend=ghcr.io/${{ github.repository }}/cc-registry-v2-backend:${{ github.sha }} \
          -n codecollection-registry
```

### Automated Rollback

Monitor deployments and automatically rollback on failure:

```yaml
- name: Check deployment health
  run: |
    kubectl rollout status deployment/cc-registry-backend -n codecollection-registry --timeout=5m
    
- name: Rollback on failure
  if: failure()
  run: |
    kubectl rollout undo deployment/cc-registry-backend -n codecollection-registry
```

## Best Practices

1. **Always use tagged images** - Never use `:latest` in production
2. **Implement health checks** - All services have liveness and readiness probes
3. **Set resource limits** - Prevent resource exhaustion
4. **Use secrets management** - Never commit secrets to git
5. **Monitor logs and metrics** - Use logging aggregation and monitoring tools
6. **Test in staging first** - Always test deployments in a staging environment
7. **Document changes** - Keep deployment notes for each version
8. **Backup databases** - Regular automated backups
9. **Use GitOps** - Version control your Kubernetes manifests
10. **Security scanning** - Scan images for vulnerabilities before deploying

## Additional Resources

- [Container Build Documentation](k8s/CONTAINER_BUILD.md)
- [Kubernetes Manifests](k8s/README.md)
- [GitHub Actions Workflow](.github/workflows/build-cc-registry-v2-images.yaml)
- [Docker Compose](docker-compose.yml)
- [Taskfile](Taskfile.yml)

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review logs: `task k8s:logs SERVICE=<service>`
- Check GitHub Issues
- Review Kubernetes events: `kubectl get events -n codecollection-registry`
