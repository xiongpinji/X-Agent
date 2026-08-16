#!/usr/bin/env bash
set -euo pipefail

# Usage: restore-database.sh [--dry-run] <backup.sql.gz|database.dump>
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: restore-database.sh [--dry-run] <backup.sql.gz|database.dump>" >&2
  exit 2
fi

BACKUP_FILE="$1"
DB_HOST="${XAGENT_DATABASE_HOST:-localhost}"
DB_PORT="${XAGENT_DATABASE_PORT:-5432}"
DB_USER="${XAGENT_DATABASE_USER:-xagent}"
DB_NAME="${XAGENT_DATABASE_NAME:-xagent}"
DB_PASSWORD="${XAGENT_DATABASE_PASSWORD:-}"

if [[ -z "$DB_PASSWORD" ]]; then
  echo "XAGENT_DATABASE_PASSWORD must be set" >&2
  exit 2
fi
if [[ ! "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "XAGENT_DATABASE_NAME contains unsafe characters" >&2
  exit 2
fi
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 2
fi
command -v gzip >/dev/null || { echo "gzip is required" >&2; exit 2; }

BACKUP_KIND=""
if [[ "$BACKUP_FILE" == *.sql.gz ]]; then
  if ! gzip -t "$BACKUP_FILE"; then
    echo "Invalid gzip backup: $BACKUP_FILE" >&2
    exit 2
  fi
  BACKUP_KIND="plain-gzip"
else
  command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 2; }
  if ! pg_restore --list "$BACKUP_FILE" >/dev/null; then
    echo "Invalid PostgreSQL custom backup: $BACKUP_FILE" >&2
    exit 2
  fi
  BACKUP_KIND="custom"
fi

if $DRY_RUN; then
  echo "Restore dry-run validated $BACKUP_FILE for $DB_HOST:$DB_PORT/$DB_NAME"
  exit 0
fi

if [[ "${XAGENT_RESTORE_CONFIRMATION:-}" != "$DB_NAME" ]]; then
  echo "XAGENT_RESTORE_CONFIRMATION must equal the target database name" >&2
  exit 2
fi
for tool in dropdb createdb; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 2; }
done
if [[ "$BACKUP_KIND" == "plain-gzip" ]]; then
  command -v psql >/dev/null || { echo "psql is required" >&2; exit 2; }
fi

export PGPASSWORD="$DB_PASSWORD"
dropdb --if-exists --force \
  --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" "$DB_NAME"
createdb --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" "$DB_NAME"
if [[ "$BACKUP_KIND" == "plain-gzip" ]]; then
  gzip -dc "$BACKUP_FILE" | psql \
    --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
    --dbname "$DB_NAME" --no-password --set ON_ERROR_STOP=on
else
  pg_restore --exit-on-error --no-owner --no-privileges \
    --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" \
    --dbname "$DB_NAME" --no-password "$BACKUP_FILE"
fi

echo "Restore completed for $DB_NAME"
