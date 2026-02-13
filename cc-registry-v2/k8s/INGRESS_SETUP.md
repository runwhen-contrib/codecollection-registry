# Ingress Setup Guide

## Overview

The CC-Registry-V2 application uses an Ingress to route external traffic to the frontend and backend services. This guide explains how to properly configure the ingress and React frontend to work together.

## Architecture

```
Internet → Ingress (HTTPS) → Frontend Service → React App
                          ↓
                          → Backend Service → FastAPI
```

When a user accesses `https://registry.example.com`:
- Requests to `/api/*` → routed to backend service
- Requests to `/*` → routed to frontend service
- React app makes API calls to `/api/v1/*` which go through the same ingress

## Key Configuration

### 1. Frontend API URL Configuration

**✅ CORRECT - Use Relative URL:**
```yaml
env:
- name: REACT_APP_API_URL
  value: "/api/v1"  # Relative path
```

**Why this works:**
- Browser automatically uses the same protocol (HTTP/HTTPS) and host
- Works with any domain (dev, staging, production)
- No hardcoding required
- Automatically works with TLS

**❌ WRONG - Hardcoded with Variables:**
```yaml
env:
- name: REACT_APP_API_URL
  value: "http://registry-test.${subdomain}.${domain}/api/v1"
```

**Problems:**
- `${subdomain}` and `${domain}` won't be substituted by Kubernetes
- Using `http://` when ingress has TLS configured
- Hardcoding domain makes it inflexible

### 2. Ingress Path Routing

**✅ CORRECT - API path first, then catch-all:**
```yaml
paths:
- path: /api
  pathType: Prefix
  backend:
    service:
      name: cc-registry-backend
      port:
        number: 8001

- path: /
  pathType: Prefix
  backend:
    service:
      name: cc-registry-frontend
      port:
        number: 3000
```

**Order matters!** API path must come BEFORE the root path, otherwise everything goes to frontend.

## Complete Working Example

### frontend-deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cc-registry-frontend
  namespace: registry-test
spec:
  replicas: 2
  selector:
    matchLabels:
      component: frontend
  template:
    metadata:
      labels:
        component: frontend
    spec:
      containers:
      - name: frontend
        image: your-image:tag
        ports:
        - containerPort: 3000
        env:
        - name: REACT_APP_API_URL
          value: "/api/v1"  # ← Relative URL
```

### ingress.yaml

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cc-registry
  namespace: registry-test
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
spec:
  ingressClassName: "nginx"
  tls:
  - hosts:
    - registry-test.runwhen.dev  # Your actual domain
    secretName: cc-registry-tls
  rules:
  - host: registry-test.runwhen.dev  # Your actual domain
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: cc-registry-backend
            port:
              number: 8001
      - path: /
        pathType: Prefix
        backend:
          service:
            name: cc-registry-frontend
            port:
              number: 3000
```

## Variable Substitution Options

If you need to use variables for the domain, use one of these approaches:

### Option 1: Kustomize with ConfigMap

**kustomization.yaml:**
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: registry-test

resources:
  - ingress.yaml

configMapGenerator:
  - name: domain-config
    literals:
      - hostname=registry-test.runwhen.dev

replacements:
  - source:
      kind: ConfigMap
      name: domain-config
      fieldPath: data.hostname
    targets:
      - select:
          kind: Ingress
          name: cc-registry
        fieldPaths:
          - spec.tls.[hosts="HOSTNAME_PLACEHOLDER"].hosts.0
          - spec.rules.[host="HOSTNAME_PLACEHOLDER"].host
```

**ingress.yaml:**
```yaml
spec:
  tls:
  - hosts:
    - HOSTNAME_PLACEHOLDER  # Will be replaced
  rules:
  - host: HOSTNAME_PLACEHOLDER  # Will be replaced
```

### Option 2: Helm Chart

Use Helm templating:
```yaml
spec:
  tls:
  - hosts:
    - {{ .Values.ingress.hostname }}
  rules:
  - host: {{ .Values.ingress.hostname }}
```

**values.yaml:**
```yaml
ingress:
  hostname: registry-test.runwhen.dev
```

### Option 3: envsubst (Manual)

Use environment variables and `envsubst`:

```bash
export HOSTNAME=registry-test.runwhen.dev
envsubst < ingress-template.yaml | kubectl apply -f -
```

## Testing

### 1. Verify Ingress is Created

```bash
kubectl get ingress -n registry-test
kubectl describe ingress cc-registry -n registry-test
```

Should show:
```
Name:             cc-registry
Namespace:        registry-test
Address:          <nginx-ingress-ip>
Rules:
  Host                        Path  Backends
  ----                        ----  --------
  registry-test.runwhen.dev
                              /api    cc-registry-backend:8001
                              /       cc-registry-frontend:3000
