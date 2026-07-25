"""Agent execution phases for AgentLoop refactoring.

This module provides phase-based execution for the AgentLoop.run() method,
reducing complexity by separating concerns into distinct phases.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.core.contracts import (
    AgentRunResponse,
    ExecutionFrame,
    PlanFrame,
    RunContext,
    RunStatus,
    TaskFrame,
    ToolCallRecord,
)

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop, AgentPlanStep, AgentTrajectory


@dataclass
class PhaseContext:
    """Shared context across all phases."""

    loop: AgentLoop
    context: RunContext
    task: str
    trajectory: AgentTrajectory
    extra_context: dict[str, object]
    execution_frame: ExecutionFrame
    task_frame: TaskFrame
    plan_frame: PlanFrame
    compact_context: dict[str, object]
    tool_calls: list[ToolCallRecord]
    observations: list[str]
    answer: str = ""
    iteration: int = 0


class InitializationPhase:
    """Initialize execution context and state."""

    async def execute(self, phase_ctx: PhaseContext) -> None:
        """Execute initialization phase.

        Sets up task frame, execution frame, state manager, and orchestration.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        task = phase_ctx.task

        # Build task frame
        phase_ctx.task_frame = TaskFrame(
            goal=loop._derive_goal(task, phase_ctx.compact_context),
            description=str(
                phase_ctx.compact_context.get("task_focus") or task[:500]
            ),
            risk_level=context.risk_level,
            requires_approval=bool(
                phase_ctx.compact_context.get("requires_approval", False)
            ),
            metadata={"task": task, **phase_ctx.compact_context},
        )

        # Create initial state
        state = loop.state_manager.create_initial_state(
            context=context,
            task_frame=phase_ctx.task_frame,
            metadata={"session_id": context.session_id}
            if context.session_id
            else {},
        )

        # Build execution frame
        phase_ctx.execution_frame = ExecutionFrame(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
            task=phase_ctx.task_frame,
            session_id=context.session_id,
            metadata={"session_id": context.session_id}
            if context.session_id
            else {},
        )

        state = loop.state_manager.attach_execution_frame(
            state, phase_ctx.execution_frame
        )

        # Orchestration
        orchestration_context, capability_decision, recovery_hint = (
            loop.orchestrator.prepare(
                phase_ctx.task_frame,
                phase_ctx.execution_frame,
                metadata={"task": task, **phase_ctx.compact_context},
            )
        )
        draft_plan = loop.orchestrator.draft_plan(
            phase_ctx.task_frame,
            phase_ctx.execution_frame,
            metadata={"task": task, **phase_ctx.compact_context},
        )
        tool_decision = loop.orchestrator.select_tool(
            phase_ctx.task_frame,
            phase_ctx.execution_frame,
            metadata={"task": task, **phase_ctx.compact_context},
        )

        phase_ctx.compact_context["capability_decision"] = loop._dump_model(
            capability_decision
        )
        phase_ctx.compact_context["orchestration_recovery_hint"] = loop._dump_model(
            recovery_hint
        )
        phase_ctx.compact_context["orchestration_context"] = (
            orchestration_context.metadata
        )
        phase_ctx.compact_context["draft_plan"] = loop._dump_model(draft_plan)
        phase_ctx.compact_context["tool_decision"] = loop._dump_model(tool_decision)

        phase_ctx.plan_frame = draft_plan
        initial_recovery = loop.state_manager.build_initial_recovery(
            tool_name=tool_decision.tool_name,
        )
        state = loop.state_manager.set_recovery_frame(state, initial_recovery)
        state = loop.state_manager.attach_plan_frame(state, draft_plan)

        loop._emit_trace(
            context,
            "agent.orchestrated",
            capability=capability_decision.name,
            reason=capability_decision.reason,
            recovery_branch=recovery_hint.branch,
            tool_name=tool_decision.tool_name,
        )


