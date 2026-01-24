# Database and Redis Configuration Guide

## Overview

The cc-registry-v2 application supports flexible configuration for both database and Redis connections to accommodate different deployment scenarios:

- **Database**: Standalone PostgreSQL or managed database services (Azure Database, AWS RDS, etc.)
- **Redis**: Standalone Redis or Redis Sentinel for high availability

## Configuration Options

### Database Configuration

You can configure the database connection in two ways:

#### Option 1: Complete DATABASE_URL (Simple)

Provide a complete PostgreSQL connection string:

```yaml
stringData:
  DATABASE_URL: "postgresql://user:password@hostname:5432/dbname"
```

**Use this when:**
- Using a standalone PostgreSQL instance
- Connection string is readily available
- Simple deployment scenarios

#### Option 2: Individual Components (Recommended)

Provide individual database parameters:

```yaml
stringData:
  DB_HOST: "your-postgres-host.database.azure.com"
  DB_PORT: "5432"
  DB_USER: "postgres@your-server"
  DB_PASSWORD: "your-secure-password"
  DB_NAME: "codecollection_registry"
```

The application automatically constructs the `DATABASE_URL` from these components.

**Use this when:**
- Using managed database services (Azure Database for PostgreSQL, AWS RDS, etc.)
- Parameters are managed separately (e.g., via Azure Key Vault, AWS Secrets Manager)
- Need flexibility to change individual components without rebuilding connection strings

**Azure Database for PostgreSQL Example:**
```yaml
stringData:
  DB_HOST: "myserver.postgres.database.azure.com"
  DB_PORT: "5432"
  DB_USER: "myadmin@myserver"
  DB_PASSWORD: "SecureP@ssw0rd!"
  DB_NAME: "codecollection_registry"
```

### Redis Configuration

You can configure Redis in two ways:

#### Option 1: Standalone Redis (Simple)

Provide a complete Redis connection string:

```yaml
stringData:
  REDIS_URL: "redis://redis:6379/0"
  # Or with authentication:
  # REDIS_URL: "redis://:password@redis:6379/0"
```

**Use this when:**
- Using a single Redis instance
- Development or testing environments
- Low availability requirements acceptable

#### Option 2: Redis Sentinel (Recommended for Production)

Provide Redis Sentinel configuration for high availability:

```yaml
stringData:
  REDIS_SENTINEL_HOSTS: "sentinel-1:26379,sentinel-2:26379,sentinel-3:26379"
  REDIS_SENTINEL_MASTER: "mymaster"
  REDIS_PASSWORD: "your-redis-password"  # Optional
  REDIS_DB: "0"
```

The application automatically configures Celery and other components to use Redis Sentinel.

**Use this when:**
- Production deployments requiring high availability
- Using Redis Sentinel for automatic failover
- Need resilience against Redis master failures

**Kubernetes Redis Sentinel Example:**
```yaml
stringData:
  REDIS_SENTINEL_HOSTS: "redis-sentinel-0.redis-sentinel:26379,redis-sentinel-1.redis-sentinel:26379,redis-sentinel-2.redis-sentinel:26379"
  REDIS_SENTINEL_MASTER: "mymaster"
  REDIS_PASSWORD: "SuperSecretPassword"
  REDIS_DB: "0"
```

## How It Works

### Backend Configuration Logic

The `app/core/config.py` file implements smart configuration resolution:

1. **Database URL Construction:**
   - If `DATABASE_URL` is provided, use it directly
   - Otherwise, if all components (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) are provided:
     - Construct: `postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}`
   - Falls back to development default if neither is provided

2. **Redis URL Construction:**
   - If `REDIS_URL` is provided, use it directly
   - Otherwise, if `REDIS_SENTINEL_HOSTS` is provided:
     - Construct Sentinel URL: `sentinel://[:password@]hosts/master_name/db_number`
     - Configure transport options for Celery
   - Falls back to development default if neither is provided

### Celery Configuration

The `app/tasks/celery_app.py` file handles Redis Sentinel specially:

- **Standalone Redis**: Uses standard `redis://` URL
- **Redis Sentinel**: 
  - Converts hosts to semicolon-separated format
  - Configures `broker_transport_options` with Sentinel parameters
  - Sets master name and connection timeouts
  - Enables socket keepalive for reliability

## Kubernetes Deployment

### Using Secrets

