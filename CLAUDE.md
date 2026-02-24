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
- **Database**: PostgreSQL 16 + pgvector extension (cosine similarity on 1536-dim embeddings)
- **Queue**: Celery + Redis (document processing pipeline)
- **Proxy**: Traefik v3.3 (TLS termination, routing via static file config — no Docker provider)
- **LLM**: OpenAI API or local Ollama (per-tenant; model name prefix `ollama:` routes to Ollama)
- **Embeddings**: OpenAI `text-embedding-3-small` (1536 dims) — always OpenAI, even when LLM is Ollama

### Docker Networks
Two isolated networks:
- `mentorix_proxy` (bridge) – Traefik ↔ backend, frontend
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
- Own `system_prompt`, `llm_model`, branding (`chat_color`, `chat_title`, `welcome_message`)
- Isolated document store (all queries include `WHERE tenant_id = :tenant_id`)
- Separate token limits (`daily_token_limit`, `monthly_token_limit`)
- Public URL: `/chat/{tenant_id}` embeddable as iframe

### Role Hierarchy
Three roles stored in `users.role` column:
- `superadmin` – full platform access: creates/deletes tenants and all users
- `admin` – manages own tenant: documents, settings, creates/deletes `user` role accounts in own tenant
- `user` – read-only admin panel (conversations, documents view)

Auth dependencies chain: `get_current_user()` → `get_current_admin()` → `get_current_superadmin()` in `backend/app/core/dependencies.py`.

### RAG Pipeline (Async)
Document processing runs in Celery worker, not HTTP thread:
1. Upload via `POST /api/v1/documents/upload?tenant_id=...` → saves to DB with `status=pending`, enqueues Celery task
2. Worker: parse (PyMuPDF/python-docx/txt) → chunk (800 chars, 150 overlap) → batch embed (OpenAI, batch=100) → INSERT with `embedding::vector` cast
3. Status transitions: `pending → processing → done/error`

Chat query flow (`POST /api/v1/chat/{tenant_id}/message`):
1. Validate tenant + prompt injection guard (`app/core/prompt_guard.py`)
2. `check_and_increment_usage()` – `SELECT FOR UPDATE` on tenant row; enforces daily/monthly token limits
3. Embed question → cosine similarity search via pgvector `<=>` operator
4. Build system prompt with retrieved chunks + tenant's custom prompt
5. `get_llm_client(tenant.llm_model)` → routes to OpenAI or Ollama based on model prefix → persist message → `update_usage_after_call()`

### LLM Routing (Ollama vs OpenAI)
`backend/app/services/rag_service.py` — `get_llm_client(model)`:
- Model starts with `ollama:` → `AsyncOpenAI(base_url="http://ollama:11434/v1", api_key="ollama")`, strips prefix for the actual API call
- Everything else → standard OpenAI client with `OPENAI_API_KEY`
- Ollama exposes an OpenAI-compatible `/v1` endpoint, so the same SDK is used for both
- Pull models before use: `docker compose exec ollama ollama pull llama3.2`
- `OPENAI_API_KEY` is optional when all tenants use Ollama, but still needed for document embeddings

### pgvector
The `document_chunks.embedding` column is `vector(1536)` – SQLAlchemy cannot express this natively, so:
- Added via raw SQL in Alembic (`ALTER TABLE ... ADD COLUMN embedding vector(1536)`)
- Inserted via raw `text()` SQL with `::vector` cast
- Queried with `<=>` operator (cosine distance) in raw SQL

### Security
- **Brute force**: 5 failed logins → `locked_until = now + 15min`
- **Prompt injection guard**: regex patterns in `app/core/prompt_guard.py` (DAN, `</system>`, `[INST]`, delimiter injection, role manipulation)
- **IP privacy**: SHA-256(salt+IP) hash stored as `user_ip_hash`, never raw IP
- **Token cost**: `SELECT FOR UPDATE` prevents race conditions on counter updates
- **Networks**: DB and Redis have no exposed ports (internal network only)
- **JWT**: HS256, 60-minute access tokens; payload includes `role`, `tenant_id`

### Frontend Auth
Token stored in `localStorage` as `mentorix_token`. User profile cached as `mentorix_user` (set after login via `/auth/me` call). `AdminLayout` component reads the cache; redirects to `/admin/login` if missing.

### API Prefix
All backend routes are under `/api/v1`. Swagger UI available at `/api/docs` in non-production environments.

### Key File Locations
- Backend entry: `backend/app/main.py`
- Config (env vars): `backend/app/config.py`
- Auth dependencies: `backend/app/core/dependencies.py`
- RAG logic: `backend/app/services/rag_service.py`
- Cost enforcement: `backend/app/services/cost_service.py`
- Document Celery task: `backend/app/tasks/process_document.py`
- Frontend API client: `frontend/src/lib/api.ts`
- Admin sidebar layout: `frontend/src/components/admin/AdminLayout.tsx`
- Role badge component: `frontend/src/components/admin/RoleBadge.tsx`
- DB migrations: `backend/alembic/versions/`
- Traefik routes: `traefik/dynamic/routes.yml`
