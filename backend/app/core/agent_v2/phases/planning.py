"""PlanningPhase for X-Agent v2 architecture.

Responsible for:
- Orchestrator preparation
- Plan generation
- Execution plan application
- Subtask alignment
- Plan deduplication

Target: <80 lines, cyclomatic complexity <8
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.core.agent import AgentPlanStep, AgentTrajectory
    from backend.app.core.agent_phases import PhaseContext


class PlanningPhase:
    """Generate and refine execution plan.

    Orchestrates the planning process by:
    1. Generating initial plan from LLM
    2. Applying execution plan optimizations
    3. Aligning with subtasks
    4. Deduplicating steps
    """

    async def execute(self, phase_ctx: PhaseContext) -> list[AgentPlanStep]:
        """Execute planning phase.

        Args:
            phase_ctx: Shared context across phases

        Returns:
            Refined plan steps ready for execution

        Raises:
            Exception: If plan generation fails
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        trajectory = phase_ctx.trajectory
        compact_context = phase_ctx.compact_context
        extra_context = phase_ctx.extra_context

        # 1. Generate initial plan
        plan = await self._generate_plan(loop, context, trajectory, compact_context)

        # 2. Apply execution plan optimizations
        plan = loop._apply_execution_plan(plan, compact_context)

        # 3. Initialize plan frame if needed
        self._initialize_plan_frame(phase_ctx, plan)

        # 4. Handle resume scenario
        resume_trace_id = str((extra_context or {}).get("resume_trace_id") or "")
        if resume_trace_id:
            plan = self._handle_resume(loop, context, phase_ctx, plan, resume_trace_id)

        # 5. Emit task decomposition event
        if trajectory.subtasks:
            loop._emit_trace(
                context,
                "agent.task.decomposed",
                subtask_count=len(trajectory.subtasks),
                subtasks=trajectory.subtasks,
            )

        # 6. Final deduplication
        plan = loop._dedupe_plan_steps(trajectory, plan)

        # 7. Update plan frame
        self._finalize_plan_frame(phase_ctx, plan)

        # 8. Record plan creation event
        loop._emit_trace(
            context,
            "agent.plan.created",
            task=phase_ctx.task,
            goal=trajectory.goal,
            step_count=len(plan),
        )

        return plan

    async def _generate_plan(
        self,
        loop,
        context,
        trajectory: AgentTrajectory,
        compact_context: dict[str, object],
    ) -> list[AgentPlanStep]:
        """Generate initial plan from orchestrator and LLM.

        Args:
            loop: AgentLoop instance
            context: RunContext
            trajectory: AgentTrajectory
            compact_context: Compressed context

        Returns:
            Generated plan steps
        """
        return await loop._plan(context, trajectory, compact_context)

    def _initialize_plan_frame(
        self, phase_ctx: PhaseContext, plan: list[AgentPlanStep]
    ) -> None:
        """Initialize plan frame if not already set.

        Args:
            phase_ctx: Shared context
            plan: Generated plan steps
        """
        if not phase_ctx.plan_frame.steps:
            phase_ctx.plan_frame.steps = [step.instruction for step in plan]
            phase_ctx.plan_frame.status = "ready"
            phase_ctx.plan_frame.revision += 1

    def _handle_resume(
        self,
        loop,
        context,
        phase_ctx: PhaseContext,
        plan: list[AgentPlanStep],
        resume_trace_id: str,
    ) -> list[AgentPlanStep]:
        """Handle resume scenario by filtering completed steps.

        Args:
            loop: AgentLoop instance
            context: RunContext
            phase_ctx: Shared context
            plan: Current plan
            resume_trace_id: Trace ID to resume from

        Returns:
            Filtered plan with completed steps removed
        """
        trajectory = phase_ctx.trajectory
        execution_frame = phase_ctx.execution_frame

        # Emit resume event
        loop._emit_trace(
            context,
            "agent.resumed",
            resumed_from=resume_trace_id,
            stage=trajectory.stage,
        )

        # Get resume payload from run store
        resume_payload = self._get_resume_payload(loop, resume_trace_id)

        # Filter by completed kinds
        if resume_payload.get("completed_kinds"):
            plan = self._filter_by_completed_kinds(plan, resume_payload)

        # Filter by completed step labels
        if resume_payload.get("completed_step_labels"):
            plan = self._filter_by_completed_labels(plan, resume_payload)

        # Update execution summary with resume info
        if resume_payload.get("previous_execution_summary"):
            execution_frame.execution_summary.update(
                {
                    "resumed_from": resume_trace_id,
                    "previous_execution_summary": resume_payload.get(
                        "previous_execution_summary"
                    ),
                    "previous_status": resume_payload.get("previous_status"),
                }
            )

        # Align with subtasks and deduplicate
        plan = loop._align_plan_with_subtasks(plan, trajectory)
        plan = loop._dedupe_plan_steps(trajectory, plan)

        return plan

    def _get_resume_payload(self, loop, resume_trace_id: str) -> dict[str, object]:
        """Get resume payload from run store.

        Args:
            loop: AgentLoop instance
            resume_trace_id: Trace ID to resume from

        Returns:
            Resume payload with completed steps info
        """
        if loop.run_store is None:
            return {}

        previous = loop.run_store.get(resume_trace_id)
        if previous is None:
            return {}

        completed_plan_kinds = [step.kind for step in previous.plan]
        completed_step_labels = [step.instruction for step in previous.plan]

        return {
            "completed_kinds": completed_plan_kinds,
            "completed_step_labels": completed_step_labels,
            "previous_execution_summary": previous.execution_summary,
            "previous_status": (
                previous.status.value
                if hasattr(previous.status, "value")
                else str(previous.status)
            ),
        }

    def _filter_by_completed_kinds(
        self, plan: list[AgentPlanStep], resume_payload: dict[str, object]
    ) -> list[AgentPlanStep]:
        """Filter plan by removing completed step kinds.

        Args:
            plan: Current plan
            resume_payload: Resume payload with completed kinds

        Returns:
            Filtered plan
        """
        completed_kinds = {
            str(kind) for kind in resume_payload.get("completed_kinds", [])
        }
        return [
            step
            for step in plan
            if step.kind not in completed_kinds or step.kind == "final"
        ] or plan

    def _filter_by_completed_labels(
        self, plan: list[AgentPlanStep], resume_payload: dict[str, object]
    ) -> list[AgentPlanStep]:
        """Filter plan by removing completed step labels.

        Args:
            plan: Current plan
            resume_payload: Resume payload with completed labels

        Returns:
            Filtered plan
        """
        completed_labels = {
            str(label).strip().lower()
            for label in resume_payload.get("completed_step_labels", [])
        }
        return [
            step
            for step in plan
            if step.instruction.strip().lower() not in completed_labels
            or step.kind == "final"
        ] or plan

    def _finalize_plan_frame(
        self, phase_ctx: PhaseContext, plan: list[AgentPlanStep]
    ) -> None:
        """Finalize plan frame with refined plan.

        Args:
            phase_ctx: Shared context
            plan: Refined plan steps
        """
        phase_ctx.plan_frame.steps = [step.instruction for step in plan]
        phase_ctx.plan_frame.status = "ready"
        phase_ctx.plan_frame.revision += 1
        phase_ctx.execution_frame.plan = phase_ctx.plan_frame

        # Update execution summary with orchestrator info
        phase_ctx.execution_frame.execution_summary.update(
            {
                "orchestrator_plan": phase_ctx.compact_context.get(
                    "draft_plan", {}
                ),
                "orchestrator_tool_decision": phase_ctx.compact_context.get(
                    "tool_decision", {}
                ),
                "orchestrator_recovery_hint": phase_ctx.compact_context.get(
                    "orchestration_recovery_hint", {}
                ),
            }
        )
