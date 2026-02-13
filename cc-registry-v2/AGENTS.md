# AGENTS.md — CodeCollection Registry v2

Instructions for AI coding agents working in this codebase.

---

## Project Overview

The CodeCollection Registry is a public-facing web app for browsing, searching, and configuring RunWhen automation (CodeBundles). It consists of 8 Docker services:

| Service | Stack | Port | Purpose |
|---------|-------|------|---------|
| `frontend` | React 19 + TypeScript + MUI v7 | 3000 | SPA served by nginx (prod) or dev server (local) |
| `backend` | FastAPI + SQLAlchemy 2.0 | 8001 | REST API under `/api/v1/` |
| `mcp-server` | FastAPI | 8000 | MCP protocol HTTP server for AI tool integration |
| `worker` | Celery (same image as backend) | — | Background task processing |
| `scheduler` | Celery Beat | — | Scheduled task execution |
| `database` | PostgreSQL 15 + pgvector | 5432 | Primary data store |
| `redis` | Redis 7 | 6379 | Celery broker and cache |
| `flower` | Flower | 5555 | Celery monitoring UI |

---

## Terminology

Use these exact terms — never abbreviate or paraphrase:

- **CodeCollection** — a git repo containing multiple CodeBundles
- **CodeBundle** — a folder within a CodeCollection containing automation tasks
- **Task** — an individual automation script (either `TaskSet` or `SLI` type)
- **RunWhen Platform** — the orchestration platform (not "RunWhen Core")
- **Workspace Chat** — the AI chat feature (not "AI Chat" or "Eager Edgar Chat")
- **Support Tags** — metadata tags on CodeBundles (e.g., `kubernetes`, `aws`, `azure`)
- **Data Tags** — per-task data classification tags (`data:config`, `data:logs-regexp`, etc.)

---

## File Structure

```
cc-registry-v2/
├── frontend/src/
│   ├── pages/           # Route-level components
│   ├── components/      # Shared components (Header, Footer, etc.)
│   ├── contexts/        # React Context providers (Auth, Cart, Theme)
│   ├── services/api.ts  # Centralized Axios API client
│   ├── theme.ts         # MUI theme (light/dark)
│   └── index.tsx        # App entry point
├── backend/
│   ├── app/
│   │   ├── routers/     # FastAPI route handlers
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── services/    # Business logic layer
│   │   ├── tasks/       # Celery task definitions
│   │   ├── core/        # Config (Pydantic), database setup
│   │   └── main.py      # FastAPI app initialization
│   ├── alembic/         # Database migrations
│   └── requirements.txt
├── k8s/                 # Kubernetes manifests
├── docs/                # ALL documentation goes here
├── docker-compose.yml
└── Taskfile.yml         # Dev workflow commands
```

---

## Development Workflow

### Local Dev (Docker Compose)

```bash
task start              # Build and start everything
task stop               # Stop all services
task dev                # Start db + redis + backend + frontend only
task logs               # Tail all logs
task health             # Health check all services
```

### Rebuilding After Code Changes

```bash
# Source code changes → REBUILD (restart does NOT pick up changes)
docker-compose up -d --build frontend
docker-compose up -d --build backend

# Environment variable changes → FORCE RECREATE
docker-compose up -d --force-recreate backend

# Config-only restart
docker-compose restart backend
```

### Environment

- Secrets file: `az.secret` (not committed), format: `export VAR=value`
- Must be in `env_file` for worker AND scheduler (not just backend)
- Admin login (local): `dev@example.com` / `password`

---

## Backend Conventions (Python)

### FastAPI Routers

- All routes under `/api/v1/` prefix
- Use `async def` for handlers
- Inject DB: `db: Session = Depends(get_db)`
- Admin routes: add `Depends(get_current_user)` + role check
- Register new routers in `backend/app/main.py`

### SQLAlchemy Models

- Define in `backend/app/models/`, import in `__init__.py`
- Use JSONB columns for flexible data (tags, metadata)
- Always include `created_at` and `updated_at`

### Celery Tasks

- Define in `backend/app/tasks/`, register in `celery_app.py`
- Chained tasks MUST have `previous_result=None` as first parameter
- Never run long operations in request handlers — offload to Celery

### Alembic Migrations

- Guard ALTER TABLE with `IF NOT EXISTS` for idempotency
- `run_migrations.py` calls `Base.metadata.create_all()` before Alembic for fresh DBs
- Test migrations against both fresh and existing databases

