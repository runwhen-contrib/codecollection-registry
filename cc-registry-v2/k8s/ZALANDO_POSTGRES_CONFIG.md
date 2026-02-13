# Zalando Postgres Operator Configuration Guide

## Issue

When using Zalando's postgres-operator, the automatically generated secrets have a specific structure that differs from manually created secrets.

## Zalando Postgres-Operator Secret Structure

Zalando's postgres-operator creates secrets with this naming pattern:
```
{username}.{cluster-name}.credentials.postgresql.acid.zalan.do
```

Example: `registry-user.registry-db.credentials.postgresql.acid.zalan.do`

These secrets typically contain these keys:
- `username` - The database user
- `password` - The database password

**Note:** The database name is usually the same as the username in Zalando's operator.

## Correct Configuration for CC-Registry-V2

### Option 1: Using Secret with Hardcoded DB Name (Recommended)

Create a ConfigMap or use direct env vars for static values:

```yaml
env:
- name: DB_HOST
  value: "registry-db"  # Your postgres cluster service name
- name: DB_PORT
  value: "5432"  # PostgreSQL default port (NOT 5342!)
- name: DB_NAME
  value: "registry-user"  # Usually same as username for Zalando
- name: DB_USER
  valueFrom:
    secretKeyRef:
      key: username
      name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      key: password
      name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
# Redis Sentinel configuration
- name: REDIS_SENTINEL_HOSTS
  value: "redis-sentinel-0.redis-sentinel:26379,redis-sentinel-1.redis-sentinel:26379,redis-sentinel-2.redis-sentinel:26379"
- name: REDIS_SENTINEL_MASTER
  value: "mymaster"
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      key: redis-password
      name: redis-sentinel
- name: REDIS_DB
  value: "0"
```

### Option 2: Create a Wrapper Secret

Create a new secret that references the Zalando secret and adds missing fields:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cc-registry-secrets
  namespace: registry-test
type: Opaque
stringData:
  DB_HOST: "registry-db"
  DB_PORT: "5432"
  DB_NAME: "registry-user"  # Adjust if different
  # For username and password, you'll need to copy values or use External Secrets Operator
```

Then use `envFrom`:
```yaml
envFrom:
- secretRef:
    name: cc-registry-secrets
- secretRef:
    name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
```

### Option 3: Construct DATABASE_URL Directly

If you prefer a single connection string:

```bash
# Get the password
DB_PASSWORD=$(kubectl get secret registry-user.registry-db.credentials.postgresql.acid.zalan.do \
  -n registry-test -o jsonpath='{.data.password}' | base64 -d)

# Create secret with full URL
kubectl create secret generic cc-registry-secrets \
  --from-literal=DATABASE_URL="postgresql://registry-user:${DB_PASSWORD}@registry-db:5432/registry-user" \
  --from-literal=REDIS_SENTINEL_HOSTS="redis-sentinel-0.redis-sentinel:26379,redis-sentinel-1.redis-sentinel:26379,redis-sentinel-2.redis-sentinel:26379" \
  --from-literal=REDIS_SENTINEL_MASTER="mymaster" \
  --from-literal=REDIS_PASSWORD="your-redis-password" \
  --from-literal=REDIS_DB="0" \
  -n registry-test \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Common Errors and Fixes

### Error: Port 5342

**Symptom:** Database connection errors mentioning port 5342

**Cause:** Typo in DB_PORT configuration

**Fix:**
```yaml
- name: DB_PORT
  value: "5432"  # NOT 5342
```

### Error: DB_NAME Using Wrong Secret Key

**Symptom:** Pod describes shows DB_NAME referencing `password` key

**Current (WRONG):**
```yaml
- name: DB_NAME
  valueFrom:
    secretKeyRef:
      key: password  # This gets the password, not the DB name!
      name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
```

**Fix:**
```yaml
- name: DB_NAME
  value: "registry-user"  # Static value, usually same as username
```

### Error: Exit Code 137 (SIGKILL)

**Symptom:** Pod keeps restarting with exit code 137

**Cause:** 
1. Application can't connect to database (wrong config)
2. Health check fails repeatedly
3. Liveness probe kills the container after 3 failures
4. Kubernetes restarts it

**Fix:** Correct the database configuration (port and DB name)

## Verification Steps

### 1. Check Zalando Secret Contents

```bash
# View secret keys
kubectl get secret registry-user.registry-db.credentials.postgresql.acid.zalan.do \
  -n registry-test -o jsonpath='{.data}' | jq 'keys'

# Decode username
kubectl get secret registry-user.registry-db.credentials.postgresql.acid.zalan.do \
  -n registry-test -o jsonpath='{.data.username}' | base64 -d

# The database name is typically the same as the username
```

### 2. Test Database Connection

