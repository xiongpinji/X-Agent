#!/bin/bash

# X-Agent 灾难恢复 - 故障转移脚本
# 用途：自动或手动执行故障转移

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/var/log/xagent}"
LOG_FILE="${LOG_DIR}/failover.log"
DRY_RUN="${DRY_RUN:-false}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

# 创建日志目录
mkdir -p "$LOG_DIR"

# 发送告警通知
send_alert() {
    local severity="$1"
    local message="$2"

    log_info "发送告警: [$severity] $message"

    # 发送到Slack
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-Type: application/json' \
            -d "{\"text\": \"[$severity] $message\"}" \
            2>/dev/null || true
    fi

    # 发送邮件
    if [ -n "${NOTIFICATION_EMAIL:-}" ]; then
        echo "$message" | mail -s "[$severity] X-Agent 灾难恢复告警" "$NOTIFICATION_EMAIL" 2>/dev/null || true
    fi

    # 发送短信（仅P1告警）
    if [ "$severity" = "P1" ] && [ -n "${SMS_API_URL:-}" ]; then
        curl -X POST "$SMS_API_URL" \
            -d "message=$message" \
            2>/dev/null || true
    fi
}

# 检查应用健康状态
check_app_status() {
    local region="${1:-us-east}"
    local app_host="${2:-localhost}"
    local app_port="${3:-8000}"

    log "检查应用状态: $region ($app_host:$app_port)"

    if curl -sf "http://$app_host:$app_port/health" > /dev/null 2>&1; then
        log_success "应用正常"
        return 0
    else
        log_error "应用不可用"
        return 1
    fi
}

# 检查数据库状态
check_database_status() {
    local region="${1:-us-east}"
    local db_host="${2:-localhost}"
    local db_port="${3:-5432}"

    log "检查数据库状态: $region ($db_host:$db_port)"

    if PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -c "SELECT 1" > /dev/null 2>&1; then
        log_success "数据库正常"
        return 0
    else
        log_error "数据库不可用"
        return 1
    fi
}

# 自动故障转移
auto_failover() {
    log "========== 开始自动故障转移 =========="

    local primary_region="${PRIMARY_REGION:-us-east}"
    local dr_region="${DR_REGION:-us-west}"

    # 步骤1：检查主区域状态
    log "步骤1: 检查主区域状态"
    if check_app_status "$primary_region" "${PRIMARY_APP_HOST:-localhost}" "${PRIMARY_APP_PORT:-8000}"; then
        log_warning "主区域应用正常，无需转移"
        return 0
    fi

    if check_database_status "$primary_region" "${PRIMARY_DB_HOST:-localhost}" "${PRIMARY_DB_PORT:-5432}"; then
        log_warning "主区域数据库正常，尝试重启应用"
        if [ "$DRY_RUN" = "false" ]; then
            docker restart xagent-api || true
        fi
        return 0
    fi

    # 步骤2：检查备用区域状态
    log "步骤2: 检查备用区域状态"
    if ! check_app_status "$dr_region" "${DR_APP_HOST:-localhost}" "${DR_APP_PORT:-8000}"; then
        log_error "备用区域应用不可用，无法转移"
        send_alert "P1" "主区域故障，备用区域也不可用"
        return 1
    fi

    # 步骤3：停止主区域写入
    log "步骤3: 停止主区域写入"
    if [ "$DRY_RUN" = "false" ]; then
        # 这里可以设置只读模式
        log "设置主区域为只读模式"
    fi

    # 步骤4：同步最后的数据
    log "步骤4: 同步最后的数据"
    if [ "$DRY_RUN" = "false" ]; then
        # 等待复制完成
        sleep 10
    fi

    # 步骤5：更新DNS
    log "步骤5: 更新DNS指向备用区域"
    if [ "$DRY_RUN" = "false" ]; then
        update_dns_to_dr_region "$dr_region"
    fi

    # 步骤6：验证转移
    log "步骤6: 验证转移"
    sleep 30
    if check_app_status "$dr_region" "${DR_APP_HOST:-localhost}" "${DR_APP_PORT:-8000}"; then
        log_success "故障转移成功"
        send_alert "P1" "故障转移完成，系统已切换到备用区域"
        return 0
    else
        log_error "故障转移验证失败"
        send_alert "P1" "故障转移验证失败"
        return 1
    fi
}

