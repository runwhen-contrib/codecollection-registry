# GitHub Actions Workflows

This directory contains GitHub Actions workflows for building and deploying components.

## Workflows

### 1. `build-cc-registry-v2-images.yaml`
**Purpose:** Build cc-registry-v2 application components

**Builds:**
- Backend (FastAPI)
- Frontend (React)
- Worker (Celery)

**Triggers:**
- Push to `main` affecting `cc-registry-v2/**`
- Pull requests affecting `cc-registry-v2/**`
- Manual dispatch

**Registry:**
```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/cc-registry-v2-*
```

**Usage:**
```bash
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.1.0 \
  -f build_multiarch=false
```

---

### 2. `build-mcp-server.yaml`
**Purpose:** Build MCP (Model Context Protocol) server

**Builds:**
- MCP Server (semantic search)

**Triggers:**
- Push to `main` affecting `mcp-server/**`
- Pull requests affecting `mcp-server/**`
- Manual dispatch

**Registry:**
```
us-docker.pkg.dev/runwhen-nonprod-shared/public-images/runwhen-mcp-server
```

**Usage:**
```bash
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=v1.3.0 \
  -f build_multiarch=false
```

---

## Required Secrets

Both build workflows require these secrets:

### Google Cloud
- `RUNWHEN_NONPROD_SHARED_WI_PROVIDER` - Workload Identity Provider
- `RUNWHEN_NONPROD_SHARED_WI_SA` - Service Account

### Optional
- `SLACK_BOT_TOKEN` - For Slack notifications (commented out by default)

## 🎯 Workflow Inputs

### Build Workflows (Both)

**`push_images`** (choice)
- `true` - Build and push to GCR
- `false` - Build only (validation)
- Default: `true`

**`tag`** (string)
- Custom tag for images
- Default: `<branch>-<sha8>` (auto-generated)
- Examples: `v1.0.0`, `staging`, `test-123`

**`build_multiarch`** (choice)
- `true` - Build for amd64 + arm64
- `false` - Build for amd64 only
- Default: `false`

## 📊 Workflow Comparison

| Feature | CC-Registry-V2 | MCP Server |
|---------|----------------|------------|
| **Components** | 3 | 1 |
| **Jobs** | 11 | 7 |
| **Trigger Path** | `cc-registry-v2/**` | `mcp-server/**` |
| **Avg Build Time** | ~15-20 min | ~5-8 min |
| **Image Prefix** | `cc-registry-v2-*` | `runwhen-mcp-server` |

## 🚀 Common Tasks

### Build All Components
```bash
# Build registry components
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=latest

# Build MCP server
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=latest
```

### Release New Version
```bash
# Release cc-registry-v2
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.2.0 \
  -f build_multiarch=true

# Release MCP server
gh workflow run build-mcp-server.yaml \
  -f push_images=true \
  -f tag=v1.5.0 \
  -f build_multiarch=true
```

### Test PR Build
```bash
# Just validate builds work (don't push)
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=false \
  -f tag=test-pr-123
```

### Build for ARM64
```bash
# Build multi-architecture images
gh workflow run build-cc-registry-v2-images.yaml \
  -f push_images=true \
  -f tag=v2.3.0 \
  -f build_multiarch=true
```

## 🔍 Monitoring Workflows

### Via GitHub UI
1. Go to **Actions** tab
2. Select workflow
3. View run details

### Via GitHub CLI
```bash
# List workflow runs
gh run list --workflow=build-cc-registry-v2-images.yaml

# View specific run
gh run view <run-id>

# Watch run
gh run watch <run-id>

# View logs
gh run view <run-id> --log
```

## 📝 Workflow Structure

### Build Workflow Jobs (Both)
1. **scan-repo** - Security scanning (optional Trivy)
2. **generate-tag** - Generate version tag
3. **build-amd64** - Build for x86_64
4. **build-arm64** - Build for ARM (optional)
5. **publish-manifest** - Create multi-arch manifest
6. **summary** - Generate build summary
7. **notify** - Send notifications (optional)

### Job Flow
```
scan-repo ──┐
            ├──► generate-tag ──┐
            │                   ├──► build-amd64 ────┐
            │                   │                     ├──► publish-manifest ──► summary ──► notify
            │                   └──► build-arm64 ────┘
            │                       (if multiarch)
```

## 🐛 Troubleshooting

### Workflow Won't Trigger
**Issue:** Changes pushed but workflow doesn't run

**Solutions:**
- Check if changes affect trigger paths
- Verify workflow file is on the branch
- Check workflow is enabled in GitHub

### Build Fails with "Permission Denied"
**Issue:** Can't push to GCR

**Solutions:**
- Verify `RUNWHEN_NONPROD_SHARED_WI_*` secrets are set
- Check service account has `artifactregistry.writer` role
- Validate workload identity configuration

### "Image Not Found" After Build
**Issue:** Image pushed but can't pull

**Solutions:**
- Check workflow completed successfully
- Verify push wasn't skipped (PR builds don't push by default)
- Confirm tag matches what you're pulling

### Multi-Arch Build Fails
**Issue:** ARM build fails

**Solutions:**
- Check if `ubuntu-24.04-arm` runners are available
- Try with `build_multiarch=false` for amd64 only
- ARM runners may have limited availability

## Related Documentation

- **[../cc-registry-v2/docs/DEPLOYMENT_GUIDE.md](../cc-registry-v2/docs/DEPLOYMENT_GUIDE.md)** - Deployment guide
- **[../cc-registry-v2/docs/ARCHITECTURE.md](../cc-registry-v2/docs/ARCHITECTURE.md)** - System architecture

## ✅ Workflow Health

Both workflows are:
- ✅ YAML syntax validated
- ✅ Properly structured
- ✅ Using latest actions versions
- ✅ Caching enabled
- ✅ Multi-arch ready
- ✅ Security scanning ready
- ✅ Notification ready

## 🔄 Updates

When updating workflows:
1. Test changes in a feature branch
2. Validate YAML syntax
3. Run manual dispatch to test
4. Monitor first PR build
5. Update documentation if needed

## 🆘 Support

For workflow issues:
1. Check workflow logs in GitHub Actions
2. Review [GCR_SETUP.md](../cc-registry-v2/GCR_SETUP.md) for configuration
3. Validate secrets are configured
4. Check GCP permissions
