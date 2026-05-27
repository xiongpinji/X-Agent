"""
Agent coordinator - orchestrates the refactored components.

This is the simplified AgentLoop that coordinates the extracted components.
Responsibilities:
  - Coordinate component interactions
  - Manage execution flow
  - Handle iteration loop
  - Emit events and traces
"""

from typing import Any, Awaitable, Callable
import json

from backend.app.core.contracts import (
    RunContext, TraceEvent, AgentRunResponse, RunStatus,
    ToolCallRecord, AgentPlanStepRecord, ExecutionFrame,
)
from backend.app.core.tracing import TraceStore, tracer as default_tracer
from backend.app.core.audit import AuditStore
from backend.app.core.runs import RunStore
from backend.app.core.agent.executor import ToolExecutor
from backend.app.core.agent.planner import TaskPlanner
from backend.app.core.agent.memory_manager import MemoryManager
from backend.app.core.agent.state_manager import StateManager, ExecutionState
from backend.app.core.agent.protocols import PlanStep


class AgentCoordinator:
    """Coordinates agent execution using refactored components."""

    def __init__(
        self,
        executor: ToolExecutor,
        planner: TaskPlanner,
        memory_manager: MemoryManager,
        state_manager: StateManager,
        tracer: TraceStore | None = None,
        audit_store: AuditStore | None = None,
        run_store: RunStore | None = None,
        max_iterations: int = 4,
    ):
        self.executor = executor
        self.planner = planner
        self.memory = memory_manager
        self.state = state_manager
        self.tracer = tracer or default_tracer
        self.audit_store = audit_store
        self.run_store = run_store
        self.max_iterations = max_iterations

    async def run(
        self,
        context: RunContext,
        task: str,
        extra_context: dict[str, Any] | None = None,
        event_callback: Callable[[TraceEvent], Awaitable[None] | None] | None = None,
    ) -> AgentRunResponse:
        """
        Execute task end-to-end.

        Args:
            context: Execution context
            task: Task description
            extra_context: Additional context
            event_callback: Event callback

        Returns:
            AgentRunResponse with results
        """
        extra_context = extra_context or {}
        started = self.tracer.record(context, "agent.started", task=task)

        # Analyze task
        task_profile = self.planner.analyze_task(task, extra_context)
        goal = extra_context.get("goal") or task[:240]

        # Create initial state
        from backend.app.core.contracts import TaskFrame
        task_frame = TaskFrame(
            goal=goal,
            description=str(extra_context.get("task_focus") or task[:500]),
            risk_level=context.risk_level,
            requires_approval=bool(extra_context.get("requires_approval", False)),
            metadata={"task": task, **extra_context},
        )

        state = self.state.create_initial_state(
            context=context,
            task_frame=task_frame,
            metadata={"session_id": context.session_id} if context.session_id else {},
        )

        # Generate plan
        plan = await self.planner.plan(context, task, goal, extra_context)
        self._emit_trace(context, "agent.plan.created", step_count=len(plan))

        # Execute plan
        answer = ""
        tool_calls: list[ToolCallRecord] = []
        observations: list[str] = []
        reflections: list[str] = []
        plan_records: list[AgentPlanStepRecord] = []

        iteration = 0
        while iteration < self.max_iterations and plan:
            step = plan.pop(0)
            iteration += 1

            self._emit_trace(context, "agent.iteration.started", iteration=iteration, step_kind=step.kind)

            if step.kind == "observe":
                observation = await self._observe(context, task, extra_context)
                observations.append(observation)
                state.observations.append(observation)
                self._emit_trace(context, "agent.observation.recorded", iteration=iteration)

            elif step.kind == "tool" and step.tool_name:
                result = await self.executor.execute(context, step.tool_name, step.arguments or {})
                if result.success:
                    observations.append(str(result.output))
                    state.tool_results.append({
                        "tool": step.tool_name,
                        "success": True,
                        "output": result.output,
                    })
                else:
                    state.tool_results.append({
                        "tool": step.tool_name,
                        "success": False,
                        "error": result.error,
                    })
                self._emit_trace(
                    context,
                    "agent.tool.completed",
                    iteration=iteration,
                    tool_name=step.tool_name,
                    success=result.success,
                )

            elif step.kind == "reflect":
                reflection = self._reflect(context, task, observations)
                reflections.append(reflection)
                state.reflections.append(reflection)
                answer = reflection
                self._emit_trace(context, "agent.reflection.created", iteration=iteration)

            elif step.kind == "final":
                answer = answer or self._finalize_answer(task, goal, observations, reflections)
                self._emit_trace(context, "agent.finalized", iteration=iteration, answer=answer)

            state.iterations = iteration

        # Store memory
        memory_id = await self.memory.store(
            context,
            content=answer,
            layer=3,
            importance=0.5,
            tags=["agent", "run", "reasoning"],
            metadata={
                "trace_id": context.trace_id,
                "task": task,
                "goal": goal,
            },
            session_id=context.session_id,
        )

        # Build response
        result = AgentRunResponse(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            status=RunStatus.COMPLETED,
            answer=answer,
            iterations=iteration,
            memory_hits=len(observations),
            tool_calls=tool_calls,
            events=[started],
            plan=plan_records,
            execution_summary={
                "goal": goal,
                "iterations": iteration,
                "observations": len(observations),
                "reflections": len(reflections),
                "tool_calls": len(tool_calls),
                "memory_id": memory_id,
            },
            snapshot={
                "memory_id": memory_id,
                "goal": goal,
                "observation_count": len(observations),
                "reflection_count": len(reflections),
            },
        )

        if self.run_store is not None:
            self.run_store.save(context, task, result)

        self._emit_trace(context, "agent.completed", task=task, answer=answer)

        return result

    async def _observe(
        self,
        context: RunContext,
        task: str,
        extra_context: dict[str, Any],
    ) -> str:
        """Observe context and retrieve relevant information."""
        query = extra_context.get("goal") or task
        memory_context = await self.memory.retrieve(context, query=str(query), limit=5)
        return json.dumps({
            "memory": memory_context,
            "extra_context": extra_context,
        }, ensure_ascii=False, default=str)

    def _reflect(
        self,
        context: RunContext,
        task: str,
        observations: list[str],
    ) -> str:
        """Generate reflection on observations."""
        evidence = {
            "task": task,
            "observation_count": len(observations),
            "recent_observations": observations[-3:] if observations else [],
        }
        return json.dumps(evidence, ensure_ascii=False, default=str)

    def _finalize_answer(
        self,
        task: str,
        goal: str,
        observations: list[str],
        reflections: list[str],
    ) -> str:
        """Finalize answer from execution."""
        if reflections:
            return reflections[-1]
        if observations:
            return f"{goal}: {observations[-1]}"
        return f"Completed: {goal}"

    def _emit_trace(self, context: RunContext, event: str, **data: Any) -> TraceEvent:
        """Emit trace event."""
        payload = {k: str(v) for k, v in data.items()}
        return self.tracer.record(context, event, **payload)

    def _record_audit(
        self,
        action: str,
        context: RunContext,
        task: str,
        **details: Any,
    ) -> None:
        """Record audit event."""
        if self.audit_store is None:
            return
        self.audit_store.record(
            action=action,
            resource_type="agent_run",
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            resource_id=context.trace_id,
            trace_id=context.trace_id,
            outcome=str(details.get("outcome", "success")),
            details={"task": task, **details},
        )
