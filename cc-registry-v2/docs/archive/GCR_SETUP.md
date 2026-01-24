# Google Container Registry (GCR) Setup Guide

This guide explains how to set up Google Container Registry for the CC-Registry-V2 container images.

## 📋 Prerequisites

- Google Cloud Platform (GCP) account
- GCP project with billing enabled
- GitHub repository with access to configure secrets

## 🔧 GCP Configuration

### 1. Create or Select GCP Project

```bash
# List existing projects
gcloud projects list

# Create a new project (optional)
gcloud projects create YOUR-PROJECT-ID --name="Your Project Name"

# Set the active project
gcloud config set project YOUR-PROJECT-ID
```

### 2. Enable Required APIs

```bash
# Enable Artifact Registry API (for GCR)
gcloud services enable artifactregistry.googleapis.com

# Enable IAM Service Account Credentials API
gcloud services enable iamcredentials.googleapis.com
```

### 3. Create Artifact Registry Repository

```bash
# Create a Docker repository in Artifact Registry
gcloud artifacts repositories create public-images \
  --repository-format=docker \
  --location=us \
  --description="CC-Registry-V2 container images"

# Verify the repository
gcloud artifacts repositories list --location=us
```

Your registry URL will be:
```
us-docker.pkg.dev/YOUR-PROJECT-ID/public-images
```

### 4. Set Up Workload Identity Federation

Workload Identity Federation allows GitHub Actions to authenticate to GCP without storing long-lived service account keys.

#### Create Service Account

```bash
# Create a service account for GitHub Actions
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions" \
  --description="Service account for GitHub Actions CI/CD"

# Get the service account email
export SA_EMAIL="github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com"
```

#### Grant Permissions

```bash
# Grant permissions to push to Artifact Registry
gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"

# Grant storage admin for GCS (if needed)
gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"
```

#### Create Workload Identity Pool

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create github-pool \
  --location="global" \
  --display-name="GitHub Pool"

# Get the full pool name
export WORKLOAD_IDENTITY_POOL="projects/$(gcloud projects describe YOUR-PROJECT-ID --format='value(projectNumber)')/locations/global/workloadIdentityPools/github-pool"

# Create workload identity provider
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Get the full provider name
export WORKLOAD_IDENTITY_PROVIDER="${WORKLOAD_IDENTITY_POOL}/providers/github-provider"
```

#### Allow GitHub Repository to Authenticate

```bash
# Replace OWNER/REPO with your GitHub org/repo
export GITHUB_REPO="OWNER/REPO"

# Grant the GitHub repository access to impersonate the service account
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="YOUR-PROJECT-ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL}/attribute.repository/${GITHUB_REPO}"
```

### 5. Configure GitHub Secrets

Add the following secrets to your GitHub repository:

**Settings → Secrets and variables → Actions → New repository secret**

1. **GCP_WORKLOAD_IDENTITY_PROVIDER**
   ```
   projects/PROJECT-NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider
   ```
   
   Get it with:
   ```bash
   echo "${WORKLOAD_IDENTITY_PROVIDER}"
   ```

2. **GCP_SERVICE_ACCOUNT**
   ```
   github-actions@YOUR-PROJECT-ID.iam.gserviceaccount.com
   ```
   
   Get it with:
   ```bash
   echo "${SA_EMAIL}"
   ```

3. **SLACK_BOT_TOKEN** (Optional - for Slack notifications)
   - Create a Slack app and get the bot token
   - Only needed if enabling Slack notifications

## 🔄 Update Workflow Configuration

Edit `.github/workflows/build-cc-registry-v2-images.yaml`:

```yaml
env:
  GCP_PROJECT_ID: YOUR-PROJECT-ID  # Update this
  GCR_REGISTRY: us-docker.pkg.dev/YOUR-PROJECT-ID/public-images  # Update this
  IMAGE_PREFIX: cc-registry-v2
```

## 🧪 Test the Setup

### Manual Trigger Test

1. Go to GitHub → Actions → "Build CC-Registry-V2 Container Images"
2. Click "Run workflow"
3. Configure:
   - **Branch**: main
   - **Push images**: true
   - **Tag**: test-v1
   - **Build multiarch**: false
4. Click "Run workflow"
5. Monitor the workflow execution

### Verify Images Were Pushed

```bash
# List images in the repository
gcloud artifacts docker images list \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-backend

gcloud artifacts docker images list \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-frontend

gcloud artifacts docker images list \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-worker
```

### Pull Images Locally

```bash
# Authenticate Docker with GCR
gcloud auth configure-docker us-docker.pkg.dev

# Pull images
docker pull us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-backend:test-v1
docker pull us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-frontend:test-v1
docker pull us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-worker:test-v1
```

## 🏗️ Multi-Architecture Builds

To build multi-architecture images (amd64 + arm64):

1. Ensure your GCP project has access to ARM runners (may require special configuration)
2. Trigger workflow with `build_multiarch: true`

```bash
# Or use GitHub CLI
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v1.0.0 \
  -f build_multiarch=true
