#!/bin/bash
# X-Agent Deployment Script
# Supports multiple environments: local, staging, production
# Usage: ./deploy.sh [environment] [version]

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
VERSION="${2:-latest}"
REGISTRY="ghcr.io"
IMAGE_NAME="x-agent-core"
NAMESPACE="${ENVIRONMENT}"
DEPLOYMENT_NAME="xagent-api"
REPLICAS=3

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        local|staging|production)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            echo "Valid environments: local, staging, production"
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if [ "$ENVIRONMENT" != "local" ]; then
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl is not installed"
            exit 1
        fi

        if ! command -v helm &> /dev/null; then
            log_warning "helm is not installed (optional)"
        fi
    fi

    if ! command -v docker &> /dev/null; then
        log_error "docker is not installed"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Build Docker image
build_image() {
    log_info "Building Docker image..."

    local image_tag="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

    docker build \
        --tag "$image_tag" \
        --build-arg VERSION="$VERSION" \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
        .

    log_success "Docker image built: $image_tag"
    echo "$image_tag"
}

# Push Docker image
push_image() {
    local image_tag="$1"

    if [ "$ENVIRONMENT" = "local" ]; then
        log_info "Skipping image push for local environment"
        return
    fi

    log_info "Pushing Docker image to registry..."

    docker push "$image_tag"

    log_success "Docker image pushed: $image_tag"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    local image_tag="$1"

    log_info "Deploying to Kubernetes ($ENVIRONMENT)..."

    # Create namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    # Update deployment image
    kubectl set image deployment/"$DEPLOYMENT_NAME" \
        "$DEPLOYMENT_NAME=$image_tag" \
        -n "$NAMESPACE" \
        --record

    # Wait for rollout
    log_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE" \
        --timeout=5m

    log_success "Deployment completed successfully"
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."

    local max_retries=30
    local retry_count=0
    local health_url=""

    case "$ENVIRONMENT" in
        local)
            health_url="http://localhost:8000/health"
            ;;
        staging)
            health_url="https://staging.xagent.example.com/health"
            ;;
        production)
            health_url="https://xagent.example.com/health"
            ;;
    esac

    while [ $retry_count -lt $max_retries ]; do
        if curl -sf "$health_url" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        fi

        retry_count=$((retry_count + 1))
        log_warning "Health check failed (attempt $retry_count/$max_retries)"
        sleep 2
    done

    log_error "Health check failed after $max_retries attempts"
    return 1
}

# Run smoke tests
run_smoke_tests() {
    log_info "Running smoke tests..."

    local test_url=""

    case "$ENVIRONMENT" in
        local)
            test_url="http://localhost:8000"
            ;;
        staging)
            test_url="https://staging.xagent.example.com"
            ;;
        production)
            test_url="https://xagent.example.com"
            ;;
    esac

    # Test API endpoints
    log_info "Testing API endpoints..."

    if ! curl -sf "$test_url/api/v1/health" > /dev/null; then
        log_error "API health check failed"
        return 1
    fi

    log_success "Smoke tests passed"
}

# Rollback deployment
rollback_deployment() {
    log_warning "Rolling back deployment..."

    kubectl rollout undo deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE"

    kubectl rollout status deployment/"$DEPLOYMENT_NAME" \
        -n "$NAMESPACE" \
        --timeout=5m

    log_success "Rollback completed"
}

# Generate deployment report
generate_report() {
    local image_tag="$1"
    local report_file="deployment-report-$(date +%Y%m%d-%H%M%S).txt"

    {
        echo "X-Agent Deployment Report"
        echo "=========================="
        echo ""
        echo "Deployment Details:"
        echo "  Environment: $ENVIRONMENT"
        echo "  Image Tag: $image_tag"
        echo "  Version: $VERSION"
        echo "  Timestamp: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
        echo "  Git Commit: $(git rev-parse --short HEAD)"
        echo "  Git Branch: $(git rev-parse --abbrev-ref HEAD)"
        echo ""

        if [ "$ENVIRONMENT" != "local" ]; then
            echo "Kubernetes Status:"
            echo "  Namespace: $NAMESPACE"
            echo "  Deployment: $DEPLOYMENT_NAME"
            echo ""
            kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o wide
            echo ""
            echo "Pod Status:"
            kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" -o wide
        fi
    } | tee "$report_file"

    log_success "Deployment report saved to $report_file"
}

# Main deployment flow
main() {
    log_info "Starting X-Agent deployment..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Version: $VERSION"

    validate_environment
    check_prerequisites

    # Build image
    local image_tag
    image_tag=$(build_image)

    # Push image
    push_image "$image_tag"

    # Deploy
    if [ "$ENVIRONMENT" != "local" ]; then
        deploy_kubernetes "$image_tag"
    fi

    # Health checks
    if run_health_checks; then
        # Smoke tests
        if run_smoke_tests; then
            generate_report "$image_tag"
            log_success "Deployment completed successfully!"
            exit 0
        else
            log_error "Smoke tests failed"
            rollback_deployment
            exit 1
        fi
    else
        log_error "Health checks failed"
        rollback_deployment
        exit 1
    fi
}

# Error handling
trap 'log_error "Deployment failed"; exit 1' ERR

# Run main function
main "$@"
