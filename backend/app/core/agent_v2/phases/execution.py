"""ExecutionPhase - Main execution loop for agent plan steps.

This module implements the execution phase of the agent lifecycle, handling
the iterative execution of plan steps (observe, tool, reflect, final).

Key responsibilities:
- Execute main iteration loop
- Dispatch steps to appropriate handlers
- Manage tool execution and result handling
- Handle write verification and repair
- Track observations and tool calls
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.app.core.agent import AgentPlanStep, AgentPlanStepRecord
from backend.app.core.contracts import ToolCallRecord

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop, AgentTrajectory
    from backend.app.core.agent_phases import PhaseContext


class ExecutionPhase:
    """Execute plan steps iteratively with proper error handling and recovery.

    Main loop processes steps in order: observe -> tool -> reflect -> final.
    Each step type has dedicated handler method (<30 lines each).
    Main execute method stays <50 lines.
    """

    async def execute(
        self, phase_ctx: PhaseContext, plan: list[AgentPlanStep]
    ) -> tuple[str, list[ToolCallRecord]]:
        """Execute plan steps iteratively.

        Args:
            phase_ctx: Shared execution context
            plan: List of plan steps to execute

        Returns:
            Tuple of (final_answer, tool_call_records)
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
        plan_records: list[AgentPlanStepRecord] = []

        iteration = 0
        while iteration < loop.max_iterations and plan:
            step = plan.pop(0)
            iteration += 1
            phase_ctx.iteration = iteration

            # Check if step should be deferred
            if loop._should_defer_step(step, trajectory, extra_context or {}):
                plan.append(step)
                if len(plan) == 1:
                    break
                continue

            # Emit iteration start event
            loop._emit_trace(
                context,
                "agent.iteration.started",
                iteration=iteration,
                step_kind=step.kind,
                instruction=step.instruction,
            )
            trajectory.stage = f"step_{iteration}_{step.kind}"

            # Dispatch to appropriate handler
            if step.kind == "observe":
                observation, record = await self._handle_observe(
                    loop, context, phase_ctx, step, trajectory, extra_context
                )
                observations.append(observation)
                trajectory.observations.append(observation)
                memory_hits += 1 if observation else 0
                last_tool_result = observation
                plan_records.append(record)
                continue

            if step.kind == "tool" and step.tool_name:
                tool_result, record, retry_plan = await self._handle_tool(
                    loop, context, phase_ctx, step, trajectory, extra_context, plan
                )
                if tool_result is not None:
                    observations.append(tool_result)
                    trajectory.observations.append(tool_result)
                    last_tool_result = tool_result
                tool_calls.append(record)
                plan_records.append(record)
                plan = retry_plan
                continue

            if step.kind == "reflect":
                reflection, record = self._handle_reflect(
                    loop, context, phase_ctx, step, trajectory, last_tool_result
                )
                answer = reflection
                plan_records.append(record)
                continue

            if step.kind == "final":
                answer, record = self._handle_final(
                    loop, context, phase_ctx, step, trajectory, last_tool_result, extra_context
                )
                plan_records.append(record)
                continue

        # Finalize answer if not set
        if not answer:
            answer = loop._finalize_answer(
                phase_ctx.task, trajectory, last_tool_result, extra_context or {}
            )

        phase_ctx.answer = answer
        phase_ctx.tool_calls = tool_calls
        phase_ctx.observations = observations
        phase_ctx.execution_frame.execution_summary.setdefault("iterations", iteration)

        return answer, tool_calls

    async def _handle_observe(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        trajectory: AgentTrajectory,
        extra_context: dict,
    ) -> tuple[str, AgentPlanStepRecord]:
        """Handle observe step - retrieve context from memory and discovery.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            trajectory: Agent trajectory
            extra_context: Extra context dict

        Returns:
            Tuple of (observation_string, plan_record)
        """
        observation = await loop._observe(
            context, phase_ctx.task, trajectory, extra_context or {}
        )
        loop._mark_subtask_progress(trajectory, "observe")
        phase_ctx.execution_frame.execution_summary["last_step"] = step.kind

        loop._emit_trace(
            context,
            "agent.observation.recorded",
            iteration=phase_ctx.iteration,
            observation=observation,
        )

        record = AgentPlanStepRecord(
            kind=step.kind,
            instruction=step.instruction,
            tool_name=step.tool_name,
            arguments=step.arguments,
            result={"observation": observation},
            summary=f"Observed context for {trajectory.goal}",
            actions=["observe"],
            verifications=[],
            risks=[],
            next_steps=loop._next_subtask_steps(trajectory, step.kind),
        )

        return observation, record

    async def _handle_tool(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        trajectory: AgentTrajectory,
        extra_context: dict,
        plan: list[AgentPlanStep],
    ) -> tuple[str | None, AgentPlanStepRecord, list[AgentPlanStep]]:
        """Handle tool execution step with verification and repair.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            trajectory: Agent trajectory
            extra_context: Extra context dict
            plan: Current plan (may be modified for retries)

        Returns:
            Tuple of (observation_or_none, plan_record, updated_plan)
        """
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

        result_payload = record.model_dump(mode="json")
        trajectory.tool_results.append(result_payload)
        last_tool_result = json.dumps(result_payload, ensure_ascii=False, default=str)

        loop._mark_subtask_progress(
            trajectory, step.tool_name or "tool", succeeded=record.success
        )
        phase_ctx.execution_frame.tool_history.append(result_payload)
        phase_ctx.execution_frame.execution_summary["last_step"] = step.kind

        loop._emit_trace(
            context,
            "agent.tool.completed",
            iteration=phase_ctx.iteration,
            tool_name=step.tool_name,
            success=record.success,
            latency_ms=record.latency_ms,
        )

        # Handle successful tool execution
        observation = None
        if record.success and record.output is not None:
            observation = loop._stringify(record.output)
            if step.tool_name in {"apply_text_patch", "write_file"}:
                plan = await self._handle_write_verification(
                    loop, context, phase_ctx, step, record, trajectory, extra_context, plan
                )

        # Handle failed write operations
        elif step.tool_name in {"apply_text_patch", "write_file"}:
            plan = await self._handle_write_failure(
                loop, context, phase_ctx, step, record, trajectory, extra_context, plan
            )

        # Handle repair suggestions for failed tools
        if not record.success:
            plan = await self._handle_repair_suggestion(
                loop, context, phase_ctx, step, record, trajectory, plan
            )

        plan_record = AgentPlanStepRecord(
            kind=step.kind,
            instruction=step.instruction,
            tool_name=step.tool_name,
            arguments=step.arguments,
            result=result_payload,
            error=record.error,
            summary=f"Tool {step.tool_name} executed with {'success' if record.success else 'failure'}",
            actions=[f"tool:{step.tool_name}"],
            verifications=[
                "write verified"
                if step.tool_name in {"apply_text_patch", "write_file"}
                and record.success
                else "tool result captured"
            ],
            risks=[record.risk_level.value],
            next_steps=loop._next_subtask_steps(
                trajectory, step.kind, tool_name=step.tool_name
            ),
        )

        return observation, plan_record, plan

    async def _handle_write_verification(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        record: ToolCallRecord,
        trajectory: AgentTrajectory,
        extra_context: dict,
        plan: list[AgentPlanStep],
    ) -> list[AgentPlanStep]:
        """Verify write operation and schedule repair if needed.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            record: Tool call record
            trajectory: Agent trajectory
            extra_context: Extra context dict
            plan: Current plan

        Returns:
            Updated plan (may include retry steps)
        """
        verification = await loop._verify_write_result(context, step, record)
        if verification:
            trajectory.observations.append(verification)
            return plan

        retry_step = await loop._repair_write_step(
            context, trajectory, step, record, extra_context or {}
        )
        if retry_step is not None:
            plan.insert(0, retry_step)
            loop._emit_trace(
                context,
                "agent.write.retry_scheduled",
                iteration=phase_ctx.iteration,
                tool_name=step.tool_name,
            )
        else:
            loop._maybe_replan_after_failure(
                context, trajectory, step, record, extra_context or {}, plan
            )

        return plan

    async def _handle_write_failure(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        record: ToolCallRecord,
        trajectory: AgentTrajectory,
        extra_context: dict,
        plan: list[AgentPlanStep],
    ) -> list[AgentPlanStep]:
        """Handle failed write operation with repair attempt.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            record: Tool call record
            trajectory: Agent trajectory
            extra_context: Extra context dict
            plan: Current plan

        Returns:
            Updated plan (may include retry steps)
        """
        retry_step = await loop._repair_write_step(
            context, trajectory, step, record, extra_context or {}
        )
        if retry_step is not None:
            plan.insert(0, retry_step)
            loop._emit_trace(
                context,
                "agent.write.retry_scheduled",
                iteration=phase_ctx.iteration,
                tool_name=step.tool_name,
            )
        else:
            loop._maybe_replan_after_failure(
                context, trajectory, step, record, extra_context or {}, plan
            )

        return plan

    async def _handle_repair_suggestion(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        record: ToolCallRecord,
        trajectory: AgentTrajectory,
        plan: list[AgentPlanStep],
    ) -> list[AgentPlanStep]:
        """Analyze failure and schedule repair/retry if applicable.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            record: Tool call record
            trajectory: Agent trajectory
            plan: Current plan

        Returns:
            Updated plan (may include retry steps)
        """
        verification_result, repair_suggestion = loop.repair_loop.analyze(record)

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

        if repair_suggestion.should_retry and repair_suggestion.tool_name:
            retry_budget = int(
                phase_ctx.execution_frame.execution_summary.get(
                    "retry_budget", loop.max_iterations
                )
                or loop.max_iterations
            )
            retry_count = int(
                phase_ctx.execution_frame.execution_summary.get("retry_count", 0)
                or 0
            )

            if retry_count < retry_budget:
                plan = self._schedule_retry(
                    loop,
                    context,
                    phase_ctx,
                    repair_suggestion,
                    record,
                    trajectory,
                    plan,
                    retry_count,
                    retry_budget,
                )
            else:
                phase_ctx.execution_frame.execution_summary.setdefault(
                    "repair_failures", []
                ).append(
                    {
                        "tool_name": record.tool_name,
                        "error": record.error,
                        "reason": repair_suggestion.reason,
                        "error_type": repair_suggestion.error_type,
                        "retry_count": retry_count,
                        "retry_budget": retry_budget,
                        "follow_up": repair_suggestion.follow_up,
                    }
                )
                loop._emit_trace(
                    context,
                    "agent.repair.retry_exhausted",
                    iteration=phase_ctx.iteration,
                    tool_name=record.tool_name,
                    error_type=repair_suggestion.error_type,
                    retry_count=retry_count,
                    retry_budget=retry_budget,
                )

        return plan

    def _schedule_retry(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        repair_suggestion,
        record: ToolCallRecord,
        trajectory: AgentTrajectory,
        plan: list[AgentPlanStep],
        retry_count: int,
        retry_budget: int,
    ) -> list[AgentPlanStep]:
        """Schedule a retry step based on repair suggestion.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            repair_suggestion: Repair suggestion from repair loop
            record: Tool call record
            trajectory: Agent trajectory
            plan: Current plan
            retry_count: Current retry count
            retry_budget: Maximum retries allowed

        Returns:
            Updated plan with retry step inserted
        """
        retry_tool = repair_suggestion.tool_name
        retry_args = dict(repair_suggestion.arguments)

        phase_ctx.execution_frame.execution_summary["retry_count"] = retry_count + 1
        phase_ctx.execution_frame.execution_summary["retry_budget"] = retry_budget

        retry_step = AgentPlanStep(
            kind="tool",
            instruction=f"Retry {retry_tool} after repair: {repair_suggestion.reason}",
            tool_name=retry_tool,
            arguments=retry_args,
        )

        if repair_suggestion.follow_up:
            plan[:0] = [
                AgentPlanStep(
                    kind="reflect",
                    instruction=f"Repair follow-up: {', '.join(repair_suggestion.follow_up)}",
                ),
                retry_step,
            ]
        else:
            plan.insert(0, retry_step)

        phase_ctx.execution_frame.execution_summary.setdefault(
            "repair_retries", []
        ).append(
            {
                "tool_name": retry_tool,
                "arguments": retry_args,
                "reason": repair_suggestion.reason,
                "error_type": repair_suggestion.error_type,
                "retry_count": retry_count + 1,
                "follow_up": repair_suggestion.follow_up,
            }
        )

        loop._emit_trace(
            context,
            "agent.repair.retry_scheduled",
            iteration=phase_ctx.iteration,
            tool_name=retry_tool,
            error_type=repair_suggestion.error_type,
            retry_count=retry_count + 1,
            follow_up=repair_suggestion.follow_up,
        )

        return plan

    def _handle_reflect(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        trajectory: AgentTrajectory,
        last_tool_result: str | None,
    ) -> tuple[str, AgentPlanStepRecord]:
        """Handle reflect step - generate reflection on progress.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            trajectory: Agent trajectory
            last_tool_result: Last tool result string

        Returns:
            Tuple of (reflection_string, plan_record)
        """
        loop._check_mainline(trajectory, last_tool_result or "")
        reflection = loop._reflect(context, trajectory, last_tool_result)
        trajectory.reflections.append(reflection)
        phase_ctx.execution_frame.execution_summary["last_step"] = step.kind
        loop._check_mainline(trajectory, reflection)

        loop._emit_trace(
            context,
            "agent.reflection.created",
            iteration=phase_ctx.iteration,
            reflection=reflection,
        )

        record = AgentPlanStepRecord(
            kind=step.kind,
            instruction=step.instruction,
            result={"reflection": reflection},
            summary="Reflection generated",
            actions=["reflect"],
            verifications=["evidence reviewed"],
            risks=[],
            next_steps=loop._next_subtask_steps(trajectory, step.kind),
        )

        return reflection, record

    def _handle_final(
        self,
        loop: AgentLoop,
        context,
        phase_ctx: PhaseContext,
        step: AgentPlanStep,
        trajectory: AgentTrajectory,
        last_tool_result: str | None,
        extra_context: dict,
    ) -> tuple[str, AgentPlanStepRecord]:
        """Handle final step - generate final answer.

        Args:
            loop: Agent loop instance
            context: Run context
            phase_ctx: Phase context
            step: Current plan step
            trajectory: Agent trajectory
            last_tool_result: Last tool result string
            extra_context: Extra context dict

        Returns:
            Tuple of (final_answer, plan_record)
        """
        trajectory.steps.append(step)
        answer = loop._finalize_answer(
            phase_ctx.task, trajectory, last_tool_result, extra_context or {}
        )
        loop._mark_subtask_progress(trajectory, "final", succeeded=True)
        phase_ctx.execution_frame.execution_summary["last_step"] = step.kind

        loop._emit_trace(
            context,
            "agent.finalized",
            iteration=phase_ctx.iteration,
            answer=answer,
        )

        record = AgentPlanStepRecord(
            kind=step.kind,
            instruction=step.instruction,
            result={"answer": answer},
            summary="Final answer produced",
            actions=["finalize"],
            verifications=["result assembled"],
            risks=[],
            next_steps=loop._next_subtask_steps(trajectory, step.kind),
        )

        return answer, record
