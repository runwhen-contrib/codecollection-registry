# Helm Chart Version Management

This document describes the enhanced helm configuration builder with version-aware capabilities.

## Overview

The helm configuration builder now supports:

- **Dynamic Version Selection**: Users can select from available helm chart versions
- **Version-Specific Configuration**: Each version has its own default values and schema
- **Template System**: Pre-configured templates for common use cases
- **Automatic Synchronization**: Chart versions are automatically synced from the helm repository
- **Schema Validation**: Values are validated against version-specific schemas

## Architecture

### Backend Components

1. **Database Models** (`app/models/helm_chart.py`):
   - `HelmChart`: Represents a helm chart (e.g., runwhen-local)
   - `HelmChartVersion`: Specific version with values and schema
   - `HelmChartTemplate`: Pre-configured templates for quick setup

2. **API Endpoints** (`app/routers/helm_charts.py`):
   - `GET /api/v1/helm-charts` - List all charts
   - `GET /api/v1/helm-charts/{chart_name}` - Get chart with versions
   - `GET /api/v1/helm-charts/{chart_name}/versions/{version}` - Get specific version
   - `GET /api/v1/helm-charts/{chart_name}/latest` - Get latest version
   - `GET /api/v1/helm-charts/{chart_name}/versions/{version}/templates` - Get templates
   - `POST /api/v1/helm-charts/{chart_name}/validate-values` - Validate values

3. **Synchronization Service** (`app/services/helm_sync.py`):
   - Fetches chart versions from helm repository
   - Extracts default values and schemas
   - Creates configuration templates
   - Manages version metadata

### Frontend Components

1. **Enhanced ConfigBuilder** (`src/pages/ConfigBuilder.tsx`):
   - Version selector dropdown
   - Template quick-start buttons
   - Version-specific metadata display
   - Dynamic configuration based on selected version

2. **API Integration** (`src/services/api.ts`):
   - Helm chart API client functions
   - TypeScript interfaces for helm chart data

## Usage

### For Users

1. **Select Chart Version**: Use the dropdown to select the desired helm chart version
2. **Choose Template**: Click on a template button for quick configuration
3. **Customize Values**: Modify configuration values as needed
4. **Generate YAML**: The generated values.yaml will include version information

### For Administrators

1. **Sync Chart Versions**:
   ```bash
   curl -X POST "http://localhost:8001/api/v1/admin/sync-helm-charts" \
        -H "Authorization: Bearer admin-token"
   ```

2. **Test Sync Locally**:
   ```bash
   cd cc-registry-v2
   python test_helm_sync.py
   ```

## Database Schema

### helm_charts
- `id`: Primary key
- `name`: Chart name (e.g., "runwhen-local")
- `repository_url`: Helm repository URL
- `description`: Chart description
- `home_url`: Chart home page
- `source_urls`: Source code URLs (JSON array)
- `maintainers`: Chart maintainers (JSON array)
- `keywords`: Chart keywords (JSON array)
- `last_synced_at`: Last sync timestamp
- `sync_enabled`: Whether sync is enabled
- `is_active`: Whether chart is active

### helm_chart_versions
- `id`: Primary key
- `chart_id`: Foreign key to helm_charts
- `version`: Version string (e.g., "0.0.21")
- `app_version`: Application version
- `description`: Version description
- `created_date`: Version creation date
- `digest`: Chart digest/hash
- `default_values`: Default values.yaml (JSON)
- `values_schema`: values.schema.json (JSON)
- `is_latest`: Whether this is the latest version
- `is_prerelease`: Whether this is a prerelease
- `is_deprecated`: Whether this version is deprecated
- `synced_at`: Last sync timestamp
- `is_active`: Whether version is active

### helm_chart_templates
- `id`: Primary key
- `chart_version_id`: Foreign key to helm_chart_versions
- `name`: Template name (e.g., "Basic Setup")
- `description`: Template description
- `category`: Template category (e.g., "basic", "production")
- `template_values`: Pre-configured values (JSON)
- `required_fields`: Fields that must be customized (JSON array)
- `is_default`: Whether this is the default template
- `sort_order`: Display order
- `is_active`: Whether template is active

## Configuration

### Environment Variables

- `HELM_SYNC_ENABLED`: Enable automatic helm chart synchronization (default: true)
- `HELM_SYNC_INTERVAL`: Sync interval in seconds (default: 3600)
- `HELM_REPOSITORY_URL`: Default helm repository URL

### Chart Repository

The system currently supports the RunWhen helm repository:
- Repository: https://runwhen-contrib.github.io/helm-charts
- Chart: runwhen-local
- Index: https://runwhen-contrib.github.io/helm-charts/index.yaml

## Benefits

1. **No Code Updates Required**: New helm chart versions are automatically detected and made available
2. **Version-Specific Defaults**: Each version has appropriate default values
3. **Better User Experience**: Users can easily switch between versions and see what's changed
4. **Template System**: Quick start options for common configurations
5. **Validation**: Values are validated against version-specific schemas
6. **Metadata Rich**: Version information, release dates, and deprecation status

## Future Enhancements

1. **Multiple Chart Support**: Support for additional helm charts beyond runwhen-local
2. **Chart Download**: Actually download and extract chart files for real values/schema
3. **Diff Viewer**: Show differences between chart versions
4. **Migration Assistant**: Help users migrate configurations between versions
5. **Custom Templates**: Allow users to create and save custom templates
6. **Webhook Integration**: Real-time updates when new chart versions are released

## Migration

Existing configurations will continue to work. The system will:
1. Default to the latest available chart version
2. Preserve existing configuration values
3. Show a migration notice if using an older version

## Troubleshooting

### Common Issues

1. **No Versions Available**: Check network connectivity and repository URL
2. **Sync Failures**: Check logs for detailed error messages
3. **Schema Validation Errors**: Ensure values match the selected version's schema

### Logs

Check application logs for helm sync activities:
```bash
docker logs registry-backend | grep -i helm
```

### Manual Sync

Force a manual sync via the admin API:
```bash
curl -X POST "http://localhost:8001/api/v1/admin/sync-helm-charts" \
     -H "Authorization: Bearer admin-token"
```
