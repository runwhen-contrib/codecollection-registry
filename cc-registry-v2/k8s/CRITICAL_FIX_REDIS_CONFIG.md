# CRITICAL FIX: Redis Configuration Issue Causing Worker Failures

## Problem
Workers are crashing with: `invalid literal for int() with base 10: 'mymaster/0'`

## Root Cause
The `REDIS_DB` environment variable is being set incorrectly in Kubernetes. It's receiving the string `'mymaster/0'` instead of the integer `0`.

This happens when:
1. `REDIS_URL` is set as a sentinel URL: `sentinel://host:port/mymaster/0`
2. `REDIS_DB` is not explicitly set as a separate environment variable
3. Something is extracting the wrong part of the URL path

## Immediate Fix (Code)
✅ **ALREADY APPLIED** - Added error handling in `celery_app.py` to gracefully handle invalid REDIS_DB values and default to 0.

## Required Fix (Kubernetes Secret)
You need to **explicitly set REDIS_DB** in your Kubernetes secret `cc-registry-secrets`:

### If using Redis Sentinel:
```bash
kubectl create secret generic cc-registry-secrets \
  --namespace=registry-test \
  --from-literal=REDIS_SENTINEL_HOSTS="sentinel-host:26379" \
  --from-literal=REDIS_SENTINEL_MASTER="mymaster" \
  --from-literal=REDIS_DB="0" \
  --from-literal=REDIS_PASSWORD="your-password" \
  --from-literal=DATABASE_URL="postgresql://user:pass@host:5432/db" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### If using regular Redis:
```bash
kubectl create secret generic cc-registry-secrets \
  --namespace=registry-test \
  --from-literal=REDIS_URL="redis://redis:6379/0" \
  --from-literal=DATABASE_URL="postgresql://user:pass@host:5432/db" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Verify the Fix
After updating the secret and redeploying:

```bash
# Check that pods restart
kubectl rollout restart deployment/cc-registry-worker -n registry-test

# Watch for successful startup (no more 'mymaster/0' errors)
kubectl logs -f deployment/cc-registry-worker -n registry-test | grep -i redis
```

## Current Code Protection
The code now has safeguards (lines 36-40 in `celery_app.py`):
- Validates REDIS_DB is a proper integer
- Logs a warning if invalid
- Defaults to 0 if parsing fails
- Prevents the crash

## Other Errors (Secondary)
The logs also show:
```
Enhancement failed: Never call result.get() within a task!
```
This is a separate Celery anti-pattern issue in the workflow tasks that needs addressing separately.
