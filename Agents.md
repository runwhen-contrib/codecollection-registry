# AI Agent Guidelines for CodeCollection Registry

## 📋 General Rules

### Documentation File Policy

**Allowed:** One documentation file per major feature in the `/docs/` directory
- ✅ `docs/chat.md` - Chat system architecture and usage
- ✅ `docs/chat-debug.md` - Chat debugging tools and procedures
- ✅ `docs/admin-panel.md` - Admin panel features
- ✅ `docs/codebundles.md` - CodeBundle management

**NOT Allowed:** Temporary fix/summary/guide files in root directory
- ❌ `CHAT-FOLLOWUP-FIX.md` (temporary fix documentation)
- ❌ `TESTING-THE-FIX.md` (temporary testing guide)
- ❌ `CHAT-DEBUG-GUIDE.md` (duplicate feature doc)
- ❌ `ISSUE-12345-FIX.md` (issue-specific docs)
- ❌ Any `*-SUMMARY.md`, `*-FIX.md`, `*-GUIDE.md`, `*-UPDATE.md` files

**Guidelines:**
1. **One doc per feature** - Keep feature documentation consolidated
2. **Update existing docs** - Don't create new files for updates/fixes
3. **Use `/docs/` directory** - Keep root clean
4. **Descriptive naming** - Use feature names, not actions (e.g., `chat.md` not `chat-system-guide.md`)

**When documenting fixes/changes:**
- Update the relevant feature doc (e.g., add a "Known Issues" section to `docs/chat.md`)
- Add inline code comments at the fix location
- Update this `Agents.md` file if it's an architectural change

**Only create NEW documentation when:**
- User explicitly requests it
- It's a new major feature that doesn't fit existing docs
- It's a deployment/ops guide that teams will reference repeatedly

---

## 🏗️ Project Structure

### CodeCollection Registry v2 Architecture

```
codecollection-registry/
├── docs/             # Feature documentation (one file per feature)
│   ├── chat.md       # Chat system architecture & troubleshooting
│   ├── chat-debug.md # Chat debugging tools & procedures
│   └── ...
├── cc-registry-v2/
│   ├── backend/      # FastAPI backend
│   │   ├── app/
│   │   │   ├── routers/  # API endpoints
│   │   │   │   ├── mcp_chat.py      # Main chat endpoint with MCP integration
│   │   │   │   ├── chat_debug.py    # Debug endpoints for chat quality
│   │   │   │   └── ...
│   │   │   ├── services/ # Business logic
│   │   │   ├── models/   # SQLAlchemy models
│   │   │   └── core/     # Config, dependencies
│   │   └── ...
│   ├── frontend/     # React + TypeScript + Material-UI
│   │   ├── src/
│   │   │   ├── pages/    # Main page components
│   │   │   │   ├── ChatDebug.tsx    # Hidden admin UI for chat debugging
│   │   │   │   └── ...
│   │   │   ├── components/
│   │   │   └── services/
│   │   └── ...
│   └── docker-compose.yml
└── Agents.md         # AI agent guidelines (this file)
```

---

## 📚 Feature Documentation

Detailed feature documentation is in the `/docs/` directory:

- **[docs/chat.md](docs/chat.md)** - Chat system architecture, follow-up detection, troubleshooting
- **[docs/chat-debug.md](docs/chat-debug.md)** - Debug console features, API endpoints, use cases

Refer to these docs for:
- Implementation details
- Known issues and fixes
- API specifications
- Troubleshooting procedures
- Testing strategies

---

## 🛠️ Development Guidelines

### Frontend Changes
- **Port:** Frontend runs on http://localhost:3000
- **API Base URL:** `http://localhost:8001/api/v1` (configured in `frontend/src/services/api.ts`)
- **Auth:** Use `dev@example.com` / `password` for admin login
- **Protected Routes:** Use `<ProtectedRoute requiredRole="admin">` wrapper

### Backend Changes
- **Port:** Backend runs on http://localhost:8001
- **API Prefix:** All routes under `/api/v1/`
- **Database:** PostgreSQL via SQLAlchemy ORM
- **Async:** Use `async`/`await` for all endpoint handlers
- **Logging:** Use `logger.info()`, `logger.error()` for debugging

### Docker & Services
- **Restart Backend:** `docker-compose restart backend`
- **Restart with Env Changes:** `docker-compose up --force-recreate` (required for `env_file` changes)
- **View Logs:** `docker-compose logs -f backend`
- **Services:**
  - `backend` - FastAPI app
  - `worker` - Celery background tasks
  - `scheduler` - Celery beat scheduler
  - `frontend` - React dev server (or nginx in prod)
  - `db` - PostgreSQL
  - `redis` - Cache & Celery broker

### Environment Variables
- **Location:** `az.secret` (not committed, use `export VAR=value` format)
- **Key Vars:**
  - `AI_SERVICE_PROVIDER=azure-openai`
  - `AI_ENHANCEMENT_ENABLED=true`
  - `AZURE_OPENAI_*` - Azure OpenAI credentials
- **Loading:** Add to `env_file` in `docker-compose.yml` for worker/scheduler

---

## 🧪 Testing & Debugging

### Chat Quality Debugging
- **UI:** http://localhost:3000/chat-debug (requires admin login)
- **Features:** Filtering, sorting, test queries, quality analysis
- **📖 Full guide:** See [docs/chat-debug.md](docs/chat-debug.md)

