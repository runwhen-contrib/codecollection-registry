# YAML Schedules Migration - Completed

## Summary

Successfully migrated Celery Beat schedules from hardcoded Python to an easy-to-edit YAML configuration file. Schedules are now maintainable without needing to dig through Python code.

## What Changed

### Before
- Schedules hardcoded in `backend/app/tasks/celery_app.py` (lines 91-139)
- Required Python knowledge to modify
- Changes required editing deep in the codebase
- Not accessible to operations team

### After
- Schedules in simple `schedules.yaml` at project root
- Easy to edit with clear examples and documentation
- Version controlled and reviewable
- Changes only require: edit YAML → restart scheduler

## Files Created/Modified

### New Files
1. ✅ **`schedules.yaml`** - Schedule configuration (root of cc-registry-v2)
2. ✅ **`README_SCHEDULES.md`** - Complete guide for editing schedules
3. ✅ **`YAML_SCHEDULES_MIGRATION.md`** - This document

### Modified Files
1. ✅ **`backend/app/tasks/celery_app.py`**
   - Added YAML loading function
   - Replaced hardcoded schedule dict with `load_schedules_from_yaml()`
   - Added None → '*' conversion for crontab fields
   - Added logging for schedule loading

2. ✅ **`docker-compose.yml`**
   - Added `./schedules.yaml:/app/schedules.yaml:ro` volume mount to:
     - backend service
     - worker service
     - scheduler service

3. ✅ **`backend/app/routers/schedule_config.py`**
   - Updated info message to reference schedules.yaml
   - Fixed 'unhashable type: set' error for crontab parsing

## Current Schedules in YAML

All 10 schedules successfully migrated:

```yaml
schedules:
  - validate-yaml-seed-daily: Daily at 01:00
  - sync-collections-daily: Daily at 02:00  # Main codecollection rescan
  - parse-codebundles-daily: Daily at 03:00
  - enhance-codebundles-weekly: Weekly on Monday at 04:00
  - generate-metrics-daily: Daily at 05:00
  - scheduled-sync: Daily at 06:00  # Full registry sync
  - update-statistics-hourly: Every hour
  - health-check: Every 5 minutes
  - cleanup-old-tasks: Daily at 00:30
  - health-check-tasks: Every 10 minutes
```

## How to Use

### View Schedules in Admin UI
1. Go to http://localhost:3000/admin
2. Login with `admin@runwhen.com` / `admin-dev-password`
3. Click "Schedules" tab
4. See all 10 schedules with descriptions and timing

### Edit a Schedule
1. Open `cc-registry-v2/schedules.yaml`
2. Modify the time:
   ```yaml
   - name: sync-collections-daily
     crontab:
       hour: 3  # Changed from 2 to 3
       minute: 0
   ```
3. Restart scheduler:
   ```bash
   docker-compose restart scheduler
   ```
4. Changes take effect immediately

### Disable a Schedule
```yaml
- name: enhance-codebundles-weekly
  enabled: false  # Set to false
```

### Add a New Schedule
```yaml
- name: my-new-task
  task: app.tasks.my_module.my_function
  description: What this does
  schedule_type: crontab
  crontab:
    hour: 7
    minute: 30
  enabled: true
```

## Benefits

### For Operations Team
- ✅ **No Python knowledge needed** - Edit simple YAML
- ✅ **Clear documentation** - Examples and reference in YAML file
- ✅ **Quick changes** - Edit → restart → done
- ✅ **Version controlled** - Changes tracked in Git
- ✅ **UI visibility** - View all schedules in admin panel

### For Development Team  
- ✅ **Separation of concerns** - Config separate from code
- ✅ **Easier testing** - Can swap YAML files for testing
- ✅ **Code review** - Schedule changes visible in PRs
- ✅ **Maintainable** - Clear structure vs Python dict
- ✅ **Type safe** - YAML validated on load

### For Everyone
- ✅ **Discoverable** - `schedules.yaml` is right at project root
- ✅ **Self-documenting** - Comments and examples in YAML
- ✅ **Safe** - Read-only mount in containers
- ✅ **Flexible** - Easy to adjust timing per environment

## Testing

Verification completed:

```bash
# ✓ YAML file loads successfully
docker exec registry-scheduler python3 -c "
from app.tasks.celery_app import celery_app
print(list(celery_app.conf.beat_schedule.keys()))
"
# Output: All 10 schedules listed

# ✓ API returns schedules
curl http://localhost:8001/api/v1/schedule/schedules \
  -H "Authorization: Bearer admin-dev-token"
# Output: JSON with all 10 schedules

# ✓ Admin UI shows schedules  
# Navigate to http://localhost:3000/admin → Schedules tab
# Result: All 10 schedules visible with descriptions

# ✓ Manual trigger works
# Click "Run Now" on any schedule in admin UI
# Result: Task executes immediately, visible in Job History
```

## Migration Notes

### Backward Compatibility
- Old hardcoded schedules in Python are completely replaced
- No migration path needed - YAML is the source of truth now
- If YAML fails to load, scheduler starts with empty schedule (safe fallback)

### Environment-Specific Schedules
To have different schedules per environment:

**Option 1:** Use different YAML files
```bash
# Development
ln -s schedules.dev.yaml schedules.yaml

# Production
ln -s schedules.prod.yaml schedules.yaml
```

**Option 2:** Git branches
- Keep dev schedules in `develop` branch
- Keep prod schedules in `main` branch

**Option 3:** Kubernetes ConfigMap (for k8s deployments)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: scheduler-config
data:
  schedules.yaml: |
    schedules:
      - name: sync-collections-daily
        crontab:
          hour: 2  # Different per environment
```

## Troubleshooting

### Problem: Schedules not loading
**Solution:** Check logs
```bash
docker logs registry-scheduler | grep "schedule"
```

### Problem: YAML syntax error
**Solution:** Validate YAML
```bash
python3 -c "import yaml; yaml.safe_load(open('schedules.yaml'))"
```

### Problem: Changes not taking effect
**Solution:** Restart scheduler
```bash
docker-compose restart scheduler
```

## Future Enhancements

Possible improvements for later:

1. **UI Editor** - Edit schedules directly in admin panel (requires database-backed schedules)
2. **Schedule Validation** - Pre-flight check before restart
3. **Schedule History** - Track when schedules changed
4. **A/B Testing** - Run different schedules for different collections
5. **Conditional Schedules** - Enable/disable based on conditions

For now, the YAML approach provides the best balance of:
- Simplicity
- Version control
- Easy maintenance
- No additional dependencies

## Summary

✅ **All schedules migrated to `schedules.yaml`**  
✅ **Full documentation provided**  
✅ **Admin UI showing schedules correctly**  
✅ **Manual triggers working**  
✅ **Easy to edit without Python knowledge**

The answer to the original question "why can't we update these?" is now:

**You CAN update them! Just edit `schedules.yaml` at the project root and restart the scheduler. It's that simple.**
