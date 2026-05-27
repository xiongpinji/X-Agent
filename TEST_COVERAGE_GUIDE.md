# X-Agent Test Coverage Improvement Guide

## Overview

This guide provides instructions for running the extended test suite and improving test coverage from 65% to 90%+.

## New Test Files Added

### 1. Core Modules Extended Tests
**File**: `tests/test_core_modules_extended.py`

Tests for core modules with focus on:
- Boundary conditions (empty values, very long content, special characters, unicode)
- Exception handling (validation errors, timeouts, rate limits, permission denied)
- Concurrent operations (thread safety, async operations)
- Error recovery scenarios

**Key Classes Tested**:
- `ExecutionPlanner`: Plan building with various inputs
- `RepairLoop`: Error analysis and repair suggestions
- `MemoryItem`: Memory item creation and validation
- `AgentRuntimeAdapter`: Runtime state management

**Run**: `pytest tests/test_core_modules_extended.py -v`

### 2. API Extended Tests
**File**: `tests/test_api_extended.py`

Tests for API endpoints with focus on:
- Input validation (invalid JSON, missing fields, type errors)
- Authentication and authorization
- Rate limiting and throttling
- Response format consistency
- Edge cases (nonexistent resources, invalid parameters)

**Key Scenarios**:
- Invalid JSON payloads
- Missing required fields
- Invalid field types
- Oversized payloads
- Special characters and unicode
- Deeply nested objects
- API key validation
- Role-based access control

**Run**: `pytest tests/test_api_extended.py -v`

### 3. Services Extended Tests
**File**: `tests/test_services_extended.py`

Tests for service layer with focus on:
- Error handling and recovery
- Timeout handling
- Concurrent operations
- Service integration

**Key Services Tested**:
- `BrowserSessionManager`: Session creation, cleanup, reuse
- `MemoryIndexer`: Content indexing, embedding generation
- `MemoryRetriever`: Search operations, retrieval
- `EventExporter`: Event export, retry logic

**Run**: `pytest tests/test_services_extended.py -v`

### 4. Integration Extended Tests
**File**: `tests/test_integration_extended.py`

Tests for end-to-end workflows with focus on:
- Complete workflow lifecycle
- Multi-node workflows
- Conditional branches
- Memory integration
- Data consistency
- Concurrent workflow execution
- Error recovery

**Key Scenarios**:
- Create → Execute → Monitor → Delete workflows
- Workflows with multiple interconnected nodes
- Conditional branching
- Memory operations integration
- Concurrent workflow creation and execution
- Invalid input handling
- Timeout recovery

**Run**: `pytest tests/test_integration_extended.py -v`

### 5. Performance Extended Tests
**File**: `tests/test_performance_extended.py`

Tests for performance characteristics with focus on:
- API response time benchmarks
- Throughput testing
- Memory usage monitoring
- Database query performance
- Load testing (sustained and spike)

**Key Metrics**:
- Response time < 1-2 seconds
- Throughput > 5-10 requests/second
- Memory growth < 100-500MB
- Query performance < 0.5-1 second
- Load handling with 50%+ success rate

**Run**: `pytest tests/test_performance_extended.py -v`

## Running Tests

### Run All Tests with Coverage
```bash
pytest tests/ --cov=backend/app --cov-report=html --cov-report=term-missing -v
```

### Run Specific Test File
```bash
pytest tests/test_core_modules_extended.py -v
pytest tests/test_api_extended.py -v
pytest tests/test_services_extended.py -v
pytest tests/test_integration_extended.py -v
pytest tests/test_performance_extended.py -v
```

### Run Tests by Category
```bash
# Core module tests
pytest tests/test_core_modules_extended.py -v

# API tests
pytest tests/test_api_extended.py -v

# Service tests
pytest tests/test_services_extended.py -v

# Integration tests
pytest tests/test_integration_extended.py -v

# Performance tests
pytest tests/test_performance_extended.py -v
```

### Run Tests with Specific Markers
```bash
# Async tests only
pytest tests/ -m asyncio -v

# Tests with specific keyword
pytest tests/ -k "boundary" -v
pytest tests/ -k "concurrent" -v
pytest tests/ -k "performance" -v
```

### Generate Coverage Reports
```bash
# Terminal report
pytest tests/ --cov=backend/app --cov-report=term-missing

# HTML report
pytest tests/ --cov=backend/app --cov-report=html
open htmlcov/index.html

# JSON report
pytest tests/ --cov=backend/app --cov-report=json
```

### Run Coverage Analysis Script
```bash
python scripts/coverage_analysis.py
```

## Coverage Targets

