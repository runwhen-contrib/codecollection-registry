"""
Celery application configuration - Single source of truth for all tasks
Supports both regular Redis and Redis Sentinel
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

def _configure_broker_url():
    """Configure broker URL for Redis or Redis Sentinel"""
    if settings.REDIS_SENTINEL_HOSTS and not settings.REDIS_URL.startswith('redis://'):
        # Use Redis Sentinel configuration
        # Celery format: sentinel://host1:port1;host2:port2;host3:port3
        # We need to convert comma-separated to semicolon-separated
        sentinel_hosts = settings.REDIS_SENTINEL_HOSTS.replace(',', ';')
        auth = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
        broker_url = f"sentinel://{auth}{sentinel_hosts}"
        
        # Set transport options for Sentinel
        transport_options = {
            'master_name': settings.REDIS_SENTINEL_MASTER,
            'sentinel_kwargs': {
                'socket_timeout': 0.1,
                'socket_connect_timeout': 0.1,
                'socket_keepalive': True,
            },
            'db': settings.REDIS_DB,
        }
        
        return broker_url, transport_options
    else:
        # Use regular Redis URL
        return settings.REDIS_URL, {}

broker_url, transport_options = _configure_broker_url()

# Create Celery app - single instance for entire application
celery_app = Celery(
    "codecollection_registry",
    broker=broker_url,
    backend=broker_url,
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
celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 30 * 60,  # 30 minutes
    "task_soft_time_limit": 25 * 60,  # 25 minutes
    "worker_prefetch_multiplier": 1,
    "worker_max_tasks_per_child": 1000,
    "task_acks_late": True,
    "worker_disable_rate_limits": True,
}

# Add transport options if using Sentinel
if transport_options:
    celery_config["broker_transport_options"] = transport_options
    celery_config["result_backend_transport_options"] = transport_options

celery_app.conf.update(**celery_config)

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
