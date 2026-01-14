# CC-Registry-V2 Quick Reference

## 🚀 Quick Commands

### Local Development
```bash
task start              # Start all services
task stop               # Stop all services
task logs               # View all logs
task status             # Check service status
task health             # Health check all services
```

### Build Container Images
```bash
# Build all images
task image:build

# Build specific image
task image:build:backend
task image:build:frontend
task image:build:worker

# Build with custom tag
task image:build TAG=v1.0.0
```

### Push to Registry
```bash
# Set variables
export REGISTRY="ghcr.io/your-org/your-repo"
export TAG="v1.0.0"

# Build, tag, and push
task image:publish REGISTRY=$REGISTRY TAG=$TAG
```

### Kubernetes Deployment
```bash
# Deploy
task k8s:deploy

# Check status
task k8s:status

# View logs
task k8s:logs SERVICE=backend

# Restart service
task k8s:restart SERVICE=backend

# Rollback
task k8s:rollback SERVICE=backend

# Undeploy
task k8s:undeploy
```

### Complete Deployment Flow
```bash
# Build, push, update manifests, and deploy
export REGISTRY="ghcr.io/your-org/your-repo"
export TAG="v1.0.0"

task image:publish REGISTRY=$REGISTRY TAG=$TAG
task k8s:update-images REGISTRY=$REGISTRY TAG=$TAG
task k8s:deploy
```

## 📦 Container Images

### Image Names
```
ghcr.io/<owner>/<repo>/cc-registry-v2-backend:<tag>
ghcr.io/<owner>/<repo>/cc-registry-v2-frontend:<tag>
ghcr.io/<owner>/<repo>/cc-registry-v2-worker:<tag>
```

### Build Locally
```bash
docker build -t cc-registry-v2-backend:latest ./backend
docker build -t cc-registry-v2-frontend:latest ./frontend
docker build -t cc-registry-v2-worker:latest ./worker
```

### Tag for Registry
```bash
docker tag cc-registry-v2-backend:latest ghcr.io/org/repo/cc-registry-v2-backend:v1.0.0
docker tag cc-registry-v2-frontend:latest ghcr.io/org/repo/cc-registry-v2-frontend:v1.0.0
docker tag cc-registry-v2-worker:latest ghcr.io/org/repo/cc-registry-v2-worker:v1.0.0
```

### Push to Registry
```bash
docker push ghcr.io/org/repo/cc-registry-v2-backend:v1.0.0
docker push ghcr.io/org/repo/cc-registry-v2-frontend:v1.0.0
docker push ghcr.io/org/repo/cc-registry-v2-worker:v1.0.0
```

## ☸️ Kubernetes

### Namespace
```bash
kubectl create namespace codecollection-registry
kubectl get all -n codecollection-registry
```

### Deploy
```bash
# Using kustomize
kubectl apply -k k8s/

# Manual
kubectl apply -f k8s/database-deployment.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/scheduler-deployment.yaml
```

### Secrets
```bash
# Create image pull secret
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=USERNAME \
  --docker-password=TOKEN \
  --namespace=codecollection-registry

# Apply secrets
kubectl apply -f k8s/secrets.yaml
```

### Check Status
```bash
# All resources
kubectl get all -n codecollection-registry

# Pods
kubectl get pods -n codecollection-registry
kubectl get pods -n codecollection-registry -o wide

# Watch pods
kubectl get pods -n codecollection-registry -w

# Describe pod
kubectl describe pod <pod-name> -n codecollection-registry
```

### Logs
```bash
# Follow logs
kubectl logs -f deployment/cc-registry-backend -n codecollection-registry
kubectl logs -f deployment/cc-registry-frontend -n codecollection-registry
kubectl logs -f deployment/cc-registry-worker -n codecollection-registry

# Last 100 lines
kubectl logs deployment/cc-registry-backend -n codecollection-registry --tail=100

# Previous logs (crashed pod)
kubectl logs <pod-name> --previous -n codecollection-registry

# Multiple pods
kubectl logs -l component=worker -n codecollection-registry -f
```

### Update Deployment
```bash
# Set new image
kubectl set image deployment/cc-registry-backend \
  backend=ghcr.io/org/repo/cc-registry-v2-backend:v1.1.0 \
  -n codecollection-registry

# Restart deployment
kubectl rollout restart deployment/cc-registry-backend -n codecollection-registry

# Check rollout status
kubectl rollout status deployment/cc-registry-backend -n codecollection-registry

# Rollback
kubectl rollout undo deployment/cc-registry-backend -n codecollection-registry

# Rollout history
kubectl rollout history deployment/cc-registry-backend -n codecollection-registry
```

