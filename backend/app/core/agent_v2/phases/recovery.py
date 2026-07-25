"""Recovery phase for handling execution failures and scheduling retries.

This module implements the RecoveryPhase which analyzes failures, generates
repair suggestions, and schedules retries when appropriate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.core.contracts import RecoveryFrame

if TYPE_CHECKING:
    from backend.app.core.agent_phases import PhaseContext


class RecoveryPhase:
    """Handles failure analysis and retry scheduling.

    Responsibilities:
    - Analyze tool call failures
    - Generate repair suggestions
    - Schedule retries with updated parameters
    - Update recovery frame with failure information
    - Track retry budget and exhaustion

    Complexity: <60 lines, cyclomatic complexity <8
    """

    def can_skip(self, phase_ctx: PhaseContext) -> bool:
        """Check if recovery phase can be skipped.

        Recovery is skipped if there are no failures in tool calls.

        Args:
            phase_ctx: Shared execution context.

        Returns:
            True if no failures exist, False otherwise.
        """
        return not any(not call.success for call in phase_ctx.tool_calls)

    async def execute(self, phase_ctx: PhaseContext) -> None:
        """Execute recovery phase.

        Analyzes failures, generates repair suggestions, and schedules retries.

        Args:
            phase_ctx: Shared execution context with tool call records.
        """
        loop = phase_ctx.loop
        context = phase_ctx.context
        execution_frame = phase_ctx.execution_frame

        # Collect failures
        failures = [call for call in phase_ctx.tool_calls if not call.success]
        if not failures:
            return

        # Analyze each failure and schedule retries
        for failure in failures:
            verification_result, repair_suggestion = loop.repair_loop.analyze(
                failure
            )

            # Store repair suggestion
            execution_frame.execution_summary.setdefault(
                "repair_suggestions", []
            ).append(
                {
                    "tool_name": failure.tool_name,
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

            # Schedule retry if applicable
            if (
                repair_suggestion.should_retry
                and repair_suggestion.tool_name
            ):
                self._schedule_retry(
                    loop,
                    context,
                    phase_ctx,
                    repair_suggestion,
                    failure,
                )
            else:
                # Record failure if no retry
                execution_frame.execution_summary.setdefault(
                    "repair_failures", []
                ).append(
                    {
                        "tool_name": failure.tool_name,
                        "error": failure.error,
                        "reason": repair_suggestion.reason,
                        "error_type": repair_suggestion.error_type,
                    }
                )

        # Build recovery frame
        self._build_recovery_frame(phase_ctx)

    def _schedule_retry(
        self,
        loop: object,
        context: object,
        phase_ctx: PhaseContext,
        repair_suggestion: object,
        failure: object,
    ) -> None:
        """Schedule a retry for a failed tool call.

        Args:
            loop: AgentLoop instance.
            context: Execution context.
            phase_ctx: Shared phase context.
            repair_suggestion: Repair suggestion from repair loop.
            failure: Failed tool call record.
        """
        execution_frame = phase_ctx.execution_frame
        retry_budget = int(
            execution_frame.execution_summary.get(
                "retry_budget", loop.max_iterations
            )
            or loop.max_iterations
        )
        retry_count = int(
            execution_frame.execution_summary.get("retry_count", 0) or 0
        )

        if retry_count < retry_budget:
            # Update retry counters
            execution_frame.execution_summary["retry_count"] = retry_count + 1
            execution_frame.execution_summary["retry_budget"] = retry_budget

            # Record retry
            execution_frame.execution_summary.setdefault(
                "repair_retries", []
            ).append(
                {
                    "tool_name": repair_suggestion.tool_name,
                    "arguments": dict(repair_suggestion.arguments),
                    "reason": repair_suggestion.reason,
                    "error_type": repair_suggestion.error_type,
                    "retry_count": retry_count + 1,
                    "follow_up": repair_suggestion.follow_up,
                }
            )

            # Emit trace
            loop._emit_trace(
                context,
                "agent.repair.retry_scheduled",
                tool_name=repair_suggestion.tool_name,
                error_type=repair_suggestion.error_type,
                retry_count=retry_count + 1,
                follow_up=repair_suggestion.follow_up,
            )
        else:
            # Retry budget exhausted
            execution_frame.execution_summary.setdefault(
                "repair_failures", []
            ).append(
                {
                    "tool_name": failure.tool_name,
                    "error": failure.error,
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
                tool_name=failure.tool_name,
                error_type=repair_suggestion.error_type,
                retry_count=retry_count,
                retry_budget=retry_budget,
            )

    def _build_recovery_frame(self, phase_ctx: PhaseContext) -> None:
        """Build recovery frame from execution summary.

        Args:
            phase_ctx: Shared phase context.
        """
        execution_summary = phase_ctx.execution_frame.execution_summary
        repair_summary = (
            dict(execution_summary.get("repair_summary", {}))
            if isinstance(execution_summary.get("repair_summary", {}), dict)
            else {}
        )

        recovery_branch = str(execution_summary.get("branch", "continue"))
        retryable = bool(
            execution_summary.get("retryable_failures", 0)
            or repair_summary.get("retry_count", 0)
        )

        recovery_frame = RecoveryFrame(
            branch=recovery_branch,
            reason=str(execution_summary.get("reason"))
            if execution_summary.get("reason")
            else None,
            retryable=retryable,
            confidence=float(
                repair_summary.get("confidence", 0.5)
                if isinstance(repair_summary, dict)
                else 0.5
            ),
            follow_up=list(repair_summary.get("follow_up", []))
            if isinstance(repair_summary, dict)
            and isinstance(repair_summary.get("follow_up", []), list)
            else [],
            status_detail=str(
                execution_summary.get("branch_note")
                or execution_summary.get("status")
                or recovery_branch
            ),
            remediation=str(
                execution_summary.get("next_action")
                or execution_summary.get("reason")
                or "continue execution"
            ),
        )

        phase_ctx.execution_frame.recovery = recovery_frame
