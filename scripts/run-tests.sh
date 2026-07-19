#!/bin/bash

# X-Agent Comprehensive Test Execution Suite
# This script orchestrates the complete test suite with categorization,
# coverage reporting, and detailed analysis.

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="${PROJECT_ROOT}/tests"
REPORTS_DIR="${PROJECT_ROOT}/test-reports"
COVERAGE_DIR="${PROJECT_ROOT}/coverage-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Test categories
UNIT_TESTS=(
    "tests/test_llm_router.py"
    "tests/test_persistence.py"
    "tests/test_postgres_trace.py"
    "tests/test_postgres_memory.py"
    "tests/test_memory_vector.py"
    "tests/test_tools.py"
    "tests/test_observability.py"
    "tests/test_security.py"
    "tests/test_audit.py"
    "tests/test_approvals.py"
)

INTEGRATION_TESTS=(
    "tests/test_api.py"
    "tests/test_runs.py"
    "tests/test_workflow_worker.py"
    "tests/test_browser_service.py"
    "tests/test_browser.py"
    "tests/test_memory_retrieval.py"
    "tests/test_memory_api.py"
    "tests/test_memory_detail.py"
    "tests/test_workflow_run_correlation.py"
    "tests/test_workflow_run_detail.py"
    "tests/test_workflow_run_observability.py"
    "tests/test_workflow_run_timeline.py"
    "tests/test_workflow_run_trace_link.py"
    "tests/test_workflow_schedule_detail.py"
    "tests/test_trace_audit_integration.py"
    "tests/test_trace_correlation.py"
    "tests/test_trace_replay.py"
    "tests/test_tool_detail.py"
    "tests/test_streaming_api.py"
    "tests/test_agent_run_detail.py"
    "tests/test_agent_run_timeline.py"
    "tests/test_api_contracts.py"
    "tests/test_approval_detail.py"
    "tests/test_observability_shapes.py"
    "tests/test_ops_summary.py"
    "tests/test_overview.py"
    "tests/test_api_overview.py"
    "tests/test_api_replay.py"
    "tests/test_messages_debug_api.py"
    "tests/test_messages_stream.py"
    "tests/test_messages_end_to_end.py"
    "tests/test_collaboration_api.py"
)

E2E_TESTS=(
    "tests/e2e/test_desktop_e2e.py"
    "tests/e2e/test_open_source_catalog_e2e.py"
    "tests/e2e/test_desktop_macro_e2e.py"
    "tests/e2e/test_workflow_e2e.py"
    "tests/e2e/test_open_source_e2e.py"
)

RUNTIME_TESTS=(
    "tests/runtime/test_desktop_runtime_complex.py"
    "tests/runtime/test_open_source_package_only.py"
)