### Quick Test
```bash
# Test a query
curl -X POST http://localhost:8001/api/v1/chat/debug/test-query \
  -H "Content-Type: application/json" \
  -d '{"question": "show me the link", "conversation_history": [...]}'

# Check recent chats
curl http://localhost:8001/api/v1/chat/debug/recent-chats?limit=10
```

### Common Issues

#### Frontend 404 Errors
- **Cause:** Wrong API port in `frontend/src/services/api.ts`
- **Fix:** Ensure `API_BASE_URL = http://localhost:8001/api/v1`

#### AI Enhancement Fails
- **Cause:** Environment variables not loaded in worker
- **Fix:** Add `env_file: - az.secret` to worker/scheduler in docker-compose
- **Verify:** Check `docker-compose logs worker | grep AI_ENHANCEMENT_ENABLED`

#### Database Field Errors (e.g., `'raw_content' is invalid`)
- **Cause:** Code using wrong field name for SQLAlchemy model
- **Fix:** Check model definition in `backend/app/models/` and use correct field name
- **Example:** `RawYamlData` uses `content`, not `raw_content`

---

## 📊 Chat System Quick Reference

### Request Format
```bash
POST /api/v1/chat/query
{
  "question": "Help me troubleshoot deployments",
  "context_limit": 5,
  "conversation_history": [
    {"role": "user", "content": "previous question"},
    {"role": "assistant", "content": "previous answer"}
  ]
}
```

### Key Files
- `backend/app/routers/mcp_chat.py` - Main chat logic, follow-up detection (lines 166-178)
- `backend/app/routers/chat_debug.py` - Debug API endpoints
- `frontend/src/pages/Chat.tsx` - Chat UI
- `frontend/src/pages/ChatDebug.tsx` - Debug console (admin only)

### Important URLs
- **Chat UI:** http://localhost:3000/chat (public)
- **Debug Console:** http://localhost:3000/chat-debug (admin only)

**📖 Full documentation:** See [docs/chat.md](docs/chat.md) and [docs/chat-debug.md](docs/chat-debug.md)

---

## 🎨 UI/UX Standards

### Design System
- **Colors:**
  - Primary Blue: `#5282f1`
  - Gold Accent: `#f8ad4b`
- **Fonts:**
  - Main Text: Raleway
  - Logo "Run": Damion
  - Logo "When": Nunito
- **Inspiration:** registry.terraform.io, marketplace.upbound.io

### Header Navigation
- Browse (dropdown) → Links (dropdown) → Registry Chat → Login
- Three-dot menu (⋮): Config Builder, Admin Panel, Chat Debug, Task Manager

### Follow-up Chat Indicators
- **Blue left border** (4px) for follow-up questions
- **Chip badge** showing "Turn X in conversation"
- **Indentation** to show relationship to conversation thread

---

## 🔐 Security & Auth

### Admin Routes
- **Frontend:** Wrap with `<ProtectedRoute requiredRole="admin">`
- **Backend:** Use `Depends(get_current_user)` and check `user.role`
- **Pages:**
  - `/admin` - Admin panel
  - `/chat-debug` - Chat debugging console
  - `/tasks` - Task manager

### Test Credentials
- **Email:** `dev@example.com`
- **Password:** `password`
- **Role:** `admin`

---

## 📦 Deployment Notes

### Environment Files
- `az.secret` - Azure OpenAI credentials (not committed)
- Format: `export VAR=value` (one per line)
- Must be loaded in docker-compose `env_file` for workers

### Database Migrations
- Use Alembic for schema changes
- Location: `cc-registry-v2/backend/alembic/versions/`

### Container Build
- Frontend: Multi-stage build (node → nginx)
- Backend: Python 3.11 + FastAPI
- Workers: Same image as backend, different command

---

## 💡 Tips for Future Changes

### Adding a New Chat Feature
1. Update `backend/app/routers/mcp_chat.py` for backend logic
2. Test with `curl` or Chat Debug "Test Query" tab
3. Update `frontend/src/pages/Chat.tsx` for UI changes
4. Add debug logging to `chat_debug_service.py`
5. **Document in `docs/chat.md`** - Add section for new feature/fix

### Adding a New API Endpoint
1. Create/update router in `backend/app/routers/`
2. Import and include router in `backend/app/main.py`
3. Add corresponding service method in `frontend/src/services/api.ts`
4. Create/update React component to call the service

### Fixing Chat Quality Issues
1. Reproduce issue in Chat Debug UI ([docs/chat-debug.md](docs/chat-debug.md))
2. Check "Recent Chats" tab for problematic queries
3. Look at follow-up detection (`is_followup` flag in metadata)
4. Verify relevance scores and search results
5. Adjust prompts, detection logic, or search parameters
6. **Document fix in `docs/chat.md`** - Update "Known Issues" section

---

## 🚫 What NOT to Do

1. ❌ Don't create temporary markdown files for fixes/summaries
2. ❌ Don't use `docker-compose restart` after env file changes (use `up --force-recreate`)
3. ❌ Don't add icons to dropdown menus (user preference)
4. ❌ Don't commit `az.secret` or other credential files
5. ❌ Don't run database operations in request handlers (use Celery tasks)
6. ❌ Don't show raw database IDs in UI (use slugs)
7. ❌ Don't mix terminology (use CodeCollections, CodeBundles, Tasks - not "code bundles", "bundles", etc.)

---

Last Updated: 2026-01-19
