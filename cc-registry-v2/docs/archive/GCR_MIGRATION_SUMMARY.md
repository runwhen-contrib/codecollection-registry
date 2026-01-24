# GCR Migration Summary

This document summarizes the changes made to migrate from GitHub Container Registry (GHCR) to Google Container Registry (GCR/Artifact Registry).

## 🎯 Changes Made

### 1. Updated GitHub Actions Workflow
**File:** `.github/workflows/build-cc-registry-v2-images.yaml`

#### Key Changes:
- ✅ **GCP Authentication**: Uses Workload Identity Federation instead of GitHub token
- ✅ **Multi-Architecture Support**: Builds amd64 and arm64 separately, then creates manifests
- ✅ **Parallel Builds**: Three separate components (backend, frontend, worker)
- ✅ **Flexible Push**: Can build without pushing (for PRs) or push on demand
- ✅ **Custom Tagging**: Supports custom tags via workflow dispatch
- ✅ **Build Caching**: GitHub Actions cache for faster builds
- ✅ **Notifications**: Optional Slack notifications (commented out)

#### Workflow Triggers:
1. **Pull Requests** - Builds images when PRs modify `cc-registry-v2/**`
2. **Manual Dispatch** - Manually trigger with options:
   - Push images: yes/no
   - Custom tag
   - Multi-arch build: yes/no

#### Build Matrix:
```
Backend   → amd64 + arm64 (optional) → manifest
Frontend  → amd64 + arm64 (optional) → manifest
Worker    → amd64 + arm64 (optional) → manifest
```

### 2. New Documentation Files

#### `GCR_SETUP.md`
Complete guide for setting up Google Cloud Registry:
- GCP project creation
- Artifact Registry setup
- Workload Identity Federation configuration
- Service account creation and permissions
- GitHub secrets configuration
- Testing and troubleshooting
- Cost optimization
- Security best practices

#### Updated `k8s/CONTAINER_BUILD.md`
- Updated for GCR instead of GHCR
- Added multi-arch build documentation
- Updated authentication instructions
- Added GCR setup prerequisites

### 3. Environment Variables

The workflow now uses these environment variables:

```yaml
env:
  GCP_PROJECT_ID: runwhen-nonprod-shared  # ⚠️ Update with your project
  GCR_REGISTRY: us-docker.pkg.dev/runwhen-nonprod-shared/public-images  # ⚠️ Update
  IMAGE_PREFIX: cc-registry-v2
```

### 4. Required GitHub Secrets

Two new secrets required:

1. **GCP_WORKLOAD_IDENTITY_PROVIDER**
   - Format: `projects/PROJECT-NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
   - Used for: Workload Identity Federation authentication

2. **GCP_SERVICE_ACCOUNT**
   - Format: `github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com`
   - Used for: Service account impersonation

3. **SLACK_BOT_TOKEN** (Optional)
   - Used for: Slack notifications

## 🚀 Quick Start

### Prerequisites Checklist

- [ ] GCP project created
- [ ] Artifact Registry repository created
- [ ] Workload Identity Federation configured
- [ ] Service account created with permissions
- [ ] GitHub secrets configured
- [ ] Workflow file updated with your GCP project details

### Step-by-Step Setup

#### 1. Set Up GCP (5-10 minutes)

```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"

# Enable APIs
gcloud services enable artifactregistry.googleapis.com
gcloud services enable iamcredentials.googleapis.com

# Create Artifact Registry
gcloud artifacts repositories create public-images \
  --repository-format=docker \
  --location=us \
  --description="CC-Registry-V2 container images"

# Create service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

See [GCR_SETUP.md](GCR_SETUP.md) for complete instructions.

#### 2. Configure Workload Identity (5 minutes)

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Pool"

# Create provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Allow your repository
export GITHUB_REPO="your-org/your-repo"
gcloud iam service-accounts add-iam-policy-binding \
  "github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT-NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_REPO}"
```

#### 3. Configure GitHub Secrets (2 minutes)

Add these secrets in GitHub: **Settings → Secrets and variables → Actions**

1. `GCP_WORKLOAD_IDENTITY_PROVIDER`: Get with `gcloud` command (see GCR_SETUP.md)
2. `GCP_SERVICE_ACCOUNT`: `github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com`

#### 4. Update Workflow File (1 minute)

Edit `.github/workflows/build-cc-registry-v2-images.yaml`:

```yaml
env:
  GCP_PROJECT_ID: your-project-id  # Change this
  GCR_REGISTRY: us-docker.pkg.dev/your-project-id/public-images  # Change this
  IMAGE_PREFIX: cc-registry-v2
```

#### 5. Test the Workflow (5 minutes)

```bash
# Trigger manually via GitHub UI
# Go to: Actions → Build CC-Registry-V2 Container Images → Run workflow

# Or use GitHub CLI
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=test-v1 \
  -f build_multiarch=false
