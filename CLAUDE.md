# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

All operations run inside Docker containers. Start with:

```bash
make setup        # First-time: copy .env.example → .env, create traefik/acme.json
make secrets      # Generate SECRET_KEY, POSTGRES_PASSWORD, etc. into .env
make up           # Start MVP stack (backend, worker, frontend, db, redis, traefik)
make migrate      # Run Alembic migrations (always after pulling changes)
```

Daily workflow:
```bash
make logs-backend           # Follow backend logs
make logs-worker            # Follow Celery worker logs
make restart-backend        # Restart backend + worker after code changes
make shell-backend          # bash inside backend container
make shell-db               # psql shell
```

Code quality (runs inside container):
```bash
make lint         # ruff check app/
make format       # ruff format app/
make test         # pytest tests/ -v
```

Database migrations:
```bash
make makemigrations MSG="description"   # autogenerate migration
make migrate                            # apply migrations
```

Variants:
```bash
make up-monitoring    # Include Prometheus + Grafana
make up-saas         # Add Qdrant + PgBouncer overlay
```

## Architecture

### Stack
- **Backend**: FastAPI + Python 3.12, SQLAlchemy 2.0 async (asyncpg), Alembic
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, `'use client'` components throughout admin
- **Database**: PostgreSQL 16 + pgvector extension (cosine similarity on 768-dim embeddings)
- **Queue**: Celery + Redis (document processing pipeline)
- **Proxy**: Traefik v3.3 (TLS termination, routing via static file config — no Docker provider)
- **LLM**: OpenAI, Gemini, Anthropic, or local Ollama (per-tenant configurable via model name prefix)
- **Embeddings**: Per-tenant configurable — Ollama local models (default) or OpenAI (768-dim vectors)

### Docker Networks
Two isolated networks:
- `mentorix_proxy` (bridge) – Traefik ↔ backend, frontend; also on **Ollama** (needed for internet access to pull models)
- `mentorix_internal` (internal=true) – backend/worker ↔ db, redis, ollama (no external access)

### Traefik Configuration
Traefik uses **file provider only** — no Docker provider. Routes are defined statically in `traefik/dynamic/routes.yml` using Go template syntax. The Docker provider was removed because Docker 27+ raised the minimum API version to 1.44, which conflicts with the Docker Go SDK bundled in older Traefik builds.

Key files:
- `traefik/traefik.yml` – static config (entrypoints, ACME, file provider)
- `traefik/dynamic/routes.yml` – HTTP routers and services using `{{ env "DOMAIN" }}`
- `traefik/dynamic/middlewares.yml` – security headers, rate limiting
- `traefik/acme.json` – Let's Encrypt certificates (must exist, `chmod 600`)

Traefik env vars (passed in `docker-compose.yml`): `DOMAIN`, `ACME_EMAIL`, `TRAEFIK_DASHBOARD_PASSWORD_HASH`.

`TRAEFIK_DASHBOARD_PASSWORD_HASH` in `.env` must use `$$` instead of `$` (Docker Compose escaping). Generate with: `htpasswd -nb admin 'password'`, then replace every `$` with `$$`.

**Adding new routes**: edit `traefik/dynamic/routes.yml` — no container restart needed (file provider watches for changes).

### Multi-Tenant Model
Each **tenant** = one independent chatbot profile with:
- Own `system_prompt`, `llm_model`, `embedding_model`, branding (`chat_color`, `chat_title`, `welcome_message`)
- Isolated document store (all queries include `WHERE tenant_id = :tenant_id`)
- Separate token limits (`daily_token_limit`, `monthly_token_limit`)
- Public URL: `/chat/{tenant_id}` embeddable as iframe

### Role Hierarchy
Three roles stored in `users.role` column:
- `superadmin` – full platform access: creates/deletes tenants and all users
- `admin` – manages own tenant: documents, settings, creates/deletes `user` role accounts in own tenant
- `user` – read-only admin panel (conversations, documents view)

Auth dependencies chain: `get_current_user()` → `get_current_admin()` → `get_current_superadmin()` in `backend/app/core/dependencies.py`.

`User.is_superadmin` is a legacy DB column kept for backwards compat; use `user.role == "superadmin"` in new code.

### RAG Pipeline (Async)
Document processing runs in Celery worker, not HTTP thread:
1. Upload via `POST /api/v1/documents/upload?tenant_id=...` → saves to DB with `status=pending`, enqueues Celery task
2. Worker: parse (PyMuPDF/python-docx/txt) → chunk (800 chars, 150 overlap) → batch embed (via `embedding_service.py`) → INSERT with `CAST(:embedding AS vector)` cast
3. Status transitions: `pending → processing → done/error`

Chat query flow (`POST /api/v1/chat/{tenant_id}/message`):
1. Validate tenant + prompt injection guard (`app/core/prompt_guard.py`)
2. `check_and_increment_usage()` – `SELECT FOR UPDATE` on tenant row; enforces daily/monthly token limits
3. Embed question → cosine similarity search via pgvector `<=>` operator
4. Build system prompt with retrieved chunks + tenant's custom prompt
5. Route to LLM provider based on model prefix → persist message → `update_usage_after_call()`

