# Job Failure Debugging Guide

## Where to Find Job Logs and Failure Information

### 1. **Database Task Execution Table** (Most Detailed)
The `task_executions` table stores comprehensive information about all tasks:

```sql
-- Check for failed tasks with full error details
SELECT 
    task_id, 
    task_name, 
    status, 
    error_message, 
    traceback, 
    created_at, 
    completed_at,
    parameters
FROM task_executions 
WHERE status = 'FAILURE' 
ORDER BY created_at DESC 
LIMIT 10;

-- Check for stuck pending tasks
SELECT 
    task_id, 
    task_name, 
    status, 
    created_at,
    parameters
FROM task_executions 
WHERE status = 'PENDING' 
AND created_at < NOW() - INTERVAL '10 minutes'
ORDER BY created_at DESC;
```

**Access via Docker:**
```bash
docker exec registry-database psql -U user -d codecollection_registry -c "SELECT task_id, task_name, status, error_message, created_at FROM task_executions WHERE status = 'FAILURE' ORDER BY created_at DESC LIMIT 5;"
```

### 2. **Task Management API** (Programmatic Access)
Use the backend API to get task details with error information:

```bash
# Get failed tasks
curl -s "http://localhost:8001/api/v1/task-management/tasks?status=FAILURE&limit=10" \
  -H "Authorization: Bearer admin-dev-token" | jq '.'

# Get specific task details including traceback
curl -s "http://localhost:8001/api/v1/task-management/tasks/{task_id}" \
  -H "Authorization: Bearer admin-dev-token" | jq '.'
```

### 3. **Celery Worker Container Logs** (Real-time Debugging)
```bash
# View recent worker logs
docker logs registry-worker --tail 100

# Follow worker logs in real-time
docker logs registry-worker --follow

# Search for errors in worker logs
docker logs registry-worker --tail 500 | grep -E "(ERROR|FAILURE|Exception|Traceback)" -A 5 -B 2
```

### 4. **Flower Web UI** (Limited Log Visibility)
- **URL:** http://localhost:5555
- **Limitation:** Flower doesn't show detailed logs or tracebacks by default
- **What it shows:** Task status, basic results, worker info

### 5. **Backend Application Logs**
```bash
# Check backend container logs
docker logs registry-backend --tail 100

# Follow backend logs
docker logs registry-backend --follow
```

## Current Issues Identified

### 1. **Celery Backend Error**
There's a Celery backend serialization issue causing this error:
```
ValueError: Exception information must include the exception type
```

This prevents proper error reporting in some cases.

### 2. **AI Enhancement Tasks Stuck**
Several AI enhancement tasks are stuck in PENDING status because:
- No AI configuration is active/enabled
- Tasks complete successfully but report "No pending CodeBundles found"

## Recommended Debugging Workflow

1. **Check Database First:**
   ```bash
   docker exec registry-database psql -U user -d codecollection_registry -c "
   SELECT task_name, status, COUNT(*) as count 
   FROM task_executions 
   WHERE created_at > NOW() - INTERVAL '24 hours' 
   GROUP BY task_name, status 
   ORDER BY task_name, status;"
   ```

2. **Get Detailed Error for Specific Failed Task:**
   ```bash
   docker exec registry-database psql -U user -d codecollection_registry -c "
   SELECT task_id, error_message, traceback 
   FROM task_executions 
   WHERE status = 'FAILURE' 
   AND task_id = 'your-task-id-here';"
   ```

3. **Check Worker Logs for Real-time Issues:**
   ```bash
   docker logs registry-worker --tail 200 | grep -E "(ERROR|Exception)" -A 10 -B 2
   ```

4. **Use Task Management API for Programmatic Access:**
   ```bash
   curl -s "http://localhost:8001/api/v1/task-management/tasks?limit=20" \
     -H "Authorization: Bearer admin-dev-token" | \
     jq '.tasks[] | select(.status == "FAILURE") | {task_name, error_message, traceback}'
   ```

## Fixing Common Issues

### Enable Proper AI Configuration
If AI enhancement tasks are failing:
1. Ensure you have an active AI configuration
2. Check that the API key is valid
3. Verify Azure OpenAI endpoint settings (if using Azure)

### Clear Stuck Tasks
```sql
-- Mark old pending tasks as failed
UPDATE task_executions 
SET status = 'FAILURE', 
    error_message = 'Task timeout - stuck in pending state',
    completed_at = NOW()
WHERE status = 'PENDING' 
AND created_at < NOW() - INTERVAL '1 hour';
```