```

## 📊 Comparison: GHCR vs GCR

| Feature | GHCR (Old) | GCR (New) |
|---------|-----------|-----------|
| Authentication | GitHub Token | Workload Identity Federation |
| Registry URL | `ghcr.io/owner/repo/*` | `us-docker.pkg.dev/project/repo/*` |
| Multi-arch | Single job | Separate jobs per arch |
| Cost | Free (with limits) | Pay per storage/bandwidth |
| Security | GitHub managed | GCP IAM |
| Vulnerability Scanning | Basic | Advanced with Binary Authorization |
| Build Cache | GHA cache | GHA cache |
| ARM64 Support | Emulation | Native ARM runners |

## 🔄 Workflow Behavior

### On Pull Request
```
1. Scan repository (optional Trivy scan)
2. Generate tag: <branch>-<sha8>
3. Build amd64 images (backend, frontend, worker) - parallel
4. Images NOT pushed (build-only validation)
5. Post build summary to PR
```

### On Manual Dispatch with Push
```
1. Scan repository
2. Generate tag: custom or <branch>-<sha8>
3. Build amd64 images (parallel)
4. Build arm64 images (parallel, if enabled)
5. Authenticate to GCP
6. Push architecture-specific images
7. Create and push multi-arch manifests
8. Post summary
9. Send notifications (optional)
```

### Tag Format

**Single Architecture (amd64 only):**
```
backend:main-abc12345
backend:main-abc12345-amd64
```

**Multi Architecture:**
```
backend:main-abc12345          (manifest pointing to both)
backend:main-abc12345-amd64    (amd64 specific)
backend:main-abc12345-arm64    (arm64 specific)
```

## 🔐 Security Improvements

### Workload Identity Federation Benefits:
1. ✅ No long-lived credentials
2. ✅ Automatic token rotation
3. ✅ Fine-grained IAM permissions
4. ✅ Audit logs in Cloud Logging
5. ✅ Can restrict by repository/branch

### Additional Security Features:
- Optional Trivy vulnerability scanning
- Binary Authorization support
- Automatic image scanning in Artifact Registry
- IAM-based access control
- Audit logging for all operations

## 💡 Usage Examples

### Build and Push Single Architecture
```bash
# Via GitHub UI
Actions → Build CC-Registry-V2 Container Images → Run workflow
- Branch: main
- Push images: true
- Tag: v1.0.0
- Build multiarch: false
```

### Build and Push Multi-Architecture
```bash
# Via GitHub CLI
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v1.0.0 \
  -f build_multiarch=true
```

### Pull Images
```bash
# Authenticate
gcloud auth configure-docker us-docker.pkg.dev

# Pull images
docker pull us-docker.pkg.dev/your-project/public-images/cc-registry-v2-backend:v1.0.0
docker pull us-docker.pkg.dev/your-project/public-images/cc-registry-v2-frontend:v1.0.0
docker pull us-docker.pkg.dev/your-project/public-images/cc-registry-v2-worker:v1.0.0
```

### Use in Kubernetes
```yaml
# deployment.yaml
spec:
  containers:
  - name: backend
    image: us-docker.pkg.dev/your-project/public-images/cc-registry-v2-backend:v1.0.0
```

## 🐛 Common Issues & Solutions

### Issue: "Failed to authenticate"
**Solution:**
```bash
# Verify secrets are set correctly
gh secret list

# Test workload identity locally
gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool=github-pool
```

### Issue: "Permission denied pushing to registry"
**Solution:**
```bash
# Check service account permissions
gcloud projects get-iam-policy YOUR-PROJECT-ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions@*"

# Grant missing permissions
gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
  --member="serviceAccount:github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
```

### Issue: "ARM64 build failed"
**Solution:**
- ARM64 builds require `ubuntu-24.04-arm` runners
- These may not be available in all GitHub plans
- Set `build_multiarch: false` to skip ARM64 builds

## 📚 Next Steps

1. ✅ Review [GCR_SETUP.md](GCR_SETUP.md) for detailed setup
2. ✅ Configure GCP and GitHub secrets
3. ✅ Update workflow file with your project details
4. ✅ Test with a manual workflow run
5. ✅ Update Kubernetes manifests with new image URLs
6. ✅ Set up cost alerts and cleanup policies
7. ✅ Enable vulnerability scanning (optional)
8. ✅ Configure Slack notifications (optional)

## 🆘 Support Resources

- **GCP Setup**: [GCR_SETUP.md](GCR_SETUP.md)
- **Container Build**: [k8s/CONTAINER_BUILD.md](k8s/CONTAINER_BUILD.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **GCP Documentation**: https://cloud.google.com/artifact-registry/docs
- **Workload Identity**: https://cloud.google.com/iam/docs/workload-identity-federation

## ✅ Migration Checklist

- [ ] Read GCR_SETUP.md
- [ ] Create GCP project
- [ ] Enable required APIs
- [ ] Create Artifact Registry repository
- [ ] Set up Workload Identity Federation
- [ ] Create service account
- [ ] Grant IAM permissions
- [ ] Configure GitHub secrets
- [ ] Update workflow file
- [ ] Test manual workflow run
- [ ] Update Kubernetes manifests
- [ ] Update local development docs
- [ ] Test image pull locally
- [ ] Deploy to test cluster
- [ ] Set up cost monitoring
- [ ] Configure cleanup policies
- [ ] Enable vulnerability scanning (optional)
- [ ] Configure Slack notifications (optional)
