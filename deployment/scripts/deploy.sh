#!/bin/bash
set -euo pipefail

# X-Agent Production Deployment Script
# This script deploys X-Agent to Kubernetes using Helm

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
NAMESPACE=${NAMESPACE:-xagent}
RELEASE_NAME=${RELEASE_NAME:-xagent}
ENVIRONMENT=${ENVIRONMENT:-production}
# P1-15 修正: SCRIPT_DIR 为 deployment/scripts, Chart 在 deployment/helm;
# 原值 "${SCRIPT_DIR}/helm" 指向不存在的 deployment/scripts/helm
HELM_CHART_PATH="${PROJECT_ROOT}/deployment/helm"
IMAGE_REPOSITORY="${XAGENT_IMAGE_REPOSITORY:-}"
IMAGE_TAG="${XAGENT_IMAGE_TAG:-}"
BACKUP_IMAGE_REPOSITORY="${XAGENT_BACKUP_IMAGE_REPOSITORY:-}"
BACKUP_IMAGE_TAG="${XAGENT_BACKUP_IMAGE_TAG:-}"
SECRET_NAME="${XAGENT_K8S_SECRET_NAME:-}"
ARTIFACTS_PVC="${XAGENT_ARTIFACTS_PVC:-}"
PRE_MIGRATION_BACKUP_ID="${XAGENT_PRE_MIGRATION_BACKUP_ID:-}"
BACKUP_S3_BUCKET="${XAGENT_BACKUP_S3_BUCKET:-}"
BACKUP_ROLE_ARN="${XAGENT_BACKUP_ROLE_ARN:-}"
POSTGRES_HOST="${XAGENT_POSTGRES_HOST:-}"
REDIS_HOST="${XAGENT_REDIS_HOST:-}"
QDRANT_HOST="${XAGENT_QDRANT_HOST:-}"
API_HOST="${XAGENT_API_HOST:-}"

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

    if [ ! -f "${PROJECT_ROOT}/backend/migrations/alembic.ini" ]; then
        log_error "Required Alembic configuration is missing"
        exit 1
    fi

    local required_name
    for required_name in \
        IMAGE_REPOSITORY IMAGE_TAG BACKUP_IMAGE_REPOSITORY BACKUP_IMAGE_TAG \
        SECRET_NAME ARTIFACTS_PVC PRE_MIGRATION_BACKUP_ID BACKUP_S3_BUCKET \
        BACKUP_ROLE_ARN POSTGRES_HOST REDIS_HOST QDRANT_HOST API_HOST; do
        if [ -z "${!required_name}" ]; then
            log_error "$required_name must be configured"
            exit 2
        fi
    done

    if [[ ! "$IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]] || [[ ! "$BACKUP_IMAGE_TAG" =~ ^sha-[0-9a-f]{40}$ ]]; then
        log_error "IMAGE_TAG and BACKUP_IMAGE_TAG must be immutable sha-<40 hex> tags"
        exit 2
    fi

    log_info "Prerequisites check passed"
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

    local values_file="${PROJECT_ROOT}/deployment/helm/values-${ENVIRONMENT}.yaml"

    if [ ! -f "$values_file" ]; then
        log_error "Environment-specific values file not found: $values_file"
        exit 2
    fi

    helm upgrade --install "$RELEASE_NAME" "$HELM_CHART_PATH" \
        --namespace "$NAMESPACE" \
        --values "$values_file" \
        --set-string image.repository="$IMAGE_REPOSITORY" \
        --set-string image.tag="$IMAGE_TAG" \
        --set-string backup.image.repository="$BACKUP_IMAGE_REPOSITORY" \
        --set-string backup.image.tag="$BACKUP_IMAGE_TAG" \
        --set-string secrets.existingSecret="$SECRET_NAME" \
        --set-string artifacts.existingClaim="$ARTIFACTS_PVC" \
        --set-string migration.verifiedBackupId="$PRE_MIGRATION_BACKUP_ID" \
        --set-string backup.s3.bucket="$BACKUP_S3_BUCKET" \
        --set-string backup.serviceAccount.roleArn="$BACKUP_ROLE_ARN" \
        --set-string external.postgresHost="$POSTGRES_HOST" \
        --set-string external.redisHost="$REDIS_HOST" \
        --set-string external.qdrantHost="$QDRANT_HOST" \
        --set-string ingress.hosts[0].host="$API_HOST" \
        --set-string ingress.tls[0].hosts[0]="$API_HOST" \
        --wait \
        --wait-for-jobs \
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

# Main deployment flow
main() {
    log_info "Starting X-Agent production deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Namespace: $NAMESPACE"
    log_info "Release: $RELEASE_NAME"

    check_prerequisites
    create_namespace
    deploy_helm
    wait_for_deployment
    verify_deployment

    log_info "X-Agent deployment completed successfully!"
    log_info "Access the API at: http://xagent-api.$NAMESPACE.svc.cluster.local:8000"
}

# Run main function
main "$@"
