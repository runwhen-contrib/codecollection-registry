# Container Image Build Workflow

This document describes the GitHub Actions workflow for building and pushing container images for CC-Registry-V2.

## Workflow Overview

The workflow builds three container images:
1. **Backend** - FastAPI application (`cc-registry-v2-backend`)
2. **Frontend** - React application (`cc-registry-v2-frontend`)
3. **Worker** - Celery worker/scheduler (`cc-registry-v2-worker`)

## Workflow Triggers

### Pull Requests
The workflow automatically triggers when:
- A PR is opened, synchronized, or reopened
- Changes are made to files in `cc-registry-v2/**`
- Changes are made to the workflow file itself

**Note:** Images built from PRs are **not pushed** to the registry by default (build-only mode for validation).

### Manual Dispatch
You can manually trigger the workflow from the GitHub Actions UI with options:
- **Push images**: Choose whether to push images to registry (`true`/`false`)
- **Custom tag**: Optionally specify a custom tag for the images

### Main Branch
When merged to `main`, images are automatically built and pushed with the `latest` tag.

## Image Naming Convention

Images are pushed to Google Container Registry (GCR/Artifact Registry) with the following naming:

```
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-backend:<tag>
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-frontend:<tag>
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-worker:<tag>
```

Example:
```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-backend:main-abc12345
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-frontend:main-abc12345
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-worker:main-abc12345
```

### Tags
Each image is tagged with:
- `<branch>-<sha>` - Branch name (sanitized) and short commit SHA (e.g., `main-abc12345`)
- `<branch>-<sha>-amd64` - Architecture-specific tag (e.g., `main-abc12345-amd64`)
- `<branch>-<sha>-arm64` - Architecture-specific tag if multi-arch build (e.g., `main-abc12345-arm64`)
- Custom tag if specified in manual dispatch (e.g., `v1.0.0`)

Multi-arch images create a manifest that includes both amd64 and arm64 variants.

## Prerequisites

Before using this workflow, you need to set up Google Cloud Registry:

1. **Create GCP Project** and enable Artifact Registry API
2. **Set up Workload Identity Federation** for GitHub Actions authentication
3. **Configure GitHub Secrets** with GCP credentials
4. **Update workflow file** with your GCP project ID and registry URL

📚 **See [GCR_SETUP.md](../GCR_SETUP.md) for complete setup instructions.**

## Using the Images

### Docker Compose

Update your `docker-compose.yml` to use the built images:

```yaml
services:
  backend:
    image: us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-backend:latest
    # ... rest of configuration

  frontend:
    image: us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-frontend:latest
    # ... rest of configuration

  worker:
    image: us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-worker:latest
    # ... rest of configuration

  scheduler:
    image: us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-worker:latest  # Same image as worker
    command: celery -A app.tasks.celery_app beat --loglevel=info
    # ... rest of configuration
```

### Kubernetes

See the example manifests in this directory:
- `backend-deployment.yaml` - Backend deployment
- `frontend-deployment.yaml` - Frontend deployment
- `worker-deployment.yaml` - Worker deployment
- `scheduler-deployment.yaml` - Scheduler deployment

Update the `image:` field in each deployment to reference the built images.

### Pull Images Locally

To pull and test images locally:

```bash
# Authenticate with Google Container Registry
gcloud auth configure-docker us-docker.pkg.dev

# Pull images
docker pull us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-backend:latest
docker pull us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-frontend:latest
docker pull us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-worker:latest

# Run a container
docker run -p 8001:8001 us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-backend:latest
```

## Testing PRs

### For PR Authors
When you open a PR, the workflow will:
1. Automatically build all three images
2. Validate that builds complete successfully
3. Post comments to the PR with build status
4. Add a summary to the workflow run

Images are **not pushed** to the registry for security reasons (to prevent unauthorized image publishing).

### For Maintainers
To test a PR's built images:
1. Go to the PR's "Actions" tab
2. Find the "Build CC-Registry-V2 Container Images" workflow run
3. Check build logs and PR comments for build status
4. Manually re-run with `push_images: true` if you want to push images for testing
5. Or manually build locally:
   ```bash
   git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>
   git checkout pr-<PR_NUMBER>
   cd cc-registry-v2
   docker-compose build
   ```

