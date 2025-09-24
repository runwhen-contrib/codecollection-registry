# AI CodeBundle Enhancement Framework

This document describes the AI-powered enhancement framework for CodeBundles in the CodeCollection Registry v2.

## Overview

The AI Enhancement Framework automatically improves CodeBundle descriptions and classifies their access requirements using Large Language Models (LLMs). It provides:

1. **Enhanced Descriptions**: AI-generated, comprehensive descriptions that explain what each CodeBundle does, when to use it, and what value it provides
2. **Access Classification**: Automatic classification of CodeBundles as "read-only" or "read-write" based on their operations
3. **IAM Requirements**: Identification of minimum required permissions and roles needed to execute each CodeBundle

## Architecture

### Backend Components

#### 1. AI Configuration (`app/models/ai_config.py`)
- Stores AI service configuration (API keys, models, rate limits)
- Supports multiple AI providers (OpenAI, Anthropic)
- Admin-configurable settings

#### 2. AI Service Layer (`app/services/ai_service.py`)
- Core service for AI-powered enhancement
- Handles API communication with LLM providers
- Generates enhanced descriptions and access classifications

#### 3. Enhanced CodeBundle Model (`app/models/codebundle.py`)
New fields added:
- `ai_enhanced_description`: AI-generated improved description
- `access_level`: Classification as 'read-only', 'read-write', or 'unknown'
- `minimum_iam_requirements`: List of required IAM permissions/roles
- `enhancement_status`: Tracking enhancement progress

#### 4. Celery Tasks (`app/tasks/ai_enhancement_tasks.py`)
- `enhance_codebundle_task`: Enhance a single CodeBundle
- `enhance_multiple_codebundles_task`: Batch enhancement
- `enhance_collection_codebundles_task`: Enhance all CodeBundles in a collection
- `enhance_pending_codebundles_task`: Enhance all pending CodeBundles

#### 5. Admin API (`app/routers/ai_admin.py`)
REST endpoints for:
- AI configuration management
- Enhancement triggering and monitoring
- Statistics and progress tracking

#### 6. Enhanced Robot Parser (`app/services/robot_parser.py`)
- Analyzes Robot Framework files for access patterns
- Classifies tasks based on keywords and operations
- Extracts platform-specific IAM requirements

### Frontend Components

#### 1. AI Configuration UI (`frontend/src/components/AIConfiguration.tsx`)
- Configure AI service settings (API keys, models, rate limits)
- Monitor enhancement statistics and progress
- Trigger enhancement tasks
- View real-time task status

#### 2. Enhanced Admin Panel (`frontend/src/pages/Admin.tsx`)
- Tabbed interface with separate AI Configuration section
- Integration with existing data management features

## Configuration

### 1. Environment Variables
Add to your `.env` file:
```bash
OPENAI_API_KEY=your_openai_api_key_here
AI_MODEL=gpt-4
AI_ENHANCEMENT_ENABLED=true
```

### 2. Database Migration
Run the migration to add AI enhancement fields:
```sql
-- See: database/migrations/002_add_ai_enhancement.sql
```

### 3. Dependencies
Add to `requirements.txt`:
```
openai==1.3.7
```

## Usage

### Admin Configuration

1. **Access Admin Panel**: Navigate to `/admin` and log in
2. **Configure AI Service**: 
   - Go to "AI Configuration" tab
   - Click "Add Configuration"
   - Enter your OpenAI API key and configure settings
   - Enable enhancement

3. **Trigger Enhancement**:
   - Click "Enhance Pending" to process all unenhanced CodeBundles
   - Monitor progress in real-time
   - View statistics and completion rates

### API Endpoints

#### Configuration Management
```bash
# Get AI configurations
GET /api/v1/admin/ai/config

# Create AI configuration
POST /api/v1/admin/ai/config
{
  "service_provider": "openai",
  "api_key": "sk-...",
  "model_name": "gpt-4",
  "enhancement_enabled": true
}

# Update AI configuration
PUT /api/v1/admin/ai/config/{id}

# Delete AI configuration
DELETE /api/v1/admin/ai/config/{id}
```

