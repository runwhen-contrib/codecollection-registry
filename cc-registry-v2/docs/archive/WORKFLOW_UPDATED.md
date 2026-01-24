# ✅ Workflow Updated for Google Container Registry

The GitHub Actions workflow has been successfully updated to push to Google Container Registry (GCR) instead of GitHub Container Registry (GHCR).

## 🎯 What Changed

### Main Workflow File
**`.github/workflows/build-cc-registry-v2-images.yaml`**

The workflow now:
- ✅ Uses **Google Cloud Workload Identity Federation** for authentication (no stored credentials!)
- ✅ Pushes to **GCR/Artifact Registry** (`us-docker.pkg.dev`)
- ✅ Supports **multi-architecture builds** (amd64 + arm64)
- ✅ Builds three components in parallel (backend, frontend, worker)
- ✅ Creates multi-arch manifests combining amd64 and arm64 variants
- ✅ Includes PR validation (builds without pushing)
- ✅ Supports manual dispatch with custom options
- ✅ Has optional Slack notifications

### Workflow Structure
```
11 Jobs Total:

1. scan-repo              → Security scanning (optional Trivy)
2. generate-tag           → Generate version tag
3. build-backend-amd64    → Build backend for amd64
4. build-backend-arm64    → Build backend for arm64 (optional)
5. build-frontend-amd64   → Build frontend for amd64
6. build-frontend-arm64   → Build frontend for arm64 (optional)
7. build-worker-amd64     → Build worker for amd64
8. build-worker-arm64     → Build worker for arm64 (optional)
9. publish-manifests      → Create multi-arch manifests
10. summary               → Generate build summary
11. notify                → Send notifications (optional)
```

### Triggers
- **Pull Requests**: Auto-builds when PR modifies `cc-registry-v2/**`
- **Manual Dispatch**: Trigger from GitHub UI with options

### Registry Configuration
```yaml
Current Settings (Update these!):
  GCP_PROJECT_ID: runwhen-nonprod-shared
  GCR_REGISTRY: us-docker.pkg.dev/runwhen-nonprod-shared/public-images
  IMAGE_PREFIX: cc-registry-v2
```

## 📝 Required GitHub Secrets

Add these in **Settings → Secrets and variables → Actions**:

1. **GCP_WORKLOAD_IDENTITY_PROVIDER**
   - Full workload identity provider path
   - Format: `projects/PROJECT-NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`

2. **GCP_SERVICE_ACCOUNT**
   - Service account email
   - Format: `github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com`

3. **SLACK_BOT_TOKEN** (Optional)
   - For Slack notifications
   - Only needed if enabling Slack integration

## 🚀 Quick Setup

### 1. Update Workflow File

Edit `.github/workflows/build-cc-registry-v2-images.yaml`:

```yaml
env:
  GCP_PROJECT_ID: your-project-id  # ⚠️ CHANGE THIS
  GCR_REGISTRY: us-docker.pkg.dev/your-project-id/public-images  # ⚠️ CHANGE THIS
  IMAGE_PREFIX: cc-registry-v2
```

### 2. Set Up GCP

Follow the complete guide in **[GCR_SETUP.md](GCR_SETUP.md)**

Quick commands:
```bash
# Set your project
export GCP_PROJECT_ID="your-project-id"

# Enable APIs
gcloud services enable artifactregistry.googleapis.com
gcloud services enable iamcredentials.googleapis.com

# Create repository
gcloud artifacts repositories create public-images \
  --repository-format=docker \
  --location=us

# Create service account
gcloud iam service-accounts create github-actions

# Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Set up Workload Identity (see GCR_SETUP.md for details)
```

### 3. Configure GitHub Secrets

Get the values:
```bash
# Get workload identity provider
gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --format="value(name)"

# Get service account
echo "github-actions@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
```

Add to GitHub: **Settings → Secrets and variables → Actions → New repository secret**

### 4. Test the Workflow

**Via GitHub UI:**
1. Go to **Actions** tab
2. Select **"Build CC-Registry-V2 Container Images"**
3. Click **"Run workflow"**
4. Configure:
   - Branch: `main`
   - Push images: `true`
   - Tag: `test-v1`
   - Build multiarch: `false`
5. Click **"Run workflow"**

**Via GitHub CLI:**
```bash
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=test-v1 \
  -f build_multiarch=false
```

### 5. Verify Images

```bash
# List images
gcloud artifacts docker images list \
  us-docker.pkg.dev/$GCP_PROJECT_ID/public-images

# Pull an image
gcloud auth configure-docker us-docker.pkg.dev
docker pull us-docker.pkg.dev/$GCP_PROJECT_ID/public-images/cc-registry-v2-backend:test-v1
```

## 🎨 Workflow Options

