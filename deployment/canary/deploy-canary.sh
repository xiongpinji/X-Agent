#!/bin/bash

# X-Agent Canary Deployment Script
# P2-05: 支持两种模式:
#   1. Argo Rollouts 模式 (默认): 声明式金丝雀, 权重路由 + 自动指标门控
#   2. Legacy 模式 (--legacy): 手动副本扩缩, 兼容未安装 Argo Rollouts 的环境
#
# 用法:
#   ./deploy-canary.sh <version>              # Argo Rollouts 模式
#   ./deploy-canary.sh <version> --legacy     # 手动模式 (fallback)
#   ./deploy-canary.sh <version> --abort      # 中止金丝雀
#   ./deploy-canary.sh <version> --promote    # 手动推进到下一步
#   ./deploy-canary.sh <version> --status     # 查看金丝雀状态

set -euo pipefail

# Configuration
# P1-15: 命名空间与容器名对齐权威清单 deployment/k8s/ 与 deployment/canary/
NAMESPACE=${NAMESPACE:-xagent}
NEW_VERSION=${1:-}
MODE=${2:-"--argo"}
ROLLOUT_NAME=xagent-api-rollout
CANARY_REPLICAS_STAGES=(1 2 3 5 10)
MONITORING_INTERVAL=${MONITORING_INTERVAL:-300}
ERROR_RATE_THRESHOLD=${ERROR_RATE_THRESHOLD:-0.01}
PROMETHEUS_URL=${PROMETHEUS_URL:-http://prometheus:9090}
# 容器名 == 各 Deployment 名(deployment/k8s/*.yaml 与 canary-deployment.yaml 的约定)
CONTAINER_API=xagent-api
CONTAINER_WORKER=xagent-worker
CONTAINER_BEAT=xagent-beat
CONTAINER_CANARY=xagent-api

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Validation
if [ -z "$NEW_VERSION" ]; then
    log_error "Usage: $0 <new_version> [--legacy|--abort|--promote|--status]"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found"
    exit 1
fi

if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_error "Namespace '$NAMESPACE' not found"
    exit 1
fi

# ============================================================
# P2-05: Argo Rollouts 模式 (默认)
# ============================================================
argo_rollouts_available() {
    kubectl get crd rollouts.argoproj.io &> /dev/null 2>&1
}

argo_deploy() {
    log_info "[Argo Rollouts] Starting canary deployment for version: $NEW_VERSION"
    log_info "Namespace: $NAMESPACE | Rollout: $ROLLOUT_NAME"

    # 设置新镜像触发金丝雀
    kubectl argo rollouts set image "$ROLLOUT_NAME" \
        "$CONTAINER_API=xagent:$NEW_VERSION" \
        -n "$NAMESPACE" || {
        log_error "Failed to set image on rollout"
        exit 1
    }

    log_info "Canary rollout triggered. Steps: 5% → 20% → 50% → 80% → 100%"
    log_info "Analysis gates: success-rate >= 99%, P95 latency <= 1s"
    log_info ""
    log_info "Monitor with: kubectl argo rollouts status $ROLLOUT_NAME -n $NAMESPACE"
    log_info "Abort with:   kubectl argo rollouts abort $ROLLOUT_NAME -n $NAMESPACE"
    log_info "Promote with: kubectl argo rollouts promote $ROLLOUT_NAME -n $NAMESPACE"

    # 等待初始 Pod 就绪
    log_step "Waiting for canary pods to be ready..."
    kubectl argo rollouts status "$ROLLOUT_NAME" -n "$NAMESPACE" --timeout 120 || true

    log_info "Canary deployment initiated successfully."
    log_info "Argo Rollouts will automatically advance through steps based on analysis."
}

argo_abort() {
    log_warn "[Argo Rollouts] Aborting canary rollout..."
    kubectl argo rollouts abort "$ROLLOUT_NAME" -n "$NAMESPACE"
    log_info "Rollout aborted. Traffic reverted to stable."
}

argo_promote() {
    log_info "[Argo Rollouts] Manually promoting to next step..."
    kubectl argo rollouts promote "$ROLLOUT_NAME" -n "$NAMESPACE"
    log_info "Promoted. Check status for current weight."
}

argo_status() {
    kubectl argo rollouts status "$ROLLOUT_NAME" -n "$NAMESPACE"
    echo ""
    log_info "AnalysisRuns:"
    kubectl get analysisrun -n "$NAMESPACE" -l rollouts.argoproj.io/rollout-name="$ROLLOUT_NAME" 2>/dev/null || true
}

# 路由: 根据 MODE 参数选择执行路径
case "$MODE" in
    --abort)
        argo_abort
        exit 0
        ;;
    --promote)
        argo_promote
        exit 0
        ;;
    --status)
        argo_status
        exit 0
        ;;
    --legacy)
        log_warn "Using legacy mode (manual replica scaling)"
        ;;
    --argo|"")
        if argo_rollouts_available; then
            argo_deploy
            exit 0
        else
            log_warn "Argo Rollouts CRD not found. Falling back to legacy mode."
            log_warn "Install: kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml"
        fi
        ;;
    *)
        log_error "Unknown mode: $MODE"
        log_error "Usage: $0 <version> [--legacy|--abort|--promote|--status]"
        exit 1
        ;;
esac

# ============================================================
# Legacy 模式: 手动副本扩缩 (原逻辑, 兼容无 Argo Rollouts 环境)
# ============================================================
log_info "Starting canary deployment for version: $NEW_VERSION (legacy mode)"
log_info "Namespace: $NAMESPACE"

# Step 1: Deploy canary version
log_step "Deploying canary version..."
kubectl set image deployment/xagent-canary \
    "$CONTAINER_CANARY=xagent:$NEW_VERSION" \
    -n "$NAMESPACE" || {
    log_error "Failed to set canary image"
    exit 1
}