| Module | Target | Current | Status |
|--------|--------|---------|--------|
| backend.app.core | 95% | 65% | In Progress |
| backend.app.api | 95% | 65% | In Progress |
| backend.app.services | 90% | 65% | In Progress |
| backend.app.services.browser | 90% | 65% | In Progress |
| backend.app.services.memory | 90% | 65% | In Progress |
| backend.app.services.observability | 90% | 65% | In Progress |
| **Overall** | **90%+** | **65%** | **In Progress** |

## Test Statistics

### Core Modules Extended (test_core_modules_extended.py)
- **Total Tests**: 40+
- **Test Classes**: 6
- **Coverage Areas**:
  - ExecutionPlanner: 8 tests
  - RepairLoop: 10 tests
  - MemoryItem: 8 tests
  - AgentRuntimeAdapter: 5 tests
  - Concurrent Operations: 3 tests
  - Error Recovery: 6 tests

### API Extended (test_api_extended.py)
- **Total Tests**: 50+
- **Test Classes**: 6
- **Coverage Areas**:
  - Validation: 10 tests
  - Authentication: 6 tests
  - Rate Limiting: 2 tests
  - Response Formats: 4 tests
  - Edge Cases: 8 tests
  - Memory Operations: 6 tests

### Services Extended (test_services_extended.py)
- **Total Tests**: 45+
- **Test Classes**: 5
- **Coverage Areas**:
  - BrowserSessionManager: 8 tests
  - MemoryIndexer: 8 tests
  - MemoryRetriever: 8 tests
  - EventExporter: 8 tests
  - Service Integration: 2 tests

### Integration Extended (test_integration_extended.py)
- **Total Tests**: 30+
- **Test Classes**: 4
- **Coverage Areas**:
  - End-to-End Workflows: 5 tests
  - Concurrent Execution: 2 tests
  - Error Recovery: 3 tests
  - Data Consistency: 2 tests

### Performance Extended (test_performance_extended.py)
- **Total Tests**: 35+
- **Test Classes**: 7
- **Coverage Areas**:
  - Response Time: 4 tests
  - Throughput: 3 tests
  - Memory Usage: 3 tests
  - Database Performance: 2 tests
  - Async Performance: 2 tests
  - Cache Performance: 1 test
  - Load Testing: 2 tests

## Key Testing Patterns

### 1. Boundary Condition Testing
```python
# Test with empty values
test_memory_item_with_empty_content()

# Test with maximum values
test_memory_item_with_max_importance()

# Test with very long content
test_memory_item_with_very_long_content()

# Test with special characters
test_api_special_characters_in_fields()
```

### 2. Exception Handling Testing
```python
# Test specific error types
test_analyze_with_validation_error()
test_analyze_with_missing_resource()
test_analyze_with_permission_denied()

# Test error recovery
test_session_creation_failure_recovery()
test_export_retry_on_failure()
```

### 3. Concurrent Operations Testing
```python
# Test concurrent creation
test_concurrent_memory_item_creation()
test_concurrent_workflow_creation()

# Test concurrent execution
test_concurrent_workflow_execution()
test_concurrent_requests_throughput()
```

### 4. Performance Testing
```python
# Test response time
test_get_workflows_response_time()

# Test throughput
test_sequential_requests_throughput()
test_concurrent_requests_throughput()

# Test resource usage
test_memory_usage_during_workflow_creation()
```

## Troubleshooting

### Tests Failing Due to Missing Dependencies
```bash
pip install -e ".[test]"
```

### Tests Timing Out
- Increase timeout in pytest.ini
- Check for slow database queries
- Review async operation performance

### Coverage Not Reaching 90%
1. Run coverage report to identify gaps:
   ```bash
   pytest tests/ --cov=backend/app --cov-report=term-missing
   ```

2. Review uncovered lines in the report

3. Add targeted tests for uncovered code paths

4. Re-run coverage analysis

### Performance Tests Failing
- Check system resources (CPU, memory)
- Verify database performance
- Review network latency
- Adjust performance thresholds if needed

## Best Practices

1. **Run tests frequently**: Run tests after each code change
2. **Monitor coverage**: Keep coverage above 90%
3. **Test edge cases**: Always test boundary conditions
4. **Test error paths**: Ensure error handling is tested
5. **Test concurrency**: Test concurrent operations
6. **Monitor performance**: Track performance metrics
7. **Keep tests fast**: Optimize slow tests
8. **Maintain test quality**: Review and refactor tests regularly

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -e ".[test]"
      - run: pytest tests/ --cov=backend/app --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [AsyncIO Testing](https://docs.python.org/3/library/asyncio-dev.html)

## Contact & Support

For questions or issues with the test suite, please refer to the project documentation or contact the development team.