```bash
# Get password from secret
DB_PASSWORD=$(kubectl get secret registry-user.registry-db.credentials.postgresql.acid.zalan.do \
  -n registry-test -o jsonpath='{.data.password}' | base64 -d)

# Test connection from a debug pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -n registry-test -- \
  psql "postgresql://registry-user:${DB_PASSWORD}@registry-db:5432/registry-user" -c "SELECT version();"
```

### 3. Check Pod Environment

```bash
# View all environment variables in the pod
kubectl exec -n registry-test deployment/cc-registry-backend -- env | grep DB_

# Should show:
# DB_HOST=registry-db
# DB_PORT=5432  (NOT 5342!)
# DB_USER=registry-user
# DB_PASSWORD=<password>
# DB_NAME=registry-user  (NOT the password!)
```

### 4. Check Application Logs

```bash
# Check current logs
kubectl logs -n registry-test deployment/cc-registry-backend --tail=100

# Check previous crashed container
kubectl logs -n registry-test deployment/cc-registry-backend --previous

# Look for:
# - "could not connect to server"
# - Port errors
# - Authentication errors
# - SQLAlchemy connection errors
```

## Complete Working Example

Here's a complete, working configuration for Zalando postgres-operator + Redis Sentinel:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cc-registry-backend
  namespace: registry-test
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cc-registry
      component: backend
  template:
    metadata:
      labels:
        app: cc-registry
        component: backend
    spec:
      containers:
      - name: backend
        image: us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-backend:hack-mcp-12183954
        imagePullPolicy: Always
        ports:
        - containerPort: 8001
          name: http
        env:
        # Database configuration
        - name: DB_HOST
          value: "registry-db"
        - name: DB_PORT
          value: "5432"  # CORRECT PORT
        - name: DB_NAME
          value: "registry-user"  # USUALLY SAME AS USERNAME
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              key: username
              name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              key: password
              name: registry-user.registry-db.credentials.postgresql.acid.zalan.do
        
        # Redis Sentinel configuration
        - name: REDIS_SENTINEL_HOSTS
          value: "redis-sentinel-0.redis-sentinel:26379,redis-sentinel-1.redis-sentinel:26379,redis-sentinel-2.redis-sentinel:26379"
        - name: REDIS_SENTINEL_MASTER
          value: "mymaster"
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              key: redis-password
              name: redis-sentinel
        - name: REDIS_DB
          value: "0"
        
        # Application configuration
        - name: ENVIRONMENT
          value: "production"
        - name: MCP_SERVER_URL
          value: "http://mcp-server:8000"
        - name: AI_SERVICE_PROVIDER
          value: "azure-openai"
        - name: AI_ENHANCEMENT_ENABLED
          value: "true"
        
        envFrom:
        # Load Azure OpenAI credentials
        - secretRef:
            name: azure-openai-credentials
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
```

## Apply the Fix

1. **Update your deployment YAML with correct configuration**
2. **Apply the changes:**
   ```bash
   kubectl apply -f backend-deployment.yaml -n registry-test
   ```

3. **Watch the rollout:**
   ```bash
   kubectl rollout status deployment/cc-registry-backend -n registry-test
   ```

4. **Verify the pods are healthy:**
   ```bash
   kubectl get pods -n registry-test -l component=backend
   # Should show: Running, Ready: 1/1
   ```

5. **Check health endpoint:**
   ```bash
   kubectl port-forward -n registry-test svc/cc-registry-backend 8001:8001
   curl http://localhost:8001/api/v1/health
   
   # Should return:
   # {"status":"healthy","database":"connected","environment":"production","version":"1.0.0"}
   ```

## Troubleshooting

If still having issues after fixing the configuration:

1. **Check if the postgres cluster is healthy:**
   ```bash
   kubectl get postgresql -n registry-test
   kubectl get pods -n registry-test -l cluster-name=registry-db
   ```

2. **Verify the secret exists and has correct keys:**
   ```bash
   kubectl describe secret registry-user.registry-db.credentials.postgresql.acid.zalan.do -n registry-test
   ```

3. **Test connection manually:**
   ```bash
   kubectl run -it --rm psql-test --image=postgres:15 --restart=Never -n registry-test -- bash
   # Inside the pod:
   psql "postgresql://registry-user:<password>@registry-db:5432/registry-user"
   ```

4. **Check backend startup logs in detail:**
   ```bash
   kubectl logs -n registry-test deployment/cc-registry-backend -f
   ```

## Related Documentation

- [DATABASE_REDIS_CONFIG.md](../DATABASE_REDIS_CONFIG.md) - General database and Redis configuration
- [CONFIG_UPDATE_SUMMARY.md](../CONFIG_UPDATE_SUMMARY.md) - Configuration update summary
- [Zalando Postgres Operator Documentation](https://postgres-operator.readthedocs.io/)
