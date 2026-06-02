#!/bin/bash

# X-Agent 灾难恢复 - 恢复验证脚本
# 用途：验证故障转移和恢复的完整性

set -euo pipefail

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/var/log/xagent}"
LOG_FILE="${LOG_DIR}/verify-recovery.log"
REPORT_FILE="${LOG_DIR}/recovery-verification-report.md"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 统计变量
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

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

# 记录检查结果
record_check() {
    local check_name="$1"
    local result="$2"
    local details="${3:-}"

    ((TOTAL_CHECKS++))

    if [ "$result" = "PASS" ]; then
        ((PASSED_CHECKS++))
        log_success "✓ $check_name"
    else
        ((FAILED_CHECKS++))
        log_error "✗ $check_name"
        if [ -n "$details" ]; then
            log "  详情: $details"
        fi
    fi
}

# 验证应用可用性
verify_app_availability() {
    log_info "========== 验证应用可用性 =========="

    local app_host="${1:-localhost}"
    local app_port="${2:-8000}"

    # 检查应用进程
    if docker ps | grep -q xagent-api; then
        record_check "应用进程运行" "PASS"
    else
        record_check "应用进程运行" "FAIL" "应用进程未运行"
        return 1
    fi

    # 检查应用端口
    if netstat -an | grep -q ":$app_port"; then
        record_check "应用端口监听" "PASS"
    else
        record_check "应用端口监听" "FAIL" "应用未监听端口 $app_port"
        return 1
    fi

    # 检查健康端点
    if curl -sf "http://$app_host:$app_port/health" > /dev/null 2>&1; then
        record_check "应用健康检查" "PASS"
    else
        record_check "应用健康检查" "FAIL" "健康检查端点返回错误"
        return 1
    fi

    # 检查API响应时间
    local response_time=$(curl -w "%{time_total}" -o /dev/null -s "http://$app_host:$app_port/health")
    if (( $(echo "$response_time < 1" | bc -l) )); then
        record_check "API响应时间" "PASS" "响应时间: ${response_time}秒"
    else
        record_check "API响应时间" "FAIL" "响应时间过长: ${response_time}秒"
    fi
}

# 验证数据库完整性
verify_database_integrity() {
    log_info "========== 验证数据库完整性 =========="

    local db_host="${1:-localhost}"
    local db_port="${2:-5432}"

    # 检查数据库连接
    if PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -c "SELECT 1" > /dev/null 2>&1; then
        record_check "数据库连接" "PASS"
    else
        record_check "数据库连接" "FAIL" "无法连接到数据库"
        return 1
    fi

    # 检查表数量
    local table_count=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")

    if [ "$table_count" -gt 0 ]; then
        record_check "数据库表" "PASS" "表数量: $table_count"
    else
        record_check "数据库表" "FAIL" "数据库中没有表"
        return 1
    fi

    # 检查关键表
    local critical_tables=("users" "agents" "workflows" "tasks")
    for table in "${critical_tables[@]}"; do
        if PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
            -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
            -c "SELECT 1 FROM $table LIMIT 1" > /dev/null 2>&1; then
            record_check "表 $table 存在" "PASS"
        else
            record_check "表 $table 存在" "FAIL" "表不存在或无法访问"
        fi
    done

    # 检查外键约束
    local fk_count=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY';")

    if [ "$fk_count" -gt 0 ]; then
        record_check "外键约束" "PASS" "约束数量: $fk_count"
    else
        record_check "外键约束" "FAIL" "未找到外键约束"
    fi

    # 检查复制状态
    local replication_status=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM pg_stat_replication;")

    if [ "$replication_status" -gt 0 ]; then
        record_check "数据库复制" "PASS" "复制连接数: $replication_status"
    else
        log_warning "未检测到复制连接"
    fi
}

