"""Completion phase for finalizing execution and building response.

This module implements the CompletionPhase which stores execution results,
builds execution summaries, updates session memory, and creates the final response.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.app.core.contracts import AgentRunResponse, RunStatus

if TYPE_CHECKING:
    from backend.app.core.agent_phases import PhaseContext


class CompletionPhase:
    """Finalizes execution and builds response.

    Responsibilities:
    - Build execution summary from trajectory and observations
    - Store memory with execution results
    - Update session summary if applicable
    - Create final response object
    - Save run record to store
    - Emit completion trace events

    Complexity: <80 lines, cyclomatic complexity <6
    """

    async def execute(self, phase_ctx: PhaseContext) -> AgentRunResponse:
        """Execute completion phase.

        Finalizes execution by storing results and building response.

        Args:
            phase_ctx: Shared execution context with execution results.

        Returns:
            AgentRunResponse with final execution results.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        trajectory = phase_ctx.trajectory
        extra_context = phase_ctx.extra_context
        tool_calls = phase_ctx.tool_calls
        observations = phase_ctx.observations
        answer = phase_ctx.answer
        execution_frame = phase_ctx.execution_frame

        # Record audit
        loop._record_audit(
            "agent.run.completed",
            context,
            trajectory,
            outcome="success",
            answer_preview=answer[:200],
        )

        # Determine session ID
        session_id = context.session_id or str(
            extra_context.get("session_id") or ""
        ) or None

        # Update execution frame
        execution_frame.plan = phase_ctx.plan_frame
        execution_frame.memory = {
            "memory_id": None,
            "observations": observations,
            "tool_count": len(tool_calls),
        }
        execution_frame.tool_history = [
            call.model_dump(mode="json") for call in tool_calls
        ]

        # Build execution summary
        execution_summary = loop._build_execution_summary(
            trajectory,
            observations,
            tool_calls,
            [],
            answer,
            extra_context,
        )
        execution_frame.execution_summary = execution_summary

        # Store in memory
        memory_id = await loop.memory.store(
            context,
            content=answer,
            layer=3,
            importance=0.5,
            tags=["agent", "run", "reasoning"],
            metadata={
                "trace_id": context.trace_id,
                "request_id": context.request_id,
                "session_id": session_id,
                "task": phase_ctx.task,
                "goal": trajectory.goal,
                "observations": observations,
                "tool_count": len(tool_calls),
                "reflection_count": len(trajectory.reflections),
            },
            session_id=session_id,
        )

        # Update session summary if applicable
        if session_id and hasattr(loop.memory, "append_session_summary"):
            session_summary = {
                "goal": trajectory.goal,
                "answer": answer[:280],
                "steps": len(phase_ctx.execution_frame.execution_summary.get("plan", [])),
                "tools": len(tool_calls),
                "reflection_count": len(trajectory.reflections),
            }
            loop.memory.append_session_summary(
                session_id,
                json.dumps(session_summary, ensure_ascii=False, default=str),
            )

        # Finalize trajectory
        trajectory.stage = "finalizing"
        execution_summary["session_id"] = session_id
        execution_summary["subtask_status"] = trajectory.subtask_status
        execution_summary["current_subtask_index"] = trajectory.current_subtask_index

        # Build run view
        run_view = loop.runtime_adapter.build_run_view(
            {}, status=RunStatus.COMPLETED.value, answer=answer
        )
        execution_summary["run_view"] = run_view.model_dump()

        # Emit completion trace
        loop._emit_trace(
            context,
            "agent.completed",
            task=phase_ctx.task,
            answer=answer,
            memory_id=memory_id,
        )

        # Build response
        result = AgentRunResponse(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            status=RunStatus.COMPLETED,
            answer=answer,
            iterations=min(phase_ctx.iteration, loop.max_iterations),
            memory_hits=len(observations) or 1,
            tool_calls=tool_calls,
            events=[],
            plan=[],
            execution_summary=execution_summary,
            snapshot={
                "count": loop.memory.count(),
                "layers": [],
                "memory_id": memory_id,
                "goal": trajectory.goal,
                "stage": trajectory.stage,
                "subtask_status": trajectory.subtask_status,
                "current_subtask_index": trajectory.current_subtask_index,
                "observation_count": len(observations),
                "tool_count": len(tool_calls),
                "reflection_count": len(trajectory.reflections),
                "plan_count": 0,
                "capabilities": loop.tools.capability_index(),
                "execution_summary": execution_summary,
                "session_id": session_id,
                "execution_frame": execution_frame.model_dump(mode="json"),
                "run_view": run_view,
            },
        )

        # Save run record
        if loop.run_store is not None:
            loop.run_store.save(
                context, phase_ctx.task, result, run_view=run_view.model_dump()
            )

        return result
