#!/bin/bash

# Start Celery worker for background tasks
echo "Starting Celery worker..."

# Start the worker
celery -A app.tasks.data_population_tasks worker --loglevel=info --concurrency=2

