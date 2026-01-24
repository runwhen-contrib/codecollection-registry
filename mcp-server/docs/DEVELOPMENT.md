# Quick Reference - RunWhen MCP Server

## 🚀 Minimal Setup

```bash
cd /workspaces/codecollection-registry/mcp-server

task build    # Build image
task start    # Start server + web client
task logs     # View logs
task stop     # Stop server
```

**That's it!** 
- **Web Client** (AI-powered): http://localhost:8080
- **API Server**: http://localhost:8000

## All Commands

| Command | What it does |
|---------|--------------|
| `task build` | Build Docker image |
| `task start` | Start HTTP server + Web Client |
| `task stop` | Stop all services |
| `task logs` | View logs |
| `task test` | Run tests |
| `task clean` | Clean up |

## Quick Access

**Web Client (AI-powered):** http://localhost:8080  
**API Server:** http://localhost:8000  
**API Docs:** http://localhost:8000/docs

## Test the API

```bash
# Health check
curl http://localhost:8000/health

# API docs (browser)
open http://localhost:8000/docs

# Web client (browser)
open http://localhost:8080
```

## 📋 Most Common Commands

| Command | Task | Make | Description |
|---------|------|------|-------------|
| Setup | `task setup` | `make setup` | First-time setup |
| Test | `task test` | `make test` | Run all tests |
| Demo | `task demo` | `make demo` | First query demo |
| Interactive | `task interactive` | `make interactive` | Interactive mode ⭐ |
| Clean | `task clean` | `make clean` | Clean temp files |
| Help | `task` | `make` | Show all commands |

## 🔧 Task Commands Quick Reference

### Setup & Install
```bash
task setup          # Create venv + install deps
task install        # Update dependencies
task clean:all      # Clean everything + venv
```

### Testing
```bash
task test           # Run tests
task demo           # First query demo
task dev            # Test + interactive
task ci             # Run CI checks
```

### Running
```bash
task interactive    # Interactive client ⭐
task server         # MCP server (stdio)
task run            # Alias for interactive
```

### Data
```bash
task data:validate  # Validate JSON files
task data:stats     # Show statistics
task data:sync      # Sync from DB (future)
```

### Health & Info
```bash
task health         # Health check
task info           # Project info
task version        # Show versions
task docs           # Documentation links
```

### Shortcuts
```bash
task t              # = task test
task i              # = task interactive
task s              # = task server
```

## 📁 Important Files

| File | Purpose |
|------|---------|
| `Taskfile.yml` | Task automation |
| `Makefile` | Fallback for non-Task users |
| `server.py` | Main MCP server |
| `interactive_client.py` | Interactive CLI |
| `client_test.py` | Test suite |
| `requirements.txt` | Python dependencies |
| `data/*.json` | Data files |

## 🎯 Common Workflows

### First Time
```bash
task setup
task demo
task interactive
```

### Daily Dev
```bash
task test
task interactive
```

### Before Commit
```bash
task ci
task clean
```

### Troubleshoot
```bash
python verify_setup.py  # Check setup
task health             # Health check
task clean:all          # Nuclear option
task setup              # Recreate
```

## 📚 Documentation

| File | What's Inside |
|------|---------------|
| `INDEX.md` | Navigation hub |
| `GETTING_STARTED.md` | Quick start guide |
| `README.md` | Complete docs |
| `TASKFILE.md` | Taskfile guide |
| `PROJECT_OVERVIEW.md` | Architecture |

## 🐛 Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| `task: command not found` | Use `make` instead or install Task |
| Virtual env not found | `task setup` |
| Module not found | `task install` |
| JSON errors | `task data:validate` |
| Tests failing | `task health` then `task clean:all && task setup` |

## 💡 Pro Tips

1. **Use Task**: Faster and more features than Make
   ```bash
   # Install Task
   sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d
   ```

2. **Shortcuts**: Use `task t`, `task i`, `task s` for speed

3. **Watch Mode**: Auto-run tests on file changes
   ```bash
   task dev:watch  # requires entr
   ```

4. **Check Health**: Before starting work
   ```bash
   task health
   ```

5. **Verify Setup**: If anything seems broken
   ```bash
   python verify_setup.py
   ```

## 🔗 Related Systems

### cc-registry-v2 Integration
```bash
# Terminal 1: Start cc-registry-v2
cd ../../cc-registry-v2
task start

# Terminal 2: Run MCP server  
cd ../mcp-server
task interactive
```

Future: `task data:sync` will pull from cc-registry-v2 database

## 📞 Getting Help

```bash
task              # List all tasks
task info         # Project information
task docs         # Documentation links
python verify_setup.py  # Check setup
```

Or check: `INDEX.md` → `GETTING_STARTED.md` → `README.md`

---

**Most Used Commands:**
1. `task setup` - First time only
2. `task test` - Run tests
3. `task interactive` - Main interface ⭐
4. `task demo` - See it in action
5. `task health` - Check everything

**Remember:** You can use `make` instead of `task` for all commands!