class PlanningPhase:
    """Generate and refine execution plan."""

    async def execute(self, phase_ctx: PhaseContext) -> list[AgentPlanStep]:
        """Execute planning phase.

        Returns refined plan steps ready for execution.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        trajectory = phase_ctx.trajectory
        compact_context = phase_ctx.compact_context

        plan = await loop._plan(context, trajectory, compact_context)
        plan = loop._apply_execution_plan(plan, compact_context)

        if not phase_ctx.plan_frame.steps:
            phase_ctx.plan_frame.steps = [step.instruction for step in plan]
            phase_ctx.plan_frame.status = "ready"
            phase_ctx.plan_frame.revision += 1

        # Handle resume
        resume_trace_id = str(
            (phase_ctx.extra_context or {}).get("resume_trace_id") or ""
        )
        if resume_trace_id:
            loop._emit_trace(
                context,
                "agent.resumed",
                resumed_from=resume_trace_id,
                stage=trajectory.stage,
            )
            plan = loop._dedupe_plan_steps(trajectory, plan)

        if trajectory.subtasks:
            loop._emit_trace(
                context,
                "agent.task.decomposed",
                subtask_count=len(trajectory.subtasks),
                subtasks=trajectory.subtasks,
            )

        plan = loop._dedupe_plan_steps(trajectory, plan)
        phase_ctx.plan_frame.steps = [step.instruction for step in plan]
        phase_ctx.plan_frame.status = "ready"
        phase_ctx.plan_frame.revision += 1
        phase_ctx.execution_frame.plan = phase_ctx.plan_frame

        loop._emit_trace(
            context,
            "agent.plan.created",
            task=phase_ctx.task,
            goal=trajectory.goal,
            step_count=len(plan),
        )

        return plan


class ExecutionPhase:
    """Execute plan steps iteratively."""

    async def execute(
        self, phase_ctx: PhaseContext, plan: list[AgentPlanStep]
    ) -> tuple[str, list[ToolCallRecord]]:
        """Execute plan steps.

        Returns final answer and tool call records.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        trajectory = phase_ctx.trajectory
        extra_context = phase_ctx.extra_context

        answer = ""
        memory_hits = 0
        tool_calls: list[ToolCallRecord] = []
        observations: list[str] = []
        last_tool_result: str | None = None

        iteration = 0
        while iteration < loop.max_iterations and plan:
            step = plan.pop(0)
            iteration += 1
            phase_ctx.iteration = iteration

            if loop._should_defer_step(step, trajectory, extra_context or {}):
                plan.append(step)
                if len(plan) == 1:
                    break
                continue

            loop._emit_trace(
                context,
                "agent.iteration.started",
                iteration=iteration,
                step_kind=step.kind,
                instruction=step.instruction,
            )
            trajectory.stage = f"step_{iteration}_{step.kind}"

            if step.kind == "observe":
                observation = await loop._observe(
                    context, phase_ctx.task, trajectory, extra_context or {}
                )
                observations.append(observation)
                trajectory.observations.append(observation)
                memory_hits += 1 if observation else 0
                last_tool_result = observation
                loop._mark_subtask_progress(trajectory, "observe")
                phase_ctx.execution_frame.execution_summary["last_step"] = (
                    step.kind
                )
                loop._emit_trace(
                    context,
                    "agent.observation.recorded",
                    iteration=iteration,
                    observation=observation,
                )
                continue

            if step.kind == "tool" and step.tool_name:
                tool_context = loop._build_tool_context(context, step)
                record = await loop.tools.execute(
                    tool_context, step.tool_name, step.arguments
                )
                loop._record_audit(
                    "agent.tool.executed",
                    context,
                    trajectory,
                    tool_name=step.tool_name,
                    success=record.success,
                    risk_level=record.risk_level.value,
                )
                tool_calls.append(record)
                result_payload = record.model_dump(mode="json")
                trajectory.tool_results.append(result_payload)
                last_tool_result = json.dumps(
                    result_payload, ensure_ascii=False, default=str
                )
                loop._mark_subtask_progress(
                    trajectory, step.tool_name or "tool", succeeded=record.success
                )
                phase_ctx.execution_frame.tool_history.append(result_payload)
                phase_ctx.execution_frame.execution_summary["last_step"] = (
                    step.kind
                )
                loop._emit_trace(
                    context,
                    "agent.tool.completed",
                    iteration=iteration,
                    tool_name=step.tool_name,
                    success=record.success,
                    latency_ms=record.latency_ms,
                )

                # Handle write verification and repair
                if record.success and record.output is not None:
                    observation = loop._stringify(record.output)
                    observations.append(observation)
                    trajectory.observations.append(observation)
                    last_tool_result = observation
                    if step.tool_name in {"apply_text_patch", "write_file"}:
                        verification = await loop._verify_write_result(
                            context, step, record
                        )
                        if verification:
                            trajectory.observations.append(verification)
                            observations.append(verification)
                            last_tool_result = verification
                            continue
                        retry_step = await loop._repair_write_step(
                            context, trajectory, step, record, extra_context or {}
                        )
                        if retry_step is not None:
                            plan.insert(0, retry_step)
                            loop._emit_trace(
                                context,
                                "agent.write.retry_scheduled",
                                iteration=iteration,
                                tool_name=step.tool_name,
                            )
                        else:
                            loop._maybe_replan_after_failure(
                                context,
                                trajectory,
                                step,
                                record,
                                extra_context or {},
                                plan,
                            )
                elif step.tool_name in {"apply_text_patch", "write_file"}:
                    retry_step = await loop._repair_write_step(
                        context, trajectory, step, record, extra_context or {}
                    )
                    if retry_step is not None:
                        plan.insert(0, retry_step)
                        loop._emit_trace(
                            context,
                            "agent.write.retry_scheduled",
                            iteration=iteration,
                            tool_name=step.tool_name,
                        )
                    else:
                        loop._maybe_replan_after_failure(
                            context,
                            trajectory,
                            step,
                            record,
                            extra_context or {},
                            plan,
                        )

                # Handle repair suggestions
                if not record.success:
                    verification_result, repair_suggestion = (
                        loop.repair_loop.analyze(record)
                    )
                    phase_ctx.execution_frame.execution_summary.setdefault(
                        "repair_suggestions", []
                    ).append(
                        {
                            "tool_name": record.tool_name,
                            "verification": loop._dump_model(verification_result),
                            "suggestion": {
                                "should_retry": repair_suggestion.should_retry,
                                "tool_name": repair_suggestion.tool_name,
                                "arguments": repair_suggestion.arguments,
                                "reason": repair_suggestion.reason,
                                "error_type": repair_suggestion.error_type,
                                "confidence": repair_suggestion.confidence,
                                "follow_up": repair_suggestion.follow_up,
                            },
                        }
                    )
                    if (
                        repair_suggestion.should_retry
                        and repair_suggestion.tool_name
                    ):
                        retry_budget = int(
                            phase_ctx.execution_frame.execution_summary.get(
                                "retry_budget", loop.max_iterations
                            )
                            or loop.max_iterations
                        )
                        retry_count = int(
                            phase_ctx.execution_frame.execution_summary.get(
                                "retry_count", 0
                            )
                            or 0
                        )
                        if retry_count < retry_budget:
                            retry_tool = repair_suggestion.tool_name
                            dict(repair_suggestion.arguments)
                            phase_ctx.execution_frame.execution_summary[
                                "retry_count"
                            ] = retry_count + 1
                            phase_ctx.execution_frame.execution_summary[
                                "retry_budget"
                            ] = retry_budget
                            retry_step = loop._create_retry_step(
                                retry_tool, repair_suggestion
                            )
                            if repair_suggestion.follow_up:
                                plan[:0] = [
                                    loop._create_reflect_step(
                                        repair_suggestion.follow_up
                                    ),
                                    retry_step,
                                ]
                            else:
                                plan.insert(0, retry_step)
                            loop._emit_trace(
                                context,
                                "agent.repair.retry_scheduled",
                                iteration=iteration,
                                tool_name=retry_tool,
                                error_type=repair_suggestion.error_type,
                                retry_count=retry_count + 1,
                                follow_up=repair_suggestion.follow_up,
                            )
                        else:
                            loop._emit_trace(
                                context,
                                "agent.repair.retry_exhausted",
                                iteration=iteration,
                                tool_name=record.tool_name,
                                error_type=repair_suggestion.error_type,
                                retry_count=retry_count,
                                retry_budget=retry_budget,
                            )
                continue

            if step.kind == "reflect":
                loop._check_mainline(trajectory, last_tool_result or "")
                reflection = loop._reflect(context, trajectory, last_tool_result)
                trajectory.reflections.append(reflection)
                answer = reflection
                phase_ctx.execution_frame.execution_summary["last_step"] = (
                    step.kind
                )
                loop._check_mainline(trajectory, reflection)
                loop._emit_trace(
                    context,
                    "agent.reflection.created",
                    iteration=iteration,
                    reflection=reflection,
                )
                continue

            if step.kind == "final":
                trajectory.steps.append(step)
                answer = loop._finalize_answer(
                    phase_ctx.task, trajectory, last_tool_result, extra_context or {}
                )
                loop._mark_subtask_progress(trajectory, "final", succeeded=True)
                phase_ctx.execution_frame.execution_summary["last_step"] = (
                    step.kind
                )
                loop._emit_trace(
                    context,
                    "agent.finalized",
                    iteration=iteration,
                    answer=answer,
                )
                continue

        if not answer:
            answer = loop._finalize_answer(
                phase_ctx.task, trajectory, last_tool_result, extra_context or {}
            )

        phase_ctx.answer = answer
        phase_ctx.tool_calls = tool_calls
        phase_ctx.observations = observations
        phase_ctx.execution_frame.execution_summary.setdefault("iterations", iteration)

        return answer, tool_calls