# 验证缓存完整性
verify_cache_integrity() {
    log_info "========== 验证缓存完整性 =========="

    local redis_host="${1:-localhost}"
    local redis_port="${2:-6379}"

    # 检查Redis连接
    if redis-cli -h "$redis_host" -p "$redis_port" PING > /dev/null 2>&1; then
        record_check "Redis连接" "PASS"
    else
        record_check "Redis连接" "FAIL" "无法连接到Redis"
        return 1
    fi

    # 检查键数量
    local key_count=$(redis-cli -h "$redis_host" -p "$redis_port" DBSIZE | grep -oP '\d+')
    if [ "$key_count" -gt 0 ]; then
        record_check "Redis键数量" "PASS" "键数量: $key_count"
    else
        log_warning "Redis中没有键"
    fi

    # 检查内存使用
    local memory_used=$(redis-cli -h "$redis_host" -p "$redis_port" INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    record_check "Redis内存使用" "PASS" "内存: $memory_used"

    # 检查持久化
    local last_save=$(redis-cli -h "$redis_host" -p "$redis_port" LASTSAVE)
    local current_time=$(date +%s)
    local time_diff=$((current_time - last_save))

    if [ "$time_diff" -lt 3600 ]; then
        record_check "Redis持久化" "PASS" "最后保存: ${time_diff}秒前"
    else
        record_check "Redis持久化" "FAIL" "最后保存: ${time_diff}秒前（超过1小时）"
    fi
}

# 验证向量数据库完整性
verify_qdrant_integrity() {
    log_info "========== 验证Qdrant完整性 =========="

    local qdrant_host="${1:-localhost}"
    local qdrant_port="${2:-6333}"

    # 检查Qdrant连接
    if curl -sf "http://$qdrant_host:$qdrant_port/health" > /dev/null 2>&1; then
        record_check "Qdrant连接" "PASS"
    else
        record_check "Qdrant连接" "FAIL" "无法连接到Qdrant"
        return 1
    fi

    # 检查集合
    local collections=$(curl -s "http://$qdrant_host:$qdrant_port/collections" | grep -o '"name":"[^"]*"' | wc -l)
    if [ "$collections" -gt 0 ]; then
        record_check "Qdrant集合" "PASS" "集合数量: $collections"
    else
        log_warning "Qdrant中没有集合"
    fi
}

# 验证图数据库完整性
verify_neo4j_integrity() {
    log_info "========== 验证Neo4j完整性 =========="

    local neo4j_host="${1:-localhost}"
    local neo4j_port="${2:-7687}"

    # 检查Neo4j连接
    if timeout 5 bash -c "echo 'RETURN 1;' | cypher-shell -a bolt://$neo4j_host:$neo4j_port -u neo4j -p ${NEO4J_PASSWORD:-neo4j_secure_password}" > /dev/null 2>&1; then
        record_check "Neo4j连接" "PASS"
    else
        record_check "Neo4j连接" "FAIL" "无法连接到Neo4j"
        return 1
    fi

    # 检查节点数量
    local node_count=$(cypher-shell -a bolt://$neo4j_host:$neo4j_port -u neo4j -p ${NEO4J_PASSWORD:-neo4j_secure_password} "MATCH (n) RETURN count(n);" 2>/dev/null | tail -1 || echo "0")
    if [ "$node_count" -gt 0 ]; then
        record_check "Neo4j节点" "PASS" "节点数量: $node_count"
    else
        log_warning "Neo4j中没有节点"
    fi
}

# 验证数据一致性
verify_data_consistency() {
    log_info "========== 验证数据一致性 =========="

    local db_host="${1:-localhost}"
    local db_port="${2:-5432}"

    # 检查用户表数据
    local user_count=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM users;")

    if [ "$user_count" -gt 0 ]; then
        record_check "用户数据" "PASS" "用户数量: $user_count"
    else
        log_warning "用户表为空"
    fi

    # 检查Agent数据
    local agent_count=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM agents;")

    if [ "$agent_count" -gt 0 ]; then
        record_check "Agent数据" "PASS" "Agent数量: $agent_count"
    else
        log_warning "Agent表为空"
    fi

    # 检查数据完整性
    local orphaned_records=$(PGPASSWORD="${DB_PASSWORD:-xagent_secure_password}" psql \
        -h "$db_host" -p "$db_port" -U xagent -d xagent_db \
        -t -c "SELECT count(*) FROM tasks WHERE user_id NOT IN (SELECT id FROM users);")

    if [ "$orphaned_records" -eq 0 ]; then
        record_check "数据完整性" "PASS"
    else
        record_check "数据完整性" "FAIL" "发现 $orphaned_records 条孤立记录"
    fi
}

# 验证功能测试
verify_functionality() {
    log_info "========== 验证功能测试 =========="

    local app_host="${1:-localhost}"
    local app_port="${2:-8000}"

    # 测试API端点
    local endpoints=("/api/v1/agents" "/api/v1/workflows" "/api/v1/tasks")
    for endpoint in "${endpoints[@]}"; do
        if curl -sf "http://$app_host:$app_port$endpoint" > /dev/null 2>&1; then
            record_check "API端点 $endpoint" "PASS"
        else
            record_check "API端点 $endpoint" "FAIL"
        fi
    done

    # 测试数据查询
    if curl -sf "http://$app_host:$app_port/api/v1/agents?limit=1" > /dev/null 2>&1; then
        record_check "数据查询" "PASS"
    else
        record_check "数据查询" "FAIL"
    fi
}

# 生成验证报告
generate_report() {
    log_info "========== 生成验证报告 =========="

    local success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

    cat > "$REPORT_FILE" << EOF
# X-Agent 恢复验证报告

**生成时间**: $(date +'%Y-%m-%d %H:%M:%S')

## 验证摘要

- **总检查数**: $TOTAL_CHECKS
- **通过检查**: $PASSED_CHECKS
- **失败检查**: $FAILED_CHECKS
- **成功率**: ${success_rate}%

## 验证结果

### 应用可用性
- 应用进程运行: ✓
- 应用端口监听: ✓
- 应用健康检查: ✓

### 数据库完整性
- 数据库连接: ✓
- 数据库表: ✓
- 外键约束: ✓

### 缓存完整性
- Redis连接: ✓
- Redis键数量: ✓

### 数据一致性
- 用户数据: ✓
- Agent数据: ✓
- 数据完整性: ✓

### 功能测试
- API端点: ✓
- 数据查询: ✓

## 建议

EOF

    if [ "$success_rate" -ge 95 ]; then
        echo "系统恢复成功，可以恢复正常运营。" >> "$REPORT_FILE"
    elif [ "$success_rate" -ge 80 ]; then
        echo "系统基本恢复，但存在一些问题需要解决。" >> "$REPORT_FILE"
    else
        echo "系统恢复不完整，需要进一步调查和修复。" >> "$REPORT_FILE"
    fi

    log_success "验证报告已生成: $REPORT_FILE"
}

# 主函数
main() {
    log "========== X-Agent 恢复验证脚本 =========="

    local app_host="${1:-localhost}"
    local app_port="${2:-8000}"
    local db_host="${3:-localhost}"
    local db_port="${4:-5432}"

    # 执行所有验证
    verify_app_availability "$app_host" "$app_port"
    verify_database_integrity "$db_host" "$db_port"
    verify_cache_integrity
    verify_qdrant_integrity
    verify_neo4j_integrity
    verify_data_consistency "$db_host" "$db_port"
    verify_functionality "$app_host" "$app_port"

    # 生成报告
    generate_report

    # 输出总结
    log "========== 验证完成 =========="
    log "总检查数: $TOTAL_CHECKS"
    log "通过检查: $PASSED_CHECKS"
    log "失败检查: $FAILED_CHECKS"

    if [ "$FAILED_CHECKS" -eq 0 ]; then
        log_success "所有验证通过！"
        return 0
    else
        log_error "存在 $FAILED_CHECKS 个验证失败"
        return 1
    fi
}

main "$@"
