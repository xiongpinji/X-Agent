#!/usr/bin/env bash
set -euo pipefail

# Usage: backup-database.sh [--dry-run] [backup_dir]
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi

BACKUP_DIR="${1:-./.backups}"
DB_HOST="${XAGENT_DATABASE_HOST:-localhost}"
DB_PORT="${XAGENT_DATABASE_PORT:-5432}"
DB_USER="${XAGENT_DATABASE_USER:-xagent}"
DB_NAME="${XAGENT_DATABASE_NAME:-xagent}"
DB_PASSWORD="${XAGENT_DATABASE_PASSWORD:-}"
RETENTION_COUNT="${XAGENT_BACKUP_RETENTION_COUNT:-30}"

if [[ -z "$DB_PASSWORD" ]]; then
  echo "XAGENT_DATABASE_PASSWORD must be set" >&2
  exit 2
fi
if [[ ! "$RETENTION_COUNT" =~ ^[1-9][0-9]*$ ]]; then
  echo "XAGENT_BACKUP_RETENTION_COUNT must be a positive integer" >&2
  exit 2
fi

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/backup-$TIMESTAMP.sql.gz"

if $DRY_RUN; then
  echo "Backup dry-run validated target $DB_HOST:$DB_PORT/$DB_NAME -> $BACKUP_FILE"
  exit 0
fi

command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 2; }
command -v gzip >/dev/null || { echo "gzip is required" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
TEMP_FILE="${BACKUP_FILE}.tmp.$$"
trap 'rm -f -- "$TEMP_FILE"' EXIT

PGPASSWORD="$DB_PASSWORD" pg_dump \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --dbname "$DB_NAME" \
  --no-password \
  --format=plain \
  | gzip -9 > "$TEMP_FILE"
gzip -t "$TEMP_FILE"
mv -- "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT

shopt -s nullglob
BACKUP_FILES=("$BACKUP_DIR"/backup-*.sql.gz)
OLD_BACKUPS=()
if (( ${#BACKUP_FILES[@]} > RETENTION_COUNT )); then
  mapfile -t SORTED_BACKUPS < <(printf '%s\n' "${BACKUP_FILES[@]}" | sort -r)
  OLD_BACKUPS=("${SORTED_BACKUPS[@]:RETENTION_COUNT}")
fi
for old_backup in "${OLD_BACKUPS[@]}"; do
  rm -f -- "$old_backup"
done

echo "Backup completed: $BACKUP_FILE"
