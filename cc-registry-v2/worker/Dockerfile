FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend (workers use same dependencies)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd --create-home --shell /bin/bash worker \
    && chown -R worker:worker /app
USER worker

# Note: Application code is mounted from backend via volume
# This allows workers to share the same codebase as the API

# Default command (overridden in docker-compose)
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"]