### Scale
```bash
# Scale deployment
kubectl scale deployment/cc-registry-backend --replicas=5 -n codecollection-registry

# Check HPA
kubectl get hpa -n codecollection-registry
kubectl describe hpa cc-registry-worker -n codecollection-registry
```

### Port Forward
```bash
# Backend
kubectl port-forward svc/cc-registry-backend 8001:8001 -n codecollection-registry

# Frontend
kubectl port-forward svc/cc-registry-frontend 3000:3000 -n codecollection-registry

# Flower
kubectl port-forward svc/cc-registry-flower 5555:5555 -n codecollection-registry

# Database
kubectl port-forward svc/postgres 5432:5432 -n codecollection-registry

# Redis
kubectl port-forward svc/redis 6379:6379 -n codecollection-registry
```

### Execute Commands
```bash
# Shell in pod
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- /bin/bash

# Run command
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- env

# Database shell
kubectl exec -it deployment/postgres -n codecollection-registry -- \
  psql -U user -d codecollection_registry
```

### Delete Resources
```bash
# Delete specific deployment
kubectl delete deployment cc-registry-backend -n codecollection-registry

# Delete using kustomize
kubectl delete -k k8s/

# Delete namespace (deletes everything)
kubectl delete namespace codecollection-registry
```

## 🐛 Troubleshooting

### Check Pod Issues
```bash
# Pod status
kubectl get pods -n codecollection-registry

# Pod details
kubectl describe pod <pod-name> -n codecollection-registry

# Events
kubectl get events -n codecollection-registry --sort-by='.lastTimestamp'

# Logs
kubectl logs <pod-name> -n codecollection-registry
kubectl logs <pod-name> --previous -n codecollection-registry
```

### Resource Usage
```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -n codecollection-registry

# Resource limits
kubectl describe node
```

### Network Issues
```bash
# Services
kubectl get svc -n codecollection-registry

# Endpoints
kubectl get endpoints -n codecollection-registry

# Test DNS
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  nslookup postgres

# Test connectivity
kubectl exec -it deployment/cc-registry-backend -n codecollection-registry -- \
  curl -v http://postgres:5432
```

### Image Pull Issues
```bash
# Check secret
kubectl get secret ghcr-pull-secret -n codecollection-registry -o yaml

# Recreate secret
kubectl delete secret ghcr-pull-secret -n codecollection-registry
kubectl create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=USERNAME \
  --docker-password=TOKEN \
  --namespace=codecollection-registry

# Test image pull
kubectl run test --image=ghcr.io/org/repo/cc-registry-v2-backend:latest \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"ghcr-pull-secret"}]}}' \
  -n codecollection-registry
```

## 📊 Monitoring

### Health Endpoints
```bash
# Backend health
curl http://localhost:8001/api/v1/health

# Redis
redis-cli ping

# Database
psql $DATABASE_URL -c "SELECT 1"
```

### Flower (Celery Monitoring)
```bash
# Port-forward
kubectl port-forward svc/cc-registry-flower 5555:5555 -n codecollection-registry

# Access at http://localhost:5555
```

### Resource Metrics
```bash
# Metrics server required
kubectl top nodes
kubectl top pods -n codecollection-registry
```

## 🔐 Secrets

### Create Secrets
```bash
# From literal values
kubectl create secret generic my-secret \
  --from-literal=key=value \
  -n codecollection-registry

# From file
kubectl create secret generic my-secret \
  --from-file=./secret.txt \
  -n codecollection-registry

# From env file
kubectl create secret generic my-secret \
  --from-env-file=.env \
  -n codecollection-registry
```

### View Secrets
```bash
# List secrets
kubectl get secrets -n codecollection-registry

# Get secret (base64 encoded)
kubectl get secret my-secret -n codecollection-registry -o yaml

# Decode secret
kubectl get secret my-secret -n codecollection-registry -o jsonpath='{.data.key}' | base64 -d
```

## 🔄 GitHub Actions

### Manual Workflow Trigger
1. Go to **Actions** tab
2. Select "Build CC-Registry-V2 Container Images"
3. Click "Run workflow"
4. Configure:
   - Branch: `main` or feature branch
   - Push images: `true`
   - Tag: `v1.0.0`
5. Click "Run workflow"

### Workflow Outputs
- Images pushed to GHCR
- Comments on PR with build status
- Build summary in workflow run

## 📚 Documentation

- [Full Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Container Build Documentation](k8s/CONTAINER_BUILD.md)
- [Kubernetes Manifests](k8s/README.md)
- [Taskfile](Taskfile.yml)
- [Docker Compose](docker-compose.yml)

## 🆘 Get Help

```bash
# Task help
task --list
task --summary

# Kubectl help
kubectl --help
kubectl <command> --help

# Docker help
docker --help
docker <command> --help
```
