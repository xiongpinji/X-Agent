"""Refactored run() method for AgentLoop using phase-based execution.

This module demonstrates the refactored run() method that uses
InitializationPhase, PlanningPhase, ExecutionPhase, and CompletionPhase
to reduce complexity from 300+ lines to ~50 lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.core.agent_phases import (
    CompletionPhase,
    ExecutionPhase,
    InitializationPhase,
    PhaseContext,
    PlanningPhase,
)
from backend.app.core.contracts import AgentRunResponse, TraceEvent

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop, AgentTrajectory
    from backend.app.core.contracts import RunContext


async def refactored_run(
    self: AgentLoop,
    context: RunContext,
    task: str,
    extra_context: dict | None = None,
    event_callback=None,
) -> AgentRunResponse:
    """Refactored run() method using phase-based execution.

    Reduces complexity by separating concerns into distinct phases:
    1. Initialization: Setup context and state
    2. Planning: Generate execution plan
    3. Execution: Execute plan steps iteratively
    4. Completion: Finalize and return results

    Complexity: ~50 lines (down from 300+)
    Cyclomatic complexity: ~5 (down from >15)
    """
    # Record start
    started = self.tracer.record(context, "agent.started", task=task, extra_context=extra_context or {})
    events: list[TraceEvent] = [started]

    # Prepare context
    compact_context = self._compress_context(extra_context or {})
    if context.session_id:
        compact_context.setdefault("session_id", context.session_id)

    # Index code
    indexed_repo = self._index_code(compact_context)
    compact_context["code_index"] = indexed_repo

    # Build trajectory
    trajectory: AgentTrajectory = self._build_trajectory(task, compact_context)

    # Create phase context
    phase_ctx = PhaseContext(
        loop=self,
        context=context,
        task=task,
        trajectory=trajectory,
        extra_context=extra_context or {},
        execution_frame=None,  # Will be set in initialization
        task_frame=None,  # Will be set in initialization
        plan_frame=None,  # Will be set in initialization
        compact_context=compact_context,
        tool_calls=[],
        observations=[],
    )

    # Phase 1: Initialization
    init_phase = InitializationPhase()
    await init_phase.execute(phase_ctx)
    self._record_audit("agent.run.started", context, trajectory, outcome="success")

    # Phase 2: Planning
    planning_phase = PlanningPhase()
    plan = await planning_phase.execute(phase_ctx)

    # Phase 3: Execution
    execution_phase = ExecutionPhase()
    answer, _tool_calls = await execution_phase.execute(phase_ctx, plan)

    # Phase 4: Completion
    completion_phase = CompletionPhase()
    result = await completion_phase.execute(phase_ctx)

    # Emit completion event
    completed = self._emit_trace(
        context,
        "agent.completed",
        task=task,
        answer=answer,
        memory_id=result.snapshot.get("memory_id"),
    )
    events.append(completed)
    result.events = events

    return result
