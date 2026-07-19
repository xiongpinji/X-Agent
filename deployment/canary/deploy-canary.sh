#!/bin/bash

# X-Agent Canary Deployment Script
# Implements gradual rollout with monitoring and automatic rollback

set -euo pipefail

# Configuration
NAMESPACE=${NAMESPACE:-production}
NEW_VERSION=${1:-}
CANARY_REPLICAS_STAGES=(1 2 3 5 10)
MONITORING_INTERVAL=${MONITORING_INTERVAL:-300}
ERROR_RATE_THRESHOLD=${ERROR_RATE_THRESHOLD:-0.01}
PROMETHEUS_URL=${PROMETHEUS_URL:-http://prometheus:9090}

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
    log_error "Usage: $0 <new_version>"
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

log_info "Starting canary deployment for version: $NEW_VERSION"
log_info "Namespace: $NAMESPACE"

# Step 1: Deploy canary version
log_step "Deploying canary version..."
kubectl set image deployment/xagent-canary \
    xagent="xagent:$NEW_VERSION" \
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
    xagent="xagent:$NEW_VERSION" \
    -n "$NAMESPACE"

kubectl set image deployment/xagent-worker \
    xagent="xagent:$NEW_VERSION" \
    -n "$NAMESPACE"

kubectl set image deployment/xagent-beat \
    xagent="xagent:$NEW_VERSION" \
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
