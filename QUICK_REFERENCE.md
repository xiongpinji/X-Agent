"""Quick Reference Guide for X-Agent v2 Execution Kernel

## Module Structure

backend/app/core/agent_v2/
├── __init__.py              # Public API exports
├── state_manager.py         # State machine implementation
└── agent_executor.py        # Execution coordinator

## Quick Start

### 1. Import Components

```python
from backend.app.core.agent_v2 import (
    AgentExecutor,
    AgentState,
    AgentStateManager,
    InvalidStateTransitionError,
)
```

### 2. Create Executor

```python
executor = AgentExecutor(max_iterations=4)
```

### 3. Execute Workflow

```python
response = await executor.execute(
    context=run_context,
    task="Your task here",
    phase_context=phase_ctx,
    phases=[
        (AgentState.INITIALIZING, init_phase),
        (AgentState.PLANNING, planning_phase),
        (AgentState.EXECUTING, execution_phase),
        (AgentState.COMPLETING, completion_phase),
    ],
)
```

## State Machine

### States (9 total)

| State | Purpose | Transitions |
|-------|---------|-------------|
| IDLE | Initial state | → INITIALIZING, PAUSED |
| INITIALIZING | Setup phase | → PLANNING, FAILED, PAUSED |
| PLANNING | Plan generation | → EXECUTING, FAILED, PAUSED |
| EXECUTING | Execute plan | → RECOVERING, COMPLETING, FAILED, PAUSED |
| RECOVERING | Handle failures | → EXECUTING, COMPLETING, FAILED, PAUSED |
| COMPLETING | Finalize results | → COMPLETED, FAILED, PAUSED |
| COMPLETED | Success terminal | → PAUSED |
| FAILED | Failure terminal | → PAUSED |
| PAUSED | Paused state | → Any previous state |

### State Diagram

```
IDLE
  ↓
INITIALIZING
  ↓
PLANNING
  ↓
EXECUTING ←→ RECOVERING
  ↓
COMPLETING
  ↓
COMPLETED / FAILED

Any state → PAUSED → previous state
```

## AgentStateManager API

### Constructor
```python
manager = AgentStateManager()
```

### Methods

#### transition_to(new_state: AgentState) -> None
Transition to a new state. Raises InvalidStateTransitionError if invalid.

```python
manager.transition_to(AgentState.INITIALIZING)
```

#### get_state() -> AgentState
Get current state.

```python
current = manager.get_state()
```

#### get_history() -> list[tuple[AgentState, datetime]]
Get state transition history.

```python
history = manager.get_history()
for state, timestamp in history:
    print(f"{state.value} at {timestamp}")
```

#### is_terminal_state() -> bool
Check if in terminal state (COMPLETED or FAILED).

```python
if manager.is_terminal_state():
    print("Execution finished")
```

#### is_paused() -> bool
Check if paused.

```python
if manager.is_paused():
    print("Execution paused")
```

#### get_paused_state() -> Optional[AgentState]
Get state before pause.

```python
paused_from = manager.get_paused_state()
```

#### reset() -> None
Reset to initial state.

```python
manager.reset()
```

## AgentExecutor API

### Constructor
```python
executor = AgentExecutor(max_iterations=4)
```

### Methods

#### async execute(context, task, phase_context, phases) -> AgentRunResponse
Execute complete workflow.

```python
response = await executor.execute(
    context=run_context,
    task="Fix bug",
    phase_context=phase_ctx,
    phases=[(state, phase) for state, phase in ...],
)
```

#### get_state() -> AgentState
Get current state.

```python
state = executor.get_state()
```

#### get_state_history() -> list[tuple[str, str]]
Get state history as strings.

```python
history = executor.get_state_history()
```

#### is_completed() -> bool
Check if execution completed.

```python
if executor.is_completed():
    print("Done")
```

#### pause() -> None
Pause execution.

```python
executor.pause()
```

#### resume() -> None
Resume from pause.

```python
executor.resume()
```

#### reset() -> None
Reset to initial state.

```python
executor.reset()
```

#### register_phase(state, phase) -> None
Register phase for state.

```python
executor.register_phase(AgentState.PLANNING, planning_phase)
```

## Error Handling

### InvalidStateTransitionError

Raised when invalid state transition attempted.

```python
try:
    manager.transition_to(AgentState.EXECUTING)
except InvalidStateTransitionError as e:
    print(f"Cannot go from {e.from_state} to {e.to_state}")
```

### Execution Errors

AgentExecutor catches exceptions and builds error response.

```python
response = await executor.execute(...)
if response.status == RunStatus.FAILED:
    print(f"Error: {response.error}")
```

## Common Patterns

### Pattern 1: Basic Execution

```python
executor = AgentExecutor()
response = await executor.execute(
    context=run_context,
    task="Do something",
    phase_context=phase_ctx,
    phases=phases,
)
print(response.answer)
```

### Pattern 2: Pause and Resume

```python
executor = AgentExecutor()

# Start execution in background
task = asyncio.create_task(executor.execute(...))

# Pause after some time
await asyncio.sleep(5)
executor.pause()

# Resume later
executor.resume()

# Wait for completion
response = await task
```

### Pattern 3: State Monitoring

```python
executor = AgentExecutor()

async def monitor():
    while not executor.is_completed():
        state = executor.get_state()
        print(f"Current state: {state.value}")
        await asyncio.sleep(1)

# Run monitoring and execution concurrently
await asyncio.gather(
    executor.execute(...),
    monitor(),
)
```

### Pattern 4: Custom Phase Registration

```python
executor = AgentExecutor()
executor.register_phase(AgentState.PLANNING, custom_planning_phase)
executor.register_phase(AgentState.EXECUTING, custom_execution_phase)
```

## Testing

### Test State Transitions

```python
def test_valid_transition():
    manager = AgentStateManager()
    manager.transition_to(AgentState.INITIALIZING)
    assert manager.get_state() == AgentState.INITIALIZING

def test_invalid_transition():
    manager = AgentStateManager()
    with pytest.raises(InvalidStateTransitionError):
        manager.transition_to(AgentState.EXECUTING)
```

### Test Executor

```python
@pytest.mark.asyncio
async def test_executor_execution():
    executor = AgentExecutor()
    response = await executor.execute(
        context=run_context,
        task="test",
        phase_context=phase_ctx,
        phases=phases,
    )
    assert response.status == RunStatus.COMPLETED
```

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| State transition | O(1) | Constant time lookup |
| Get state | O(1) | Direct access |
| Get history | O(n) | n = number of transitions |
| Is terminal | O(1) | Set membership check |
| Reset | O(1) | Clear and reinitialize |

## Logging

AgentExecutor logs important events:

```
DEBUG: Starting agent execution
DEBUG: Executing phase initializing
DEBUG: Executing phase planning
DEBUG: Executing phase executing
INFO: Agent execution completed successfully
```

Enable debug logging:

```python
import logging
logging.getLogger("backend.app.core.agent_v2.agent_executor").setLevel(logging.DEBUG)
```

## Integration with Existing Code

### With AgentLoop

```python
# In AgentLoop.run()
executor = AgentExecutor(max_iterations=self.max_iterations)
response = await executor.execute(
    context=context,
    task=task,
    phase_context=phase_context,
    phases=[
        (AgentState.INITIALIZING, InitializationPhase()),
        (AgentState.PLANNING, PlanningPhase()),
        (AgentState.EXECUTING, ExecutionPhase()),
        (AgentState.COMPLETING, CompletionPhase()),
    ],
)
return response
```

### With PhaseContext

PhaseContext is passed to each phase and updated:

```python
phase_context = PhaseContext(
    loop=self,
    context=context,
    task=task,
    trajectory=trajectory,
    extra_context=extra_context or {},
    execution_frame=execution_frame,
    task_frame=task_frame,
    plan_frame=plan_frame,
    compact_context=compact_context,
    tool_calls=[],
    observations=[],
)
```

## Troubleshooting

### Issue: InvalidStateTransitionError

**Cause**: Attempting invalid state transition

**Solution**: Check state machine diagram and valid transitions

```python
# Wrong
manager.transition_to(AgentState.EXECUTING)  # From IDLE

# Right
manager.transition_to(AgentState.INITIALIZING)
manager.transition_to(AgentState.PLANNING)
manager.transition_to(AgentState.EXECUTING)
```

### Issue: Executor stuck in PAUSED

**Cause**: Paused but not resumed

**Solution**: Call resume() to continue

```python
executor.pause()
# ... do something ...
executor.resume()
```

### Issue: No response from execute()

**Cause**: Phase didn't set response in phase_context

**Solution**: Ensure phases set response or use fallback

```python
# Fallback response is generated if phase_context.response not set
# Or ensure completion phase sets response
```

## Files Reference

- **state_manager.py**: State machine implementation (165 lines)
- **agent_executor.py**: Execution coordinator (280 lines)
- **__init__.py**: Public API (44 lines)
- **test_agent_v2.py**: Test suite (450+ lines)

## Next Steps

1. Implement individual phases
2. Integrate with AgentLoop
3. Add feature flags for gradual rollout
4. Monitor and optimize performance
5. Migrate existing logic to phases

## Support

For issues or questions:
1. Check this guide
2. Review test cases in test_agent_v2.py
3. Check implementation_summary.md for detailed design
4. Review state machine diagram
"""
