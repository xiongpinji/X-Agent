#!/bin/bash
set -e

# X-Agent Database Backup Script
# Usage: bash deployment/scripts/backup-database.sh [backup_dir]

BACKUP_DIR="${1:-./.backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup-$TIMESTAMP.sql.gz"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Starting database backup...${NC}"
echo "Backup file: $BACKUP_FILE"

# Get database connection details from environment
DB_HOST="${XAGENT_DATABASE_HOST:-localhost}"
DB_PORT="${XAGENT_DATABASE_PORT:-5432}"
DB_USER="${XAGENT_DATABASE_USER:-xagent}"
DB_NAME="${XAGENT_DATABASE_NAME:-xagent}"

# Perform backup
if PGPASSWORD="$XAGENT_DATABASE_PASSWORD" pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --verbose \
  --no-password \
  | gzip > "$BACKUP_FILE"; then

  FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
  echo -e "${GREEN}✓ Backup completed successfully${NC}"
  echo "File size: $FILE_SIZE"
  echo "Location: $BACKUP_FILE"

  # Keep only last 30 backups
  echo "Cleaning up old backups..."
  ls -t "$BACKUP_DIR"/backup-*.sql.gz | tail -n +31 | xargs -r rm

  echo -e "${GREEN}✓ Backup cleanup completed${NC}"
  exit 0
else
  echo -e "${RED}✗ Backup failed${NC}"
  rm -f "$BACKUP_FILE"
  exit 1
fi
