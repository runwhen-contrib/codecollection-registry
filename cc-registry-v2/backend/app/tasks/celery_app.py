"""
Celery application configuration - Single source of truth for all tasks
Supports both regular Redis and Redis Sentinel
Schedules are loaded from schedules.yaml in the project root
"""
from celery import Celery
from celery.schedules import crontab, schedule
from celery.signals import task_prerun, task_postrun, task_success, task_failure
from app.core.config import settings
import yaml
import os
import logging

logger = logging.getLogger(__name__)

def _configure_broker_url():
    """Configure broker URL for Redis or Redis Sentinel.

    Precedence rules:
      1. If REDIS_SENTINEL_HOSTS is set, always use the sentinel:// scheme
         with proper transport_options. This wins even when REDIS_URL is
         also set, because Helm charts commonly set both and silently
         speaking Redis protocol to a Sentinel endpoint (port 26379) is a
         fail-closed nightmare: Sentinel rejects every non-HELLO command,
         which makes the entire Celery beat/worker fan unable to dispatch.
      2. Otherwise fall back to REDIS_URL.

    Guardrail: if REDIS_URL targets port 26379 (the standard Sentinel
    port) and REDIS_SENTINEL_HOSTS is *not* set, refuse to start with a
    clear error — we'd rather crash fast than connect, fail every
    command, and pretend everything is fine.
    """
    if settings.REDIS_SENTINEL_HOSTS:
        if settings.REDIS_URL:
            logger.info(
                "Both REDIS_SENTINEL_HOSTS and REDIS_URL are set; "
                "preferring Sentinel. (Remove REDIS_URL from the deployment "
                "to silence this notice.)"
            )

        # Parse and convert to semicolon-separated (Kombu format).
        sentinel_hosts = [hp.strip() for hp in settings.REDIS_SENTINEL_HOSTS.split(',')]
        sentinel_hosts_str = ';'.join(sentinel_hosts)
        password_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""

        # sentinel:// URL with master_name and db in transport_options.
        broker_url = f"sentinel://{password_part}{sentinel_hosts_str}"

        # Ensure REDIS_DB is an int; tolerate stringy env-var inputs.
        try:
            redis_db = int(settings.REDIS_DB) if isinstance(settings.REDIS_DB, (str, int)) else 0
        except (ValueError, TypeError):
            logger.warning(f"Invalid REDIS_DB value '{settings.REDIS_DB}', defaulting to 0")
            redis_db = 0

        transport_options = {
            'master_name': settings.REDIS_SENTINEL_MASTER,
            'db': redis_db,
            'sentinel_kwargs': {
                'socket_timeout': 1.0,
                'socket_connect_timeout': 1.0,
                'password': settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            },
        }
        return broker_url, transport_options

    # Guardrail: catch REDIS_URL=redis://...:26379/... when Sentinel
    # hosts are unset. That's the misconfiguration that causes "Only
    # HELLO messages are accepted by Sentinel instances" in worker logs.
    if settings.REDIS_URL and ':26379/' in settings.REDIS_URL:
        raise RuntimeError(
            "REDIS_URL points at port 26379 (standard Sentinel port) but "
            "REDIS_SENTINEL_HOSTS is not set. Either set REDIS_SENTINEL_HOSTS "
            "(recommended — the broker will speak Sentinel protocol properly), "
            "or change REDIS_URL to target the actual Redis master/replica "
            "on its data-plane port (typically 6379). Refusing to start to "
            "avoid silently producing broker errors on every task dispatch."
        )

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
        "app.tasks.task_monitoring",
        "app.tasks.workflow_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.indexing_tasks",
        "app.tasks.image_sync_tasks",
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
    # Exception handling configuration
    "result_extended": True,  # Store extended task result metadata including exceptions
    "result_serializer": "json",
    "result_accept_content": ["json"],
    # Store exception info properly
    "task_send_sent_event": True,
    "task_store_errors_even_if_ignored": True,
}

# Add transport options if using Sentinel
if transport_options:
    celery_config["broker_transport_options"] = transport_options
    celery_config["result_backend_transport_options"] = transport_options

celery_app.conf.update(**celery_config)

