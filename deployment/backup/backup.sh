#!/bin/bash

# X-Agent Backup Script
# Backs up all critical data: database, Redis, Qdrant, and configuration

set -euo pipefail

# Configuration
BACKUP_DIR=${BACKUP_DIR:-/backups}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"
RETENTION_DAYS=${RETENTION_DAYS:-30}
S3_ENABLED=${S3_ENABLED:-false}
S3_BUCKET=${S3_BUCKET:-}
S3_REGION=${S3_REGION:-us-east-1}

# Database
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-xagent}
DB_NAME=${DB_NAME:-xagent_prod}
DB_PASSWORD=${DB_PASSWORD:-}

# Redis
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${REDIS_PASSWORD:-}

# Qdrant
QDRANT_HOST=${QDRANT_HOST:-localhost}
QDRANT_PORT=${QDRANT_PORT:-6333}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "$BACKUP_PATH"
log_info "Backup directory: $BACKUP_PATH"

# Backup PostgreSQL
log_info "Backing up PostgreSQL database..."
if [ -n "$DB_PASSWORD" ]; then
    export PGPASSWORD="$DB_PASSWORD"
fi

if pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=custom \
    --file="$BACKUP_PATH/database.dump" \
    --verbose; then
    log_info "PostgreSQL backup completed"
    ls -lh "$BACKUP_PATH/database.dump"
else
    log_error "PostgreSQL backup failed"
    exit 1
fi

# Backup Redis
log_info "Backing up Redis..."
if [ -n "$REDIS_PASSWORD" ]; then
    REDIS_CLI_ARGS="-h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD"
else
    REDIS_CLI_ARGS="-h $REDIS_HOST -p $REDIS_PORT"
fi

if redis-cli $REDIS_CLI_ARGS --rdb "$BACKUP_PATH/redis.rdb" > /dev/null 2>&1; then
    log_info "Redis backup completed"
    ls -lh "$BACKUP_PATH/redis.rdb"
else
    log_warn "Redis backup failed (continuing with other backups)"
fi

# Backup Qdrant
log_info "Backing up Qdrant..."
if curl -s -X POST "http://$QDRANT_HOST:$QDRANT_PORT/collections/backup" \
    -o "$BACKUP_PATH/qdrant.backup" 2>/dev/null; then
    log_info "Qdrant backup completed"
    ls -lh "$BACKUP_PATH/qdrant.backup"
else
    log_warn "Qdrant backup failed (continuing with other backups)"
fi

# Backup configuration files
log_info "Backing up configuration files..."
if [ -d "/etc/xagent" ]; then
    cp -r /etc/xagent "$BACKUP_PATH/config"
    log_info "Configuration backup completed"
else
    log_warn "Configuration directory not found"
fi

# Create backup manifest
log_info "Creating backup manifest..."
cat > "$BACKUP_PATH/manifest.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "version": "1.0",
  "components": {
    "database": {
      "type": "postgresql",
      "host": "$DB_HOST",
      "port": $DB_PORT,
      "database": "$DB_NAME",
      "file": "database.dump"
    },
    "redis": {
      "type": "redis",
      "host": "$REDIS_HOST",
      "port": $REDIS_PORT,
      "file": "redis.rdb"
    },
    "qdrant": {
      "type": "qdrant",
      "host": "$QDRANT_HOST",
      "port": $QDRANT_PORT,
      "file": "qdrant.backup"
    }
  },
  "files": $(ls -1 "$BACKUP_PATH" | grep -v manifest.json | jq -R -s -c 'split("\n")[:-1]')
}
EOF

# Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
log_info "Total backup size: $BACKUP_SIZE"

# Upload to S3 if enabled
if [ "$S3_ENABLED" = true ] && [ -n "$S3_BUCKET" ]; then
    log_info "Uploading backup to S3..."
    if command -v aws &> /dev/null; then
        if aws s3 sync "$BACKUP_PATH" "s3://$S3_BUCKET/$TIMESTAMP/" \
            --region "$S3_REGION" \
            --sse AES256; then
            log_info "S3 upload completed"
        else
            log_error "S3 upload failed"
            exit 1
        fi
    else
        log_warn "AWS CLI not found, skipping S3 upload"
    fi
fi

# Cleanup old backups
log_info "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf {} \; 2>/dev/null || true

# List recent backups
log_info "Recent backups:"
ls -lhd "$BACKUP_DIR"/*/ | tail -5

log_info "Backup completed successfully!"
log_info "Backup path: $BACKUP_PATH"

# Send notification
if [ -n "${SLACK_WEBHOOK:-}" ]; then
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"X-Agent backup completed\",
            \"blocks\": [
                {
                    \"type\": \"section\",
                    \"text\": {
                        \"type\": \"mrkdwn\",
                        \"text\": \"*X-Agent Backup Completed*\nSize: $BACKUP_SIZE\nPath: $BACKUP_PATH\nTime: $(date)\"
                    }
                }
            ]
        }" || log_warn "Failed to send Slack notification"
fi

exit 0