### Multi-Architecture Builds

To build images for both amd64 and arm64 architectures:
1. Go to Actions → "Build CC-Registry-V2 Container Images"
2. Click "Run workflow"
3. Set `build_multiarch` to `true`
4. The workflow will build on both x86_64 and ARM runners
5. A multi-arch manifest will be created combining both architectures

## Manual Workflow Dispatch

### Push with Custom Tag
1. Go to Actions → "Build CC-Registry-V2 Container Images"
2. Click "Run workflow"
3. Select branch
4. Set `push_images` to `true`
5. Enter custom tag (e.g., `v1.0.0`, `test-deployment`)
6. Click "Run workflow"

This will build and push images with your custom tag:
```
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-backend:v1.0.0
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-frontend:v1.0.0
us-docker.pkg.dev/<project-id>/<repository>/cc-registry-v2-worker:v1.0.0
```

### Build Only (No Push)
To validate builds without pushing:
1. Follow steps above
2. Set `push_images` to `false`
3. Images will be built but not pushed to registry

## Caching

The workflow uses GitHub Actions cache to speed up builds:
- Docker layer caching across builds
- Separate cache per image (backend, frontend, worker)
- Cache invalidation on Dockerfile or dependency changes

## Troubleshooting

### Build Failures

Check the workflow logs in GitHub Actions:
1. Go to Actions tab
2. Click on the failed workflow run
3. Click on the failed job (backend/frontend/worker)
4. Review the build logs

Common issues:
- **Dependency errors**: Check `requirements.txt` or `package.json`
- **Context errors**: Ensure Dockerfile `COPY` commands reference correct paths
- **Build timeout**: Increase runner resources or optimize Dockerfile

### Permission Errors

If you see "permission denied" when pushing images:
1. Verify GCP Workload Identity Federation is configured correctly
2. Check that GitHub secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` are set
3. Ensure the service account has `roles/artifactregistry.writer` permission
4. Verify the workload identity pool allows your GitHub repository

See [GCR_SETUP.md](../GCR_SETUP.md) for troubleshooting steps.

### Cache Issues

To clear the cache:
1. Go to repository Settings → Actions → Caches
2. Delete caches for the workflow
3. Re-run the workflow

## Security

### Image Signing
Consider adding image signing with Cosign:
```yaml
- name: Sign image
  uses: sigstore/cosign-installer@v3
- run: cosign sign ghcr.io/${{ github.repository }}/cc-registry-v2-backend:${{ steps.meta.outputs.tags }}
```

### Vulnerability Scanning
Add Trivy security scanning:
```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/${{ github.repository }}/cc-registry-v2-backend:${{ steps.meta.outputs.tags }}
    format: 'sarif'
    output: 'trivy-results.sarif'
```

## CI/CD Integration

### Deploy on Successful Build
Trigger deployment after successful image builds:

```yaml
# Add to workflow
  deploy:
    needs: [build-backend, build-frontend, build-worker]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to test cluster
        run: |
          # Your deployment commands here
          kubectl set image deployment/backend backend=ghcr.io/${{ github.repository }}/cc-registry-v2-backend:latest
```

### Integration with Other Workflows
Reference built images in other workflows:
```yaml
jobs:
  integration-test:
    runs-on: ubuntu-latest
    steps:
      - name: Pull images
        run: |
          docker pull ghcr.io/${{ github.repository }}/cc-registry-v2-backend:${{ github.sha }}
      - name: Run tests
        run: docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## Future Enhancements

- [ ] Add image vulnerability scanning (Trivy/Snyk)
- [ ] Add image signing with Cosign
- [ ] Multi-architecture builds (ARM64, AMD64)
- [ ] Automatic deployment to test cluster
- [ ] Image size optimization reports
- [ ] Build time metrics tracking
- [ ] Automated rollback on failed deployments