```

### 2. Check TLS Certificate

```bash
kubectl get certificate -n registry-test
kubectl describe certificate cc-registry-tls -n registry-test
```

Should show `Ready: True` after cert-manager provisions it.

### 3. Test Frontend Access

```bash
# Test HTTP redirect to HTTPS
curl -I http://registry-test.runwhen.dev
# Should return 301 or 308 redirect to https://

# Test HTTPS access
curl -I https://registry-test.runwhen.dev
# Should return 200 OK
```

### 4. Test API Access

```bash
# Test backend health endpoint through ingress
curl https://registry-test.runwhen.dev/api/v1/health

# Should return:
{
  "status": "healthy",
  "database": "connected",
  "environment": "production",
  "version": "1.0.0"
}
```

### 5. Test from Browser

1. Open `https://registry-test.runwhen.dev` in browser
2. Open browser DevTools → Network tab
3. Check that API calls go to `/api/v1/*` (relative URLs)
4. Verify responses are successful

## Troubleshooting

### Frontend Shows But API Calls Fail

**Symptom:** Frontend loads, but API calls return 404 or CORS errors

**Check:**
```bash
# Verify API path routing
curl -v https://registry-test.runwhen.dev/api/v1/health

# Check ingress path order
kubectl get ingress cc-registry -n registry-test -o yaml | grep -A 5 "paths:"
```

**Solution:** Ensure `/api` path comes BEFORE `/` path in ingress rules.

### TLS Certificate Not Working

**Symptom:** Browser shows SSL errors

**Check:**
```bash
# Check certificate status
kubectl describe certificate cc-registry-tls -n registry-test

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager
```

**Common fixes:**
- Verify `cert-manager.io/cluster-issuer` annotation
- Check that ClusterIssuer exists: `kubectl get clusterissuer`
- DNS must be pointing to ingress before cert-manager can verify

### Variables Not Being Replaced

**Symptom:** Ingress shows literal `${subdomain}` in host field

**Cause:** Kubernetes doesn't do variable substitution

**Solutions:**
- Use Kustomize replacements (see Option 1 above)
- Use Helm templating
- Use `envsubst` before applying
- Or just use the actual domain value directly

### CORS Errors

**Symptom:** Browser console shows CORS errors

**Solution:** Add CORS annotations to ingress:
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://registry-test.runwhen.dev"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "Authorization, Content-Type"
```

However, with relative URLs (`/api/v1`), CORS shouldn't be an issue since requests are same-origin.

## Security Best Practices

1. **Always use TLS in production:**
   ```yaml
   annotations:
     nginx.ingress.kubernetes.io/ssl-redirect: "true"
     nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
   ```

2. **Set appropriate timeouts:**
   ```yaml
   annotations:
     nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
     nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
   ```

3. **Limit request body size:**
   ```yaml
   annotations:
     nginx.ingress.kubernetes.io/proxy-body-size: "100m"
   ```

4. **Enable rate limiting (optional):**
   ```yaml
   annotations:
     nginx.ingress.kubernetes.io/limit-rps: "100"
     nginx.ingress.kubernetes.io/limit-connections: "50"
   ```

5. **Use strong TLS settings:**
   ```yaml
   annotations:
     nginx.ingress.kubernetes.io/ssl-protocols: "TLSv1.2 TLSv1.3"
     nginx.ingress.kubernetes.io/ssl-ciphers: "HIGH:!aNULL:!MD5"
   ```

## Multi-Environment Setup

For different environments (dev, staging, production), use separate ingresses:

**dev:**
```yaml
host: registry-dev.runwhen.dev
```

**staging:**
```yaml
host: registry-staging.runwhen.dev
```

**production:**
```yaml
host: registry.runwhen.dev
```

Frontend always uses `/api/v1` (relative), so no changes needed.

## Related Documentation

- [frontend-deployment.yaml](frontend-deployment.yaml) - Frontend deployment configuration
- [backend-deployment.yaml](backend-deployment.yaml) - Backend deployment configuration
- [ingress-example.yaml](ingress-example.yaml) - Example ingress configuration
- [DATABASE_REDIS_CONFIG.md](../DATABASE_REDIS_CONFIG.md) - Database and Redis configuration
