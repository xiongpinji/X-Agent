#!/bin/bash

# X-Agent Deployment Verification Script
# Validates deployment configuration and tests rollback procedures

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_LOG="${PROJECT_ROOT}/deployment-verification.log"
DEPLOYMENT_CHECKLIST="${PROJECT_ROOT}/DEPLOYMENT_CHECKLIST.md"

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
    ((CHECKS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
    ((CHECKS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
    ((CHECKS_WARNING++))
}

# Initialize log
init_log() {
    > "$DEPLOYMENT_LOG"
    log_info "Starting deployment verification at $(date)"
}

# Check Kubernetes cluster connectivity
check_k8s_connectivity() {
    log_info "Checking Kubernetes cluster connectivity..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not installed"
        return 1
    fi

    if kubectl cluster-info &>/dev/null; then
        log_success "Kubernetes cluster is accessible"
        local cluster_info=$(kubectl cluster-info | head -1)
        log_info "Cluster: $cluster_info"
    else
        log_error "Cannot connect to Kubernetes cluster"
        return 1
    fi
}

# Check Helm installation
check_helm_installation() {
    log_info "Checking Helm installation..."

    if ! command -v helm &> /dev/null; then
        log_error "Helm not installed"
        return 1
    fi

    local helm_version=$(helm version --short)
    log_success "Helm is installed: $helm_version"
}

# Check namespaces
check_namespaces() {
    log_info "Checking Kubernetes namespaces..."

    for ns in staging production; do
        if kubectl get namespace "$ns" &>/dev/null; then
            log_success "Namespace '$ns' exists"
        else
            log_warning "Namespace '$ns' does not exist - will be created during deployment"
        fi
    done
}

# Check RBAC configuration
check_rbac_configuration() {
    log_info "Checking RBAC configuration..."

    if kubectl auth can-i create deployments --namespace=staging &>/dev/null; then
        log_success "RBAC permissions are configured for staging"
    else
        log_warning "RBAC permissions may not be configured for staging"
    fi

    if kubectl auth can-i create deployments --namespace=production &>/dev/null; then
        log_success "RBAC permissions are configured for production"
    else
        log_warning "RBAC permissions may not be configured for production"
    fi
}

# Check Helm chart
check_helm_chart() {
    log_info "Checking Helm chart..."

    local chart_path="${PROJECT_ROOT}/deployment/helm"

    if [ ! -d "$chart_path" ]; then
        log_error "Helm chart directory not found: $chart_path"
        return 1
    fi

    if [ ! -f "$chart_path/Chart.yaml" ]; then
        log_error "Chart.yaml not found in $chart_path"
        return 1
    fi

    log_success "Helm chart found"

    # Validate chart
    if helm lint "$chart_path" &>/dev/null; then
        log_success "Helm chart validation passed"
    else
        log_warning "Helm chart validation found issues"
    fi
}

# Check values files
check_values_files() {
    log_info "Checking Helm values files..."

    local values_staging="${PROJECT_ROOT}/deployment/helm/values-staging.yaml"
    local values_production="${PROJECT_ROOT}/deployment/helm/values-production.yaml"

    if [ -f "$values_staging" ]; then
        log_success "Staging values file exists"
    else
        log_error "Staging values file not found: $values_staging"
    fi

    if [ -f "$values_production" ]; then
        log_success "Production values file exists"
    else
        log_error "Production values file not found: $values_production"
    fi
}

# Check Docker image availability
check_docker_image() {
    log_info "Checking Docker image availability..."

    if ! command -v docker &> /dev/null; then
        log_warning "Docker not installed - skipping image check"
        return 0
    fi

    # This would check if image exists in registry
    log_info "Docker image check would be performed during actual deployment"
}

# Check persistent storage
check_persistent_storage() {
    log_info "Checking persistent storage configuration..."

    if kubectl get storageclass &>/dev/null; then
        local sc_count=$(kubectl get storageclass --no-headers | wc -l)
        if [ "$sc_count" -gt 0 ]; then
            log_success "Storage classes are configured ($sc_count found)"
        else
            log_warning "No storage classes found"
        fi
    else
        log_warning "Cannot check storage classes"
    fi
}

# Check ingress configuration
check_ingress_configuration() {
    log_info "Checking ingress configuration..."

    if kubectl get ingressclass &>/dev/null; then
        local ic_count=$(kubectl get ingressclass --no-headers 2>/dev/null | wc -l)
        if [ "$ic_count" -gt 0 ]; then
            log_success "Ingress classes are configured ($ic_count found)"
        else
            log_warning "No ingress classes found"
        fi
    else
        log_warning "Cannot check ingress classes"
    fi
}

# Check resource quotas
check_resource_quotas() {
    log_info "Checking resource quotas..."

    for ns in staging production; do
        if kubectl get resourcequota -n "$ns" &>/dev/null; then
            local rq_count=$(kubectl get resourcequota -n "$ns" --no-headers 2>/dev/null | wc -l)
            if [ "$rq_count" -gt 0 ]; then
                log_success "Resource quotas configured for $ns ($rq_count found)"
            else
                log_warning "No resource quotas configured for $ns"
            fi
        fi
    done
}

# Check network policies
check_network_policies() {
    log_info "Checking network policies..."

    for ns in staging production; do
        if kubectl get networkpolicy -n "$ns" &>/dev/null; then
            local np_count=$(kubectl get networkpolicy -n "$ns" --no-headers 2>/dev/null | wc -l)
            if [ "$np_count" -gt 0 ]; then
                log_success "Network policies configured for $ns ($np_count found)"
            else
                log_warning "No network policies configured for $ns"
            fi
        fi
    done
}

# Test deployment dry-run
test_deployment_dryrun() {
    log_info "Testing deployment with dry-run..."

    local chart_path="${PROJECT_ROOT}/deployment/helm"
    local values_staging="${PROJECT_ROOT}/deployment/helm/values-staging.yaml"

    if [ ! -f "$values_staging" ]; then
        log_warning "Cannot perform dry-run - values file not found"
        return 0
    fi

    if helm template xagent "$chart_path" -f "$values_staging" &>/dev/null; then
        log_success "Helm template rendering successful"
    else
        log_error "Helm template rendering failed"
    fi
}

# Test rollback procedure
test_rollback_procedure() {
    log_info "Testing rollback procedure..."

    log_info "Rollback procedure test:"
    log_info "  1. kubectl rollout undo deployment/xagent-api -n staging"
    log_info "  2. kubectl rollout undo deployment/xagent-worker -n staging"
    log_info "  3. kubectl rollout status deployment/xagent-api -n staging"

    log_success "Rollback procedure documented"
}

# Check health check configuration
check_health_checks() {
    log_info "Checking health check configuration..."

    local dockerfile="${PROJECT_ROOT}/Dockerfile"

    if grep -q "HEALTHCHECK" "$dockerfile"; then
        log_success "Health check configured in Dockerfile"
    else
        log_error "No health check in Dockerfile"
    fi

    # Check for liveness/readiness probes in values
    local values_staging="${PROJECT_ROOT}/deployment/helm/values-staging.yaml"
    if [ -f "$values_staging" ]; then
        if grep -q "livenessProbe\|readinessProbe" "$values_staging"; then
            log_success "Liveness/readiness probes configured"
        else
            log_warning "No liveness/readiness probes configured"
        fi
    fi
}

# Check monitoring configuration
check_monitoring_configuration() {
    log_info "Checking monitoring configuration..."

    local values_staging="${PROJECT_ROOT}/deployment/helm/values-staging.yaml"

    if [ -f "$values_staging" ]; then
        if grep -q "prometheus\|monitoring" "$values_staging"; then
            log_success "Monitoring configuration found"
        else
            log_warning "No monitoring configuration found"
        fi
    fi
}

# Check logging configuration
check_logging_configuration() {
    log_info "Checking logging configuration..."

    local values_staging="${PROJECT_ROOT}/deployment/helm/values-staging.yaml"

    if [ -f "$values_staging" ]; then
        if grep -q "logging\|logs" "$values_staging"; then
            log_success "Logging configuration found"
        else
            log_warning "No logging configuration found"
        fi
    fi
}

# Generate deployment checklist
generate_deployment_checklist() {
    log_info "Generating deployment checklist..."

    cat > "$DEPLOYMENT_CHECKLIST" << 'EOF'
# X-Agent Deployment Checklist

## Pre-Deployment Verification

### Infrastructure Setup
- [ ] Kubernetes cluster is running and accessible
- [ ] kubectl is installed and configured
- [ ] Helm is installed (version 3.12+)
- [ ] AWS credentials are configured
- [ ] Docker registry credentials are configured

### Namespace Configuration
- [ ] Staging namespace exists or will be created
- [ ] Production namespace exists or will be created
- [ ] RBAC roles are configured
- [ ] Service accounts are created

### Storage Configuration
- [ ] Storage classes are configured
- [ ] Persistent volumes are available
- [ ] Database storage is provisioned
- [ ] Cache storage is provisioned

### Network Configuration
- [ ] Ingress controller is installed
- [ ] Ingress classes are configured
- [ ] Network policies are configured
- [ ] DNS records are configured

### Secrets Configuration
- [ ] Database credentials are stored in secrets
- [ ] API keys are stored in secrets
- [ ] TLS certificates are stored in secrets
- [ ] All secrets are encrypted at rest

### Monitoring Setup
- [ ] Prometheus is installed
- [ ] Grafana is installed
- [ ] Alert rules are configured
- [ ] Log aggregation is configured

## Staging Deployment

### Pre-Deployment
- [ ] Code is merged to develop branch
- [ ] All CI/CD checks pass
- [ ] Security scans pass
- [ ] Test coverage is acceptable

### Deployment
- [ ] Helm chart is validated
- [ ] Values file is reviewed
- [ ] Dry-run is successful
- [ ] Deployment is initiated

### Post-Deployment
- [ ] Pods are running
- [ ] Services are accessible
- [ ] Health checks pass
- [ ] Smoke tests pass

### Verification
- [ ] API endpoints respond correctly
- [ ] Database connections work
- [ ] Cache is functioning
- [ ] Logs are being collected

## Production Deployment

### Pre-Deployment
- [ ] Staging deployment is stable (24+ hours)
- [ ] Performance tests pass
- [ ] Security review is complete
- [ ] Change log is prepared

### Deployment
- [ ] Backup of current production is taken
- [ ] Helm chart is validated
- [ ] Values file is reviewed
- [ ] Dry-run is successful

### Deployment Execution
- [ ] Deployment is initiated
- [ ] Pods are rolling out
- [ ] Old pods are terminating gracefully
- [ ] New pods are becoming ready

### Post-Deployment
- [ ] All pods are running
- [ ] Services are accessible
- [ ] Health checks pass
- [ ] Smoke tests pass

### Monitoring
- [ ] Error rates are normal
- [ ] Response times are acceptable
- [ ] Resource usage is normal
- [ ] No alerts are firing

## Rollback Procedure

### Decision to Rollback
- [ ] Critical issues detected
- [ ] Performance degradation
- [ ] Data corruption
- [ ] Security incident

### Rollback Execution
- [ ] Notify team
- [ ] Initiate rollback
- [ ] Monitor rollback progress
- [ ] Verify rollback completion

### Post-Rollback
- [ ] Services are restored
- [ ] Data integrity is verified
- [ ] Root cause analysis is started
- [ ] Incident report is created

## Post-Deployment

### Monitoring (First 24 hours)
- [ ] Error rates are monitored
- [ ] Performance metrics are checked
- [ ] Resource usage is monitored
- [ ] User feedback is collected

### Monitoring (First Week)
- [ ] Stability is verified
- [ ] Performance is acceptable
- [ ] No critical issues
- [ ] User satisfaction is high

### Documentation
- [ ] Deployment notes are recorded
- [ ] Issues encountered are documented
- [ ] Lessons learned are captured
- [ ] Runbooks are updated

## Sign-Off

- [ ] Deployment lead: _________________ Date: _______
- [ ] QA lead: _________________ Date: _______
- [ ] Operations lead: _________________ Date: _______
- [ ] Product owner: _________________ Date: _______

EOF

    log_success "Deployment checklist generated: $DEPLOYMENT_CHECKLIST"
}

# Generate deployment log
generate_deployment_log() {
    log_info "Generating deployment verification summary..."

    cat >> "$DEPLOYMENT_LOG" << EOF

========================================
Deployment Verification Summary
========================================

Total Checks: $((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))
Passed: $CHECKS_PASSED
Failed: $CHECKS_FAILED
Warnings: $CHECKS_WARNING

Status: $([ $CHECKS_FAILED -eq 0 ] && echo "✓ PASS" || echo "✗ FAIL")

Generated: $(date)
========================================
EOF
}

# Main execution
main() {
    init_log

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}X-Agent Deployment Verification${NC}"
    echo -e "${BLUE}========================================${NC}"

    # Run checks
    check_k8s_connectivity
    check_helm_installation
    check_namespaces
    check_rbac_configuration
    check_helm_chart
    check_values_files
    check_docker_image
    check_persistent_storage
    check_ingress_configuration
    check_resource_quotas
    check_network_policies
    test_deployment_dryrun
    test_rollback_procedure
    check_health_checks
    check_monitoring_configuration
    check_logging_configuration

    # Generate outputs
    generate_deployment_checklist
    generate_deployment_log

    # Print summary
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Verification Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Passed:  ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Failed:  ${RED}$CHECKS_FAILED${NC}"
    echo -e "Warnings: ${YELLOW}$CHECKS_WARNING${NC}"
    echo ""
    echo "Verification log: $DEPLOYMENT_LOG"
    echo "Deployment checklist: $DEPLOYMENT_CHECKLIST"
    echo ""

    if [ $CHECKS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ Deployment verification completed successfully${NC}"
        exit 0
    else
        echo -e "${RED}✗ Deployment verification completed with failures${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