The deployment manifests use `envFrom` to load all environment variables from secrets:

```yaml
envFrom:
- secretRef:
    name: cc-registry-secrets
- secretRef:
    name: azure-openai-credentials
```

This allows the application to receive either:
- Direct URLs (`DATABASE_URL`, `REDIS_URL`)
- Component variables (`DB_HOST`, `DB_USER`, etc. or `REDIS_SENTINEL_HOSTS`, etc.)

### Example Secret Configuration

See `cc-registry-v2/k8s/secrets-example.yaml` for complete examples.

**Production Setup (Azure + Sentinel):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cc-registry-secrets
  namespace: codecollection-registry
type: Opaque
stringData:
  # Database - individual components for Azure Database
  DB_HOST: "myserver.postgres.database.azure.com"
  DB_PORT: "5432"
  DB_USER: "ccregistry@myserver"
  DB_PASSWORD: "MySecurePassword123!"
  DB_NAME: "codecollection_registry"
  
  # Redis - Sentinel configuration for HA
  REDIS_SENTINEL_HOSTS: "redis-sentinel-0.redis-sentinel:26379,redis-sentinel-1.redis-sentinel:26379,redis-sentinel-2.redis-sentinel:26379"
  REDIS_SENTINEL_MASTER: "mymaster"
  REDIS_PASSWORD: "RedisSecurePassword"
  REDIS_DB: "0"
```

**Development Setup (Standalone):**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cc-registry-secrets
  namespace: codecollection-registry
type: Opaque
stringData:
  # Database - simple URL for standalone PostgreSQL
  DATABASE_URL: "postgresql://postgres:devpassword@postgres:5432/codecollection_registry"
  
  # Redis - simple URL for standalone Redis
  REDIS_URL: "redis://redis:6379/0"
```

## Migration Guide

### From Simple URLs to Components

If you're currently using `DATABASE_URL` or `REDIS_URL` and want to migrate to component-based configuration:

1. **Identify your current connection parameters:**
   ```bash
   # Current DATABASE_URL: postgresql://user:pass@host:5432/dbname
   # Becomes:
   DB_HOST=host
   DB_PORT=5432
   DB_USER=user
   DB_PASSWORD=pass
   DB_NAME=dbname
   ```

2. **Update your Kubernetes secret:**
   ```bash
   kubectl create secret generic cc-registry-secrets \
     --from-literal=DB_HOST=your-host \
     --from-literal=DB_PORT=5432 \
     --from-literal=DB_USER=your-user \
     --from-literal=DB_PASSWORD=your-password \
     --from-literal=DB_NAME=codecollection_registry \
     -n codecollection-registry \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. **Restart the deployments:**
   ```bash
   kubectl rollout restart deployment/cc-registry-backend -n codecollection-registry
   kubectl rollout restart deployment/cc-registry-worker -n codecollection-registry
   kubectl rollout restart deployment/cc-registry-scheduler -n codecollection-registry
   ```

### From Standalone Redis to Sentinel

1. **Deploy Redis Sentinel** (if not already deployed)

2. **Update secret with Sentinel configuration:**
   ```bash
   kubectl create secret generic cc-registry-secrets \
     --from-literal=REDIS_SENTINEL_HOSTS=sentinel-1:26379,sentinel-2:26379,sentinel-3:26379 \
     --from-literal=REDIS_SENTINEL_MASTER=mymaster \
     --from-literal=REDIS_PASSWORD=your-password \
     --from-literal=REDIS_DB=0 \
     -n codecollection-registry \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. **Restart all Redis-dependent deployments:**
   ```bash
   kubectl rollout restart deployment/cc-registry-backend -n codecollection-registry
   kubectl rollout restart deployment/cc-registry-worker -n codecollection-registry
   kubectl rollout restart deployment/cc-registry-scheduler -n codecollection-registry
   kubectl rollout restart deployment/cc-registry-flower -n codecollection-registry
   ```

4. **Verify Sentinel connectivity:**
   ```bash
   # Check backend logs
   kubectl logs -n codecollection-registry deployment/cc-registry-backend | grep -i sentinel
   
   # Check worker logs
   kubectl logs -n codecollection-registry deployment/cc-registry-worker | grep -i celery
   ```

## Testing

### Verify Database Connection

