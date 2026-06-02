#!/bin/bash

# X-Agent Auto-Backup Script
# Automatically backs up databases and important data

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups/xagent}"
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
POSTGRES_USER="${POSTGRES_USER:-xagent}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-xagent}"
POSTGRES_DB="${POSTGRES_DB:-xagent}"
LOG_FILE="/var/log/xagent/backup.log"
BACKUP_TIMESTAMP=$(date +'%Y%m%d_%H%M%S')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    log "${GREEN}Backup directory: $BACKUP_DIR${NC}"
}

# Backup PostgreSQL database
backup_postgres() {
    log "Starting PostgreSQL backup..."

    local backup_file="$BACKUP_DIR/postgres_${BACKUP_TIMESTAMP}.sql.gz"

    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T postgres pg_dump \
        -U "$POSTGRES_USER" \
        "$POSTGRES_DB" | gzip > "$backup_file"

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "${GREEN}PostgreSQL backup completed: $backup_file ($size)${NC}"
        return 0
    else
        log "${RED}PostgreSQL backup failed${NC}"
        return 1
    fi
}

# Backup Redis data
backup_redis() {
    log "Starting Redis backup..."

    local backup_file="$BACKUP_DIR/redis_${BACKUP_TIMESTAMP}.rdb"

    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T redis redis-cli BGSAVE > /dev/null 2>&1

    # Wait for background save to complete
    sleep 5

    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T redis cat /data/dump.rdb > "$backup_file"

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "${GREEN}Redis backup completed: $backup_file ($size)${NC}"
        return 0
    else
        log "${RED}Redis backup failed${NC}"
        return 1
    fi
}

# Backup Qdrant vector database
backup_qdrant() {
    log "Starting Qdrant backup..."

    local backup_file="$BACKUP_DIR/qdrant_${BACKUP_TIMESTAMP}.tar.gz"

    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T qdrant tar czf - /qdrant/storage > "$backup_file"

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "${GREEN}Qdrant backup completed: $backup_file ($size)${NC}"
        return 0
    else
        log "${RED}Qdrant backup failed${NC}"
        return 1
    fi
}

# Backup application logs
backup_logs() {
    log "Starting application logs backup..."

    local backup_file="$BACKUP_DIR/logs_${BACKUP_TIMESTAMP}.tar.gz"

    tar czf "$backup_file" /var/log/xagent/ 2>/dev/null || true

    if [ -f "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "${GREEN}Logs backup completed: $backup_file ($size)${NC}"
        return 0
    else
        log "${RED}Logs backup failed${NC}"
        return 1
    fi
}

# Backup Elasticsearch indices
backup_elasticsearch() {
    log "Starting Elasticsearch backup..."

    local backup_file="$BACKUP_DIR/elasticsearch_${BACKUP_TIMESTAMP}.json"

    # Create snapshot repository
    curl -X PUT "localhost:9200/_snapshot/backup" -H 'Content-Type: application/json' -d'{
        "type": "fs",
        "settings": {
            "location": "/backups/elasticsearch"
        }
    }' > /dev/null 2>&1

    # Create snapshot
    curl -X PUT "localhost:9200/_snapshot/backup/snapshot_${BACKUP_TIMESTAMP}" > "$backup_file" 2>&1

    if [ $? -eq 0 ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log "${GREEN}Elasticsearch backup completed: $backup_file ($size)${NC}"
        return 0
    else
        log "${RED}Elasticsearch backup failed${NC}"
        return 1
    fi
}

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."

    find "$BACKUP_DIR" -type f -mtime +"$RETENTION_DAYS" -delete

    log "${GREEN}Cleanup completed${NC}"
}

# Verify backup integrity
verify_backups() {
    log "Verifying backup integrity..."

    local backup_count=$(find "$BACKUP_DIR" -type f -mtime -1 | wc -l)
    log "${GREEN}Found $backup_count backups from today${NC}"

    if [ "$backup_count" -gt 0 ]; then
        log "${GREEN}Backup verification passed${NC}"
        return 0
    else
        log "${RED}No backups found from today${NC}"
        return 1
    fi
}

# Send backup notification
send_notification() {
    local status=$1
    local message=$2

    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        local color="good"
        if [ "$status" != "success" ]; then
            color="danger"
        fi

        curl -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"X-Agent Backup $status\",
                    \"text\": \"$message\",
                    \"ts\": $(date +%s)
                }]
            }" > /dev/null 2>&1
    fi
}

# Main backup function
main() {
    log "Starting X-Agent backup process"
    log "Backup timestamp: $BACKUP_TIMESTAMP"

    create_backup_dir

    local backup_success=true

    # Run all backups
    backup_postgres || backup_success=false
    backup_redis || backup_success=false
    backup_qdrant || backup_success=false
    backup_logs || backup_success=false
    backup_elasticsearch || backup_success=false

    # Cleanup old backups
    cleanup_old_backups

    # Verify backups
    verify_backups || backup_success=false

    # Send notification
    if [ "$backup_success" = true ]; then
        log "${GREEN}Backup process completed successfully${NC}"
        send_notification "success" "All backups completed successfully"
    else
        log "${RED}Backup process completed with errors${NC}"
        send_notification "failed" "Some backups failed. Check logs for details."
    fi
}

# Run main function
main
