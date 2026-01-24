# Azure OpenAI Setup Guide

This guide explains the Azure OpenAI configuration needed for cc-registry-v2 and the MCP server.

## 🎯 Two Types of Azure OpenAI Credentials

Your deployment needs **two types** of Azure OpenAI credentials:

### 1. **GPT/Chat Credentials** (for AI Enhancement)
**Used by:** cc-registry-v2 backend  
**Purpose:** AI-powered features like codebundle enhancement, descriptions, summaries  
**Model:** GPT-4, GPT-4-turbo, or GPT-3.5-turbo  

**Environment Variables:**
```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

### 2. **Embedding Credentials** (for Semantic Search)
**Used by:** MCP server  
**Purpose:** Vector embeddings for semantic search of codebundles, libraries, documentation  
**Model:** text-embedding-3-small, text-embedding-3-large, or text-embedding-ada-002  

**Environment Variables:**
```bash
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://your-embedding-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDING_API_KEY=your-embedding-api-key
AZURE_OPENAI_EMBEDDING_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
```

## 🏗️ Setup Scenarios

### Scenario 1: Same Azure OpenAI Resource (Recommended for Testing)

If you have **one Azure OpenAI resource** with multiple deployments:

**Azure OpenAI Resource:** `my-openai-resource`
- **Deployment 1:** `gpt-4` (for chat)
- **Deployment 2:** `embeddings` (for embeddings)

**Configuration:**
```yaml
# Same endpoint and key, different deployments
AZURE_OPENAI_ENDPOINT: "https://my-openai-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY: "same-key-for-both"
AZURE_OPENAI_DEPLOYMENT: "gpt-4"

AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://my-openai-resource.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_KEY: "same-key-for-both"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "embeddings"
```

### Scenario 2: Separate Azure OpenAI Resources (Recommended for Production)

If you have **separate Azure OpenAI resources** (e.g., different regions, quotas, or billing):

**Resource 1:** `openai-gpt` (for chat)
**Resource 2:** `openai-embeddings` (for embeddings)

**Configuration:**
```yaml
# Different endpoints and keys
AZURE_OPENAI_ENDPOINT: "https://openai-gpt.openai.azure.com/"
AZURE_OPENAI_API_KEY: "key-for-gpt"
AZURE_OPENAI_DEPLOYMENT: "gpt-4"

AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://openai-embeddings.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_KEY: "key-for-embeddings"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-small"
```

### Scenario 3: Embeddings Only (No GPT Features)

If you only want semantic search without AI enhancement:

**Configuration:**
```yaml
# Only embedding credentials needed
AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://openai-embeddings.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_KEY: "key-for-embeddings"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-small"

# Optional: Disable AI enhancement in backend
AI_ENHANCEMENT_ENABLED: "false"
```

### Scenario 4: Local Embeddings (No Azure Costs)

For development/testing without Azure OpenAI costs:

**Configuration:**
```yaml
# No embedding credentials - MCP server will use local sentence-transformers
# (automatically detects missing credentials)

# Still need GPT for AI enhancement (or disable it)
AI_ENHANCEMENT_ENABLED: "false"
```

**Note:** Local embeddings use the `sentence-transformers` library with CPU inference.

## 📦 Creating Azure OpenAI Resources

### Step 1: Create Azure OpenAI Resource

```bash
# Using Azure CLI
az cognitiveservices account create \
  --name my-openai-resource \
  --resource-group my-rg \
  --kind OpenAI \
  --sku S0 \
  --location eastus
```

Or via [Azure Portal](https://portal.azure.com) → Create Resource → Azure OpenAI

### Step 2: Create Deployments

**For GPT-4:**
```bash
az cognitiveservices account deployment create \
  --name my-openai-resource \
  --resource-group my-rg \
  --deployment-name gpt-4 \
  --model-name gpt-4 \
  --model-version "0613" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --capacity 10
```

**For Embeddings:**
```bash
az cognitiveservices account deployment create \
  --name my-openai-resource \
  --resource-group my-rg \
  --deployment-name embeddings \
  --model-name text-embedding-3-small \
  --model-version "1" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --capacity 10
```

### Step 3: Get API Keys

```bash
# Get endpoint
az cognitiveservices account show \
  --name my-openai-resource \
  --resource-group my-rg \
  --query "properties.endpoint" -o tsv

# Get API key
az cognitiveservices account keys list \
  --name my-openai-resource \
  --resource-group my-rg \
  --query "key1" -o tsv
