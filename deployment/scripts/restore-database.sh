#!/bin/bash
set -e

# X-Agent Database Restore Script
# Usage: bash deployment/scripts/restore-database.sh <backup_file>

if [ -z "$1" ]; then
  echo "Usage: bash deployment/scripts/restore-database.sh <backup_file>"
  echo "Example: bash deployment/scripts/restore-database.sh backup-20260527-120000.sql.gz"
  exit 1
fi

BACKUP_FILE="$1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
  echo -e "${RED}✗ Backup file not found: $BACKUP_FILE${NC}"
  exit 1
fi

echo -e "${YELLOW}Starting database restore...${NC}"
echo "Backup file: $BACKUP_FILE"

# Get database connection details from environment
DB_HOST="${XAGENT_DATABASE_HOST:-localhost}"
DB_PORT="${XAGENT_DATABASE_PORT:-5432}"
DB_USER="${XAGENT_DATABASE_USER:-xagent}"
DB_NAME="${XAGENT_DATABASE_NAME:-xagent}"

# Confirm restore
echo -e "${YELLOW}WARNING: This will overwrite the current database!${NC}"
read -p "Are you sure you want to restore from $BACKUP_FILE? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "Restore cancelled"
  exit 0
fi

# Drop existing database
echo "Dropping existing database..."
PGPASSWORD="$XAGENT_DATABASE_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "DROP DATABASE IF EXISTS $DB_NAME;" || true

# Create new database
echo "Creating new database..."
PGPASSWORD="$XAGENT_DATABASE_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "CREATE DATABASE $DB_NAME;"

# Restore from backup
echo "Restoring from backup..."
if gunzip -c "$BACKUP_FILE" | PGPASSWORD="$XAGENT_DATABASE_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --no-password; then

  echo -e "${GREEN}✓ Restore completed successfully${NC}"
  exit 0
else
  echo -e "${RED}✗ Restore failed${NC}"
  exit 1
fi