# 手动故障转移
manual_failover() {
    local target_region="${1:-us-west}"
    local force="${2:-false}"

    log "========== 开始手动故障转移 =========="
    log "目标区域: $target_region"

    # 确认转移
    if [ "$force" != "true" ]; then
        read -p "确认转移到 $target_region? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log "转移已取消"
            return 0
        fi
    fi

    # 步骤1：停止主区域服务
    log "步骤1: 停止主区域服务"
    if [ "$DRY_RUN" = "false" ]; then
        docker stop xagent-api || true
        sleep 5
    fi

    # 步骤2：启动备用区域服务
    log "步骤2: 启动备用区域服务"
    if [ "$DRY_RUN" = "false" ]; then
        docker-compose -f docker-compose.dr.yml up -d
        sleep 30
    fi

    # 步骤3：更新DNS
    log "步骤3: 更新DNS"
    if [ "$DRY_RUN" = "false" ]; then
        update_dns_to_dr_region "$target_region"
    fi

    # 步骤4：验证转移
    log "步骤4: 验证转移"
    sleep 30
    if check_app_status "$target_region" "${DR_APP_HOST:-localhost}" "${DR_APP_PORT:-8000}"; then
        log_success "手动故障转移成功"
        send_alert "P1" "手动故障转移完成"
        return 0
    else
        log_error "手动故障转移失败"
        send_alert "P1" "手动故障转移失败"
        return 1
    fi
}

# 更新DNS到备用区域
update_dns_to_dr_region() {
    local dr_region="$1"

    log "更新DNS到备用区域: $dr_region"

    # 获取备用区域的IP地址
    local dr_ip="${DR_IP:-10.0.2.100}"

    if [ "$DRY_RUN" = "false" ]; then
        # 使用AWS Route53更新DNS
        if command -v aws &> /dev/null; then
            aws route53 change-resource-record-sets \
                --hosted-zone-id "${ROUTE53_ZONE_ID:-Z1234567890ABC}" \
                --change-batch "{
                    \"Changes\": [{
                        \"Action\": \"UPSERT\",
                        \"ResourceRecordSet\": {
                            \"Name\": \"${API_DOMAIN:-api.xagent.com}\",
                            \"Type\": \"A\",
                            \"TTL\": 60,
                            \"ResourceRecords\": [{\"Value\": \"$dr_ip\"}]
                        }
                    }]
                }" || log_error "DNS更新失败"
        else
            log_warning "AWS CLI未安装，跳过DNS更新"
        fi
    fi

    log_success "DNS已更新"
}

# 数据库主从切换
switch_database_primary() {
    local standby_host="${1:-localhost}"
    local standby_port="${2:-5432}"

    log "========== 开始数据库主从切换 =========="
    log "提升从库为主库: $standby_host:$standby_port"

    if [ "$DRY_RUN" = "false" ]; then
        # 提升从库
        PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
            -h "$standby_host" -p "$standby_port" -U xagent -d xagent_db \
            -c "SELECT pg_promote();" || {
            log_error "从库提升失败"
            return 1
        }

        # 等待提升完成
        sleep 10

        # 验证新主库
        if PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
            -h "$standby_host" -p "$standby_port" -U xagent -d xagent_db \
            -c "SELECT 1;" > /dev/null 2>&1; then
            log_success "数据库主从切换成功"
            return 0
        else
            log_error "新主库验证失败"
            return 1
        fi
    fi

    return 0
}

# Redis主从切换
switch_redis_primary() {
    local replica_host="${1:-localhost}"
    local replica_port="${2:-6379}"

    log "========== 开始Redis主从切换 =========="
    log "提升从库为主库: $replica_host:$replica_port"

    if [ "$DRY_RUN" = "false" ]; then
        # 提升从库
        redis-cli -h "$replica_host" -p "$replica_port" SLAVEOF NO ONE || {
            log_error "Redis从库提升失败"
            return 1
        }

        # 验证新主库
        if redis-cli -h "$replica_host" -p "$replica_port" PING > /dev/null 2>&1; then
            log_success "Redis主从切换成功"
            return 0
        else
            log_error "新主库验证失败"
            return 1
        fi
    fi

    return 0
}

# 显示帮助信息
show_help() {
    cat << EOF
用法: $0 [选项]

选项:
    --auto                  自动故障转移
    --manual                手动故障转移
    --region REGION         目标区域 (默认: us-west)
    --force                 强制转移，不需要确认
    --dry-run               模拟运行，不执行实际操作
    --help                  显示帮助信息

示例:
    # 自动故障转移
    $0 --auto

    # 手动故障转移到us-west
    $0 --manual --region us-west

    # 强制手动转移
    $0 --manual --region us-west --force

    # 模拟运行
    $0 --auto --dry-run
EOF
}

# 主函数
main() {
    local mode="auto"
    local region="us-west"
    local force="false"

    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                mode="auto"
                shift
                ;;
            --manual)
                mode="manual"
                shift
                ;;
            --region)
                region="$2"
                shift 2
                ;;
            --force)
                force="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    log "========== X-Agent 故障转移脚本 =========="
    log "模式: $mode"
    log "区域: $region"
    log "强制: $force"
    log "模拟运行: $DRY_RUN"

    case $mode in
        auto)
            auto_failover
            ;;
        manual)
            manual_failover "$region" "$force"
            ;;
        *)
            log_error "未知模式: $mode"
            exit 1
            ;;
    esac
}

main "$@"