class CompletionPhase:
    """Finalize execution and build response."""

    async def execute(self, phase_ctx: PhaseContext) -> AgentRunResponse:
        """Execute completion phase.

        Stores results, builds execution summary, and returns response.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        trajectory = phase_ctx.trajectory
        extra_context = phase_ctx.extra_context
        tool_calls = phase_ctx.tool_calls
        observations = phase_ctx.observations
        answer = phase_ctx.answer

        loop._record_audit(
            "agent.run.completed",
            context,
            trajectory,
            outcome="success",
            answer_preview=answer[:200],
        )

        session_id = context.session_id or str(
            extra_context.get("session_id") or ""
        ) or None
        phase_ctx.execution_frame.plan = phase_ctx.plan_frame
        phase_ctx.execution_frame.memory = {
            "memory_id": None,
            "observations": observations,
            "tool_count": len(tool_calls),
        }
        phase_ctx.execution_frame.tool_history = [
            call.model_dump(mode="json") for call in tool_calls
        ]

        # Build execution summary
        execution_summary = loop._build_execution_summary(
            trajectory, observations, tool_calls, [], answer, extra_context
        )
        phase_ctx.execution_frame.execution_summary = execution_summary

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

        trajectory.stage = "finalizing"
        execution_summary["session_id"] = session_id
        execution_summary["subtask_status"] = trajectory.subtask_status
        execution_summary["current_subtask_index"] = trajectory.current_subtask_index

        run_view = loop.runtime_adapter.build_run_view(
            {}, status=RunStatus.COMPLETED.value, answer=answer
        )
        execution_summary["run_view"] = run_view.model_dump()

        loop._emit_trace(
            context,
            "agent.completed",
            task=phase_ctx.task,
            answer=answer,
            memory_id=memory_id,
        )

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
                "execution_frame": phase_ctx.execution_frame.model_dump(
                    mode="json"
                ),
                "run_view": run_view,
            },
        )

        if loop.run_store is not None:
            loop.run_store.save(context, phase_ctx.task, result, run_view=run_view.model_dump())

        return result