### LLM Routing
`backend/app/services/rag_service.py` — `generate_answer()` routes by model name:
- `ollama:*` → Ollama via OpenAI-compatible `/v1` API at `http://ollama:11434`
- `claude-*` → Anthropic SDK (`AsyncAnthropic`)
- `gemini-*` → Gemini via OpenAI-compatible endpoint at `https://generativelanguage.googleapis.com/v1beta/openai/`
- Everything else → OpenAI SDK

Pull Ollama models before use: `docker compose exec ollama ollama pull llama3.2`

### Embedding Routing
`backend/app/services/embedding_service.py` — per-tenant `embedding_model` field:
- `ollama:nomic-embed-text` – default, free, local (768-dim)
- `ollama:mxbai-embed-large` – higher quality, local (768-dim)
- `openai` – `text-embedding-3-small` truncated to 768-dim (requires `sk-...` key)

All vectors are **768-dim** (migration 005 reduced from 1536). Consistent dimension is required — if you change a tenant's `embedding_model`, re-upload all documents.

### pgvector SQL Pattern
The `document_chunks.embedding` column is `vector(768)` — SQLAlchemy cannot express this natively:
- Added via raw SQL in Alembic (`ALTER TABLE ... ADD COLUMN embedding vector(768)`)
- **IMPORTANT**: asyncpg parses `:name` parameters and `::` confuses it. Always use `CAST(:param AS vector)` — never `:param::vector`
- Queried with `<=>` operator (cosine distance) in raw `text()` SQL

### Security
- **Brute force**: 5 failed logins → `locked_until = now + 15min`
- **Prompt injection guard**: regex patterns in `app/core/prompt_guard.py` (DAN, `</system>`, `[INST]`, delimiter injection, role manipulation)
- **IP privacy**: SHA-256(salt+IP) hash stored as `user_ip_hash`, never raw IP
- **Token cost**: `SELECT FOR UPDATE` prevents race conditions on counter updates
- **Networks**: DB and Redis have no exposed ports (internal network only)
- **JWT**: HS256, 60-minute access tokens; payload includes `role`, `tenant_id`

### Frontend Auth
Token stored in `localStorage` as `mentorix_token`. User profile cached as `mentorix_user` (populated via `/auth/me` after login). `AdminLayout` component reads the cache; redirects to `/admin/login` if token missing.

`apiFetch` in `src/lib/api.ts` checks `res.status === 204` before calling `res.json()` — do not remove this check or DELETE/no-content responses will throw "Unexpected end of JSON input".

### Frontend i18n
Language switcher (PL/EN/DE) in `AdminLayout` sidebar. Translations in `frontend/src/lib/i18n.ts`. Language persisted in `localStorage` as `mentorix_lang`. When adding new UI strings, add the key to all three language objects in `T` (must satisfy `Record<Lang, Record<string, string>>`).

### Admin Panel Pages
- `/admin` – dashboard (role-aware: superadmin sees all tenants, admin sees own)
- `/admin/profiles` – superadmin only: all profiles as cards
- `/admin/my-profile` – admin/user: own profile + chat link + usage bar
- `/admin/tenants/[id]` – create/edit profile form with `ModelBrowser` component
- `/admin/users` – user list with role filter and delete
- `/admin/users/new` – create user form
- `/admin/conversations` – conversation history
- `/admin/documents` – document management

### API Prefix
All backend routes are under `/api/v1`. Swagger UI available at `/api/docs` in non-production environments.

Key endpoints added beyond CRUD:
- `GET /api/v1/auth/me` – returns current user profile
- `GET /api/v1/admin/ollama/models` – lists available Ollama models
- `POST /api/v1/admin/ollama/pull` – pulls model in background (BackgroundTasks)
- `POST /api/v1/admin/models/fetch` – fetches model list from any provider (openai/gemini/anthropic/ollama)

### Key File Locations
- Backend entry: `backend/app/main.py`
- Config (env vars): `backend/app/config.py`
- Auth dependencies: `backend/app/core/dependencies.py`
- RAG logic: `backend/app/services/rag_service.py`
- Embedding routing: `backend/app/services/embedding_service.py`
- Cost enforcement: `backend/app/services/cost_service.py`
- Document Celery task: `backend/app/tasks/process_document.py`
- Ollama/model management API: `backend/app/api/v1/admin.py`
- Frontend API client: `frontend/src/lib/api.ts`
- Frontend i18n: `frontend/src/lib/i18n.ts`
- Admin sidebar layout: `frontend/src/components/admin/AdminLayout.tsx`
- Model browser component: `frontend/src/components/admin/ModelBrowser.tsx`
- DB migrations: `backend/alembic/versions/` (001→006)
- Traefik routes: `traefik/dynamic/routes.yml`
