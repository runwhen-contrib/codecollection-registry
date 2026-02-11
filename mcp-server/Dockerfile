# RunWhen MCP Server Dockerfile
# Thin, stateless MCP server — all data comes from the Registry API.
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (lightweight — no ML, no browser, no DB drivers)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app

USER mcp

# HTTP server for Kubernetes/production deployments
CMD ["python", "server_http.py"]
