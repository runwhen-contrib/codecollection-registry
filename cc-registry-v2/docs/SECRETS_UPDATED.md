# ✅ Secrets Updated - Embedding Credentials Added

The Kubernetes secrets example has been updated to include **Azure OpenAI embedding credentials** for the MCP server.

## 🎯 What Changed

### Updated File
**`cc-registry-v2/k8s/secrets-example.yaml`**

### Added Credentials

#### 1. **Embedding Credentials** (for MCP Server)
```yaml
# Azure OpenAI for Embeddings (used by MCP server semantic search)
AZURE_OPENAI_EMBEDDING_API_KEY: "your-embedding-api-key-here"
AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://your-embedding-resource.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_VERSION: "2024-02-15-preview"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-small"
```

#### 2. **GitHub Token** (for MCP Server - Optional)
```yaml
# GitHub Token (for MCP server GitHub issue creation - optional)
GITHUB_TOKEN: "ghp_your_github_token_here"
```

#### 3. **Alternative Deployment Name**
```yaml
AZURE_OPENAI_DEPLOYMENT: "gpt-4"  # Alternative name used by some services
```

### Added Documentation

**New header comments explaining:**
- GPT/Chat credentials vs Embedding credentials
- Same resource vs separate resources
- Fallback behavior when credentials missing

## 📚 New Documentation Created

### `AZURE_OPENAI_SETUP.md`
Complete guide covering:
- Two types of credentials (GPT vs Embeddings)
- Setup scenarios (same resource, separate resources, local embeddings)
- Creating Azure OpenAI resources
- Cost optimization
- Testing and troubleshooting

## 🔑 Two Types of Credentials Explained

### 1. GPT/Chat Credentials
**Used by:** cc-registry-v2 backend  
**Purpose:** AI enhancement features  
**Model:** GPT-4, GPT-4-turbo, GPT-3.5-turbo  
**Cost:** ~$0.03-0.06 per 1K tokens  

**Environment Variables:**
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_VERSION`

### 2. Embedding Credentials
**Used by:** MCP server  
**Purpose:** Semantic search, vector embeddings  
**Model:** text-embedding-3-small, text-embedding-3-large  
**Cost:** ~$0.0001 per 1K tokens (much cheaper!)  

**Environment Variables:**
- `AZURE_OPENAI_EMBEDDING_ENDPOINT`
- `AZURE_OPENAI_EMBEDDING_API_KEY`
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`
- `AZURE_OPENAI_EMBEDDING_API_VERSION`

## 🏗️ Common Configurations

### Option 1: Same Azure OpenAI Resource (Simplest)
```yaml
# Same endpoint and key, different deployments
AZURE_OPENAI_ENDPOINT: "https://my-openai.openai.azure.com/"
AZURE_OPENAI_API_KEY: "same-key"
AZURE_OPENAI_DEPLOYMENT: "gpt-4"

AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://my-openai.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_KEY: "same-key"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "embeddings"
```

### Option 2: Separate Resources (Production)
```yaml
# Different resources for better quota management
AZURE_OPENAI_ENDPOINT: "https://openai-gpt.openai.azure.com/"
AZURE_OPENAI_API_KEY: "key-for-gpt"
AZURE_OPENAI_DEPLOYMENT: "gpt-4"

AZURE_OPENAI_EMBEDDING_ENDPOINT: "https://openai-embeddings.openai.azure.com/"
AZURE_OPENAI_EMBEDDING_API_KEY: "key-for-embeddings"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-small"
```

### Option 3: Local Embeddings (Free)
```yaml
# Only GPT credentials, MCP server uses local embeddings
AZURE_OPENAI_ENDPOINT: "https://my-openai.openai.azure.com/"
AZURE_OPENAI_API_KEY: "key-for-gpt"
AZURE_OPENAI_DEPLOYMENT: "gpt-4"

# No embedding credentials = automatic fallback to local embeddings
```

## 🚀 How to Use

### Step 1: Update Secrets File