### Manual Dispatch Options

**Push images** (`push_images`):
- `true` - Build and push to GCR
- `false` - Build only (no push)

**Custom tag** (`tag`):
- Leave empty for auto-generated tag (`branch-sha`)
- Or specify custom: `v1.0.0`, `staging`, etc.

**Build multiarch** (`build_multiarch`):
- `false` - Build amd64 only (default, faster)
- `true` - Build both amd64 and arm64

### Image Tags

**Auto-generated format:**
```
<branch>-<sha8>
Example: main-abc12345
```

**Architecture-specific tags:**
```
main-abc12345-amd64
main-abc12345-arm64
```

**Multi-arch manifest:**
```
main-abc12345  (points to both amd64 and arm64)
```

## 📚 Documentation Created

1. **[GCR_SETUP.md](GCR_SETUP.md)** - Complete GCP/GCR setup guide
2. **[GCR_MIGRATION_SUMMARY.md](GCR_MIGRATION_SUMMARY.md)** - Detailed migration summary
3. **[k8s/CONTAINER_BUILD.md](k8s/CONTAINER_BUILD.md)** - Updated for GCR
4. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Full deployment guide
5. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Command cheat sheet

## 🔍 Key Differences from Example Workflow

### Similarities (from runwhen-local workflow):
- ✅ Google Cloud authentication with Workload Identity
- ✅ Multi-architecture builds (separate amd64/arm64 jobs)
- ✅ Manifest creation to combine architectures
- ✅ GitHub Actions caching
- ✅ Optional Slack notifications
- ✅ Build arguments (GITHUB_SHA, GITHUB_REF)

### Differences:
- ✅ **Three components** instead of one (backend, frontend, worker)
- ✅ **PR validation** - builds without pushing for security
- ✅ **Flexible push option** - can build-only or build-and-push
- ✅ **Optional multi-arch** - can skip arm64 builds via input
- ✅ **PR comments** - posts build status to PRs
- ✅ **Worker requirements** - copies backend requirements.txt

## 🎯 Next Steps

### Immediate (Required)
1. ✅ Update workflow file with your GCP project ID
2. ✅ Set up GCP (follow [GCR_SETUP.md](GCR_SETUP.md))
3. ✅ Configure GitHub secrets
4. ✅ Test with manual workflow run

### Soon (Recommended)
5. ✅ Update Kubernetes manifests with new registry URLs
6. ✅ Set up cost monitoring and cleanup policies
7. ✅ Enable vulnerability scanning
8. ✅ Configure Slack notifications (optional)

### Later (Optional)
9. ✅ Set up Binary Authorization for additional security
10. ✅ Configure automated deployments after successful builds
11. ✅ Add additional security scanning tools
12. ✅ Set up monitoring dashboards

## 🐛 Troubleshooting

### "Failed to authenticate to Google Cloud"
**Solution:** Check GitHub secrets are correctly configured
```bash
gh secret list
# Should show: GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_SERVICE_ACCOUNT
```

### "Permission denied when pushing to registry"
**Solution:** Verify service account has correct permissions
```bash
gcloud projects get-iam-policy $GCP_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions@*"
```

### "Image not found after build"
**Solution:** Check workflow logs to see if push was skipped
- PRs don't push by default (set `push_images: true` to override)
- Check the `publish-manifests` job for push status

## 💡 Usage Examples

### Test PR Build (No Push)
```bash
# Create a PR touching cc-registry-v2/
git checkout -b test-build
echo "test" >> cc-registry-v2/README.md
git commit -am "Test build"
git push origin test-build
# Open PR - workflow will run automatically
```

### Build and Push Development Version
```bash
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=dev-$(date +%Y%m%d) \
  -f build_multiarch=false
```

### Build Production Multi-Arch Release
```bash
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v1.0.0 \
  -f build_multiarch=true
```

## ✅ Validation Results

```
✅ Workflow validation complete!
✅ Jobs: 11 defined
✅ Job names: scan-repo, generate-tag, build-backend-amd64, 
              build-backend-arm64, build-frontend-amd64, 
              build-frontend-arm64, build-worker-amd64, 
              build-worker-arm64, publish-manifests, 
              summary, notify
✅ Registry: us-docker.pkg.dev/runwhen-nonprod-shared/public-images
✅ Project: runwhen-nonprod-shared
✅ YAML syntax is valid
```

## 📞 Need Help?

- **GCP Setup Issues**: See [GCR_SETUP.md](GCR_SETUP.md) troubleshooting section
- **Workflow Issues**: Check workflow logs in GitHub Actions tab
- **Build Failures**: Review individual job logs for errors
- **Permission Issues**: Verify IAM roles and workload identity configuration

---

**Ready to deploy?** Follow the [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete deployment instructions!
