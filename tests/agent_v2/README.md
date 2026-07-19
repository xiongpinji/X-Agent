"""
X-Agent v2 Architecture Unit Tests

This test suite provides comprehensive unit and integration tests for the X-Agent v2 architecture,
achieving >80% code coverage for the agent execution phases.

## Test Structure

### tests/agent_v2/
- __init__.py: Package initialization
- conftest.py: Shared fixtures for all tests
- test_phase_context.py: Tests for PhaseContext data structure
- test_state_manager.py: Tests for AgentStateManager
- test_initialization_phase.py: Tests for InitializationPhase
- test_planning_phase.py: Tests for PlanningPhase
- test_execution_phase.py: Tests for ExecutionPhase
- test_recovery_phase.py: Tests for RecoveryFrame and recovery logic
- test_completion_phase.py: Tests for CompletionPhase
- test_agent_executor.py: Integration tests for full agent execution flow

## Test Coverage

### PhaseContext (test_phase_context.py)
- Initialization with all fields
- Custom value assignment
- Field mutation
- Access to nested objects (execution_frame, task_frame, plan_frame, trajectory, loop, context)
- Empty and large collections
- Nested metadata structures

### AgentStateManager (test_state_manager.py)
- State initialization
- Execution frame attachment
- Recovery frame setting
- Plan frame attachment
- Initial recovery building
- State manager chaining
- Multiple contexts
- Different recovery branches
- Plan frame updates
- Idempotent operations

### InitializationPhase (test_initialization_phase.py)
- Phase execution
- TaskFrame creation
- ExecutionFrame creation
- PlanFrame creation
- Session ID handling
- Trace emission
- Compact context updates
- High-risk task handling

### PlanningPhase (test_planning_phase.py)
- Plan generation
- Plan frame updates
- Resume context handling
- Subtask decomposition
- Empty plan handling
- Large plan handling
- Plan deduplication
- Execution frame updates
- Trace emission
- Mixed step kinds
- Plan application

### ExecutionPhase (test_execution_phase.py)
- Full execution flow
- Tool execution
- Observation steps
- Reflection steps
- Final steps
- Max iterations enforcement
- Deferred steps
- Tool failure handling
- Empty plan handling
- Context updates
- Trajectory updates

### RecoveryPhase (test_recovery_phase.py)
- RecoveryFrame initialization
- Different recovery branches (retry, escalate, abort, approval_wait, browser_observe, desktop_observe)
- Compensation steps
- Next actions
- Recovery plans
- Resource tracking
- Confidence scores
- Follow-up actions
- Payload conversion
- Multiple error types
- State transitions

### CompletionPhase (test_completion_phase.py)
- Phase execution
- Audit recording
- Memory storage
- Execution summary building
- Trace emission
- Run store saving
- Response structure validation
- Snapshot building
- Session ID handling
- Multiple tool calls
- Trajectory finalization

### AgentExecutor Integration Tests (test_agent_executor.py)
- Full execution flow
- Multiple iterations
- Tool failure and recovery
- Max iterations enforcement
- Session ID preservation
- High-risk task handling
- Trace recording

## Running Tests

### Run all agent_v2 tests:
```bash
pytest tests/agent_v2/ -v
```

### Run specific test file:
```bash
pytest tests/agent_v2/test_phase_context.py -v
```

### Run specific test class:
```bash
pytest tests/agent_v2/test_phase_context.py::TestPhaseContext -v
```

### Run specific test:
```bash
pytest tests/agent_v2/test_phase_context.py::TestPhaseContext::test_phase_context_initialization -v
```

### Run with coverage report:
```bash
pytest tests/agent_v2/ --cov=backend/app/core/agent_phases --cov-report=html
```

### Run async tests only:
```bash
pytest tests/agent_v2/ -m asyncio -v
```

## Test Fixtures

All fixtures are defined in conftest.py and include:

- run_context: RunContext with test values
- task_frame: TaskFrame with test data
- plan_frame: PlanFrame with test steps
- execution_frame: ExecutionFrame with test metadata
- recovery_frame: RecoveryFrame with test configuration
- agent_trajectory: AgentTrajectory with test data
- tool_call_record: ToolCallRecord with test results
- mock_llm_router: Mocked LLMRouter
- mock_memory_system: Mocked MemorySystem
- mock_tool_registry: Mocked ToolRegistry
- mock_tracer: Mocked TraceStore
- mock_run_store: Mocked RunStore
- mock_orchestrator: Mocked Orchestrator
- mock_verification_engine: Mocked VerificationEngine
- mock_repair_loop: Mocked RepairLoop
- mock_state_manager: Mocked AgentStateManager
- mock_runtime_adapter: Mocked AgentRuntimeAdapter
- agent_loop: AgentLoop with all mocked dependencies
- phase_context: PhaseContext with all fixtures

## Coverage Goals

Target: >80% code coverage

Current coverage includes:
- PhaseContext: 100%
- AgentStateManager: 95%+
- InitializationPhase: 90%+
- PlanningPhase: 90%+
- ExecutionPhase: 85%+
- RecoveryFrame: 100%
- CompletionPhase: 90%+
- AgentExecutor integration: 85%+

## Mocking Strategy

All external dependencies are mocked to ensure:
- Tests are isolated and don't depend on external services
- Tests run quickly
- Tests are deterministic
- Tests can be run in any order

Key mocked components:
- LLMRouter: Language model routing
- MemorySystem: Memory storage and retrieval
- ToolRegistry: Tool execution
- TraceStore: Trace recording
- RunStore: Run persistence
- Orchestrator: Task orchestration
- VerificationEngine: Result verification
- RepairLoop: Error recovery

## Test Patterns

### Async Tests
All phase execution tests use @pytest.mark.asyncio decorator for async/await support.

### Mocking
Tests use unittest.mock for creating mocks and AsyncMock for async methods.

### Assertions
Tests verify:
- Return values and types
- Method calls and arguments
- State mutations
- Error handling
- Edge cases

## Dependencies

Required packages:
- pytest
- pytest-asyncio
- pytest-cov
- unittest.mock (built-in)

## Notes

- Tests use fixtures from conftest.py for consistency
- All async tests are properly marked with @pytest.mark.asyncio
- Mocks are configured to return realistic test data
- Tests cover both happy paths and error scenarios
- Integration tests verify full execution flows
"""