```

## 🔐 Security Best Practices

### 1. Principle of Least Privilege

Only grant the minimum required permissions:
```bash
# Instead of roles/artifactregistry.writer, you can create a custom role
gcloud iam roles create github_actions_custom \
  --project=YOUR-PROJECT-ID \
  --title="GitHub Actions Custom" \
  --permissions=artifactregistry.repositories.uploadArtifacts,artifactregistry.dockerimages.push
```

### 2. Restrict Repository Access

Limit which GitHub repositories can authenticate:
```bash
# Only allow specific repository
--member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL}/attribute.repository/OWNER/REPO"

# Allow all repos in an org
--member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL}/attribute.repository_owner/OWNER"
```

### 3. Enable Binary Authorization

```bash
# Enable Binary Authorization for additional security
gcloud services enable binaryauthorization.googleapis.com
```

### 4. Set Up Vulnerability Scanning

```bash
# Enable automatic vulnerability scanning
gcloud artifacts repositories update public-images \
  --location=us \
  --enable-vulnerability-scanning
```

## 💰 Cost Optimization

### Storage Lifecycle Policies

Clean up old images to reduce storage costs:

```bash
# Create cleanup policy to delete untagged images older than 30 days
cat > cleanup-policy.json <<EOF
{
  "name": "projects/YOUR-PROJECT-ID/locations/us/repositories/public-images/cleanupPolicies/cleanup-untagged",
  "action": "DELETE",
  "condition": {
    "tagState": "UNTAGGED",
    "olderThan": "2592000s"
  }
}
EOF

# Apply the policy
gcloud artifacts repositories set-cleanup-policies public-images \
  --location=us \
  --policy=cleanup-policy.json
```

### Monitor Costs

```bash
# View storage usage
gcloud artifacts repositories describe public-images \
  --location=us \
  --format="value(sizeBytes)"

# List images and their sizes
gcloud artifacts docker images list \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images \
  --format="table(package,version,size_bytes)"
```

## 📊 Monitoring

### View Artifact Registry Metrics

```bash
# View repository metrics in Cloud Console
# Navigate to: Artifact Registry → Repositories → public-images → Metrics
```

### Set Up Alerts

```bash
# Create alert policy for storage usage
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="GCR Storage Alert" \
  --condition-display-name="High storage usage" \
  --condition-expression='
    resource.type="artifact_registry_repository" AND
    metric.type="artifactregistry.googleapis.com/repository/storage_bytes" AND
    resource.label.location="us"
  ' \
  --condition-threshold-value=10737418240 \
  --condition-threshold-duration=300s
```

## 🔄 Migration from GHCR to GCR

If migrating from GitHub Container Registry:

### 1. Pull Images from GHCR

```bash
# Pull existing images
docker pull ghcr.io/OWNER/REPO/cc-registry-v2-backend:latest
docker pull ghcr.io/OWNER/REPO/cc-registry-v2-frontend:latest
docker pull ghcr.io/OWNER/REPO/cc-registry-v2-worker:latest
```

### 2. Retag for GCR

```bash
# Retag images
docker tag ghcr.io/OWNER/REPO/cc-registry-v2-backend:latest \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-backend:latest

docker tag ghcr.io/OWNER/REPO/cc-registry-v2-frontend:latest \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-frontend:latest

docker tag ghcr.io/OWNER/REPO/cc-registry-v2-worker:latest \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-worker:latest
```

### 3. Push to GCR

```bash
# Authenticate
gcloud auth configure-docker us-docker.pkg.dev

# Push images
docker push us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-backend:latest
docker push us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-frontend:latest
docker push us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-worker:latest
```

### 4. Update Kubernetes Manifests

```bash
# Update image references in k8s manifests
cd cc-registry-v2/k8s
find . -type f -name "*.yaml" ! -name "secrets-example.yaml" -exec sed -i \
  's|ghcr.io/.*registry-v2-|us-docker.pkg.dev/YOUR-PROJECT-ID/public-images/cc-registry-v2-|g' {} +
```

## 🐛 Troubleshooting

### Authentication Errors

```bash
# Verify workload identity configuration
gcloud iam service-accounts get-iam-policy ${SA_EMAIL}

# Test authentication locally
gcloud auth application-default login
gcloud auth configure-docker us-docker.pkg.dev
```

### Permission Denied

```bash
# Check service account permissions
gcloud projects get-iam-policy YOUR-PROJECT-ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:${SA_EMAIL}"

# Grant missing permissions
gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

### Image Not Found

```bash
# Verify image exists
gcloud artifacts docker images list \
  us-docker.pkg.dev/YOUR-PROJECT-ID/public-images \
  --include-tags

# Check repository permissions
gcloud artifacts repositories get-iam-policy public-images \
  --location=us
```

## 📚 Additional Resources

- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Docker Build Multi-Platform](https://docs.docker.com/build/building/multi-platform/)
- [GitHub Actions with GCP](https://github.com/google-github-actions/auth)

## 🆘 Support

For issues related to:
- **GCP Setup**: Check [GCP Support](https://cloud.google.com/support)
- **GitHub Actions**: Review workflow logs and [GitHub Actions docs](https://docs.github.com/en/actions)
- **Workload Identity**: See [troubleshooting guide](https://cloud.google.com/iam/docs/troubleshooting-workload-identity-federation)
