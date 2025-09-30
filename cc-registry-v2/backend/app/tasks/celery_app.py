"""
Celery application configuration - Single source of truth for all tasks
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app - single instance for entire application
celery_app = Celery(
    "codecollection_registry",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.data_tasks",
        "app.tasks.sync_tasks", 
        "app.tasks.registry_tasks",
        "app.tasks.ai_enhancement_tasks",
        "app.tasks.data_population_tasks",
        "app.tasks.task_monitoring"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    worker_disable_rate_limits=True,
)

# Consolidated scheduled tasks from all modules
celery_app.conf.beat_schedule = {
    # From registry_tasks.py
    'validate-yaml-seed-daily': {
        'task': 'app.tasks.registry_tasks.validate_yaml_seed_task',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'sync-collections-daily': {
        'task': 'app.tasks.registry_tasks.sync_all_collections_task',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'parse-codebundles-daily': {
        'task': 'app.tasks.registry_tasks.parse_all_codebundles_task',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'enhance-codebundles-weekly': {
        'task': 'app.tasks.registry_tasks.enhance_all_codebundles_task',
        'schedule': crontab(hour=4, minute=0, day_of_week=1),  # Weekly on Monday at 4 AM
    },
    'generate-metrics-daily': {
        'task': 'app.tasks.registry_tasks.generate_metrics_task',
        'schedule': crontab(hour=5, minute=0),  # Daily at 5 AM
    },
    
    # From data_population_tasks.py
    'update-statistics-hourly': {
        'task': 'app.tasks.data_population_tasks.update_collection_statistics_task',
        'schedule': crontab(minute=0),  # Every hour
    },
    
    # From sync_tasks.py
    'health-check': {
        'task': 'app.tasks.sync_tasks.health_check_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'scheduled-sync': {
        'task': 'app.tasks.sync_tasks.scheduled_sync_task',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    
    # From task_monitoring.py
    'cleanup-old-tasks': {
        'task': 'app.tasks.task_monitoring.cleanup_old_tasks_task',
        'schedule': crontab(hour=0, minute=30),  # Daily at 12:30 AM
    },
    'health-check-tasks': {
        'task': 'app.tasks.task_monitoring.health_check_tasks_task',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}

# Autodiscover tasks
celery_app.autodiscover_tasks()
