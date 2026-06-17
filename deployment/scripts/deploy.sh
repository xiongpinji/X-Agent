#!/bin/bash
set -e

# X-Agent Production Deployment Script
# This script deploys X-Agent to Kubernetes using Helm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
NAMESPACE=${NAMESPACE:-xagent}
RELEASE_NAME=${RELEASE_NAME:-xagent}
ENVIRONMENT=${ENVIRONMENT:-production}
HELM_CHART_PATH="${HELM_CHART_PATH:-$PROJECT_ROOT/deployment/helm}"
# SECURITY: deploy an immutable, explicit image tag. Avoid mutable ":latest"
# in production so rollouts and rollbacks are reproducible. Override with
# IMAGE_TAG (e.g. a git SHA or release version).
IMAGE_REPO=${IMAGE_REPO:-xagent}
IMAGE_TAG=${IMAGE_TAG:-1.0.0}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_warn "docker is not installed (needed for building images)"
    fi

    log_info "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."

    if ! command -v docker &> /dev/null; then
        log_warn "Skipping Docker build (docker not installed)"
        return
    fi

    cd "$PROJECT_ROOT"
    docker build -t "${IMAGE_REPO}:${IMAGE_TAG}" -f Dockerfile .
    log_info "Docker image built successfully: ${IMAGE_REPO}:${IMAGE_TAG}"
}

# Create namespace
create_namespace() {
    log_info "Creating namespace: $NAMESPACE"

    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    log_info "Namespace created/updated"
}

# Deploy with Helm
deploy_helm() {
    log_info "Deploying with Helm..."

    if [ ! -f "$HELM_CHART_PATH/Chart.yaml" ]; then
        log_error "Helm chart not found at: $HELM_CHART_PATH"
        exit 1
    fi

    local values_file="${HELM_CHART_PATH}/values-${ENVIRONMENT}.yaml"

    if [ ! -f "$values_file" ]; then
        log_warn "Environment-specific values file not found: $values_file"
        log_info "Using default values.yaml"
        values_file="${HELM_CHART_PATH}/values.yaml"
    fi

    log_info "Helm chart: $HELM_CHART_PATH"
    log_info "Helm values: $values_file"

    helm upgrade --install "$RELEASE_NAME" "$HELM_CHART_PATH" \
        --namespace "$NAMESPACE" \
        --values "$values_file" \
        --wait \
        --timeout 10m

    log_info "Helm deployment completed"
}

# Wait for deployment
wait_for_deployment() {
    log_info "Waiting for deployment to be ready..."

    kubectl rollout status deployment/xagent-api \
        -n "$NAMESPACE" \
        --timeout=5m

    log_info "Deployment is ready"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."

    local api_pods=$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[*].metadata.name}')

    if [ -z "$api_pods" ]; then
        log_error "No API pods found"
        return 1
    fi

    log_info "API pods: $api_pods"

    # Check pod status
    kubectl get pods -n "$NAMESPACE" -l app=xagent-api

    log_info "Deployment verification completed"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."

    local api_pod=$(kubectl get pods -n "$NAMESPACE" -l app=xagent-api -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$api_pod" ]; then
        log_error "No API pod found for migrations"
        return 1
    fi

    kubectl exec -it "$api_pod" -n "$NAMESPACE" -- \
        python -m alembic upgrade head

    log_info "Database migrations completed"
}

# Main deployment flow
main() {
    log_info "Starting X-Agent production deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"

    check_prerequisites
    build_image
    create_namespace
    deploy_helm
    wait_for_deployment
    verify_deployment
    run_migrations

    log_info "X-Agent deployment completed successfully!"
    log_info "Access the API at: http://xagent-api.$NAMESPACE.svc.cluster.local:8000"
}

# Run main function
main "$@"
