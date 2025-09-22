# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the CodeCollection Registry.

## Quick Start

1. **Generate manifests from docker-compose:**
   ```bash
   task k8s:export
   ```

2. **Or use the provided manifests:**
   ```bash
   kubectl apply -f k8s/
   ```

## Manual Deployment

```bash
# Create namespace
kubectl create namespace codecollection-registry

# Deploy database
kubectl apply -f database-deployment.yaml
kubectl apply -f database-service.yaml

# Deploy Redis
kubectl apply -f redis-deployment.yaml
kubectl apply -f redis-service.yaml

# Deploy backend
kubectl apply -f backend-deployment.yaml
kubectl apply -f backend-service.yaml

# Deploy frontend
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

# Deploy workers
kubectl apply -f worker-deployment.yaml
kubectl apply -f scheduler-deployment.yaml
kubectl apply -f flower-deployment.yaml
```

## Configuration

Update the ConfigMap and Secrets with your environment-specific values:

```bash
kubectl create configmap registry-config --from-env-file=../.env
kubectl create secret generic registry-secrets --from-env-file=../.env
```

## Ingress

Configure ingress for external access:

```bash
kubectl apply -f ingress.yaml
```

## Monitoring

The deployment includes:
- Health checks for all services
- Resource limits and requests
- Horizontal Pod Autoscaler (HPA) ready
- Service monitors for Prometheus (if available)
