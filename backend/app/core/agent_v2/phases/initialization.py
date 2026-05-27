"""InitializationPhase for X-Agent v2 architecture.

Responsible for:
- Context compression and code indexing
- Task frame creation
- State initialization
- Execution frame setup
- Orchestration (prepare, draft plan, select tool)
- Recovery frame initialization
- Test mapping and execution plan building

Target: <100 lines, cyclomatic complexity <10

Extracted from AgentLoop.run() L148-L252
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop, AgentTrajectory
    from backend.app.core.agent_v2.phase_context import PhaseContext


class InitializationPhase:
    """Initialize execution context and state.

    Sets up task frame, execution frame, state manager, and orchestration
    decisions. This phase prepares all necessary context for planning and
    execution phases.

    Responsibilities:
    1. Compress and validate input context
    2. Index code repository
    3. Create task frame with goal and risk level
    4. Initialize agent state
    5. Build execution frame
    6. Run orchestration (prepare, draft plan, select tool)
    7. Set up recovery frame
    8. Build test mapping and execution plan
    9. Handle run resumption if applicable
    """

    async def execute(self, phase_ctx: PhaseContext) -> None:
        """Execute initialization phase.

        Args:
            phase_ctx: Shared context across phases. Modified in-place to
                      populate task_frame, execution_frame, and compact_context.

        Raises:
            ValueError: If required context is missing
            Exception: If orchestration or state setup fails
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        task = phase_ctx.task
        extra_context = phase_ctx.extra_context
        trajectory = phase_ctx.trajectory

        # Step 1: Compress context and index code
        self._compress_and_index(loop, phase_ctx, task, extra_context)

        # Step 2: Create task frame
        phase_ctx.task_frame = self._build_task_frame(
            loop, context, task, phase_ctx.compact_context
        )

        # Step 3: Initialize state
        state = loop.state_manager.create_initial_state(
            context=context,
            task_frame=phase_ctx.task_frame,
            metadata={"session_id": context.session_id}
            if context.session_id
            else {},
        )

        # Step 4: Build execution frame
        phase_ctx.execution_frame = self._build_execution_frame(
            context, phase_ctx.task_frame
        )
        state = loop.state_manager.attach_execution_frame(
            state, phase_ctx.execution_frame
        )

        # Step 5: Run orchestration
        self._run_orchestration(loop, phase_ctx, task)

        # Step 6: Initialize recovery frame
        initial_recovery = loop.state_manager.build_initial_recovery(
            tool_name=phase_ctx.compact_context.get("tool_decision", {}).get(
                "tool_name"
            ),
        )
        state = loop.state_manager.set_recovery_frame(state, initial_recovery)
        state = loop.state_manager.attach_plan_frame(
            state, phase_ctx.plan_frame
        )

        # Step 7: Build test mapping and execution plan
        self._build_test_and_execution_plan(loop, phase_ctx, task)

        # Step 8: Emit orchestration trace
        capability_decision = phase_ctx.compact_context.get(
            "capability_decision", {}
        )
        recovery_hint = phase_ctx.compact_context.get(
            "orchestration_recovery_hint", {}
        )
        tool_decision = phase_ctx.compact_context.get("tool_decision", {})
        loop._emit_trace(
            context,
            "agent.orchestrated",
            capability=capability_decision.get("name", "unknown"),
            reason=capability_decision.get("reason", ""),
            recovery_branch=recovery_hint.get("branch", "continue"),
            tool_name=tool_decision.get("tool_name"),
        )

        # Step 9: Handle run resumption
        self._handle_resumption(loop, phase_ctx, trajectory)

        # Step 10: Record audit
        loop._record_audit(
            "agent.run.started", context, trajectory, outcome="success"
        )

    def _compress_and_index(
        self,
        loop: AgentLoop,
        phase_ctx: PhaseContext,
        task: str,
        extra_context: dict[str, object],
    ) -> None:
        """Compress context and index code repository.

        Args:
            loop: AgentLoop instance
            phase_ctx: Phase context to populate
            task: Task string
            extra_context: Extra context from caller
        """
        from backend.app.core.code_index import code_index
        from backend.app.core.test_mapper import test_mapper

        phase_ctx.compact_context = loop._compress_context(extra_context or {})
        if phase_ctx.context.session_id:
            phase_ctx.compact_context.setdefault(
                "session_id", phase_ctx.context.session_id
            )

        # Index code repository
        indexed_repo = code_index.index(
            phase_ctx.compact_context.get("root", "."),
            limit=int(phase_ctx.compact_context.get("index_limit", 2000)),
        )
        phase_ctx.compact_context["code_index"] = {
            "count": indexed_repo.get("count", 0),
            "related_files": code_index.related_files(task, limit=8),
            "impact_hints": code_index.impact_hints(
                str(
                    phase_ctx.compact_context.get("path")
                    or phase_ctx.compact_context.get("target_path")
                    or ""
                ),
                limit=8,
            ),
            "test_files": code_index.test_files_for(task, limit=8),
        }

        # Map tests
        test_mapping = test_mapper.map(task, limit=6)
        phase_ctx.compact_context["test_mapping"] = {
            "related_files": test_mapping.related_files,
            "test_files": test_mapping.test_files,
            "impact_hints": test_mapping.impact_hints,
            "dependency_hints": test_mapping.dependency_hints,
            "recommended_commands": test_mapping.recommended_commands,
        }

    def _build_task_frame(
        self,
        loop: AgentLoop,
        context,
        task: str,
        compact_context: dict[str, object],
    ):
        """Build task frame with goal and metadata.

        Args:
            loop: AgentLoop instance
            context: RunContext
            task: Task string
            compact_context: Compressed context

        Returns:
            TaskFrame instance
        """
        from backend.app.core.contracts import TaskFrame

        return TaskFrame(
            goal=loop._derive_goal(task, compact_context),
            description=str(compact_context.get("task_focus") or task[:500]),
            risk_level=context.risk_level,
            requires_approval=bool(
                compact_context.get("requires_approval", False)
            ),
            metadata={"task": task, **compact_context},
        )

    def _build_execution_frame(self, context, task_frame):
        """Build execution frame for tracing.

        Args:
            context: RunContext
            task_frame: TaskFrame

        Returns:
            ExecutionFrame instance
        """
        from backend.app.core.contracts import ExecutionFrame

        return ExecutionFrame(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
            task=task_frame,
            session_id=context.session_id,
            metadata={"session_id": context.session_id}
            if context.session_id
            else {},
        )

    def _run_orchestration(
        self, loop: AgentLoop, phase_ctx: PhaseContext, task: str
    ) -> None:
        """Run orchestration to prepare, draft plan, and select tool.

        Args:
            loop: AgentLoop instance
            phase_ctx: Phase context to populate
            task: Task string
        """
        metadata = {"task": task, **phase_ctx.compact_context}

        # Prepare orchestration context
        (
            orchestration_context,
            capability_decision,
            recovery_hint,
        ) = loop.orchestrator.prepare(
            phase_ctx.task_frame, phase_ctx.execution_frame, metadata=metadata
        )

        # Draft plan
        draft_plan = loop.orchestrator.draft_plan(
            phase_ctx.task_frame, phase_ctx.execution_frame, metadata=metadata
        )

        # Select tool
        tool_decision = loop.orchestrator.select_tool(
            phase_ctx.task_frame, phase_ctx.execution_frame, metadata=metadata
        )

        # Store in compact context
        phase_ctx.compact_context["capability_decision"] = loop._dump_model(
            capability_decision
        )
        phase_ctx.compact_context["orchestration_recovery_hint"] = (
            loop._dump_model(recovery_hint)
        )
        phase_ctx.compact_context["orchestration_context"] = (
            orchestration_context.metadata
        )
        phase_ctx.compact_context["draft_plan"] = loop._dump_model(draft_plan)
        phase_ctx.compact_context["tool_decision"] = loop._dump_model(
            tool_decision
        )

        phase_ctx.plan_frame = draft_plan

    def _build_test_and_execution_plan(
        self, loop: AgentLoop, phase_ctx: PhaseContext, task: str
    ) -> None:
        """Build test mapping and execution plan.

        Args:
            loop: AgentLoop instance
            phase_ctx: Phase context to populate
            task: Task string
        """
        from backend.app.core.execution_planner import execution_planner

        # Verification summary
        test_mapping_data = phase_ctx.compact_context.get("test_mapping", {})
        phase_ctx.compact_context["verification"] = (
            loop.verification_engine.summarize_run([], test_mapping=test_mapping_data)
        )

        # Execution plan
        execution_plan_obj = execution_planner.build(
            task, test_mapping=test_mapping_data
        )
        phase_ctx.compact_context["execution_plan"] = loop._dump_model(
            execution_plan_obj
        )

    def _handle_resumption(
        self,
        loop: AgentLoop,
        phase_ctx: PhaseContext,
        trajectory: AgentTrajectory,
    ) -> None:
        """Handle run resumption if resume_trace_id is provided.

        Args:
            loop: AgentLoop instance
            phase_ctx: Phase context
            trajectory: AgentTrajectory to populate
        """
        resume_trace_id = str(
            (phase_ctx.extra_context or {}).get("resume_trace_id") or ""
        )

        if not resume_trace_id or loop.run_store is None:
            return

        previous = loop.run_store.get(resume_trace_id)
        if previous is None:
            return

        # Populate trajectory from previous run
        trajectory.stage = f"resuming:{resume_trace_id}"

        previous_subtasks = list(
            previous.execution_summary.get("subtasks", [])
        ) if isinstance(previous.execution_summary.get("subtasks", []), list) else []
        previous_status = dict(
            previous.execution_summary.get("subtask_status", {})
        ) if isinstance(
            previous.execution_summary.get("subtask_status", {}), dict
        ) else {}

        if previous_subtasks:
            trajectory.subtasks = previous_subtasks
        if previous_status:
            trajectory.subtask_status = previous_status

        trajectory.current_subtask_index = int(
            previous.execution_summary.get("current_subtask_index", 0) or 0
        )

        if previous.execution_summary.get("observations"):
            trajectory.observations = list(
                previous.execution_summary.get("observations", [])
            )
        if previous.execution_summary.get("tool_results"):
            trajectory.tool_results = list(
                previous.execution_summary.get("tool_results", [])
            )
        if previous.execution_summary.get("reflections"):
            trajectory.reflections = list(
                previous.execution_summary.get("reflections", [])
            )

        # Update execution frame with resume policy
        phase_ctx.execution_frame.execution_summary.update(
            {
                "resume_policy": {
                    "subtasks_inherited": bool(previous_subtasks),
                    "subtask_status_inherited": bool(previous_status),
                    "tool_results_inherited": bool(
                        previous.execution_summary.get("tool_results")
                    ),
                    "observations_inherited": bool(
                        previous.execution_summary.get("observations")
                    ),
                    "reflections_inherited": bool(
                        previous.execution_summary.get("reflections")
                    ),
                }
            }
        )
