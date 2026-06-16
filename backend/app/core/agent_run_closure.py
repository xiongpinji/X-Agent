from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from backend.app.core.contracts import RunStatus, ToolCallRecord, TraceEvent

ENGINEERING_PATCH_TOOLS = {
    "engineering_create_patch_approval",
    "engineering_stage_patch_approval",
    "engineering_parse_diff",
}


def build_agent_run_closure_report(
    *,
    task: str,
    status: RunStatus,
    iterations: int,
    memory_hits: int,
    tool_calls: Sequence[ToolCallRecord],
    events: Sequence[TraceEvent],
    answer: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    """Build a compact evidence chain for Codex-like task closure."""

    tool_names = [record.tool_name for record in tool_calls]
    validation_records = [
        record for record in tool_calls if record.tool_name == "engineering_run_validation"
    ]
    patch_records = [record for record in tool_calls if record.tool_name in ENGINEERING_PATCH_TOOLS]
    failed_records = [record for record in tool_calls if not record.success]
    failed_validation_records = [record for record in validation_records if _validation_failed(record)]
    failure_suggestions = _failure_suggestions(
        failed_records=failed_records,
        failed_validation_records=failed_validation_records,
        events=events,
        error=error,
    )
    phase_states = {
        "plan": "completed" if _has_event(events, "context.pack") else "missing",
        "execute": "completed" if tool_calls else "not_started",
        "change": "completed" if patch_records else "not_started",
        "test": _test_phase_state(validation_records),
        "repair": "recommended" if failure_suggestions else "not_needed",
        "report": "completed" if status == RunStatus.COMPLETED else "blocked",
    }
    blocking_reasons = _blocking_reasons(
        status=status,
        phase_states=phase_states,
        failed_records=failed_records,
        failed_validation_records=failed_validation_records,
        failure_suggestions=failure_suggestions,
        error=error,
    )
    ready_for_handoff = (
        status == RunStatus.COMPLETED
        and not blocking_reasons
        and phase_states["execute"] == "completed"
        and phase_states["test"] == "passed"
        and phase_states["report"] == "completed"
    )
    return {
        "kind": "agent_run_closure_report",
        "version": 1,
        "status": "ready_for_handoff" if ready_for_handoff else "needs_followup",
        "ready_for_handoff": ready_for_handoff,
        "task_excerpt": task[:500],
        "phase_states": phase_states,
        "evidence": {
            "iterations": iterations,
            "memory_hits": memory_hits,
            "event_count": len(events),
            "tool_call_count": len(tool_calls),
            "tools": tool_names,
            "validation": [_validation_evidence(record) for record in validation_records],
            "changes": [_change_evidence(record) for record in patch_records],
            "failed_tools": [_failed_tool_evidence(record) for record in failed_records],
            "final_answer_excerpt": answer[:500],
        },
        "failure_suggestions": failure_suggestions,
        "blocking_reasons": blocking_reasons,
        "next_actions": _next_actions(
            phase_states=phase_states,
            blocking_reasons=blocking_reasons,
            failure_suggestions=failure_suggestions,
        ),
    }


def _has_event(events: Sequence[TraceEvent], event_name: str) -> bool:
    return any(event.event == event_name for event in events)


def _validation_failed(record: ToolCallRecord) -> bool:
    output = record.output if isinstance(record.output, dict) else {}
    exit_code = output.get("exit_code")
    return record.success is False or output.get("timed_out") is True or (
        isinstance(exit_code, int) and exit_code != 0
    )


def _test_phase_state(validation_records: Sequence[ToolCallRecord]) -> str:
    if not validation_records:
        return "not_started"
    if any(_validation_failed(record) for record in validation_records):
        return "failed"
    return "passed"


def _validation_evidence(record: ToolCallRecord) -> dict[str, Any]:
    output = record.output if isinstance(record.output, dict) else {}
    return {
        "tool_name": record.tool_name,
        "command": output.get("command") or record.arguments_preview.get("command"),
        "exit_code": output.get("exit_code"),
        "timed_out": output.get("timed_out"),
        "stdout_excerpt": str(output.get("stdout") or "")[:500],
        "stderr_excerpt": str(output.get("stderr") or "")[:500],
        "failure_attribution": output.get("failure_attribution"),
    }


def _change_evidence(record: ToolCallRecord) -> dict[str, Any]:
    output = record.output if isinstance(record.output, dict) else {}
    changed_files = output.get("changed_files") or output.get("files") or []
    if not isinstance(changed_files, list):
        changed_files = []
    return {
        "tool_name": record.tool_name,
        "success": record.success,
        "changed_files": [str(item) for item in changed_files][:20],
        "approval_id": output.get("approval_id") or record.policy.approval_id,
        "summary": output.get("summary"),
    }


def _failed_tool_evidence(record: ToolCallRecord) -> dict[str, Any]:
    strategy = _record_failure_strategy(record)
    return {
        "tool_name": record.tool_name,
        "error": record.error,
        "risk_level": record.risk_level.value,
        "arguments_preview": record.arguments_preview,
        "failure_recovery_strategy": strategy,
    }


def _failure_suggestions(
    *,
    failed_records: Sequence[ToolCallRecord],
    failed_validation_records: Sequence[ToolCallRecord],
    events: Sequence[TraceEvent],
    error: str | None,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for record in failed_validation_records:
        output = record.output if isinstance(record.output, dict) else {}
        attribution = output.get("failure_attribution")
        next_action = (
            attribution.get("next_action")
            if isinstance(attribution, dict)
            else "inspect_validation_output"
        )
        suggestions.append(
            {
                "source": "engineering_run_validation",
                "category": attribution.get("category") if isinstance(attribution, dict) else "validation_failed",
                "next_action": next_action,
                "command": output.get("command") or record.arguments_preview.get("command"),
            }
        )
    for record in failed_records:
        strategy = _record_failure_strategy(record)
        if not isinstance(strategy, dict):
            continue
        suggestions.append(
            {
                "source": record.tool_name,
                "category": strategy.get("category") or "tool_failed",
                "next_action": strategy.get("next_action") or "manual_review",
                "retry_budget": strategy.get("retry_budget"),
            }
        )
    for event in events:
        if event.event != "tool.failure_strategy":
            continue
        suggestions.append(
            {
                "source": event.data.get("tool_name"),
                "category": event.data.get("category"),
                "next_action": event.data.get("next_action"),
                "retry_budget": event.data.get("retry_budget"),
                "tool_router": event.data.get("tool_router"),
            }
        )
    if error and not suggestions:
        suggestions.append(
            {
                "source": "agent",
                "category": "agent_error",
                "next_action": "inspect_agent_error_and_rerun_targeted_validation",
                "error_excerpt": error[:500],
            }
        )
    return _dedupe_suggestions(suggestions)


def _record_failure_strategy(record: ToolCallRecord) -> dict[str, Any] | None:
    boundary = getattr(record, "security_boundary", None)
    if isinstance(boundary, dict) and isinstance(boundary.get("failure_recovery_strategy"), dict):
        return dict(boundary["failure_recovery_strategy"])
    output = record.output if isinstance(record.output, dict) else {}
    strategy = output.get("failure_recovery_strategy")
    return dict(strategy) if isinstance(strategy, dict) else None


def _dedupe_suggestions(suggestions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in suggestions:
        key = (
            str(item.get("source") or ""),
            str(item.get("category") or ""),
            str(item.get("next_action") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(item))
    return deduped[:10]


def _blocking_reasons(
    *,
    status: RunStatus,
    phase_states: dict[str, str],
    failed_records: Sequence[ToolCallRecord],
    failed_validation_records: Sequence[ToolCallRecord],
    failure_suggestions: Sequence[dict[str, Any]],
    error: str | None,
) -> list[str]:
    reasons: list[str] = []
    if status != RunStatus.COMPLETED:
        reasons.append(f"agent_status:{status.value}")
    if phase_states.get("execute") == "not_started":
        reasons.append("execution_missing")
    if phase_states.get("test") == "not_started":
        reasons.append("validation_missing")
    if failed_validation_records:
        reasons.append("validation_failed")
    if failed_records:
        reasons.append("tool_failure")
    if error:
        reasons.append("agent_error")
    if failure_suggestions and not reasons:
        reasons.append("review_repair_suggestions")
    return reasons


def _next_actions(
    *,
    phase_states: dict[str, str],
    blocking_reasons: Sequence[str],
    failure_suggestions: Sequence[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if phase_states["execute"] == "not_started":
        actions.append("run_engineering_tools_before_claiming_completion")
    if phase_states["test"] == "not_started":
        actions.append("run_targeted_validation")
    if phase_states["test"] == "failed":
        actions.append("fix_validation_failure_and_rerun")
    for suggestion in failure_suggestions:
        action = suggestion.get("next_action")
        if isinstance(action, str) and action and action not in actions:
            actions.append(action)
    if blocking_reasons and not actions:
        actions.append("review_blocking_reasons")
    if not actions:
        actions.append("prepare_commit_or_handoff_report")
    return actions[:10]