Copy and edit:
```bash
cd cc-registry-v2/k8s
cp secrets-example.yaml secrets.yaml
# Edit secrets.yaml with your actual credentials
```

### Step 2: Apply to Cluster

```bash
kubectl apply -f secrets.yaml
```

### Step 3: Verify

```bash
# Check secret exists
kubectl get secret azure-openai-credentials -n codecollection-registry

# Check backend has env vars
kubectl exec deployment/cc-registry-backend -n codecollection-registry -- \
  env | grep AZURE_OPENAI

# Check MCP server has env vars
kubectl exec deployment/mcp-server -n codecollection-registry -- \
  env | grep AZURE_OPENAI
```

### Step 4: Test

```bash
# Test semantic search (uses embeddings)
kubectl port-forward svc/mcp-server 8000:8000 -n codecollection-registry
curl "http://localhost:8000/api/codebundles/search?query=kubernetes"

# Check logs for embedding provider
kubectl logs deployment/mcp-server -n codecollection-registry | grep -i embedding
# Should show: "Embedding provider: azure" or "Embedding provider: local"
```

## 🔍 What Each Service Uses

| Service | GPT/Chat | Embeddings | Purpose |
|---------|----------|------------|---------|
| **Backend** | ✅ Yes | ❌ No | AI enhancement, descriptions |
| **MCP Server** | ❌ No | ✅ Yes | Semantic search |
| **Frontend** | ❌ No | ❌ No | UI only |
| **Worker** | ✅ Yes | ❌ No | Background AI tasks |

## 💰 Cost Implications

### Typical Usage (per 1000 queries)

**GPT-4 (Backend):**
- 1000 queries × 500 tokens avg = 500K tokens
- Cost: ~$15-30

**Embeddings (MCP Server):**
- 1000 queries × 100 tokens avg = 100K tokens
- Cost: ~$0.01

**Takeaway:** Embeddings are **~1000x cheaper** than GPT-4!

### Cost Optimization

1. **Use separate resources** - Better quota management
2. **Use text-embedding-3-small** - Cheaper than 3-large, still good quality
3. **Cache embeddings** - MCP server caches in vector store
4. **Use local embeddings for dev** - Free but slower

## 🐛 Troubleshooting

### MCP Server Uses Local Embeddings

**Symptom:** Logs show "Embedding provider: local"

**Cause:** Azure OpenAI embedding credentials not found

**Solutions:**
1. Check secret has `AZURE_OPENAI_EMBEDDING_*` variables
2. Verify MCP server deployment mounts the secret
3. Check for typos in environment variable names

**Note:** This is OK for development! Local embeddings work fine, just slower.

### Backend Can't Use GPT

**Symptom:** AI enhancement fails

**Cause:** GPT credentials missing or incorrect

**Solutions:**
1. Check secret has `AZURE_OPENAI_*` (main) variables
2. Verify backend deployment mounts the secret
3. Test credentials manually with Azure CLI

### "Invalid deployment name"

**Symptom:** API errors about deployment not found

**Cause:** Deployment name doesn't match Azure

**Solutions:**
1. Check deployment exists in Azure Portal
2. Verify exact name (case-sensitive)
3. Use `az cognitiveservices account deployment list` to see deployments

## 📚 Related Documentation

- **[AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md)** - Complete Azure OpenAI setup guide
- **[MCP_SERVER_INTEGRATION.md](MCP_SERVER_INTEGRATION.md)** - MCP server integration
- **[k8s/secrets-example.yaml](k8s/secrets-example.yaml)** - Updated secrets template
- **[mcp-server/env.example](../mcp-server/env.example)** - MCP server env template

## ✅ Summary

- ✅ Secrets example updated with embedding credentials
- ✅ Comprehensive Azure OpenAI setup guide created
- ✅ Documentation explains GPT vs Embeddings
- ✅ Multiple configuration scenarios covered
- ✅ Cost optimization tips included
- ✅ Troubleshooting guide provided

**You're all set!** The secrets now include everything needed for both AI enhancement (GPT) and semantic search (embeddings). 🎉