CONTRACT_TESTS=(
    "tests/contracts/test_open_source_import_guard.py"
    "tests/test_api_contracts.py"
    "tests/test_end_to_end_contracts.py"
    "tests/test_open_source_contracts.py"
    "tests/test_open_source_registry_contracts.py"
    "tests/test_open_source_provider_contracts.py"
    "tests/test_integration_state_contracts.py"
    "tests/test_workflow_compose_contract.py"
)

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_section() {
    echo -e "\n${YELLOW}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check environment
check_environment() {
    print_header "Environment Check"

    # Check Python version
    python_version=$(python --version 2>&1 | awk '{print $2}')
    print_info "Python version: $python_version"

    # Check pytest installation
    if ! python -m pytest --version > /dev/null 2>&1; then
        print_error "pytest not installed"
        return 1
    fi
    print_success "pytest installed"

    # Check pytest-cov installation
    if ! python -m pip show pytest-cov > /dev/null 2>&1; then
        print_error "pytest-cov not installed"
        return 1
    fi
    print_success "pytest-cov installed"

    # Check pytest-asyncio installation
    if ! python -m pip show pytest-asyncio > /dev/null 2>&1; then
        print_error "pytest-asyncio not installed"
        return 1
    fi
    print_success "pytest-asyncio installed"

    # Create report directories
    mkdir -p "$REPORTS_DIR"
    mkdir -p "$COVERAGE_DIR"
    print_success "Report directories created"

    return 0
}

# Run test category
run_test_category() {
    local category=$1
    local test_files=("${@:2}")
    local report_file="${REPORTS_DIR}/${category}_${TIMESTAMP}.json"
    local junit_file="${REPORTS_DIR}/${category}_${TIMESTAMP}.xml"

    print_section "Running $category tests (${#test_files[@]} files)"

    local cmd=(
        "python" "-m" "pytest"
        "${test_files[@]}"
        "--tb=short"
        "--verbose"
        "--json-report"
        "--json-report-file=$report_file"
        "--junit-xml=$junit_file"
        "-v"
    )

    if python -m pytest "${test_files[@]}" --tb=short -v 2>&1 | tee "${REPORTS_DIR}/${category}_${TIMESTAMP}.log"; then
        print_success "$category tests passed"
        return 0
    else
        print_error "$category tests failed"
        return 1
    fi
}

# Run all tests with coverage
run_all_tests_with_coverage() {
    print_header "Running All Tests with Coverage"

    local coverage_file="${COVERAGE_DIR}/coverage_${TIMESTAMP}.json"
    local html_dir="${COVERAGE_DIR}/html_${TIMESTAMP}"

    local cmd=(
        "python" "-m" "pytest"
        "tests/"
        "--cov=backend"
        "--cov=data"
        "--cov=scripts"
        "--cov-report=json:${coverage_file}"
        "--cov-report=html:${html_dir}"
        "--cov-report=term-missing"
        "--cov-report=term"
        "--tb=short"
        "-v"
        "--durations=10"
    )

    print_info "Command: ${cmd[*]}"

    if "${cmd[@]}"; then
        print_success "All tests passed with coverage"
        print_info "Coverage HTML report: ${html_dir}/index.html"
        return 0
    else
        print_error "Tests failed"
        return 1
    fi
}

# Run categorized tests
run_categorized_tests() {
    print_header "Running Categorized Tests"

    local failed_categories=()

    # Unit tests
    if ! run_test_category "unit" "${UNIT_TESTS[@]}"; then
        failed_categories+=("unit")
    fi

    # Integration tests
    if ! run_test_category "integration" "${INTEGRATION_TESTS[@]}"; then
        failed_categories+=("integration")
    fi

    # Contract tests
    if ! run_test_category "contracts" "${CONTRACT_TESTS[@]}"; then
        failed_categories+=("contracts")
    fi

    # Runtime tests
    if ! run_test_category "runtime" "${RUNTIME_TESTS[@]}"; then
        failed_categories+=("runtime")
    fi

    # E2E tests (optional, may require external services)
    print_section "E2E tests (optional)"
    if ! run_test_category "e2e" "${E2E_TESTS[@]}"; then
        print_info "E2E tests skipped or failed (may require external services)"
    fi

    if [ ${#failed_categories[@]} -gt 0 ]; then
        print_error "Failed categories: ${failed_categories[*]}"
        return 1
    fi

    return 0
}

# Generate test summary
generate_test_summary() {
    print_header "Test Execution Summary"

    local summary_file="${REPORTS_DIR}/TEST_SUMMARY_${TIMESTAMP}.md"

    cat > "$summary_file" << 'EOF'
# Test Execution Summary

## Overview
- **Execution Date**: $(date)
- **Project**: X-Agent Core
- **Test Framework**: pytest
- **Python Version**: $(python --version)

## Test Categories

### Unit Tests
- Count: $(find tests -name "test_*.py" -type f | wc -l)
- Focus: Individual component testing
- Isolation: High (mocked dependencies)

### Integration Tests
- Focus: Component interaction testing
- Isolation: Medium (real database connections)
- External Services: Mocked

### Contract Tests
- Focus: API contract validation
- Isolation: High (schema validation)
- Purpose: Ensure API compatibility

### Runtime Tests
- Focus: Runtime behavior validation
- Isolation: Medium
- Purpose: Verify runtime characteristics

### E2E Tests
- Focus: End-to-end workflow testing
- Isolation: Low (full system)
- External Services: May require real services

## Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| backend/app | 85% | TBD |
| backend/core | 90% | TBD |
| data | 80% | TBD |
| scripts | 75% | TBD |

## Test Execution Plan

1. **Phase 1**: Environment validation
2. **Phase 2**: Unit tests (fast feedback)
3. **Phase 3**: Integration tests
4. **Phase 4**: Contract tests
5. **Phase 5**: Runtime tests
6. **Phase 6**: E2E tests (optional)
7. **Phase 7**: Coverage analysis

## Estimated Execution Time

- Unit Tests: ~5-10 minutes
- Integration Tests: ~10-15 minutes
- Contract Tests: ~5 minutes
- Runtime Tests: ~5 minutes
- E2E Tests: ~15-30 minutes (optional)
- **Total**: ~40-65 minutes

## Report Locations

- Test Reports: `test-reports/`
- Coverage Reports: `coverage-reports/`
- HTML Coverage: `coverage-reports/html_*/index.html`

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run Tests
  run: bash scripts/run-tests.sh
```

### GitLab CI
```yaml
test:
  script:
    - bash scripts/run-tests.sh
```

## Failure Handling

- Unit test failures: Block merge
- Integration test failures: Block merge
- Contract test failures: Block merge
- E2E test failures: Warning only
- Coverage below target: Warning

## Next Steps

1. Review coverage reports
2. Identify low-coverage areas
3. Add tests for critical paths
4. Update coverage targets
5. Integrate into CI/CD pipeline

EOF

    print_success "Summary generated: $summary_file"
}

# Generate coverage analysis
generate_coverage_analysis() {
    print_header "Coverage Analysis"

    local analysis_file="${COVERAGE_DIR}/COVERAGE_ANALYSIS_${TIMESTAMP}.md"

    cat > "$analysis_file" << 'EOF'
# Coverage Analysis Report

## Summary
- Generated: $(date)
- Project: X-Agent Core

## Coverage by Module

### backend/app
- Core application logic
- Target: 85%
- Critical paths: API handlers, auth, workflows

### backend/core
- Core business logic
- Target: 90%
- Critical paths: Agent loop, memory, tools

### data
- Data models and persistence
- Target: 80%
- Critical paths: Database operations

### scripts
- Utility scripts
- Target: 75%
- Critical paths: Deployment, monitoring

## Low Coverage Areas

Areas requiring additional test coverage:
1. Error handling paths
2. Edge cases in data validation
3. Async operation failures
4. Resource cleanup scenarios
5. Concurrent access patterns

## Recommendations

1. **Increase Unit Test Coverage**
   - Add tests for error paths
   - Test edge cases
   - Mock external dependencies

2. **Improve Integration Tests**
   - Test database transactions
   - Verify async operations
   - Test concurrent access

3. **Add Contract Tests**
   - Validate API schemas
   - Test request/response formats
   - Verify error responses

4. **E2E Test Scenarios**
   - Complete workflows
   - Multi-step operations
   - Error recovery

## Coverage Improvement Plan

| Phase | Target | Timeline |
|-------|--------|----------|
| Phase 1 | 70% | Week 1 |
| Phase 2 | 80% | Week 2 |
| Phase 3 | 85% | Week 3 |
| Phase 4 | 90% | Week 4 |

EOF

    print_success "Coverage analysis generated: $analysis_file"
}

# Main execution
main() {
    print_header "X-Agent Test Execution Suite"
    print_info "Timestamp: $TIMESTAMP"
    print_info "Project Root: $PROJECT_ROOT"

    # Check environment
    if ! check_environment; then
        print_error "Environment check failed"
        exit 1
    fi

    # Run tests based on arguments
    case "${1:-all}" in
        unit)
            run_test_category "unit" "${UNIT_TESTS[@]}"
            ;;
        integration)
            run_test_category "integration" "${INTEGRATION_TESTS[@]}"
            ;;
        contracts)
            run_test_category "contracts" "${CONTRACT_TESTS[@]}"
            ;;
        runtime)
            run_test_category "runtime" "${RUNTIME_TESTS[@]}"
            ;;
        e2e)
            run_test_category "e2e" "${E2E_TESTS[@]}"
            ;;
        categorized)
            run_categorized_tests
            ;;
        coverage)
            run_all_tests_with_coverage
            ;;
        all)
            run_all_tests_with_coverage
            run_categorized_tests
            ;;
        *)
            echo "Usage: $0 {unit|integration|contracts|runtime|e2e|categorized|coverage|all}"
            exit 1
            ;;
    esac

    # Generate reports
    generate_test_summary
    generate_coverage_analysis

    print_header "Test Execution Complete"
    print_success "Reports generated in: $REPORTS_DIR"
    print_success "Coverage reports in: $COVERAGE_DIR"
}

# Run main function
main "$@"
