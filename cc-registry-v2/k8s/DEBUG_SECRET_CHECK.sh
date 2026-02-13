#!/bin/bash
# Debug script to check for conflicting environment variables

echo "==================================================================="
echo "Checking azure-openai-credentials secret for Redis config"
echo "==================================================================="

# Decode and display the secret keys (not values for security)
echo ""
echo "Keys in azure-openai-credentials secret:"
kubectl get secret azure-openai-credentials -n registry-test -o json | jq -r '.data | keys[]' 2>/dev/null || echo "❌ Secret not found or jq not available"

echo ""
echo "==================================================================="
echo "Checking for REDIS-related keys:"
echo "==================================================================="
kubectl get secret azure-openai-credentials -n registry-test -o json | jq -r '.data | keys[] | select(. | test("REDIS"; "i"))' 2>/dev/null || echo "No REDIS keys found (or error)"

echo ""
echo "==================================================================="
echo "To see the actual value of REDIS_DB (if it exists):"
echo "==================================================================="
echo "kubectl get secret azure-openai-credentials -n registry-test -o json | jq -r '.data.REDIS_DB // \"NOT_FOUND\"' | base64 -d"

echo ""
echo "==================================================================="
echo "To see the actual value of REDIS_URL (if it exists):"
echo "==================================================================="
echo "kubectl get secret azure-openai-credentials -n registry-test -o json | jq -r '.data.REDIS_URL // \"NOT_FOUND\"' | base64 -d"

echo ""
echo "==================================================================="
echo "All keys in the secret:"
echo "==================================================================="
kubectl get secret azure-openai-credentials -n registry-test -o json | jq -r '.data | to_entries[] | .key' 2>/dev/null | sort
