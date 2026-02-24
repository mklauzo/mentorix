#!/usr/bin/env bash
# Mentorix PostgreSQL backup script
# Cron: 0 2 * * * /opt/mentorix/scripts/backup_postgres.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a && source "$PROJECT_DIR/.env" && set +a
fi

BACKUP_DIR="${BACKUP_DIR:-/opt/mentorix/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mentorix_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup to $BACKUP_FILE"

docker exec mentorix-db-1 pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --no-password \
    --format=plain \
    | gzip > "$BACKUP_FILE"

echo "[$(date)] Backup completed: $(du -sh "$BACKUP_FILE" | cut -f1)"

# Rotate old backups
find "$BACKUP_DIR" -name "mentorix_*.sql.gz" -mtime "+$RETENTION_DAYS" -delete
echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days"

# Optional: sync to remote (configure REMOTE_BACKUP_PATH in .env)
if [ -n "${REMOTE_BACKUP_PATH:-}" ]; then
    rsync -az "$BACKUP_FILE" "$REMOTE_BACKUP_PATH/" || echo "[WARN] Remote sync failed"
fi

echo "[$(date)] Backup done."