#### Enhancement Operations
```bash
# Enhance pending CodeBundles
POST /api/v1/admin/ai/enhance
{
  "enhance_pending": true,
  "limit": 10
}

# Enhance specific CodeBundles
POST /api/v1/admin/ai/enhance
{
  "codebundle_ids": [1, 2, 3]
}

# Enhance collection
POST /api/v1/admin/ai/enhance
{
  "collection_slug": "aws-troubleshooting"
}

# Get enhancement status
GET /api/v1/admin/ai/enhance/status/{task_id}

# Get enhancement statistics
GET /api/v1/admin/ai/stats
```

## Access Classification Logic

The system classifies CodeBundles based on:

### Read-Only Operations
Keywords: `get`, `list`, `describe`, `show`, `check`, `verify`, `validate`, `inspect`, `monitor`, `watch`, `query`, `search`, `find`, `fetch`, `read`, `view`, `display`, `print`, `log`, `status`, `health`, `ping`, `test`, `probe`, `scan`, `audit`, `analyze`, `report`

### Read-Write Operations  
Keywords: `create`, `update`, `delete`, `modify`, `change`, `set`, `put`, `post`, `patch`, `remove`, `add`, `insert`, `deploy`, `install`, `configure`, `setup`, `start`, `stop`, `restart`, `scale`, `resize`, `migrate`, `backup`, `restore`, `sync`, `apply`, `execute`, `run`, `trigger`, `launch`, `kill`, `terminate`, `disable`, `enable`, `attach`, `detach`, `mount`, `unmount`, `copy`, `move`, `transfer`

## IAM Requirements Detection

Platform-specific IAM requirements are automatically detected:

### AWS
- EC2: `ec2:DescribeInstances`, `ec2:*`
- S3: `s3:GetObject`, `s3:ListBucket`, `s3:*`
- EKS: `eks:DescribeCluster`, `eks:ListClusters`

### Kubernetes
- Pods: `pods:get`, `pods:list`, `pods:*`
- Deployments: `deployments:get`, `deployments:list`, `deployments:*`
- Services: `services:get`, `services:list`

### Azure
- Resource Groups: `Microsoft.Resources/subscriptions/resourceGroups/read`, `Microsoft.Resources/subscriptions/resourceGroups/*`
- VMs: `Microsoft.Compute/virtualMachines/read`

### GCP
- Compute: `compute.instances.get`, `compute.instances.list`, `compute.instances.*`
- Storage: `storage.objects.get`, `storage.buckets.list`

## Security Considerations

1. **API Key Storage**: API keys should be encrypted in production
2. **Rate Limiting**: Configure appropriate rate limits to avoid API quota issues
3. **Access Control**: Only admin users can configure AI settings
4. **Audit Logging**: All AI enhancement activities are logged

## Monitoring and Troubleshooting

### Statistics Dashboard
- Total CodeBundles and completion rates
- Enhancement status breakdown (pending, processing, completed, failed)
- Access level distribution (read-only, read-write, unknown)

### Task Monitoring
- Real-time progress tracking for enhancement tasks
- Detailed error reporting for failed enhancements
- Task history and status logs

### Common Issues

1. **API Key Issues**: Verify API key is valid and has sufficient quota
2. **Rate Limiting**: Adjust `max_requests_per_hour` and `max_concurrent_requests`
3. **Model Availability**: Ensure the specified model is available for your API key
4. **Network Issues**: Check connectivity to AI service providers

## Future Enhancements

1. **Multi-Provider Support**: Add support for Anthropic Claude, Google Bard
2. **Custom Prompts**: Allow customization of enhancement prompts
3. **Batch Processing**: Optimize for large-scale enhancement operations
4. **Quality Metrics**: Track enhancement quality and user feedback
5. **Auto-Enhancement**: Automatically enhance new CodeBundles as they're added

## Development

### Adding New AI Providers

1. Update `AIConfiguration` model with new provider options
2. Extend `AIEnhancementService` to support new provider APIs
3. Add provider-specific configuration in the UI
4. Update documentation and examples

### Extending Classification Logic

1. Modify keyword sets in `RobotFrameworkParser`
2. Add new platform detection logic
3. Extend IAM requirement extraction methods
4. Test with representative CodeBundles

### Testing

```bash
# Run backend tests
cd backend
pytest app/tests/test_ai_enhancement.py

# Run frontend tests
cd frontend
npm test -- --testPathPattern=AIConfiguration
```

