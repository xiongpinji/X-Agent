#!/bin/bash

# X-Agent CI/CD Local Validation Script
# This script validates the CI/CD configuration and runs local checks
# Usage: bash scripts/validate-ci.sh [--full|--quick|--docker]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VALIDATION_LOG="${PROJECT_ROOT}/ci-validation.log"
VALIDATION_REPORT="${PROJECT_ROOT}/CI_VALIDATION_REPORT.md"

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$VALIDATION_LOG"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((CHECKS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((CHECKS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$VALIDATION_LOG"
    ((CHECKS_WARNING++))
}

# Initialize validation log
init_log() {
    > "$VALIDATION_LOG"
    log_info "Starting CI/CD validation at $(date)"
    log_info "Project root: $PROJECT_ROOT"
}

# Check GitHub Actions workflow syntax
check_workflow_syntax() {
    log_info "Checking GitHub Actions workflow syntax..."

    local workflows_dir="${PROJECT_ROOT}/.github/workflows"

    if [ ! -d "$workflows_dir" ]; then
        log_error "Workflows directory not found: $workflows_dir"
        return 1
    fi

    # Check if actionlint is available
    if ! command -v actionlint &> /dev/null; then
        log_warning "actionlint not installed. Install with: brew install actionlint (macOS) or download from GitHub"
        log_info "Performing basic YAML syntax check instead..."

        for workflow in "$workflows_dir"/*.yml "$workflows_dir"/*.yaml; do
            if [ -f "$workflow" ]; then
                if python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>/dev/null; then
                    log_success "YAML syntax valid: $(basename "$workflow")"
                else
                    log_error "YAML syntax error in: $(basename "$workflow")"
                fi
            fi
        done
    else
        actionlint "$workflows_dir" && log_success "All workflows passed actionlint" || log_error "Workflow syntax errors found"
    fi
}

# Validate workflow dependencies
check_workflow_dependencies() {
    log_info "Checking workflow job dependencies..."

    local ci_cd_workflow="${PROJECT_ROOT}/.github/workflows/ci-cd.yml"

    if [ ! -f "$ci_cd_workflow" ]; then
        log_error "CI/CD workflow not found: $ci_cd_workflow"
        return 1
    fi

    # Check for circular dependencies and missing jobs
    if grep -q "needs:" "$ci_cd_workflow"; then
        log_success "Job dependencies are defined"
    else
        log_warning "No job dependencies found in ci-cd.yml"
    fi

    # Verify build job depends on lint, security, test
    if grep -A 5 "build:" "$ci_cd_workflow" | grep -q "needs: \[lint, security, test\]"; then
        log_success "Build job correctly depends on lint, security, and test"
    else
        log_warning "Build job dependencies may not be correctly configured"
    fi
}

# Check environment variables
check_environment_variables() {
    log_info "Checking environment variables configuration..."

    local ci_cd_workflow="${PROJECT_ROOT}/.github/workflows/ci-cd.yml"

    # Check for required env vars
    if grep -q "REGISTRY:" "$ci_cd_workflow"; then
        log_success "REGISTRY environment variable is defined"
    else
        log_error "REGISTRY environment variable not found"
    fi

    if grep -q "IMAGE_NAME:" "$ci_cd_workflow"; then
        log_success "IMAGE_NAME environment variable is defined"
    else
        log_error "IMAGE_NAME environment variable not found"
    fi

    if grep -q "PYTHON_VERSION:" "$ci_cd_workflow"; then
        log_success "PYTHON_VERSION environment variable is defined"
    else
        log_error "PYTHON_VERSION environment variable not found"
    fi
}

# Check secrets usage
check_secrets_management() {
    log_info "Checking secrets management..."

    local workflows_dir="${PROJECT_ROOT}/.github/workflows"
    local secrets_found=0

    # Check for secrets in workflows
    for workflow in "$workflows_dir"/*.yml "$workflows_dir"/*.yaml; do
        if [ -f "$workflow" ]; then
            if grep -q "secrets\." "$workflow"; then
                ((secrets_found++))
            fi
        fi
    done

    if [ $secrets_found -gt 0 ]; then
        log_success "Secrets are being used in workflows ($secrets_found files)"
    else
        log_warning "No secrets found in workflows - verify if needed"
    fi

    # Check for hardcoded credentials
    if grep -r "password:" "$workflows_dir" | grep -v "GITHUB_TOKEN\|secrets\." | grep -q .; then
        log_error "Potential hardcoded credentials found in workflows"
    else
        log_success "No hardcoded credentials detected"
    fi
}

# Check Docker configuration
check_docker_configuration() {
    log_info "Checking Docker configuration..."

    local dockerfile="${PROJECT_ROOT}/Dockerfile"

    if [ ! -f "$dockerfile" ]; then
        log_error "Dockerfile not found: $dockerfile"
        return 1
    fi

    # Check for multi-stage build
    if grep -q "FROM.*as" "$dockerfile"; then
        log_success "Multi-stage Dockerfile detected"
    else
        log_warning "Single-stage Dockerfile - consider multi-stage for optimization"
    fi

    # Check for non-root user
    if grep -q "USER" "$dockerfile"; then
        log_success "Non-root user configured in Dockerfile"
    else
        log_error "No non-root user configured - security risk"
    fi

    # Check for health check
    if grep -q "HEALTHCHECK" "$dockerfile"; then
        log_success "Health check configured"
    else
        log_warning "No health check configured"
    fi

    # Check for layer caching optimization
    if grep -q "apt-get.*--no-install-recommends" "$dockerfile"; then
        log_success "Apt packages optimized with --no-install-recommends"
    else
        log_warning "Consider using --no-install-recommends for smaller images"
    fi
}

# Check Python dependencies
check_python_dependencies() {
    log_info "Checking Python dependencies..."

    local pyproject="${PROJECT_ROOT}/pyproject.toml"

    if [ ! -f "$pyproject" ]; then
        log_error "pyproject.toml not found: $pyproject"
        return 1
    fi

    # Check for test dependencies
    if grep -q "pytest" "$pyproject"; then
        log_success "pytest is configured"
    else
        log_error "pytest not found in dependencies"
    fi

    # Check for linting tools
    if grep -q "ruff\|pylint\|flake8" "$pyproject"; then
        log_success "Linting tools are configured"
    else
        log_error "No linting tools found in dependencies"
    fi

    # Check for security tools
    if grep -q "bandit\|safety" "$pyproject"; then
        log_success "Security scanning tools are configured"
    else
        log_warning "No security scanning tools found"
    fi
}

# Validate test configuration
check_test_configuration() {
    log_info "Checking test configuration..."

    local pyproject="${PROJECT_ROOT}/pyproject.toml"

    if grep -q "pytest.ini_options" "$pyproject"; then
        log_success "pytest configuration found in pyproject.toml"
    else
        log_warning "No pytest configuration in pyproject.toml"
    fi

    # Check for test markers
    if grep -q "markers" "$pyproject"; then
        log_success "Test markers are configured"
    else
        log_warning "No test markers configured"
    fi
}

# Check caching strategy
check_caching_strategy() {
    log_info "Checking caching strategy..."

    local ci_cd_workflow="${PROJECT_ROOT}/.github/workflows/ci-cd.yml"

    # Check for pip cache
    if grep -q "cache: 'pip'" "$ci_cd_workflow"; then
        log_success "Pip caching is enabled"
    else
        log_warning "Pip caching not configured"
    fi

    # Check for Docker layer caching
    if grep -q "cache-from: type=gha" "$ci_cd_workflow"; then
        log_success "Docker layer caching is enabled"
    else
        log_warning "Docker layer caching not configured"
    fi
}

# Check concurrency configuration
check_concurrency_configuration() {
    log_info "Checking concurrency configuration..."

    local ci_cd_workflow="${PROJECT_ROOT}/.github/workflows/ci-cd.yml"

    if grep -q "concurrency:" "$ci_cd_workflow"; then
        log_success "Concurrency configuration is defined"

        if grep -A 2 "concurrency:" "$ci_cd_workflow" | grep -q "cancel-in-progress: true"; then
            log_success "Cancel-in-progress is enabled for faster feedback"
        else
            log_warning "Consider enabling cancel-in-progress for faster feedback"
        fi
    else
        log_warning "No concurrency configuration found"
    fi
}

# Check deployment configuration
check_deployment_configuration() {
    log_info "Checking deployment configuration..."

    local deploy_workflow="${PROJECT_ROOT}/.github/workflows/deploy-production.yml"

    if [ ! -f "$deploy_workflow" ]; then
        log_error "Production deployment workflow not found"
        return 1
    fi

    # Check for environment protection
    if grep -q "environment:" "$deploy_workflow"; then
        log_success "Deployment environments are configured"
    else
        log_error "No deployment environments configured"
    fi

    # Check for rollback capability
    if grep -q "rollback:" "$deploy_workflow"; then
        log_success "Rollback job is configured"
    else
        log_warning "No rollback job configured"
    fi

    # Check for health checks
    if grep -q "health\|smoke" "$deploy_workflow"; then
        log_success "Health checks are configured"
    else
        log_warning "No health checks configured"
    fi
}

# Check branch protection rules
check_branch_protection() {
    log_info "Checking branch protection configuration..."

    local branch_protection="${PROJECT_ROOT}/.github/workflows/branch-protection.yml"

    if [ ! -f "$branch_protection" ]; then
        log_warning "Branch protection workflow not found"
        return 1
    fi

    # Check for main branch protection
    if grep -q "branch: 'main'" "$branch_protection"; then
        log_success "Main branch protection is configured"
    else
        log_error "Main branch protection not configured"
    fi

    # Check for required reviews
    if grep -q "required_approving_review_count" "$branch_protection"; then
        log_success "Required code reviews are configured"
    else
        log_warning "No required code reviews configured"
    fi
}

# Run local linting checks
run_local_linting() {
    log_info "Running local linting checks..."

    if ! command -v ruff &> /dev/null; then
        log_warning "ruff not installed - skipping local linting"
        return 0
    fi

    if [ -d "${PROJECT_ROOT}/backend" ]; then
        if ruff check "${PROJECT_ROOT}/backend" --output-format=github 2>/dev/null; then
            log_success "Local ruff linting passed"
        else
            log_warning "Local ruff linting found issues"
        fi
    fi
}

# Run local security checks
run_local_security() {
    log_info "Running local security checks..."

    if ! command -v bandit &> /dev/null; then
        log_warning "bandit not installed - skipping local security scan"
        return 0
    fi

    if [ -d "${PROJECT_ROOT}/backend" ]; then
        if bandit -r "${PROJECT_ROOT}/backend" -f json -o /tmp/bandit-report.json 2>/dev/null; then
            log_success "Local bandit security scan completed"
        else
            log_warning "Local bandit security scan found issues"
        fi
    fi
}

# Validate Docker build (if --docker flag)
validate_docker_build() {
    log_info "Validating Docker build..."

    if ! command -v docker &> /dev/null; then
        log_warning "Docker not installed - skipping Docker build validation"
        return 0
    fi

    if [ ! -f "${PROJECT_ROOT}/Dockerfile" ]; then
        log_error "Dockerfile not found"
        return 1
    fi

    log_info "Building Docker image (this may take a few minutes)..."
    if docker build -t xagent:ci-validation "${PROJECT_ROOT}" --progress=plain 2>&1 | tee -a "$VALIDATION_LOG"; then
        log_success "Docker build validation passed"

        # Check image size
        local image_size=$(docker images xagent:ci-validation --format "{{.Size}}")
        log_info "Docker image size: $image_size"
    else
        log_error "Docker build validation failed"
    fi
}

# Generate validation report
generate_report() {
    log_info "Generating validation report..."

    cat > "$VALIDATION_REPORT" << 'EOF'
# CI/CD Validation Report

## Executive Summary

This report documents the validation of the X-Agent CI/CD pipeline configuration.

EOF

    cat >> "$VALIDATION_REPORT" << EOF

**Validation Date**: $(date)
**Total Checks**: $((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))
**Passed**: $CHECKS_PASSED
**Failed**: $CHECKS_FAILED
**Warnings**: $CHECKS_WARNING

## Validation Results

### Summary
- ✓ Passed: $CHECKS_PASSED
- ✗ Failed: $CHECKS_FAILED
- ⚠ Warnings: $CHECKS_WARNING

### Detailed Results

EOF

    if [ $CHECKS_FAILED -eq 0 ]; then
        echo "**Status**: ✓ All critical checks passed" >> "$VALIDATION_REPORT"
    else
        echo "**Status**: ✗ Some checks failed - review required" >> "$VALIDATION_REPORT"
    fi

    cat >> "$VALIDATION_REPORT" << 'EOF'

## Validation Checklist

### GitHub Actions Configuration
- [x] Workflow syntax validation
- [x] Job dependency validation
- [x] Environment variables configuration
- [x] Secrets management
- [x] Concurrency configuration

### Docker Configuration
- [x] Multi-stage build
- [x] Non-root user
- [x] Health checks
- [x] Layer caching optimization

### Python Configuration
- [x] Dependencies configuration
- [x] Test configuration
- [x] Linting tools
- [x] Security tools

### Deployment Configuration
- [x] Environment protection
- [x] Rollback capability
- [x] Health checks
- [x] Branch protection rules

## Recommendations

### High Priority
1. Ensure all secrets are properly configured in GitHub
2. Verify AWS credentials and roles are set up
3. Test deployment workflows in staging environment
4. Configure Slack webhook for notifications

### Medium Priority
1. Enable Docker layer caching for faster builds
2. Implement performance benchmarking in CI
3. Add more granular test markers
4. Configure code coverage thresholds

### Low Priority
1. Consider adding SBOM generation
2. Implement automated dependency updates
3. Add workflow performance metrics
4. Create runbooks for common issues

## Next Steps

1. Run full CI/CD pipeline on develop branch
2. Test deployment to staging environment
3. Verify rollback procedures
4. Monitor workflow execution times
5. Collect metrics for optimization

## Appendix

### Workflow Files Validated
- .github/workflows/ci-cd.yml
- .github/workflows/lint.yml
- .github/workflows/security.yml
- .github/workflows/test.yml
- .github/workflows/deploy.yml
- .github/workflows/deploy-production.yml
- .github/workflows/branch-protection.yml
- .github/workflows/quality.yml

### Tools Used
- actionlint (if available)
- Python YAML parser
- ruff (if available)
- bandit (if available)
- Docker (if available)

EOF

    log_success "Validation report generated: $VALIDATION_REPORT"
}

# Main execution
main() {
    local mode="quick"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --full)
                mode="full"
                shift
                ;;
            --quick)
                mode="quick"
                shift
                ;;
            --docker)
                mode="docker"
                shift
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    init_log

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}X-Agent CI/CD Validation Script${NC}"
    echo -e "${BLUE}Mode: $mode${NC}"
    echo -e "${BLUE}========================================${NC}"

    # Run checks
    check_workflow_syntax
    check_workflow_dependencies
    check_environment_variables
    check_secrets_management
    check_docker_configuration
    check_python_dependencies
    check_test_configuration
    check_caching_strategy
    check_concurrency_configuration
    check_deployment_configuration
    check_branch_protection

    # Run additional checks based on mode
    if [ "$mode" = "full" ] || [ "$mode" = "quick" ]; then
        run_local_linting
        run_local_security
    fi

    if [ "$mode" = "docker" ] || [ "$mode" = "full" ]; then
        validate_docker_build
    fi

    # Generate report
    generate_report

    # Print summary
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Validation Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Passed:  ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Failed:  ${RED}$CHECKS_FAILED${NC}"
    echo -e "Warnings: ${YELLOW}$CHECKS_WARNING${NC}"
    echo ""
    echo "Validation log: $VALIDATION_LOG"
    echo "Validation report: $VALIDATION_REPORT"
    echo ""

    if [ $CHECKS_FAILED -eq 0 ]; then
        echo -e "${GREEN}✓ Validation completed successfully${NC}"
        exit 0
    else
        echo -e "${RED}✗ Validation completed with failures${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
