# Analytics Features

## Task Growth Chart

The homepage displays a historical task growth chart showing how the task library has grown over the last 18 months.

### Architecture

**Components:**
- **Frontend:** `frontend/src/components/TaskGrowthChart.tsx` - React component with Recharts
- **Backend API:** `backend/app/routers/analytics.py` - Analytics endpoints
- **Background Task:** `backend/app/tasks/analytics_tasks.py` - Celery task for data computation
- **Database:** `backend/app/models/analytics.py` - `TaskGrowthMetric` model
- **Migration:** `backend/alembic/versions/002_add_task_growth_metrics.py`

### How It Works

1. **Background Computation:** Celery task runs daily at 2:30 AM
   - Clones each code collection repository
   - Uses `git log --diff-filter=A` to find first commit date of each codebundle
   - Aggregates data monthly for last 18 months
   - Stores results in `task_growth_metrics` table

2. **API Response:** `/api/v1/analytics/tasks-by-week-cached`
   - Returns cached data from database
   - No git operations on page load (fast!)
   - Shows cumulative task count by month

3. **Frontend Display:**
   - Area chart with gradient fill
   - Monthly labels (e.g., "Jan '25")
   - Responsive layout

### Database Schema

```sql
CREATE TABLE task_growth_metrics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR(50) DEFAULT 'monthly_growth',
    time_period VARCHAR(20) NOT NULL,  -- '18_months'
    data JSON NOT NULL,
    computed_at TIMESTAMP WITH TIME ZONE,
    computation_duration_seconds INTEGER,
    codebundles_analyzed INTEGER,
    notes TEXT
);
```

### Schedule Configuration

**File:** `backend/schedules.yaml`

```yaml
- name: compute-task-growth-analytics
  task: app.tasks.analytics_tasks.compute_task_growth_analytics
  description: Analyze git history and compute task growth metrics
  schedule_type: crontab
  crontab:
    hour: 2
    minute: 30
  enabled: true
```

### Manual Trigger

Trigger computation manually via API:

```bash
curl -X POST http://localhost:8001/api/v1/analytics/compute-task-growth \
  -H "Authorization: Bearer admin-test"
```

### Testing Locally

```bash
# Run computation immediately
docker-compose exec worker celery -A app.tasks.celery_app call \
  app.tasks.analytics_tasks.compute_task_growth_analytics

# Check results
curl http://localhost:8001/api/v1/analytics/tasks-by-week-cached | jq '.'
```

### Performance Notes

- Initial computation takes ~20-30 seconds (cloning repos + git log)
- Cached data served in milliseconds
- Database entry updated daily
- Computation excludes `meta.yml` changes (focuses on actual code changes)

---

## Google Analytics Integration

The frontend includes Google Analytics 4 (GA4) for tracking user behavior.

### Setup

**File:** `frontend/src/utils/analytics.ts`

Contains utility functions:
- `initGA(measurementId)` - Initialize GA4
- `logPageView()` - Track page views
- `logEvent(action, params)` - Track custom events

### Configuration

**Environment Variable:** `REACT_APP_GA_MEASUREMENT_ID`

```bash
# .env file
REACT_APP_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

### Usage in Components

```typescript
import { initGA, logPageView, logEvent } from '../utils/analytics';

// Initialize on app load
useEffect(() => {
  const gaId = process.env.REACT_APP_GA_MEASUREMENT_ID;
  if (gaId) {
    initGA(gaId);
  }
}, []);

// Track page views
useEffect(() => {
  logPageView();
}, [location.pathname]);

// Track custom events
logEvent('codebundle_viewed', {
  codebundle: codebundleSlug,
  collection: collectionSlug
});
```

### Events Tracked

- Page views (automatic on route change)
- Codebundle detail views
- Task clicks
- Chat interactions
- Admin actions (optional)

### Privacy

- No PII collected
- IP anonymization enabled
- Cookie consent banner (implement if required)

---

## Task Counting Logic

### Important: Tasks vs SLIs

The system tracks TWO types of tasks:
1. **Runbook Tasks** (`codebundle.tasks`) - Interactive troubleshooting workflows
2. **SLI Tasks** (`codebundle.slis`) - Service Level Indicator checks

**Total Tasks = Runbook Tasks + SLI Tasks**

Current counts (as of Jan 2026):
- Runbook tasks: 479
- SLI tasks: 298
- **Total: 777**

### Endpoints Using Total Count

All these endpoints now correctly include both task types:

- `/api/v1/registry/stats` - Homepage statistics
- `/api/v1/admin/population-status` - Admin panel stats
- `/api/v1/registry/collections` - Per-collection statistics
- `/api/v1/analytics/tasks-by-week-cached` - Growth chart data

### Database Fields

```python
# In Codebundle model
task_count = Column(Integer)      # Number of runbook tasks
sli_count = Column(Integer)       # Number of SLI tasks
tasks = Column(JSON)              # Array of runbook task names
slis = Column(JSON)               # Array of SLI task names
```

### Counting in Code

```python
# Correct way to count total tasks
total_tasks = sum((cb.task_count or 0) + (cb.sli_count or 0) 
                  for cb in codebundles)

# Or via JSON arrays
total_tasks = sum(len(cb.tasks or []) + len(cb.slis or []) 
                  for cb in codebundles)
```

---

**Last Updated:** January 27, 2026
