# Troubleshooting Guide

## Common Issues

### Services Won't Start

```bash
docker-compose down
docker-compose up -d --build
docker-compose logs
```

### Database Connection Errors

```bash
docker exec registry-database pg_isready -U user
docker-compose restart database
sleep 5
docker-compose restart backend worker scheduler
```

### AI Enhancement Not Working

1. Check az.secret exists: `cat az.secret`
2. Admin UI → AI Enhancement section
3. Check logs: `docker logs registry-worker --tail 100`

### Schedules Not Running

```bash
docker logs registry-scheduler --tail 50
docker-compose restart scheduler
```

### Login Not Working

Use: `admin@runwhen.com` / `admin-dev-password` (NOT admin-dev-token!)

### Tasks Failing

```bash
docker logs registry-worker --tail 200
docker-compose restart worker
```

## Debugging Commands

```bash
# Service health
docker-compose ps
curl http://localhost:8001/api/v1/health

# View logs
docker-compose logs -f backend
docker-compose logs -f worker  
docker-compose logs -f scheduler

# Database
docker exec -it registry-database psql -U user -d codecollection_registry

# Worker stats
docker exec registry-worker celery -A app.tasks.celery_app inspect active
```

## Emergency Reset

```bash
docker-compose down
docker-compose down -v  # DELETES DATA!
docker-compose up -d --build
```

See Flower UI at http://localhost:5555 for task monitoring.
