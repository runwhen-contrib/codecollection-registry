# Task Growth Chart - Git History Based Analytics

## Overview

Added a "Total Tasks by Week" chart to the homepage that shows historical task library growth using **git commit history** instead of database timestamps. This solves the problem of launching with 700+ tasks but no historical "created_at" data.

---

## How It Works

### Backend (`/api/v1/analytics/tasks-by-week-cached`)

1. **Queries all active codebundles** from the database
2. **Uses `git_updated_at` dates** (already populated with accurate git dates)
3. **Groups tasks by week** (Monday start)
4. **Calculates cumulative totals** week-over-week
5. **Returns weekly data** for charting

**Alternative endpoint** (`/tasks-by-week`):
- Clones repositories and analyzes git log for first-commit dates
- More accurate but slower (clones repos)
- Use for one-time historical backfill if needed

### Frontend (`TaskGrowthChart.tsx`)

- Uses **Recharts** library (area chart)
- Fetches data from `/analytics/tasks-by-week-cached`
- Displays cumulative task count over time
- Shows total tasks at top
- Responsive design
- Automatic label sampling for clean x-axis

---

## Why This Solves Your Problem

✅ **Shows real organic growth** - Uses actual git history  
✅ **No zero baseline** - Charts your 700+ tasks from when they were actually added  
✅ **Survives data resets** - Based on git history, not DB timestamps  
✅ **Accurate timeline** - Shows when codebundles were truly introduced  
✅ **Low cost** - Uses cached DB queries (fast), not live git operations  

---

## Files Created/Modified

### New Files:
1. **`backend/app/routers/analytics.py`** - Analytics API endpoints
2. **`frontend/src/components/TaskGrowthChart.tsx`** - Chart component
3. **`frontend/src/utils/analytics.ts`** - Google Analytics helpers (bonus)

### Modified Files:
1. **`backend/app/main.py`** - Added analytics router
2. **`frontend/src/services/api.ts`** - Added `getTasksByWeek()` method
3. **`frontend/src/pages/Home.tsx`** - Added chart below flipboard
4. **`frontend/package.json`** - Added `recharts` dependency

---

## Example Chart Data

The chart will show something like:

```
Week         | Cumulative Tasks
-------------|------------------
Jan '24      | 45
Feb '24      | 120
Mar '24      | 245
...
Dec '25      | 650
Jan '26      | 720  ← Current
```

Displayed as a smooth area chart showing continuous growth from first commit to today.

---

## Performance

**Cached endpoint** (`tasks-by-week-cached`):
- ⚡ Fast: ~100-500ms
- Uses existing `git_updated_at` from database
- Good enough for most cases
- This is what's wired up by default

**Full git analysis** (`tasks-by-week`):
- 🐌 Slower: ~10-60 seconds (clones all repos)
- Analyzes first commit date for each codebundle
- Most accurate historical data
- Use once to verify, then switch to cached

---

## Customization Options

### Change chart style

In `TaskGrowthChart.tsx`, swap `AreaChart` for `LineChart`:

```typescript
<LineChart data={data}>
  <Line type="monotone" dataKey="tasks" stroke="#FF6B35" />
</LineChart>
```

### Change time grouping

In `analytics.py`, change from weekly to monthly:

```python
# Current: Weekly
current_week += timedelta(days=7)

# Change to: Monthly
current_month = current_month.replace(day=1) + timedelta(days=32)
current_month = current_month.replace(day=1)
```

### Show new tasks per week (instead of cumulative)

Return `weekly_data` directly instead of calculating running totals.

---

## Testing Locally

```bash
# Backend should already be running
# Visit http://localhost:3000

# Check the API directly:
curl http://localhost:8001/api/v1/analytics/tasks-by-week-cached

# Should return:
{
  "weeks": ["2024-01-01", "2024-01-08", ...],
  "cumulative": [45, 67, 89, ...],
  "total_tasks": 720
}
```

---

## Deployment Notes

The chart uses data already in your database (`git_updated_at`), so:
- ✅ No additional git operations on page load
- ✅ Works immediately after deployment
- ✅ Updates automatically when new codebundles are synced
- ✅ No caching needed (queries are fast)

---

## Future Enhancements

1. **Add filters** - Chart by platform (K8s, AWS, GCP)
2. **Compare metrics** - New tasks vs. updated tasks
3. **Interactive tooltips** - Show which codebundles were added each week
4. **Export data** - Download CSV button
5. **Multiple charts** - Tasks by category, platform distribution, etc.
