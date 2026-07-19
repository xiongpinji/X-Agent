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
# P1-17: Qdrant 快照 API 鉴权(可选)与集合清单(可选, 逗号分隔; 缺省自动发现)
QDRANT_API_KEY=${QDRANT_API_KEY:-}
QDRANT_COLLECTIONS=${QDRANT_COLLECTIONS:-}

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
# P1-17: 改用官方快照 API (POST /collections/{name}/snapshots 创建快照,
# 再 GET /collections/{name}/snapshots/{file} 下载; 恢复见 DISASTER_RECOVERY.md)。
# 旧实现调用的 /collections/backup 端点不存在, 会静默走入 warn 分支造成"假成功"。
log_info "Backing up Qdrant..."

QDRANT_BASE_URL="http://$QDRANT_HOST:$QDRANT_PORT"
QDRANT_AUTH_HEADER=()
if [ -n "${QDRANT_API_KEY:-}" ]; then
    QDRANT_AUTH_HEADER=(-H "api-key: $QDRANT_API_KEY")
fi

qdrant_backup_ok=true

# 集合清单: 优先 QDRANT_COLLECTIONS(逗号分隔显式指定), 否则自动发现
COLLECTIONS=()
if [ -n "${QDRANT_COLLECTIONS:-}" ]; then
    IFS=',' read -ra COLLECTIONS <<< "$QDRANT_COLLECTIONS"
    log_info "Qdrant collections (from QDRANT_COLLECTIONS): ${COLLECTIONS[*]}"
else
    collections_json=$(curl -sf "${QDRANT_AUTH_HEADER[@]}" "$QDRANT_BASE_URL/collections" 2>/dev/null || echo "")
    if [ -z "$collections_json" ]; then
        log_warn "Qdrant backup failed: 无法获取集合列表 ($QDRANT_BASE_URL/collections)"
        qdrant_backup_ok=false
    else
        if command -v jq &> /dev/null; then
            mapfile -t COLLECTIONS < <(echo "$collections_json" | jq -r '.result.collections[].name' 2>/dev/null)
        else
            # 无 jq 的降级解析(仅适配 Qdrant 返回的扁平 name 列表)
            mapfile -t COLLECTIONS < <(echo "$collections_json" | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*:[[:space:]]*"\([^"]*\)"/\1/')
        fi
        if [ "${#COLLECTIONS[@]}" -eq 0 ] && echo "$collections_json" | grep -q '"collections"'; then
            # 集合接口返回正常但解析为空 —— 显式告警, 不静默跳过
            log_warn "Qdrant 集合列表解析结果为空, 请检查响应格式或用 QDRANT_COLLECTIONS 显式指定"
        fi
        log_info "Qdrant collections (auto-discovered): ${COLLECTIONS[*]:-<none>}"
    fi
fi

qdrant_files=()
if [ "$qdrant_backup_ok" = true ]; then
    if [ "${#COLLECTIONS[@]}" -eq 0 ]; then
        log_warn "Qdrant 无任何集合, 跳过快照(空实例)"
    fi
    for collection in "${COLLECTIONS[@]}"; do
        log_info "Creating snapshot for collection: $collection"
        snapshot_resp=$(curl -sf -X POST "${QDRANT_AUTH_HEADER[@]}" \
            "$QDRANT_BASE_URL/collections/$collection/snapshots" 2>/dev/null || echo "")
        if [ -z "$snapshot_resp" ]; then
            log_warn "Qdrant snapshot creation failed for collection: $collection"
            qdrant_backup_ok=false
            continue
        fi
        if command -v jq &> /dev/null; then
            snapshot_name=$(echo "$snapshot_resp" | jq -r '.result.name' 2>/dev/null)
        else
            snapshot_name=$(echo "$snapshot_resp" | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"\([^"]*\)"/\1/')
        fi
        if [ -z "$snapshot_name" ] || [ "$snapshot_name" = "null" ]; then
            log_warn "Qdrant snapshot name not found in response for collection: $collection"
            qdrant_backup_ok=false
            continue
        fi
        out_file="$BACKUP_PATH/qdrant_${collection}.snapshot"
        if curl -sf "${QDRANT_AUTH_HEADER[@]}" \
            "$QDRANT_BASE_URL/collections/$collection/snapshots/$snapshot_name" \
            -o "$out_file"; then
            log_info "Qdrant snapshot downloaded: $out_file"
            qdrant_files+=("qdrant_${collection}.snapshot")
        else
            log_warn "Qdrant snapshot download failed for collection: $collection"
            qdrant_backup_ok=false
        fi
    done
fi

if [ "$qdrant_backup_ok" = true ]; then
    log_info "Qdrant backup completed (${#qdrant_files[@]} collection snapshot(s))"
    for f in ${qdrant_files[@]+"${qdrant_files[@]}"}; do
        ls -lh "$BACKUP_PATH/$f"
    done
else
    log_warn "Qdrant backup incomplete (continuing with other backups)"
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
# P1-17: jq 可选化 —— 有 jq 用 jq, 无 jq 用 bash 降级拼装(备份镜像内已装 jq)。
# 注意 pipefail: grep 无匹配会返回 1, 各管道尾部统一 `|| true` 兜底。
if command -v jq &> /dev/null; then
    FILES_JSON=$(ls -1 "$BACKUP_PATH" | grep -v manifest.json | jq -R -s -c 'split("\n")[:-1] | map(select(length>0))' || true)
    QDRANT_FILES_JSON=$(printf '%s\n' "${qdrant_files[@]:-}" | jq -R -s -c 'split("\n")[:-1] | map(select(length>0))' || true)
else
    FILES_JSON=$(ls -1 "$BACKUP_PATH" | grep -v manifest.json | sed 's/.*/"&"/' | paste -sd, - || true)
    FILES_JSON="[${FILES_JSON}]"
    # 空数组安全: ${arr[@]+...} 为空时不展开, for 零迭代退出码为 0
    qdrant_list=$(for f in ${qdrant_files[@]+"${qdrant_files[@]}"}; do printf '"%s",' "$f"; done)
    QDRANT_FILES_JSON="[${qdrant_list%,}]"
fi
[ -z "${FILES_JSON:-}" ] || [ "${FILES_JSON}" = "[null]" ] && FILES_JSON="[]"
[ -z "${QDRANT_FILES_JSON:-}" ] || [ "${QDRANT_FILES_JSON}" = "[null]" ] && QDRANT_FILES_JSON="[]"
cat > "$BACKUP_PATH/manifest.json" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "version": "1.1",
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
      "method": "snapshot-api",
      "files": $QDRANT_FILES_JSON
    }
  },
  "files": $FILES_JSON
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
