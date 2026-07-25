"""X-Agent v2 execution kernel.

This package provides the new modular execution architecture for X-Agent,
replacing the monolithic AgentLoop.run() method with a phase-based approach.

Core Components:
- AgentStateManager: State machine for execution lifecycle
- AgentExecutor: Coordinator for orchestrating execution phases
- PhaseContext: Shared context across execution phases

State Machine:
    IDLE -> INITIALIZING -> PLANNING -> EXECUTING -> COMPLETING -> COMPLETED
                                          ↕
                                      RECOVERING
    Any state -> PAUSED -> previous state
    Any state -> FAILED

Usage:
    from backend.app.core.agent_v2 import AgentExecutor, AgentState, AgentStateManager

    executor = AgentExecutor(max_iterations=4)
    response = await executor.execute(
        context=run_context,
        task="Fix the bug",
        phase_context=phase_ctx,
        phases=[(AgentState.INITIALIZING, init_phase), ...],
    )
"""

from backend.app.core.agent_v2.agent_executor import AgentExecutor
from backend.app.core.agent_v2.execution_phase import ExecutionPhase as ExecutionPhaseBase
from backend.app.core.agent_v2.phase_context import PhaseContext
from backend.app.core.agent_v2.phases import (
    CompletionPhase,
    ExecutionPhase,
    InitializationPhase,
    PlanningPhase,
    RecoveryPhase,
)
from backend.app.core.agent_v2.state_manager import (
    AgentState,
    AgentStateManager,
    InvalidStateTransitionError,
)

__all__ = [
    "AgentExecutor",
    "AgentState",
    "AgentStateManager",
    "CompletionPhase",
    "ExecutionPhase",
    "ExecutionPhaseBase",
    "InitializationPhase",
    "InvalidStateTransitionError",
    "PhaseContext",
    "PlanningPhase",
    "RecoveryPhase",
]
