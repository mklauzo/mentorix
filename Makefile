.PHONY: help up down build logs shell-backend shell-db migrate makemigrations \
        secrets monitoring test lint format

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ────────────────────────────────────────────────────
up: ## Start MVP stack
	docker compose up -d

up-monitoring: ## Start with monitoring profile
	docker compose --profile monitoring up -d

up-saas: ## Start SaaS variant (Qdrant + PgBouncer)
	docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d

down: ## Stop all containers
	docker compose down

down-v: ## Stop and remove volumes (DESTRUCTIVE)
	docker compose down -v

build: ## Rebuild all images
	docker compose build --no-cache

restart-backend: ## Restart backend only
	docker compose restart backend worker

logs: ## Follow all logs
	docker compose logs -f

logs-backend: ## Follow backend logs
	docker compose logs -f backend

logs-worker: ## Follow worker logs
	docker compose logs -f worker

# ── Database ──────────────────────────────────────────────────
migrate: ## Run Alembic migrations
	docker compose exec backend alembic upgrade head

makemigrations: ## Create new migration (MSG=description)
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

shell-db: ## Open psql shell
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

# ── Development ───────────────────────────────────────────────
shell-backend: ## Open backend bash shell
	docker compose exec backend bash

shell-frontend: ## Open frontend bash shell
	docker compose exec frontend sh

# ── Secrets ───────────────────────────────────────────────────
secrets: ## Generate all secrets and write to .env
	./scripts/generate_secrets.sh

# ── Monitoring ───────────────────────────────────────────────
monitoring: ## Open Grafana (requires SSH tunnel or domain)
	@echo "Grafana: https://$${DOMAIN}/grafana"

# ── Code Quality ─────────────────────────────────────────────
lint: ## Lint backend (ruff)
	docker compose exec backend ruff check app/

format: ## Format backend (ruff)
	docker compose exec backend ruff format app/

test: ## Run backend tests
	docker compose exec backend pytest tests/ -v

# ── Backup ────────────────────────────────────────────────────
backup: ## Run manual database backup
	./scripts/backup_postgres.sh

# ── Setup ─────────────────────────────────────────────────────
setup: ## Initial setup: generate secrets, create acme.json
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example – edit it now!")
	@touch traefik/acme.json && chmod 600 traefik/acme.json
	@echo "Setup complete. Edit .env then run: make up && make migrate"
