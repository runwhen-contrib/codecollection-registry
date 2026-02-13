#!/bin/bash
# Non-interactive check for Redis configuration

echo "==================================================================="
echo "Checking Redis configuration in worker pods"
echo "==================================================================="

# Get first worker pod
POD=$(kubectl get pod -n registry-test -l component=worker --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD" ]; then
    echo "❌ No running worker pod found"
    exit 1
fi

echo "Using pod: $POD"
echo ""

echo "==================================================================="
echo "Environment variables (REDIS):"
echo "==================================================================="
kubectl exec -n registry-test $POD -- sh -c 'env | grep -i redis' 2>/dev/null | sort || echo "Failed to get env vars"

echo ""
echo "==================================================================="
echo "Check what Python sees:"
echo "==================================================================="
kubectl exec -n registry-test $POD -- python3 -c '
import os
import sys
sys.path.insert(0, "/app")

print("Environment REDIS_DB:", repr(os.environ.get("REDIS_DB", "NOT_SET")))
print("Environment REDIS_SENTINEL_MASTER:", repr(os.environ.get("REDIS_SENTINEL_MASTER", "NOT_SET")))
print("Environment REDIS_SENTINEL_HOSTS:", repr(os.environ.get("REDIS_SENTINEL_HOSTS", "NOT_SET")))

try:
    from app.core.config import settings
    print("\nParsed settings.REDIS_DB:", repr(settings.REDIS_DB), "Type:", type(settings.REDIS_DB).__name__)
    print("Parsed settings.REDIS_URL:", repr(settings.REDIS_URL)[:80] + "...")
except Exception as e:
    print("Error loading settings:", e)
' 2>&1

echo ""
echo "==================================================================="
echo "Check recent worker logs for Redis errors:"
echo "==================================================================="
kubectl logs -n registry-test deployment/cc-registry-worker --tail=50 | grep -i -E "redis|mymaster|invalid literal" || echo "No Redis errors in recent logs"