kubectl scale deployment/xagent-canary --replicas=1 -n "$NAMESPACE"
kubectl rollout status deployment/xagent-canary -n "$NAMESPACE" --timeout=5m

log_info "Canary deployment started with 1 replica"

# Step 2: Monitor canary
log_step "Monitoring canary deployment..."
sleep "$MONITORING_INTERVAL"

# Check error rate
# 注意: 判据依赖 http_requests_total{version=...} 指标; 该指标由后端 Prometheus 中间件产生,
# 其接线属于监控子系统范围(P0-04)。若指标缺失, Prometheus 返回空结果, 错误率按 0 处理 —
# 即金丝雀门控会"降级为仅按时间推进", 不会误报失败, 也不会拦截真实故障。接入指标前请知悉该限制。
check_error_rate() {
    local version=$1
    local query="rate(http_requests_total{version='$version',status=~'5..'}[5m])"

    local response=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=${query}" 2>/dev/null || echo "{}")
    local error_rate=$(echo "$response" | grep -o '"value":\[[^]]*\]' | tail -1 | grep -o '[0-9.]*' | tail -1 || echo "0")

    echo "$error_rate"
}

log_info "Checking error rate for canary..."
ERROR_RATE=$(check_error_rate "canary")
log_info "Canary error rate: $ERROR_RATE"

if (( $(echo "$ERROR_RATE > $ERROR_RATE_THRESHOLD" | bc -l) )); then
    log_error "High error rate detected: $ERROR_RATE > $ERROR_RATE_THRESHOLD"
    log_info "Rolling back canary..."
    kubectl scale deployment/xagent-canary --replicas=0 -n "$NAMESPACE"
    exit 1
fi

log_info "Error rate acceptable, proceeding with gradual rollout"

# Step 3: Gradual traffic shift
log_step "Gradually increasing canary replicas..."

for REPLICAS in "${CANARY_REPLICAS_STAGES[@]}"; do
    log_info "Scaling canary to $REPLICAS replicas..."
    kubectl scale deployment/xagent-canary --replicas="$REPLICAS" -n "$NAMESPACE"

    # Wait for replicas to be ready
    kubectl rollout status deployment/xagent-canary -n "$NAMESPACE" --timeout=5m

    # Monitor
    log_info "Monitoring for ${MONITORING_INTERVAL}s..."
    sleep "$MONITORING_INTERVAL"

    # Check metrics
    ERROR_RATE=$(check_error_rate "canary")
    log_info "Error rate at $REPLICAS replicas: $ERROR_RATE"

    if (( $(echo "$ERROR_RATE > $ERROR_RATE_THRESHOLD" | bc -l) )); then
        log_error "High error rate detected at $REPLICAS replicas"
        log_info "Rolling back..."
        kubectl scale deployment/xagent-canary --replicas=0 -n "$NAMESPACE"
        exit 1
    fi

    # Check latency
    LATENCY=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket{version='canary'}[5m]))" 2>/dev/null | grep -o '[0-9.]*' | tail -1 || echo "0")
    log_info "P95 latency: ${LATENCY}s"

    if (( $(echo "$LATENCY > 1.0" | bc -l) )); then
        log_warn "High latency detected: ${LATENCY}s"
    fi
done

# Step 4: Full rollout
log_step "Promoting canary to stable..."

# Get current stable replicas
STABLE_REPLICAS=$(kubectl get deployment/xagent-api -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
log_info "Current stable replicas: $STABLE_REPLICAS"

# Update stable deployment
kubectl set image deployment/xagent-api \
    "$CONTAINER_API=xagent:$NEW_VERSION" \
    -n "$NAMESPACE"

kubectl set image deployment/xagent-worker \
    "$CONTAINER_WORKER=xagent:$NEW_VERSION" \
    -n "$NAMESPACE"

kubectl set image deployment/xagent-beat \
    "$CONTAINER_BEAT=xagent:$NEW_VERSION" \
    -n "$NAMESPACE"

# Wait for rollout
log_info "Waiting for stable deployment rollout..."
kubectl rollout status deployment/xagent-api -n "$NAMESPACE" --timeout=10m
kubectl rollout status deployment/xagent-worker -n "$NAMESPACE" --timeout=10m

# Scale down canary
log_info "Scaling down canary deployment..."
kubectl scale deployment/xagent-canary --replicas=0 -n "$NAMESPACE"

# Final verification
log_step "Final verification..."
sleep 30

FINAL_ERROR_RATE=$(check_error_rate "stable")
log_info "Final error rate: $FINAL_ERROR_RATE"

if (( $(echo "$FINAL_ERROR_RATE > $ERROR_RATE_THRESHOLD" | bc -l) )); then
    log_error "High error rate in stable deployment"
    log_info "Initiating rollback..."
    kubectl rollout undo deployment/xagent-api -n "$NAMESPACE"
    kubectl rollout undo deployment/xagent-worker -n "$NAMESPACE"
    kubectl rollout status deployment/xagent-api -n "$NAMESPACE" --timeout=5m
    exit 1
fi

log_info "Canary deployment completed successfully!"
log_info "Version $NEW_VERSION is now in production"

# Notification
if [ -n "${SLACK_WEBHOOK:-}" ]; then
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"Canary deployment successful\",
            \"blocks\": [
                {
                    \"type\": \"section\",
                    \"text\": {
                        \"type\": \"mrkdwn\",
                        \"text\": \"*Canary Deployment Successful*\nVersion: $NEW_VERSION\nNamespace: $NAMESPACE\nTime: $(date)\"
                    }
                }
            ]
        }" || log_warn "Failed to send Slack notification"
fi

exit 0
