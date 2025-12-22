#!/bin/bash
# Daily indexing script for CodeCollection semantic search
# Run this via cron: 0 2 * * * /path/to/daily_index.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${MCP_DIR}/data/indexer.log"

cd "$MCP_DIR"

echo "========================================" >> "$LOG_FILE"
echo "Starting daily index at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Source Azure credentials if available
if [ -f "$MCP_DIR/az.secret" ]; then
    set -a
    source "$MCP_DIR/az.secret"
    set +a
    echo "Using Azure OpenAI for embeddings" >> "$LOG_FILE"
    python indexer.py >> "$LOG_FILE" 2>&1
else
    echo "Using local embeddings (no Azure credentials)" >> "$LOG_FILE"
    python indexer.py --local >> "$LOG_FILE" 2>&1
fi

echo "Indexing completed at $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Optional: Restart services if running in Docker
if command -v docker-compose &> /dev/null; then
    if docker-compose ps | grep -q "runwhen-mcp-http"; then
        echo "Restarting MCP services..." >> "$LOG_FILE"
        docker-compose restart mcp-http web-client >> "$LOG_FILE" 2>&1
    fi
fi