```

## 🔐 Kubernetes Secrets

Update `k8s/secrets-example.yaml` with your credentials:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: azure-openai-credentials
  namespace: codecollection-registry
type: Opaque
stringData:
  # GPT/Chat
  AZURE_OPENAI_API_KEY: "abc123..."
  AZURE_OPENAI_ENDPOINT: "https://my-gpt.openai.azure.com/"
  AZURE_OPENAI_API_VERSION: "2024-02-15-preview"
  AZURE_OPENAI_DEPLOYMENT_NAME: "gpt-4"
  AZURE_OPENAI_DEPLOYMENT: "gpt-4"
  
  # Embeddings
  AZURE_OPENAI_EMBEDDING_API_KEY: "xyz789..."
  AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://my-embeddings.openai.azure.com/"
  AZURE_OPENAI_EMBEDDING_API_VERSION: "2024-02-15-preview"
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-small"
```

Then apply:
```bash
kubectl apply -f k8s/secrets-example.yaml
```

## 💰 Cost Optimization

### Use Different Tiers

- **GPT-4:** For important AI features (more expensive)
- **GPT-3.5-turbo:** For less critical features (cheaper)
- **Embeddings:** Much cheaper than GPT-4 (1/100th the cost)

### Rate Limits

Set appropriate capacity (TPM - Tokens Per Minute):
- **GPT-4:** 10-30K TPM for low-medium traffic
- **Embeddings:** 50-100K TPM (used more frequently)

### Local Embeddings

For development, use local embeddings to avoid costs:
- Automatically used if Azure credentials not provided
- Uses `sentence-transformers` library
- Slower but free

## 🧪 Testing Your Setup

### Test GPT/Chat

```bash
# Port-forward backend
kubectl port-forward svc/cc-registry-backend 8001:8001 -n codecollection-registry

# Test AI enhancement
curl -X POST http://localhost:8001/api/v1/codebundles/enhance \
  -H "Content-Type: application/json" \
  -d '{"slug": "some-codebundle"}'
```

### Test Embeddings/Semantic Search

```bash
# Port-forward MCP server
kubectl port-forward svc/mcp-server 8000:8000 -n codecollection-registry

# Test semantic search
curl "http://localhost:8000/api/codebundles/search?query=kubernetes+troubleshooting"
```

### Check Logs

```bash
# Backend logs (GPT usage)
kubectl logs -f deployment/cc-registry-backend -n codecollection-registry | grep -i azure

# MCP server logs (Embeddings usage)
kubectl logs -f deployment/mcp-server -n codecollection-registry | grep -i embedding
```

## 🐛 Troubleshooting

### "Azure OpenAI not configured"

**Check secrets are loaded:**
```bash
kubectl get secret azure-openai-credentials -n codecollection-registry -o yaml
```

**Check pods have env vars:**
```bash
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- env | grep AZURE_OPENAI
kubectl exec deployment/mcp-server -n codecollection-registry -- env | grep AZURE_OPENAI
```

### "Invalid API key"

- Verify key is correct (no extra spaces)
- Check key hasn't expired
- Verify key is for the correct resource

### "Rate limit exceeded"

- Increase TPM capacity in Azure Portal
- Use separate resources for embeddings (different quota)
- Implement retry logic with exponential backoff

### "Model not found"

- Verify deployment name matches exactly
- Check deployment is created in Azure Portal
- Use correct API version

### MCP Server Falls Back to Local Embeddings

**This is OK!** If embedding credentials aren't provided, MCP server automatically uses local embeddings.

**To verify:**
```bash
kubectl logs deployment/mcp-server -n codecollection-registry | head -20
# Look for: "Embedding provider: local" or "Embedding provider: azure"
```

## 📚 Recommended Models

### For GPT/Chat
- **GPT-4** (best quality, most expensive)
- **GPT-4-turbo** (faster, cheaper than GPT-4)
- **GPT-3.5-turbo** (cheapest, good for simple tasks)

### For Embeddings
- **text-embedding-3-small** (recommended, 1536 dims, good quality/cost)
- **text-embedding-3-large** (best quality, 3072 dims, more expensive)
- **text-embedding-ada-002** (older, 1536 dims, still good)

## 🔗 Additional Resources

- [Azure OpenAI Docs](https://learn.microsoft.com/azure/ai-services/openai/)
- [Model Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/)
- [Embedding Models](https://platform.openai.com/docs/guides/embeddings)
- [Rate Limits](https://learn.microsoft.com/azure/ai-services/openai/quotas-limits)

## ✅ Quick Checklist

- [ ] Azure OpenAI resource created
- [ ] GPT-4 deployment created
- [ ] Embedding deployment created
- [ ] API keys retrieved
- [ ] Secrets updated in `k8s/secrets-example.yaml`
- [ ] Secrets applied to cluster
- [ ] Backend deployment has secrets mounted
- [ ] MCP server deployment has secrets mounted
- [ ] Test GPT features work
- [ ] Test semantic search works
- [ ] Check logs for errors
