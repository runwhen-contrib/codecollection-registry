# RunWhen MCP Server Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
# 1. PyTorch CPU-only first to avoid pulling ~4GB of NVIDIA/CUDA libraries.
# 2. crawl4ai for headless browser-based doc crawling (clean markdown output).
# 3. Install Playwright chromium browser for crawl4ai.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium && \
    rm -rf /root/.cache/pip

# Copy application code
COPY . .

# Create non-root user and give access to Playwright browser cache
RUN useradd -m -u 1000 mcp && \
    chown -R mcp:mcp /app && \
    # Playwright stores browsers in /root/.cache or /home/user/.cache
    # Move the Playwright browser cache to a shared location
    mkdir -p /opt/playwright && \
    cp -r /root/.cache/ms-playwright/* /opt/playwright/ 2>/dev/null || true && \
    chown -R mcp:mcp /opt/playwright

# Set Playwright browser path for non-root user
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

USER mcp

# Default command (can be overridden)
# Use server_http.py for Kubernetes/production deployments
# Use server.py for stdio/desktop integration
CMD ["python", "server_http.py"]

