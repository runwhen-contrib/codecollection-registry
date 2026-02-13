# Configuration Guide

## Environment Configuration

All configuration in `az.secret`, `docker-compose.yml`, and `schedules.yaml`.

### Azure OpenAI Setup

Create `az.secret` with:

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Service Ports

- Frontend: 3000
- Backend API: 8001  
- PostgreSQL: 5432
- Redis: 6379
- Flower: 5555

### Admin Login

Development defaults:
- Email: admin@runwhen.com
- Password: admin-dev-password

See docs/SCHEDULES.md for schedule configuration.
