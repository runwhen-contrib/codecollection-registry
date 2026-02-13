# Deployment Guide

## Quick Deploy

### Docker Compose (Development/Testing)

```bash
cd cc-registry-v2
docker-compose up -d
```

Access:
- Frontend: http://localhost:3000
- Backend: http://localhost:8001
- Admin: http://localhost:3000/admin

### Production Checklist

- [ ] Change database password
- [ ] Change admin credentials  
- [ ] Set AZURE_OPENAI_* in az.secret
- [ ] Enable HTTPS
- [ ] Configure secrets management
- [ ] Set DEBUG=false
- [ ] Configure backups

## Architecture

Frontend (React) → Backend (FastAPI) → PostgreSQL
                         ↓
                   Worker/Scheduler (Celery) ↔ Redis

## Environment Variables

Required in production:
- DATABASE_URL
- REDIS_URL
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_KEY
- REACT_APP_ADMIN_EMAIL
- REACT_APP_ADMIN_PASSWORD

See docs/CONFIGURATION.md for full reference.

## Kubernetes (Optional)

Manifests in `k8s/` directory:
- backend-deployment.yaml
- worker-deployment.yaml
- scheduler-deployment.yaml
- database-statefulset.yaml

Deploy:
```bash
kubectl apply -f k8s/
```

## Monitoring

- Flower UI: http://localhost:5555
- Health endpoint: http://localhost:8001/api/v1/health
- Admin panel: http://localhost:3000/admin

## Backups

```bash
# Backup database
docker exec registry-database pg_dump -U user codecollection_registry > backup.sql

# Restore
docker exec -i registry-database psql -U user codecollection_registry < backup.sql
```

See TROUBLESHOOTING.md for common deployment issues.
