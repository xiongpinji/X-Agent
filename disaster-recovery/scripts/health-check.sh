#!/bin/bash

# X-Agent 灾难恢复 - 健康检查脚本
# 用途：定期检查系统健康状态，检测故障

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/var/log/xagent}"
LOG_FILE="${LOG_DIR}/health-check.log"
ALERT_THRESHOLD=3  # 连续失败次数阈值
CHECK_INTERVAL=10  # 检查间隔（秒）

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" | tee -a "$LOG_FILE"
}

# 创建日志目录
mkdir -p "$LOG_DIR"

# 检查应用健康状态
check_app_health() {
    local app_host="${1:-localhost}"
    local app_port="${2:-8000}"

    log "检查应用健康状态: $app_host:$app_port"

    if curl -sf "http://$app_host:$app_port/health" > /dev/null 2>&1; then
        log_success "应用健康检查通过"
        return 0
    else
        log_error "应用健康检查失败"
        return 1
    fi
}

# 检查PostgreSQL健康状态
check_postgres_health() {
    local db_host="${1:-localhost}"
    local db_port="${2:-5432}"
    local db_user="${3:-xagent}"
    local db_name="${4:-xagent_db}"

    log "检查PostgreSQL健康状态: $db_host:$db_port"

    if PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
        -c "SELECT 1" > /dev/null 2>&1; then
        log_success "PostgreSQL健康检查通过"

        # 检查复制延迟
        local replication_lag=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
            -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
            -t -c "SELECT EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp()))::int;" 2>/dev/null || echo "0")

        if [ "$replication_lag" -gt 300 ]; then
            log_warning "复制延迟过大: ${replication_lag}秒"
            return 1
        fi

        return 0
    else
        log_error "PostgreSQL健康检查失败"
        return 1
    fi
}

# 检查Redis健康状态
check_redis_health() {
    local redis_host="${1:-localhost}"
    local redis_port="${2:-6379}"

    log "检查Redis健康状态: $redis_host:$redis_port"

    if redis-cli -h "$redis_host" -p "$redis_port" PING > /dev/null 2>&1; then
        log_success "Redis健康检查通过"

        # 检查内存使用
        local memory_used=$(redis-cli -h "$redis_host" -p "$redis_port" INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        log "Redis内存使用: $memory_used"

        return 0
    else
        log_error "Redis健康检查失败"
        return 1
    fi
}

# 检查Qdrant健康状态
check_qdrant_health() {
    local qdrant_host="${1:-localhost}"
    local qdrant_port="${2:-6333}"

    log "检查Qdrant健康状态: $qdrant_host:$qdrant_port"

    if curl -sf "http://$qdrant_host:$qdrant_port/health" > /dev/null 2>&1; then
        log_success "Qdrant健康检查通过"
        return 0
    else
        log_error "Qdrant健康检查失败"
        return 1
    fi
}

# 检查Neo4j健康状态
check_neo4j_health() {
    local neo4j_host="${1:-localhost}"
    local neo4j_port="${2:-7687}"

    log "检查Neo4j健康状态: $neo4j_host:$neo4j_port"

    if timeout 5 bash -c "echo 'RETURN 1;' | cypher-shell -a bolt://$neo4j_host:$neo4j_port -u neo4j -p ${NEO4J_PASSWORD:-neo4j_secure_password}" > /dev/null 2>&1; then
        log_success "Neo4j健康检查通过"
        return 0
    else
        log_error "Neo4j健康检查失败"
        return 1
    fi
}

# 检查磁盘空间
check_disk_space() {
    log "检查磁盘空间"

    local threshold=80
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$usage" -gt "$threshold" ]; then
        log_error "磁盘使用率过高: ${usage}%"
        return 1
    else
        log_success "磁盘空间充足: ${usage}%"
        return 0
    fi
}

# 检查内存使用
check_memory_usage() {
    log "检查内存使用"

    local threshold=85
    local usage=$(free | awk 'NR==2 {printf("%.0f", $3/$2 * 100)}')

    if [ "$usage" -gt "$threshold" ]; then
        log_error "内存使用率过高: ${usage}%"
        return 1
    else
        log_success "内存使用率正常: ${usage}%"
        return 0
    fi
}

# 检查CPU使用
check_cpu_usage() {
    log "检查CPU使用"

    local threshold=80
    local usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{printf("%.0f", 100 - $1)}')

    if [ "$usage" -gt "$threshold" ]; then
        log_warning "CPU使用率较高: ${usage}%"
        return 1
    else
        log_success "CPU使用率正常: ${usage}%"
        return 0
    fi
}

# 执行所有检查
run_all_checks() {
    log "========== 开始健康检查 =========="

    local failed_checks=0

    # 应用检查
    check_app_health || ((failed_checks++))

    # 数据库检查
    check_postgres_health || ((failed_checks++))
    check_redis_health || ((failed_checks++))
    check_qdrant_health || ((failed_checks++))
    check_neo4j_health || ((failed_checks++))

    # 基础设施检查
    check_disk_space || ((failed_checks++))
    check_memory_usage || ((failed_checks++))
    check_cpu_usage || ((failed_checks++))

    log "========== 健康检查完成 =========="
    log "失败检查数: $failed_checks"

    if [ "$failed_checks" -ge "$ALERT_THRESHOLD" ]; then
        log_error "检查失败数超过阈值，触发告警"
        return 1
    fi

    return 0
}

# 持续监控模式
continuous_monitoring() {
    log "启动持续监控模式，检查间隔: ${CHECK_INTERVAL}秒"

    while true; do
        run_all_checks || {
            log_error "健康检查失败，可能需要故障转移"
            # 这里可以调用故障转移脚本
            # ./failover.sh --auto
        }
        sleep "$CHECK_INTERVAL"
    done
}

# 主函数
main() {
    case "${1:-check}" in
        check)
            run_all_checks
            ;;
        monitor)
            continuous_monitoring
            ;;
        *)
            echo "用法: $0 {check|monitor}"
            exit 1
            ;;
    esac
}

main "$@"