```bash
# Port forward to backend
kubectl port-forward -n codecollection-registry svc/cc-registry-backend 8001:8001

# Check health endpoint
curl http://localhost:8001/api/v1/health

# Should return:
{
  "status": "healthy",
  "database": "connected",
  "environment": "production",
  "version": "1.0.0"
}
```

### Verify Redis/Celery Connection

```bash
# Check worker logs for successful connection
kubectl logs -n codecollection-registry deployment/cc-registry-worker --tail=50

# Should see:
# [INFO] Connected to sentinel://...
# [INFO] mingle: searching for neighbors
# [INFO] mingle: all alone
# [INFO] celery@worker ready.

# Check Flower UI
kubectl port-forward -n codecollection-registry svc/cc-registry-flower 5555:5555
# Open http://localhost:5555 in browser
```

### Test Task Execution

```bash
# Trigger a test task via the API
curl -X POST http://localhost:8001/api/v1/admin/tasks/sync \
  -H "Authorization: Bearer YOUR_TOKEN"

# Monitor task in Flower or check logs
kubectl logs -n codecollection-registry deployment/cc-registry-worker -f
```

## Troubleshooting

### Database Connection Issues

**Symptom:** Backend health check shows "disconnected"

**Solutions:**
1. Verify all DB_ environment variables are set:
   ```bash
   kubectl exec -n codecollection-registry deployment/cc-registry-backend -- env | grep DB_
   ```

2. Check if DATABASE_URL is correctly constructed:
   ```bash
   kubectl exec -n codecollection-registry deployment/cc-registry-backend -- env | grep DATABASE_URL
   ```

3. Test connectivity from pod to database:
   ```bash
   kubectl exec -n codecollection-registry deployment/cc-registry-backend -- \
     psql "$DATABASE_URL" -c "SELECT 1"
   ```

### Redis Sentinel Connection Issues

**Symptom:** Workers not connecting or Celery errors in logs

**Solutions:**
1. Verify Sentinel environment variables:
   ```bash
   kubectl exec -n codecollection-registry deployment/cc-registry-worker -- \
     env | grep REDIS_
   ```

2. Test Sentinel connectivity:
   ```bash
   kubectl exec -n codecollection-registry deployment/cc-registry-worker -- \
     redis-cli -h redis-sentinel-0.redis-sentinel -p 26379 SENTINEL masters
   ```

3. Check if master is reachable:
   ```bash
   # Get master address from Sentinel
   kubectl exec -n codecollection-registry deployment/cc-registry-worker -- \
     redis-cli -h redis-sentinel-0.redis-sentinel -p 26379 \
     SENTINEL get-master-addr-by-name mymaster
   ```

### Mixed Configuration Issues

**Symptom:** Application not picking up component-based config

**Cause:** Both URL and components provided, URL takes precedence

**Solution:** Remove the URL variable to force component-based construction:
```bash
kubectl create secret generic cc-registry-secrets \
  --from-literal=DB_HOST=... \
  --from-literal=DB_USER=... \
  # Don't include DATABASE_URL
  --dry-run=client -o yaml | kubectl apply -f -
```

## Security Best Practices

1. **Never commit secrets to git** - Use placeholder values in examples

2. **Use external secret management:**
   - Azure Key Vault with Secrets Store CSI Driver
   - AWS Secrets Manager with External Secrets Operator
   - HashiCorp Vault
   - Sealed Secrets

3. **Rotate credentials regularly:**
   ```bash
   # Update secret
   kubectl create secret generic cc-registry-secrets \
     --from-literal=DB_PASSWORD=new-password \
     --dry-run=client -o yaml | kubectl apply -f -
   
   # Trigger rolling update
   kubectl rollout restart deployment/cc-registry-backend -n codecollection-registry
   ```

4. **Use RBAC to restrict secret access:**
   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: secret-reader
     namespace: codecollection-registry
   rules:
   - apiGroups: [""]
     resources: ["secrets"]
     resourceNames: ["cc-registry-secrets", "azure-openai-credentials"]
     verbs: ["get"]
   ```

## Related Documentation

- `cc-registry-v2/k8s/secrets-example.yaml` - Example secret configurations
- `cc-registry-v2/backend/app/core/config.py` - Configuration implementation
- `cc-registry-v2/backend/app/tasks/celery_app.py` - Celery Redis Sentinel setup
- `cc-registry-v2/AZURE_OPENAI_SETUP.md` - Azure OpenAI configuration
