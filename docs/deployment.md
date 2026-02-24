# Mentorix – Przewodnik wdrożenia produkcyjnego

## Wymagania

- VPS: Ubuntu 22.04, min. 4 GB RAM, 20 GB dysk
- Docker Engine 27+
- Docker Compose v2+
- Domena z rekordem A → IP VPS

## Krok 1: Przygotowanie serwera

```bash
# UFW (firewall)
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Fail2ban
apt install fail2ban -y
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
maxretry = 3
bantime = 1h
findtime = 10m
EOF
systemctl restart fail2ban

# Automatyczne aktualizacje bezpieczeństwa
apt install unattended-upgrades -y
dpkg-reconfigure -plow unattended-upgrades

# Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER
```

## Krok 2: Klonowanie i konfiguracja

```bash
git clone ... /opt/mentorix
cd /opt/mentorix

# Generuj sekrety
./scripts/generate_secrets.sh

# Edytuj .env
nano .env
# Ustaw: DOMAIN, ACME_EMAIL, OPENAI_API_KEY, ADMIN_CORS_ORIGINS
```

## Krok 3: Uruchomienie

```bash
# Utwórz acme.json z właściwymi uprawnieniami
touch traefik/acme.json && chmod 600 traefik/acme.json

# Uruchom
docker compose up -d

# Sprawdź logi
docker compose logs -f backend

# Uruchom migracje
docker compose exec backend alembic upgrade head

# Utwórz superadmina (tylko raz!)
curl -X POST https://$DOMAIN/api/v1/auth/register-superadmin \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "silneHaslo123!"}'
```

## Krok 4: Weryfikacja

```bash
# Health check
curl https://$DOMAIN/health
# → {"status": "healthy", "version": "1.0.0"}

# Login
curl -X POST https://$DOMAIN/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "silneHaslo123!"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}
```

## Krok 5: Backup (cron)

```bash
# Dodaj do crontab
echo "0 2 * * * /opt/mentorix/scripts/backup_postgres.sh >> /var/log/mentorix-backup.log 2>&1" | crontab -
```

## Krok 6: Monitoring (opcjonalnie)

```bash
docker compose --profile monitoring up -d
# Grafana: https://$DOMAIN/grafana
# Login: admin / $GRAFANA_ADMIN_PASSWORD
```

## Krok 7: Log rotation

```bash
cat > /etc/logrotate.d/docker-containers << 'EOF'
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
EOF
```

## Aktualizacja aplikacji

```bash
cd /opt/mentorix
git pull

# Rebuild bez downtime (rolling)
docker compose pull
docker compose up -d --build

# Uruchom nowe migracje
docker compose exec backend alembic upgrade head
```

## Konfiguracja tenanta

1. Zaloguj się jako superadmin
2. `POST /api/v1/tenants` – utwórz tenanta ze slugiem
3. `POST /api/v1/documents/upload?tenant_id=<id>` – wgraj dokumenty
4. Czekaj na status `done` w `GET /api/v1/documents/<id>`
5. Udostępnij link: `https://$DOMAIN/chat/<tenant_id>`

## Osadzenie w iframe

```html
<iframe
  src="https://yourdomain.pl/chat/{tenant_id}"
  width="400"
  height="600"
  frameborder="0"
  allow="clipboard-write"
></iframe>
```

## Wariant SaaS (50+ tenantów)

```bash
# Uruchom z Qdrant + PgBouncer
docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d
```

## Zmienne środowiskowe – kompletna lista

| Zmienna | Opis | Wymagana |
|---------|------|----------|
| `DOMAIN` | Domena serwera | ✅ |
| `ACME_EMAIL` | Email dla Let's Encrypt | ✅ |
| `SECRET_KEY` | App secret (64 hex chars) | ✅ |
| `JWT_SECRET_KEY` | JWT signing key | ✅ |
| `IP_HASH_SALT` | Salt dla hashowania IP | ✅ |
| `POSTGRES_USER` | Użytkownik PostgreSQL | ✅ |
| `POSTGRES_PASSWORD` | Hasło PostgreSQL | ✅ |
| `POSTGRES_DB` | Nazwa bazy danych | ✅ |
| `OPENAI_API_KEY` | Klucz API OpenAI | ✅ |
| `ADMIN_CORS_ORIGINS` | Dozwolone origins dla admina | ✅ |
| `GRAFANA_ADMIN_PASSWORD` | Hasło Grafana | ❌ |
| `ENVIRONMENT` | `production` lub `development` | ❌ |
| `UPLOAD_MAX_SIZE_MB` | Max rozmiar pliku (domyślnie 25) | ❌ |
