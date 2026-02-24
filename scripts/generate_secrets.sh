#!/usr/bin/env bash
# Generate all secrets and write to .env
# Usage: ./scripts/generate_secrets.sh

set -euo pipefail

ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
    cp "$(dirname "$0")/../.env.example" "$ENV_FILE"
    echo "Created .env from .env.example"
fi

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
IP_HASH_SALT=$(openssl rand -hex 16)
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
GRAFANA_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=')

# Update .env file
update_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

update_env "SECRET_KEY" "$SECRET_KEY"
update_env "JWT_SECRET_KEY" "$JWT_SECRET_KEY"
update_env "IP_HASH_SALT" "$IP_HASH_SALT"
update_env "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
update_env "GRAFANA_ADMIN_PASSWORD" "$GRAFANA_PASSWORD"

# Create Traefik acme.json with correct permissions
ACME_FILE="$(dirname "$0")/../traefik/acme.json"
touch "$ACME_FILE"
chmod 600 "$ACME_FILE"

echo ""
echo "✅ Secrets generated and written to .env"
echo ""
echo "Next steps:"
echo "  1. Edit .env and set: DOMAIN, ACME_EMAIL, OPENAI_API_KEY, ADMIN_CORS_ORIGINS"
echo "  2. Run: docker compose up -d"
echo "  3. Run: docker compose exec backend alembic upgrade head"
echo "  4. Create superadmin: POST /api/v1/auth/register-superadmin"
echo ""
echo "Generated:"
echo "  SECRET_KEY       = ${SECRET_KEY:0:16}..."
echo "  JWT_SECRET_KEY   = ${JWT_SECRET_KEY:0:16}..."
echo "  POSTGRES_PASSWORD = ${POSTGRES_PASSWORD:0:8}..."
echo "  GRAFANA_PASSWORD  = ${GRAFANA_PASSWORD}"
