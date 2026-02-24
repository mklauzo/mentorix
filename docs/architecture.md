# Mentorix AI Agent – Architektura systemu

## Przegląd

Mentorix to multi-tenant RAG (Retrieval-Augmented Generation) chatbot wdrożony na VPS z Dockerem. Każdy tenant (klient) ma izolowaną bazę wiedzy; użytkownicy końcowi rozmawiają przez unikalny link `/chat/{tenant_id}` który można osadzić jako iframe.

## Diagram kontenerów

```
Internet
  │
  ▼ 80/443
┌──────────────────────────────────┐
│  Traefik v3 (reverse proxy)      │
│  - Auto SSL (Let's Encrypt)      │
│  - HTTP→HTTPS redirect           │
│  - Security headers              │
│  - Rate limiting                 │
└──────────┬───────────────────────┘
           │ mentorix_proxy network
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────┐
│ FastAPI │  │ Next.js  │
│ backend │  │ frontend │
│ :8000   │  │ :3000    │
└────┬────┘  └──────────┘
     │ mentorix_internal (internal=true)
  ┌──┴─────────────────┐
  │                    │
  ▼                    ▼
┌───────────┐    ┌──────────┐
│PostgreSQL │    │  Redis   │
│+ pgvector │    │          │
│(no ports) │    │(no ports)│
└───────────┘    └────┬─────┘
                      │
                 ┌────▼─────┐
                 │  Celery  │
                 │  Worker  │
                 └──────────┘
```

## Sieci Docker

| Sieć | Typ | Uczestnicy |
|------|-----|------------|
| `mentorix_proxy` | bridge | Traefik, backend, frontend, Grafana |
| `mentorix_internal` | bridge + internal | backend, worker, db, Redis, Prometheus |

DB i Redis **nie mają** wystawionych portów na zewnątrz.

## Wolumeny

| Wolumin | Zawartość |
|---------|-----------|
| `postgres_data` | Dane PostgreSQL |
| `redis_data` | Dane Redis (AOF) |
| `uploads_data` | Pliki wgrane przez adminów |
| `prometheus_data` | Metryki Prometheus |
| `grafana_data` | Dane Grafana |

## Stack technologiczny

| Warstwa | Technologia | Wersja |
|---------|-------------|--------|
| Backend | FastAPI + Python | 3.12 |
| Frontend | Next.js (App Router) | 14 |
| ORM | SQLAlchemy async | 2.0 |
| Migracje | Alembic | 1.13 |
| Vector DB | PostgreSQL + pgvector | pg16 |
| Task queue | Celery + Redis | 5.4 |
| Proxy | Traefik | v3.1 |
| Embeddingi | text-embedding-3-small | - |
| LLM | gpt-4o-mini (domyślny) | - |

## Przepływ RAG

### Upload dokumentu
```
POST /api/v1/documents/upload
  → JWT validate
  → MIME/size validate (max 25MB)
  → sanitize_filename() + path traversal guard
  → save /uploads/{tenant_id}/{uuid}_{name}
  → INSERT document (status=pending)
  → celery.delay(doc_id, tenant_id)
  → 202 Accepted

Celery Worker:
  parse_document() → PyMuPDF/python-docx/plain txt
  chunk_text() → size=800, overlap=150
  embed_texts_sync() → OpenAI batch=100
  INSERT document_chunks (embedding VECTOR(1536))
  UPDATE document.status = 'done'
```

### Zapytanie użytkownika
```
POST /api/v1/chat/{tenant_id}/message
  → rate_limit (10 RPM/IP)
  → validate tenant (active, not blocked)
  → check_prompt_injection(question)
  → check_and_increment_usage() [SELECT FOR UPDATE]
  → embed question → vector[1536]
  → SELECT chunks ORDER BY embedding <=> query LIMIT 5
  → build context from top-5 chunks
  → OpenAI Chat API (temp=0.2, max_tokens=800)
  → INSERT messages + UPDATE api_usage
  → 200 {answer, conversation_id, sources[]}
```

## Bezpieczeństwo

- JWT HS256, 60 min access token
- Brute-force: 5 prób → lockout 15 min
- Prompt injection: regex patterns + max 2000 znaków
- Tenant isolation: każde query `WHERE tenant_id = :id`
- IP hashing: SHA-256 + salt (nigdy nie przechowujemy raw IP)
- Path traversal guard na upload
- Docker: `no-new-privileges:true`, non-root user, `cap_drop: ALL`

## Skalowanie

```
Etap 1 (10-50 tenantów):
  deploy.replicas: 3 (backend), Traefik load-balance

Etap 2 (50+ tenantów):
  docker-compose.saas.yml:
  - PgBouncer (pool_size=20)
  - Qdrant self-hosted (kolekcje per tenant)
  - Celery Flower (monitoring workerów)

Etap 3:
  Docker Swarm / Kubernetes
  S3-compatible storage (Backblaze B2) zamiast lokalnych plików
```