# Load schedules from YAML file
def load_schedules_from_yaml():
    """Load schedule configuration from schedules.yaml.

    Path resolution:
      1. settings.SCHEDULES_FILE — usually /app/schedules.yaml in containers
         (set via env var SCHEDULES_FILE in k8s to point at a directory-mounted
         ConfigMap path like /etc/cc-registry/schedules/schedules.yaml).
      2. Relative fallback for running directly from a source checkout.
      3. /workspaces dev fallback for the in-tree dev container.
    """
    possible_paths = [
        settings.SCHEDULES_FILE,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'schedules.yaml'),
        '/workspaces/codecollection-registry/cc-registry-v2/schedules.yaml',
    ]

    schedules_file = None
    for path in possible_paths:
        if os.path.exists(path):
            schedules_file = path
            break
    
    if not schedules_file:
        logger.error(f"schedules.yaml not found in any of these locations: {possible_paths}")
        logger.warning("Using empty beat schedule - no scheduled tasks will run!")
        return {}
    
    try:
        with open(schedules_file, 'r') as f:
            config = yaml.safe_load(f)

        # `yaml.safe_load` returns None for empty files or files containing
        # only comments. Treat that as "no schedules" instead of crashing
        # with `'NoneType' object has no attribute 'get'` (which would
        # leave the scheduler running with a silent empty beat schedule).
        if config is None:
            logger.warning(
                f"{schedules_file} is empty or contains only comments; "
                f"using empty beat schedule"
            )
            return {}

        logger.info(f"Loaded schedules from {schedules_file}")

        beat_schedule = {}
        # Tolerate both a missing `schedules:` key and an explicit `schedules: null`.
        schedules_list = config.get('schedules') or []
        for schedule_config in schedules_list:
            # Skip empty list items (e.g. a `- ` with nothing after it).
            if not schedule_config:
                continue
            if not schedule_config.get('enabled', True):
                logger.info(f"Skipping disabled schedule: {schedule_config['name']}")
                continue
            
            name = schedule_config['name']
            task = schedule_config['task']
            schedule_type = schedule_config.get('schedule_type', 'crontab')
            
            # Create schedule object based on type
            if schedule_type == 'crontab':
                crontab_config = schedule_config.get('crontab', {})
                
                # Convert None to '*' for crontab fields
                def get_cron_val(key, default='*'):
                    val = crontab_config.get(key)
                    return default if val is None else val
                
                schedule_obj = crontab(
                    minute=get_cron_val('minute', 0),
                    hour=get_cron_val('hour', '*'),
                    day_of_week=get_cron_val('day_of_week', '*'),
                    day_of_month=get_cron_val('day_of_month', '*'),
                    month_of_year=get_cron_val('month_of_year', '*'),
                )
            elif schedule_type == 'interval':
                interval_config = schedule_config.get('interval', {})
                seconds = interval_config.get('seconds', 0)
                minutes = interval_config.get('minutes', 0)
                hours = interval_config.get('hours', 0)
                days = interval_config.get('days', 0)
                
                total_seconds = seconds + (minutes * 60) + (hours * 3600) + (days * 86400)
                schedule_obj = schedule(run_every=total_seconds)
            else:
                logger.warning(f"Unknown schedule type '{schedule_type}' for {name}, skipping")
                continue
            
            beat_schedule[name] = {
                'task': task,
                'schedule': schedule_obj,
            }
            
            logger.info(f"Registered schedule: {name} -> {task}")
        
        logger.info(f"Loaded {len(beat_schedule)} schedules from {schedules_file}")
        return beat_schedule
        
    except Exception as e:
        logger.error(f"Error loading schedules from {schedules_file}: {e}")
        logger.warning("Using empty beat schedule due to error")
        return {}

# Load schedules from YAML
celery_app.conf.beat_schedule = load_schedules_from_yaml()

# Autodiscover tasks
celery_app.autodiscover_tasks()


# ============================================================================
# Task Monitoring Signals - Automatically track all task executions
# ============================================================================

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra_kwargs):
    """Signal handler for when a task starts - create task execution record"""
    try:
        from app.services.task_monitoring_service import task_monitor
        
        # Determine task type from task name
        task_name = task.name if task else sender.name if sender else "unknown"
        task_type = "scheduled" if "scheduled" in task_name else "manual"
        
        # Get triggered_by from kwargs if available
        triggered_by = kwargs.get('triggered_by', 'system') if kwargs else 'system'
        
        # Create task record
        task_monitor.create_task_record(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            parameters={'args': args, 'kwargs': kwargs} if args or kwargs else {},
            triggered_by=triggered_by
        )
        logger.debug(f"Created task record for {task_id} ({task_name})")
        
    except Exception as e:
        # Don't fail the task if monitoring fails
        logger.error(f"Failed to create task record in prerun: {e}")


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Signal handler for when a task succeeds - update task record"""
    try:
        from app.services.task_monitoring_service import task_monitor
        
        task_id = kwargs.get('task_id') or (sender.request.id if sender and hasattr(sender, 'request') else None)
        if task_id:
            task_monitor.update_task_status(task_id)
            logger.debug(f"Updated task record for {task_id} (SUCCESS)")
    except Exception as e:
        logger.error(f"Failed to update task record in success handler: {e}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    """Signal handler for when a task fails - update task record"""
    try:
        from app.services.task_monitoring_service import task_monitor
        
        if task_id:
            task_monitor.update_task_status(task_id)
            logger.debug(f"Updated task record for {task_id} (FAILURE)")
    except Exception as e:
        logger.error(f"Failed to update task record in failure handler: {e}")


logger.info("Celery app configured with task monitoring signals")