### Configuration

- Pydantic `BaseSettings` in `app/core/config.py`
- DB: either `DATABASE_URL` or individual `DB_HOST/PORT/USER/PASSWORD/NAME`
- Redis: either `REDIS_URL` or Sentinel (`REDIS_SENTINEL_HOSTS/MASTER`)
- AI: `AI_SERVICE_PROVIDER=azure-openai` + `AZURE_OPENAI_*` env vars

---

## Frontend Conventions (React + TypeScript)

### Theme & Design Tokens

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `primary.main` | `#5282f1` | `#5282f1` | Interactive elements, links |
| `text.primary` | `#3f3f3f` | `#e0e0e0` | Headings, body text |
| `text.secondary` | `#858484` | `#a0a0a0` | Descriptions, metadata |
| `background.paper` | `#ffffff` | `#1e1e1e` | Cards, surfaces |
| `background.default` | `#ffffff` | `#121212` | Page background |
| `divider` | `rgba(0,0,0,0.12)` | `rgba(255,255,255,0.12)` | Borders, separators |
| `action.hover` | — | — | Hover/zebra backgrounds |

**Rules:**
- Always use theme tokens — never hardcode `#fff`, `#000`, `#666`, `#ddd`
- Font family: **Raleway** (brand font, do not change)
- Font weight: `400` body, `500` emphasis, `600` headings/buttons — never `700` or `'bold'`
- Font size grid: `0.75rem` (12px), `0.8125rem` (13px), `0.875rem` (14px), `0.9375rem` (15px), `1rem` (16px) — no sizes below 12px
- Chip min height: `24px`, row min height: `40px`
- Dark mode is supported via `ThemeContext` — test both modes

### State Management

- React Context only — `AuthContext`, `CartContext`, `ThemeContext`
- `useThemeMode()` for dark/light toggle
- `useCart()` for codebundle selection
- No Redux, Zustand, or other state libraries

### API Calls

- All through `services/api.ts` — single Axios instance with interceptors
- Base URL: `http://localhost:8001/api/v1` (env-configurable via `REACT_APP_API_URL`)
- Auth token auto-attached for `/admin` and `/tasks` routes
- Add new endpoints as methods on the `apiService` export

### Component Patterns

- Functional components only
- Pages in `pages/`, shared UI in `components/`
- Admin routes: wrap with `<ProtectedRoute requiredRole="admin">`
- Loading: `<CircularProgress />` centered; Error: `<Alert severity="error">`

### Home Page (Exception)

`Home.tsx` is a marketing/landing page. It intentionally uses branded gradients, large typography, rgba overlays, and custom animations. Do not "normalize" it to match the app design system.

---

## Kubernetes Conventions

### Namespace & Infrastructure

- All resources in `registry-test` namespace
- Database: Zalando Postgres Operator (Spilo) — secret: `registry-user.registry-db.credentials.postgresql.acid.zalan.do`
- Redis: Sentinel at `redis-sentinel:26379`, master `mymaster`, password from `redis-sentinel` secret
- AI credentials: `azure-openai-credentials` secret via `envFrom`

### Container Images

- Registry: `us-docker.pkg.dev/runwhen-nonprod-shared/public-images/`
- Images: `cc-registry-v2-backend:latest`, `cc-registry-v2-frontend:latest`

### Security

All containers: `runAsNonRoot: true`, `runAsUser: 1000`, drop all capabilities.

---

## Documentation Policy

- ALL docs go in `docs/` — never create `.md` files in project root (except this file)
- Update existing docs, don't create duplicates
- No temporary files (`*-FIX.md`, `*-SUMMARY.md`, `*-UPDATE.md`)
- Descriptive names: `MCP_INDEXING.md` not `MCP-INDEXING-GUIDE-FIX-V2.md`

---

## Do NOT

1. Create markdown files outside `docs/` (except `AGENTS.md` and `README.md`)
2. Use `docker-compose restart` after code changes (use `up -d --build`)
3. Commit `az.secret` or credential files
4. Run database operations in HTTP request handlers (use Celery)
5. Show raw database IDs in the UI (use slugs)
6. Use emoji in code or docs unless explicitly requested
7. Change the font to Inter or the primary color to `#0570de` (registry has its own brand)
8. "Fix" `Home.tsx` to match the app design system — it's intentionally different
