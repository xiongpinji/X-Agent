from __future__ import annotations

from backend.app.core.long_tasks_recovery_audit import (
    build_long_task_recovery_audit_state_machine,
)


def _route_with_audit(
    *,
    tool: str,
    failure_category: str,
    status: str = "failed",
    observed_completion: bool = False,
    validation_passed: bool | None = None,
    changed_files: list[str] | None = None,
    error: str = "",
    next_tool_hint: str = "",
) -> dict[str, object]:
    audit = {
        "kind": "repository_failure_route_step_audit",
        "step_id": "step-1",
        "tool": tool,
        "stage": tool.replace("engineering_", ""),
        "status": status,
        "observed_completion": observed_completion,
        "failure_category": failure_category,
        "validation_passed": validation_passed,
        "changed_files": changed_files or [],
        "error": error,
        "next_tool_hint": next_tool_hint,
    }
    return {
        "kind": "long_task_repository_failure_tool_route",
        "route_id": "route-1",
        "status": status,
        "steps": [
            {"id": "search", "tool": "engineering_search", "status": "pending"},
            {
                "id": "validate",
                "tool": "engineering_run_validation",
                "status": "pending",
            },
            {
                "id": "patch",
                "tool": "engineering_create_patch_approval",
                "status": "pending",
            },
        ],
        "validation_commands": ["python -m pytest tests/test_orders.py -q"],
        "target_files": ["backend/app/orders.py"],
        "last_step_audit": audit,
        "execution_ledger": {
            "kind": "repository_failure_route_execution_ledger",
            "fingerprint": "ledger-fp",
            "step_id": "step-1",
            "tool": tool,
            "last_step_audit": audit,
        },
    }


def test_recovery_audit_routes_read_failure_to_search() -> None:
    state = build_long_task_recovery_audit_state_machine(
        repository_failure_tool_route=_route_with_audit(
            tool="engineering_read_file",
            failure_category="file_read_failed",
        ),
    )

    assert state["status"] == "ready"
    assert state["current_state"] == "read_failed"
    assert state["selected_tool"] == "engineering_search"
    assert state["selected_action"] == "search_after_audited_read_failure"
    assert state["ledger_signal"]["ledger_fingerprint"] == "ledger-fp"


def test_recovery_audit_routes_validation_failure_to_patch() -> None:
    state = build_long_task_recovery_audit_state_machine(
        repository_failure_tool_route=_route_with_audit(
            tool="engineering_run_validation",
            failure_category="validation_failed",
            validation_passed=False,
        ),
        tool_strategy_router_execution_result={
            "kind": "long_task_tool_strategy_router_execution_result",
            "status": "failed",
            "validation_passed": False,
            "fingerprint": "router-fp",
        },
    )

    assert state["current_state"] == "validation_failed"
    assert state["selected_tool"] == "engineering_create_patch_approval"
    assert state["selected_action"] == "create_patch_after_audited_validation_failure"
    assert state["evidence"]["validation_passed"] is False
    assert "validation_failure_switches_to_patch" in state["guardrails"]


def test_recovery_audit_routes_patch_without_validation_to_rerun_validation() -> None:
    state = build_long_task_recovery_audit_state_machine(
        repository_failure_tool_route=_route_with_audit(
            tool="engineering_create_patch_approval",
            failure_category="patch_missing_validation_evidence",
            changed_files=["backend/app/orders.py"],
        ),
        tool_strategy_router_execution_result={
            "kind": "long_task_tool_strategy_router_execution_result",
            "status": "patched",
            "changed_files": ["backend/app/orders.py"],
            "fingerprint": "router-fp",
        },
    )

    assert state["current_state"] == "patch_missing_validation_evidence"
    assert state["selected_tool"] == "engineering_run_validation"
    assert state["selected_action"] == "run_validation_after_audited_patch"
    assert state["changed_files"] == ["backend/app/orders.py"]
    assert "patch_without_validation_switches_to_validation" in state["guardrails"]


def test_recovery_audit_preserves_human_review_for_permission_failures() -> None:
    state = build_long_task_recovery_audit_state_machine(
        repository_failure_tool_route=_route_with_audit(
            tool="engineering_run_validation",
            failure_category="validation_execution_failed",
            error="permission denied by sandbox",
        ),
    )

    assert state["status"] == "blocked"
    assert state["current_state"] == "human_review_required"
    assert state["selected_tool"] == "human_review"
    assert state["requires_human_review"] is True
    assert state["ledger_signal"]["requires_human_review"] is True


def test_recovery_audit_uses_ready_strategy_when_no_failure_category() -> None:
    state = build_long_task_recovery_audit_state_machine(
        repository_failure_tool_route={
            "kind": "long_task_repository_failure_tool_route",
            "route_id": "route-2",
            "steps": [{"tool": "engineering_run_validation", "status": "pending"}],
        },
        repository_failure_route_next_strategy={
            "kind": "long_task_repository_failure_route_next_strategy",
            "status": "ready",
            "next_tool": "engineering_run_validation",
            "action": "execute_next_strategy",
            "reason": "策略已选择验证。",
            "fingerprint": "strategy-fp",
        },
        task_history_index={"matched_count": 3},
    )

    assert state["current_state"] == "strategy_ready"
    assert state["selected_tool"] == "engineering_run_validation"
    assert state["selected_action"] == "execute_next_strategy"
    assert state["strategy_fingerprint"] == "strategy-fp"
    assert state["history_match_count"] == 3
