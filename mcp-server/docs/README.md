# MCP Server Documentation

Welcome to the MCP (Model Context Protocol) Server documentation. This directory contains all project documentation.

## 📚 Documentation Index

### Getting Started

- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development setup, testing, and contribution guide

### Main Documentation

For general usage and setup, see the main **[README.md](../README.md)** in the project root.

### Archived Documentation

The [`archive/`](archive/) directory contains older documentation for historical reference:
- `DEPLOYMENT_FIX.md` - Historical deployment fix notes
- `WEB_CLIENT_SUMMARY.md` - Old web client implementation notes

## 🏗️ Project Architecture

```
mcp-server/
├── server.py          # MCP protocol server (stdio)
├── server_http.py     # HTTP API server
├── indexer.py         # Embeddings indexer
├── tools/             # MCP tool implementations
│   ├── codebundle_tools.py
│   ├── collection_tools.py
│   ├── documentation_tools.py
│   └── library_tools.py
├── utils/             # Core utilities
│   ├── vector_store.py
│   ├── embeddings.py
│   ├── semantic_search.py
│   └── data_loader.py
├── docs/              # Documentation (this directory)
└── README.md          # Main project overview
```

## 🚀 Quick Start

1. **Setup:**
   ```bash
   pip install -r requirements.txt
   python indexer.py
   ```

2. **Run Server:**
   ```bash
   # MCP protocol server
   python server.py
   
   # HTTP API server
   python server_http.py
   ```

3. **Development:** See [DEVELOPMENT.md](DEVELOPMENT.md)

## 🔧 Available Tools

The MCP server provides these semantic search tools:

- `find_codebundle` - Search for codebundles by description/purpose
- `find_codecollection` - Search for collections by name/purpose
- `keyword_usage_help` - Get help with keyword usage and syntax
- `find_documentation` - Search documentation sources
- `search_codebundles` - Advanced codebundle search with filters

## 📦 Data Sources

- **CodeBundles** - Parsed from `codecollections.yaml`
- **Documentation** - Indexed from `docs.yaml`
- **Embeddings** - Stored in ChromaDB (`chroma_db/`)

## 🔄 Indexing

The indexer updates embeddings for all sources:

```bash
# Full re-index
python indexer.py

# Documentation only
python indexer.py --docs-only

# Scheduled via cron
./scripts/daily_index.sh
```

## 🔗 Integration

The MCP server integrates with:
- **cc-registry-v2** - Main registry backend calls MCP tools for chat queries
- **Docker Compose** - Runs as service in `cc-registry-v2/docker-compose.yml`
- **Celery Tasks** - Automated indexing via `app.tasks.mcp_tasks`

## 📝 Contributing to Documentation

When adding new documentation:
1. Create files in `docs/` directory (not project root)
2. Use clear, descriptive names
3. Update this README.md index
4. Follow existing documentation style

**Do NOT create:**
- Temporary fix files (`*-FIX.md`, `*-SUMMARY.md`)
- Duplicate documentation
- Documentation in project root (except `README.md`)

Move old/deprecated docs to `docs/archive/`.

---

**Last Updated:** 2026-01-24
