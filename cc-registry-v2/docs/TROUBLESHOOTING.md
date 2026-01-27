# Troubleshooting Guide

## Recent Fixes (January 2026)

### Codebundle Detail Page Shows Wrong Last Updated Date
**Symptom:** Detail page shows database sync time instead of git commit date  
**Cause:** `git_updated_at` field not included in API response  
**Fix:** Added `git_updated_at` to return dict in `backend/app/main.py` line ~577  
**File:** `backend/app/main.py` - `/api/v1/collections/{collection_slug}/codebundles/{codebundle_slug}` endpoint

### User Variables Tab Always Empty
**Symptom:** Variables section shows no data even though variables exist  
**Cause:** `parse_all_codebundles_task` not extracting `user_variables` from parsed data  
**Fix:** Added `user_variables=primary_parsed.get('user_variables', [])` to codebundle creation/update  
**File:** `backend/app/tasks/registry_tasks.py` lines ~233 and ~253

### Admin Page Shows Wrong Task Count
**Symptom:** Admin shows 479 tasks instead of 777  
**Cause:** Only counting runbook tasks, ignoring SLI tasks  
**Fix:** Added SLI task count: `tasks_count = runbook_tasks + sli_tasks`  
**File:** `backend/app/routers/admin.py` - `get_population_status` endpoint  
**Note:** Total = 479 runbook tasks + 298 SLI tasks = 777

### Analytics Task Not Running
**Symptom:** `KeyError: 'app.tasks.analytics_tasks.compute_task_growth_analytics'`  
**Cause:** Analytics module not registered in Celery  
**Fix:** Added `"app.tasks.analytics_tasks"` to `include` list  
**File:** `backend/app/tasks/celery_app.py`

### Analytics API Crashes with Timezone Error
**Symptom:** `can't subtract offset-naive and offset-aware datetimes`  
**Cause:** Using `datetime.now()` instead of `datetime.now(timezone.utc)`  
**Fix:** Use timezone-aware datetime for comparison  
**File:** `backend/app/routers/analytics.py`

### Collection Statistics Wrong
**Symptom:** Per-collection task counts don't include SLI tasks  
**Cause:** SQL query only summing `task_count`, not `sli_count`  
**Fix:** Added `func.sum(Codebundle.sli_count)` to aggregation  
**File:** `backend/app/main.py` lines ~120 and ~181

---

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
