"""Testing Best Practices and Guidelines for X-Agent.

This document outlines best practices for writing tests in the X-Agent project
to achieve and maintain high test coverage (85%+).
"""

# Testing Best Practices for X-Agent

## Overview

This guide provides best practices for writing tests in X-Agent to achieve and maintain
high test coverage (85%+). Following these practices ensures code quality, reliability,
and maintainability.

## Table of Contents

1. [Test Structure](#test-structure)
2. [Unit Tests](#unit-tests)
3. [Integration Tests](#integration-tests)
4. [Fixtures and Setup](#fixtures-and-setup)
5. [Mocking and Isolation](#mocking-and-isolation)
6. [Async Testing](#async-testing)
7. [Error Handling](#error-handling)
8. [Coverage Goals](#coverage-goals)
9. [Common Patterns](#common-patterns)

## Test Structure

### File Organization

```
tests/
├── conftest.py                          # Shared fixtures
├── test_memory_system_comprehensive.py  # Memory module tests
├── test_collaboration_comprehensive.py  # Collaboration tests
├── test_workflows_comprehensive.py      # Workflow tests
├── test_llm_embeddings_comprehensive.py # LLM/Embeddings tests
├── test_api_comprehensive.py            # API endpoint tests
├── test_core_contracts_comprehensive.py # Core contract tests
└── agent_v2/
    └── conftest.py                      # Agent v2 specific fixtures
```

### Test Class Organization

```python
class TestModuleName:
    """Test module description."""

    def test_feature_normal_case(self) -> None:
        """Test normal/happy path."""
        # Arrange
        # Act
        # Assert

    def test_feature_edge_case(self) -> None:
        """Test edge cases."""
        pass

    def test_feature_error_case(self) -> None:
        """Test error handling."""
        pass
```

## Unit Tests

### What to Test

1. **Normal Cases**: Happy path execution
2. **Edge Cases**: Boundary conditions, empty inputs, max values
3. **Error Cases**: Invalid inputs, exceptions
4. **State Changes**: Object state modifications

### Example: Memory Item Tests

```python
def test_memory_item_creation(self) -> None:
    """Test creating a memory item."""
    item = MemoryItem(
        tenant_id="tenant-1",
        content="Test content",
        layer=1,
    )
    assert item.tenant_id == "tenant-1"
    assert item.content == "Test content"
    assert item.layer == 1

def test_memory_item_layer_validation(self) -> None:
    """Test layer validation."""
    with pytest.raises(ValidationError):
        MemoryItem(tenant_id="tenant-1", content="Test", layer=0)
    with pytest.raises(ValidationError):
        MemoryItem(tenant_id="tenant-1", content="Test", layer=11)
```

### Coverage Checklist

- [ ] All public methods tested
- [ ] All branches tested (if/else)
- [ ] All exception paths tested
- [ ] Boundary values tested
- [ ] Default values verified

## Integration Tests

### What to Test

1. **Module Interactions**: How modules work together
2. **API Endpoints**: Full request/response cycle
3. **Database Operations**: CRUD operations
4. **External Services**: API calls, message queues

### Example: API Integration Test

```python
def test_create_memory_workflow(
    self, client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Test complete memory creation workflow."""
    # Create memory
    response = client.post(
        "/api/v1/memory",
        json={
            "content": "Test memory",
            "layer": 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    memory_id = response.json()["id"]

    # Retrieve memory
    response = client.get(
        f"/api/v1/memory/{memory_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["content"] == "Test memory"
```

## Fixtures and Setup

### Common Fixtures

```python
@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)

@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers."""
    return {"x-api-key": "bootstrap"}

@pytest.fixture
def sample_memory() -> MemoryItem:
    """Create a sample memory item."""
    return MemoryItem(
        tenant_id="tenant-1",
        content="Sample content",
        layer=1,
    )
```

### Fixture Scope

```python
@pytest.fixture(scope="function")  # Default: new instance per test
def fresh_store() -> CollaborationStore:
    return CollaborationStore()

@pytest.fixture(scope="module")  # Shared across tests in module
def shared_client() -> TestClient:
    return TestClient(app)

@pytest.fixture(scope="session")  # Shared across all tests
def database_connection():
    # Setup
    yield connection
    # Teardown
```

## Mocking and Isolation

### When to Mock

1. External APIs
2. Database calls
3. File system operations
4. Time-dependent code
5. Random number generation

### Example: Mocking External Service

```python
from unittest.mock import Mock, patch

def test_llm_router_with_mock(self) -> None:
    """Test LLM router with mocked model."""
    with patch("backend.app.core.llm.get_model") as mock_get:
        mock_model = Mock()
        mock_model.generate.return_value = "Generated text"
        mock_get.return_value = mock_model

        router = LLMRouter()
        result = router.generate("prompt")

        assert result == "Generated text"
        mock_get.assert_called_once()
```

### Isolation Best Practices

```python
def test_collaboration_store_isolation(self) -> None:
    """Test that store instances are isolated."""
    store1 = CollaborationStore()
    store2 = CollaborationStore()

    room1 = store1.create_room(
        topic="Room 1",
        tenant_id="tenant-1",
        created_by="user-1",
    )

    # store2 should not have room1
    assert store2.get_room(room1.room_id) is None
```

## Async Testing

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_memory_operation(self) -> None:
    """Test async memory operation."""
    memory_system = MemorySystem()
    result = await memory_system.store_async(
        content="Test",
        layer=1,
    )
    assert result is not None
```

### Using pytest-asyncio

```python
# In pytest.ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

## Error Handling

### Testing Exceptions

```python
def test_invalid_layer_raises_error(self) -> None:
    """Test that invalid layer raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        MemoryItem(tenant_id="tenant-1", content="Test", layer=0)

    assert "layer" in str(exc_info.value).lower()

def test_nonexistent_room_raises_error(self) -> None:
    """Test that accessing nonexistent room raises error."""
    store = CollaborationStore()
    with pytest.raises(ValueError):
        store.close_room("nonexistent-room")
```

### Testing Error Messages

```python
def test_error_message_clarity(self) -> None:
    """Test that error messages are clear."""
    try:
        MemoryItem(tenant_id="", content="Test", layer=1)
    except ValidationError as e:
        assert "tenant_id" in str(e)
```

## Coverage Goals

### Target Coverage by Module

| Module | Target | Priority |
|--------|--------|----------|
| backend/app/core/memory.py | 95% | Critical |
| backend/app/core/workflows.py | 90% | Critical |
| backend/app/core/collaboration.py | 90% | High |
| backend/app/core/llm.py | 85% | High |
| backend/app/api/ | 85% | High |
| backend/app/core/agent.py | 80% | Medium |

### Coverage Measurement

```bash
# Run tests with coverage
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Check specific module
pytest tests/ --cov=backend.app.core.memory --cov-report=term-missing
```

## Common Patterns

### Testing Model Creation

```python
def test_model_creation_with_defaults(self) -> None:
    """Test model creation with default values."""
    item = MemoryItem(tenant_id="tenant-1", content="Test", layer=1)
    assert item.id is not None
    assert item.importance == 0.5
    assert item.tags == []

def test_model_creation_with_custom_values(self) -> None:
    """Test model creation with custom values."""
    item = MemoryItem(
        tenant_id="tenant-1",
        content="Test",
        layer=1,
        importance=0.8,
        tags=["tag1"],
    )
    assert item.importance == 0.8
    assert item.tags == ["tag1"]
```

### Testing Collections

```python
def test_list_operations(self) -> None:
    """Test list operations."""
    store = CollaborationStore()
    room1 = store.create_room(
        topic="Room 1",
        tenant_id="tenant-1",
        created_by="user-1",
    )
    room2 = store.create_room(
        topic="Room 2",
        tenant_id="tenant-1",
        created_by="user-1",
    )

    rooms = store.list_rooms(tenant_id="tenant-1")
    assert len(rooms) == 2
    assert room1.room_id in [r.room_id for r in rooms]
```

### Testing State Transitions

```python
def test_workflow_status_transitions(self) -> None:
    """Test workflow status transitions."""
    record = WorkflowRunRecord(
        workflow_id="wf-1",
        workflow_name="Test",
        status=WorkflowRunStatus.DRAFT,
    )
    assert record.status == WorkflowRunStatus.DRAFT

    record.status = WorkflowRunStatus.RUNNING
    assert record.status == WorkflowRunStatus.RUNNING

    record.status = WorkflowRunStatus.COMPLETED
    assert record.status == WorkflowRunStatus.COMPLETED
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_memory_system_comprehensive.py
```

### Run Specific Test Class

```bash
pytest tests/test_memory_system_comprehensive.py::TestMemoryItem
```

### Run Specific Test

```bash
pytest tests/test_memory_system_comprehensive.py::TestMemoryItem::test_memory_item_creation
```

### Run with Markers

```bash
pytest tests/ -m "not slow"
pytest tests/ -m "integration"
```

### Run with Coverage

```bash
pytest tests/ --cov=backend --cov-report=html
```

## Continuous Integration

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
      - run: pytest tests/ --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Troubleshooting

### Common Issues

1. **Tests fail locally but pass in CI**
   - Check environment variables
   - Verify database state
   - Check for timing issues

2. **Coverage not increasing**
   - Identify untested code paths
   - Add tests for error cases
   - Test edge cases

3. **Flaky tests**
   - Avoid time-dependent assertions
   - Use proper fixtures for setup/teardown
   - Mock external dependencies

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
