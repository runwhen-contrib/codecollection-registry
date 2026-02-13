#!/bin/bash
# Script to check what environment variables a worker pod actually sees

echo "==================================================================="
echo "Checking environment variables in worker pod"
echo "==================================================================="

POD=$(kubectl get pod -n registry-test -l component=worker -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD" ]; then
    echo "❌ No worker pod found"
    exit 1
fi

echo "Using pod: $POD"
echo ""

echo "==================================================================="
echo "All REDIS-related environment variables:"
echo "==================================================================="
kubectl exec -n registry-test $POD -- env | grep -i redis | sort

echo ""
echo "==================================================================="
echo "Specific values:"
echo "==================================================================="
echo -n "REDIS_DB: "
kubectl exec -n registry-test $POD -- env | grep "^REDIS_DB=" || echo "NOT SET"

echo -n "REDIS_SENTINEL_MASTER: "
kubectl exec -n registry-test $POD -- env | grep "^REDIS_SENTINEL_MASTER=" || echo "NOT SET"

echo -n "REDIS_URL: "
kubectl exec -n registry-test $POD -- env | grep "^REDIS_URL=" || echo "NOT SET"

echo ""
echo "==================================================================="
echo "Python check - what does settings.REDIS_DB actually contain?"
echo "==================================================================="
kubectl exec -n registry-test $POD -- python3 -c "
import os
import sys
sys.path.insert(0, '/app')
from app.core.config import settings
print(f'settings.REDIS_DB = {repr(settings.REDIS_DB)} (type: {type(settings.REDIS_DB).__name__})')
print(f'settings.REDIS_SENTINEL_MASTER = {repr(settings.REDIS_SENTINEL_MASTER)}')
print(f'settings.REDIS_URL = {repr(settings.REDIS_URL)}')
"
