#!/bin/bash

# Job Failure Checker Script
# Usage: ./check_job_failures.sh [option]
# Options: failed, pending, recent, logs, specific <task_id>

set -e

DB_CONTAINER="registry-database"
DB_USER="user"
DB_NAME="codecollection_registry"
API_TOKEN="admin-dev-token"
API_URL="http://localhost:8001/api/v1"

function check_failed_tasks() {
    echo "=== FAILED TASKS ==="
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
    SELECT 
        task_id, 
        task_name, 
        status, 
        error_message, 
        created_at 
    FROM task_executions 
    WHERE status = 'FAILURE' 
    ORDER BY created_at DESC 
    LIMIT 10;"
}

function check_pending_tasks() {
    echo "=== STUCK PENDING TASKS ==="
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
    SELECT 
        task_id, 
        task_name, 
        status, 
        created_at,
        NOW() - created_at as age
    FROM task_executions 
    WHERE status = 'PENDING' 
    AND created_at < NOW() - INTERVAL '10 minutes'
    ORDER BY created_at DESC;"
}

function check_recent_tasks() {
    echo "=== RECENT TASK SUMMARY ==="
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
    SELECT 
        task_name, 
        status, 
        COUNT(*) as count,
        MAX(created_at) as latest
    FROM task_executions 
    WHERE created_at > NOW() - INTERVAL '24 hours' 
    GROUP BY task_name, status 
    ORDER BY task_name, status;"
}

function check_worker_logs() {
    echo "=== RECENT WORKER ERRORS ==="
    docker logs registry-worker --tail 100 | grep -E "(ERROR|FAILURE|Exception|Traceback)" -A 3 -B 1 || echo "No recent errors found in worker logs"
}

function check_specific_task() {
    local task_id=$1
    if [ -z "$task_id" ]; then
        echo "Please provide a task ID"
        exit 1
    fi
    
    echo "=== TASK DETAILS: $task_id ==="
    docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
    SELECT 
        task_id,
        task_name,
        status,
        error_message,
        traceback,
        parameters,
        created_at,
        completed_at
    FROM task_executions 
    WHERE task_id = '$task_id';"
}

function show_usage() {
    echo "Usage: $0 [option]"
    echo "Options:"
    echo "  failed     - Show failed tasks"
    echo "  pending    - Show stuck pending tasks"
    echo "  recent     - Show recent task summary"
    echo "  logs       - Show recent worker errors"
    echo "  specific <task_id> - Show details for specific task"
    echo "  all        - Show all of the above (default)"
}

# Main logic
case "${1:-all}" in
    "failed")
        check_failed_tasks
        ;;
    "pending")
        check_pending_tasks
        ;;
    "recent")
        check_recent_tasks
        ;;
    "logs")
        check_worker_logs
        ;;
    "specific")
        check_specific_task "$2"
        ;;
    "all")
        check_failed_tasks
        echo ""
        check_pending_tasks
        echo ""
        check_recent_tasks
        echo ""
        check_worker_logs
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
