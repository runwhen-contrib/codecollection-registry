# Task scheduling and background job management

# Import task modules so Celery can discover them
from . import (
    sync_tasks,
    registry_tasks,
    data_population_tasks,
    ai_enhancement_tasks,
    workflow_tasks,
    task_monitoring,
    mcp_tasks,  # MCP server indexing tasks
    parse_user_vars_only  # User variables parsing
)

