#!/bin/bash

# X-Agent Production Rollback Script
# Safely rolls back to a previous version with database recovery

set -euo pipefail

# Configuration
# P1-15: 默认命名空间对齐权威清单 deployment/k8s/ (namespace: xagent);
# 容器名与 deployment/k8s/*.yaml 一致(每个 Deployment 的容器名 == Deployment 名)
NAMESPACE=${NAMESPACE:-xagent}
DEPLOYMENT_API=${DEPLOYMENT_API:-xagent-api}
DEPLOYMENT_WORKER=${DEPLOYMENT_WORKER:-xagent-worker}
DEPLOYMENT_BEAT=${DEPLOYMENT_BEAT:-xagent-beat}
CONTAINER_API=${CONTAINER_API:-xagent-api}
CONTAINER_WORKER=${CONTAINER_WORKER:-xagent-worker}
CONTAINER_BEAT=${CONTAINER_BEAT:-xagent-beat}
SERVICE_NAME=${SERVICE_NAME:-xagent-api}
ROLLBACK_TIMEOUT=${ROLLBACK_TIMEOUT:-5m}
HEALTH_CHECK_RETRIES=${HEALTH_CHECK_RETRIES:-30}
HEALTH_CHECK_INTERVAL=${HEALTH_CHECK_INTERVAL:-10}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -v, --version VERSION       Rollback to specific version (default: previous)
    -d, --database              Also rollback database schema
    -n, --namespace NAMESPACE   Kubernetes namespace (default: xagent)
    -h, --help                  Show this help message

Examples:
    $0                          # Rollback to previous version
    $0 -v v1.0.0               # Rollback to specific version
    $0 -d                       # Rollback with database schema
EOF
    exit 1
}

# Parse arguments
ROLLBACK_VERSION=""
ROLLBACK_DATABASE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            ROLLBACK_VERSION="$2"
            shift 2
            ;;
        -d|--database)
            ROLLBACK_DATABASE=true
            shift
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Verify kubectl is available
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found. Please install kubectl."
    exit 1
fi

# Check namespace exists
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log_error "Namespace '$NAMESPACE' not found"
    exit 1
fi

log_info "Starting rollback process..."
log_info "Namespace: $NAMESPACE"

# Get current deployment info
log_info "Retrieving current deployment information..."
CURRENT_API_REPLICAS=$(kubectl get deployment "$DEPLOYMENT_API" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
CURRENT_WORKER_REPLICAS=$(kubectl get deployment "$DEPLOYMENT_WORKER" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')

log_info "Current API replicas: $CURRENT_API_REPLICAS"
log_info "Current Worker replicas: $CURRENT_WORKER_REPLICAS"

# Get revision history
log_info "Retrieving revision history..."
if [ -z "$ROLLBACK_VERSION" ]; then
    # Rollback to previous revision
    log_info "Rolling back to previous revision..."

    kubectl rollout undo deployment/"$DEPLOYMENT_API" -n "$NAMESPACE"
    kubectl rollout undo deployment/"$DEPLOYMENT_WORKER" -n "$NAMESPACE"
    kubectl rollout undo deployment/"$DEPLOYMENT_BEAT" -n "$NAMESPACE"
else
    # Rollback to specific version
    log_info "Rolling back to version: $ROLLBACK_VERSION"

    kubectl set image deployment/"$DEPLOYMENT_API" \
        "$CONTAINER_API=$ROLLBACK_VERSION" \
        -n "$NAMESPACE"

    kubectl set image deployment/"$DEPLOYMENT_WORKER" \
        "$CONTAINER_WORKER=$ROLLBACK_VERSION" \
        -n "$NAMESPACE"

    kubectl set image deployment/"$DEPLOYMENT_BEAT" \
        "$CONTAINER_BEAT=$ROLLBACK_VERSION" \
        -n "$NAMESPACE"
fi

# Wait for rollout to complete
log_info "Waiting for rollout to complete (timeout: $ROLLBACK_TIMEOUT)..."

if ! kubectl rollout status deployment/"$DEPLOYMENT_API" \
    -n "$NAMESPACE" \
    --timeout="$ROLLBACK_TIMEOUT"; then
    log_error "API deployment rollout failed"
    exit 1
fi

if ! kubectl rollout status deployment/"$DEPLOYMENT_WORKER" \
    -n "$NAMESPACE" \
    --timeout="$ROLLBACK_TIMEOUT"; then
    log_error "Worker deployment rollout failed"
    exit 1
fi

log_info "Deployments rolled back successfully"

# Rollback database if requested
if [ "$ROLLBACK_DATABASE" = true ]; then
    log_info "Rolling back database schema..."

    # Get a pod to run migration command
    POD=$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$POD" ]; then
        log_error "No API pod found for database rollback"
        exit 1
    fi

    log_info "Using pod: $POD"

    # Run rollback migration
    if kubectl exec -n "$NAMESPACE" "$POD" -- \
        python deployment/migrations/migrate.py rollback 1; then
        log_info "Database rollback completed"
    else
        log_error "Database rollback failed"
        exit 1
    fi
fi

# Health checks
log_info "Running health checks..."
HEALTH_CHECK_COUNT=0

while [ $HEALTH_CHECK_COUNT -lt $HEALTH_CHECK_RETRIES ]; do
    if kubectl exec -n "$NAMESPACE" \
        -it "$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')" \
        -- curl -f http://localhost:8000/health &> /dev/null; then
        log_info "Health check passed"
        break
    fi

    HEALTH_CHECK_COUNT=$((HEALTH_CHECK_COUNT + 1))
    log_warn "Health check attempt $HEALTH_CHECK_COUNT/$HEALTH_CHECK_RETRIES failed, retrying in ${HEALTH_CHECK_INTERVAL}s..."
    sleep "$HEALTH_CHECK_INTERVAL"
done

if [ $HEALTH_CHECK_COUNT -ge $HEALTH_CHECK_RETRIES ]; then
    log_error "Health checks failed after $HEALTH_CHECK_RETRIES attempts"
    exit 1
fi

# Verify service is responding
log_info "Verifying service endpoints..."
SERVICE_IP=$(kubectl get service "$SERVICE_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

if [ -n "$SERVICE_IP" ]; then
    log_info "Service IP: $SERVICE_IP"
fi

# Get pod status
log_info "Final pod status:"
kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o wide
kubectl get pods -n "$NAMESPACE" -l app=xagent-worker -o wide

log_info "Rollback completed successfully!"
log_info "Please verify the application is functioning correctly"

# Optional: Send notification
if command -v curl &> /dev/null && [ -n "${SLACK_WEBHOOK:-}" ]; then
    log_info "Sending Slack notification..."
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"X-Agent Production Rollback Completed\",
            \"blocks\": [
                {
                    \"type\": \"section\",
                    \"text\": {
                        \"type\": \"mrkdwn\",
                        \"text\": \"*X-Agent Production Rollback Completed*\nNamespace: $NAMESPACE\nDatabase Rollback: $ROLLBACK_DATABASE\nTime: $(date)\"
                    }
                }
            ]
        }" || log_warn "Failed to send Slack notification"
fi

exit 0
