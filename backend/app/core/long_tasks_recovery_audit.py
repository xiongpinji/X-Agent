from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from backend.app.core.long_tasks_helpers import _context_string_list, _unique_strings
from backend.app.core.storage import dumps_json


def _repository_failure_route_execution_ledger_signal(
    route: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    route_ledger = (
        route.get("execution_ledger")
        if isinstance(route.get("execution_ledger"), dict)
        else {}
    )
    loop_summary = result.get("loop_summary") if isinstance(result.get("loop_summary"), dict) else {}
    runtime_ledger = (
        loop_summary.get("execution_ledger")
        if isinstance(loop_summary.get("execution_ledger"), dict)
        else {}
    )
    if not route_ledger and not runtime_ledger:
        return {}
    last_step_audit = (
        route_ledger.get("last_step_audit")
        if isinstance(route_ledger.get("last_step_audit"), dict)
        else route.get("last_step_audit")
        if isinstance(route.get("last_step_audit"), dict)
        else {}
    )
    latest_feedback = (
        route_ledger.get("latest_score_route_feedback")
        if isinstance(route_ledger.get("latest_score_route_feedback"), dict)
        else route.get("latest_score_route_feedback")
        if isinstance(route.get("latest_score_route_feedback"), dict)
        else {}
    )
    step_id = str(route_ledger.get("step_id") or last_step_audit.get("step_id") or "")
    tool = str(route_ledger.get("tool") or last_step_audit.get("tool") or "")
    validation_passed = last_step_audit.get("validation_passed")
    if validation_passed is None:
        validation_passed = latest_feedback.get("validation_passed")
    if validation_passed is None:
        validation_passed = loop_summary.get("validation_passed")
    result_status = str(
        last_step_audit.get("result_status")
        or latest_feedback.get("result_status")
        or route.get("last_result_status")
        or result.get("status")
        or loop_summary.get("status")
        or route_ledger.get("status")
        or ""
    )
    changed_files = _unique_strings(
        [
            *_context_string_list(route_ledger.get("changed_files")),
            *_context_string_list(last_step_audit.get("changed_files")),
            *_context_string_list(latest_feedback.get("changed_files")),
            *_context_string_list(result.get("changed_files")),
            *_context_string_list(loop_summary.get("changed_files")),
        ]
    )[:12]
    completed_observations = _unique_strings(
        [
            *_context_string_list(route_ledger.get("completed_observations")),
            *_context_string_list(last_step_audit.get("completed_observations")),
            *_context_string_list(runtime_ledger.get("completed_observations")),
        ]
    )[:12]
    failure_category = str(
        last_step_audit.get("failure_category")
        or latest_feedback.get("failure_category")
        or ""
    )
    observed_completion = bool(
        last_step_audit.get("observed_completion") is True
        or latest_feedback.get("observed_completion") is True
    )
    error = str(
        last_step_audit.get("error")
        or result.get("error")
        or loop_summary.get("error")
        or ""
    ).strip()
    next_tool_hint = str(last_step_audit.get("next_tool_hint") or "")
    action = "switch_repository_failure_route_tool"
    reason = str(last_step_audit.get("switch_reason") or "")
    requires_human_review = False
    priority = 108
    lowered_error = error.lower()
    if any(
        token in lowered_error
        for token in (
            "permission",
            "approval",
            "denied",
            "forbidden",
            "unauthorized",
            "requires_confirmation",
            "权限",
            "审批",
            "拒绝",
        )
    ):
        next_tool_hint = "human_review"
        action = "request_human_review"
        reason = "执行账本记录到权限或审批失败，停止自动切换并请求人工复核。"
        requires_human_review = True
        priority = 125
    elif tool == "engineering_read_file" and not observed_completion:
        next_tool_hint = next_tool_hint or "engineering_search"
        reason = reason or "执行账本显示读文件未完成，改用搜索补齐路径、符号和导入证据。"
        priority = 112
    elif (
        tool == "engineering_search"
        and not observed_completion
        and "run_targeted_validation" not in completed_observations
    ):
        next_tool_hint = next_tool_hint or "engineering_run_validation"
        reason = reason or "执行账本显示搜索没有形成有效证据，切到聚焦验证获取失败输出。"
        priority = 110
    elif tool == "engineering_run_validation" and validation_passed is False and not changed_files:
        next_tool_hint = next_tool_hint or "engineering_create_patch_approval"
        reason = reason or "执行账本显示验证已复现且尚无补丁变更，下一步生成最小补丁。"
        priority = 110
    elif tool == "engineering_create_patch_approval" and validation_passed is False and changed_files:
        next_tool_hint = next_tool_hint or "engineering_run_validation"
        action = "rerun_repository_failure_validation"
        reason = reason or "执行账本显示补丁已产生变更但验证仍失败，回到聚焦验证确认剩余失败。"
        priority = 114
    elif tool == "engineering_create_patch_approval" and validation_passed is None and changed_files:
        next_tool_hint = next_tool_hint or "engineering_run_validation"
        action = "rerun_repository_failure_validation"
        reason = reason or "执行账本显示补丁已产生变更但缺少验证证据，必须回到聚焦验证。"
        priority = 116
    elif failure_category == "patch_apply_failed":
        next_tool_hint = "human_review"
        action = "request_human_review"
        reason = reason or "执行账本显示补丁应用失败且缺少可信变更，转人工复核。"
        requires_human_review = True
        priority = 120
    if not next_tool_hint:
        return {}
    return {
        "kind": "repository_failure_route_execution_ledger_signal",
        "status": "active",
        "step_id": step_id,
        "tool": tool,
        "next_tool_hint": next_tool_hint,
        "action": action,
        "reason": reason,
        "requires_human_review": requires_human_review,
        "priority": priority,
        "failure_category": failure_category,
        "observed_completion": observed_completion,
        "result_status": result_status,
        "validation_passed": validation_passed,
        "changed_files": changed_files,
        "completed_observations": completed_observations,
        "error": error[:600],
        "ledger_fingerprint": str(route_ledger.get("fingerprint") or ""),
        "score_feedback_fingerprint": str(latest_feedback.get("fingerprint") or ""),
    }


def build_long_task_recovery_audit_state_machine(
    *,
    repository_failure_tool_route: dict[str, Any] | None = None,
    repository_failure_route_next_strategy: dict[str, Any] | None = None,
    tool_strategy_router_execution_result: dict[str, Any] | None = None,
    history_reuse_execution_driver: dict[str, Any] | None = None,
    task_history_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route = repository_failure_tool_route if isinstance(repository_failure_tool_route, dict) else {}
    strategy = (
        repository_failure_route_next_strategy
        if isinstance(repository_failure_route_next_strategy, dict)
        else {}
    )
    router_result = (
        tool_strategy_router_execution_result
        if isinstance(tool_strategy_router_execution_result, dict)
        else {}
    )
    history_driver = history_reuse_execution_driver if isinstance(history_reuse_execution_driver, dict) else {}
    history_index = task_history_index if isinstance(task_history_index, dict) else {}
    if (
        route.get("kind") != "long_task_repository_failure_tool_route"
        and strategy.get("kind") != "long_task_repository_failure_route_next_strategy"
        and router_result.get("kind") != "long_task_tool_strategy_router_execution_result"
    ):
        return {}

    last_step_audit = (
        strategy.get("last_step_audit")
        if isinstance(strategy.get("last_step_audit"), dict)
        else route.get("last_step_audit")
        if isinstance(route.get("last_step_audit"), dict)
        else {}
    )
    result_status = str(
        router_result.get("status")
        or strategy.get("result_status")
        or route.get("last_result_status")
        or route.get("status")
        or ""
    )
    validation_passed = strategy.get("validation_passed")
    if validation_passed is None:
        validation_passed = router_result.get("validation_passed")
    if validation_passed is None:
        validation_passed = route.get("last_validation_passed")
    route_result = {
        "status": result_status,
        "loop_summary": {
            "validation_passed": validation_passed,
            "changed_files": _context_string_list(
                router_result.get("changed_files") or route.get("last_changed_files")
            ),
        },
    }
    ledger_signal = _repository_failure_route_execution_ledger_signal(route, route_result) if route else {}
    if not last_step_audit and isinstance(ledger_signal, dict):
        last_step_audit = {
            "kind": "repository_failure_route_step_audit",
            "tool": str(ledger_signal.get("tool") or ""),
            "status": str(ledger_signal.get("status") or ""),
            "failure_category": str(ledger_signal.get("failure_category") or ""),
            "next_tool_hint": str(ledger_signal.get("next_tool_hint") or ""),
            "switch_reason": str(ledger_signal.get("reason") or ""),
            "validation_passed": ledger_signal.get("validation_passed"),
            "changed_files": _context_string_list(ledger_signal.get("changed_files")),
            "completed_observations": _context_string_list(ledger_signal.get("completed_observations")),
        }

    latest_feedback = (
        route.get("latest_score_route_feedback")
        if isinstance(route.get("latest_score_route_feedback"), dict)
        else route.get("execution_ledger", {}).get("latest_score_route_feedback")
        if isinstance(route.get("execution_ledger"), dict)
        and isinstance(route.get("execution_ledger", {}).get("latest_score_route_feedback"), dict)
        else {}
    )
    pending_steps = [
        step
        for step in (route.get("steps") if isinstance(route.get("steps"), list) else [])
        if isinstance(step, dict) and str(step.get("status") or "pending") in {"pending", "running", ""}
    ]
    pending_by_tool = {str(step.get("tool") or ""): step for step in pending_steps if step.get("tool")}
    changed_files = _unique_strings(
        [
            *_context_string_list(route.get("last_changed_files")),
            *_context_string_list(router_result.get("changed_files")),
            *_context_string_list(last_step_audit.get("changed_files")),
            *_context_string_list(latest_feedback.get("changed_files")),
            *_context_string_list(ledger_signal.get("changed_files")),
        ]
    )[:12]
    target_files = _unique_strings(
        [
            *_context_string_list(route.get("target_files")),
            *_context_string_list(route.get("score_selected_targets")),
            *_context_string_list(history_driver.get("preferred_files")),
            *_context_string_list(latest_feedback.get("score_target_updates")),
        ]
    )[:12]
    validation_commands = _unique_strings(
        [
            *_context_string_list(route.get("validation_commands")),
            *_context_string_list(route.get("score_selected_validation_commands")),
            *_context_string_list(history_driver.get("preferred_validation_commands")),
            *_context_string_list(latest_feedback.get("score_command_updates")),
            *_context_string_list(router_result.get("validation_commands")),
        ]
    )[:8]
    search_symbols = _unique_strings(
        [
            *_context_string_list(route.get("score_selected_search_symbols")),
            *_context_string_list(history_driver.get("preferred_search_symbols")),
            *_context_string_list(latest_feedback.get("score_symbol_updates")),
        ]
    )[:10]
    failure_category = str(
        last_step_audit.get("failure_category")
        or ledger_signal.get("failure_category")
        or ""
    )
    audit_tool = str(last_step_audit.get("tool") or ledger_signal.get("tool") or "")
    audit_stage = str(last_step_audit.get("stage") or "")
    audit_status = str(last_step_audit.get("status") or "")
    observed_completion = bool(
        last_step_audit.get("observed_completion") is True
        or ledger_signal.get("observed_completion") is True
    )
    strategy_tool = str(strategy.get("next_tool") or "")
    strategy_action = str(strategy.get("action") or "")
    strategy_status = str(strategy.get("status") or "")
    ledger_next_tool = str(ledger_signal.get("next_tool_hint") or "")
    audit_next_tool = str(last_step_audit.get("next_tool_hint") or "")
    current_state = "observing"
    selected_tool = ""
    selected_action = ""
    reason = ""
    priority = 82
    requires_human_review = False

    if (
        strategy_status == "blocked"
        or strategy.get("requires_human_review") is True
        or ledger_signal.get("requires_human_review") is True
        or strategy_tool == "human_review"
        or ledger_next_tool == "human_review"
        or audit_next_tool == "human_review"
    ):
        current_state = "human_review_required"
        selected_tool = "human_review"
        selected_action = "request_human_review"
        reason = str(
            strategy.get("reason")
            or ledger_signal.get("reason")
            or last_step_audit.get("switch_reason")
            or "恢复路线审计触发人工复核。"
        )
        priority = 100
        requires_human_review = True
    elif failure_category == "file_read_failed" or (
        audit_tool == "engineering_read_file" and audit_status == "failed" and not observed_completion
    ):
        current_state = "read_failed"
        selected_tool = "engineering_search"
        selected_action = "search_after_audited_read_failure"
        reason = "读文件审计失败，切换到搜索路径、符号和导入关系。"
        priority = 98
    elif failure_category == "search_failed" or (
        audit_tool == "engineering_search" and audit_status == "failed" and not observed_completion
    ):
        current_state = "search_failed"
        selected_tool = "engineering_run_validation" if validation_commands else "engineering_read_file"
        selected_action = (
            "run_validation_after_audited_search_failure"
            if selected_tool == "engineering_run_validation"
            else "read_files_after_audited_search_failure"
        )
        reason = "搜索审计没有形成有效证据，切换到聚焦验证或补读文件。"
        priority = 96
    elif failure_category == "validation_execution_failed":
        current_state = "validation_execution_failed"
        selected_tool = "engineering_search" if search_symbols or target_files else "engineering_read_file"
        selected_action = (
            "search_after_validation_execution_failure"
            if selected_tool == "engineering_search"
            else "read_files_after_validation_execution_failure"
        )
        reason = "验证命令执行未形成有效结果，回到搜索或读文件补齐环境和定位证据。"
        priority = 96
    elif failure_category == "validation_failed" or validation_passed is False and not changed_files:
        current_state = "validation_failed"
        selected_tool = "engineering_create_patch_approval"
        selected_action = "create_patch_after_audited_validation_failure"
        reason = "验证失败已被审计确认，下一步生成最小补丁。"
        priority = 99
    elif failure_category in {"patch_validation_failed", "patch_missing_validation_evidence"} or (
        changed_files and validation_passed is not True
    ):
        current_state = failure_category or "patch_needs_validation"
        selected_tool = "engineering_run_validation"
        selected_action = "run_validation_after_audited_patch"
        reason = "补丁已有变更但验证失败或缺少验证证据，先复跑聚焦验证。"
        priority = 99
    elif failure_category in {"patch_apply_failed", "repair_route_failed"}:
        current_state = failure_category
        selected_tool = "human_review"
        selected_action = "request_human_review"
        reason = "补丁或返修路线执行失败且缺少可信自动恢复证据，需要人工复核。"
        priority = 100
        requires_human_review = True
    elif strategy_status == "ready" and strategy_tool:
        current_state = "strategy_ready"
        selected_tool = strategy_tool
        selected_action = strategy_action or "execute_repository_failure_route_next_strategy"
        reason = str(strategy.get("reason") or "仓库恢复路线策略已给出下一步工具。")
        priority = 94
        requires_human_review = strategy.get("requires_human_review") is True or strategy_tool == "human_review"

    if selected_tool and selected_tool not in pending_by_tool and selected_tool != "human_review":
        if strategy_tool == selected_tool or ledger_next_tool == selected_tool or audit_next_tool == selected_tool:
            pass
        elif selected_tool in {"engineering_search", "engineering_read_file", "engineering_run_validation"}:
            pass
        else:
            selected_tool = ""
            selected_action = ""
            reason = ""
    if not selected_tool:
        return {}

    transition = {
        "state": current_state,
        "action": selected_action,
        "next_tool": selected_tool,
        "reason": reason,
        "priority": priority,
        "requires_human_review": requires_human_review,
        "source_failure_category": failure_category,
        "source_tool": audit_tool,
        "source_stage": audit_stage,
    }
    seed = {
        "route_id": route.get("route_id", ""),
        "strategy": strategy.get("fingerprint", ""),
        "router_result": router_result.get("fingerprint", ""),
        "ledger": ledger_signal.get("ledger_fingerprint", ""),
        "state": current_state,
        "tool": selected_tool,
        "files": [*target_files[:6], *changed_files[:6]],
        "commands": validation_commands[:4],
    }
    return {
        "kind": "long_task_recovery_audit_state_machine",
        "status": "blocked" if requires_human_review else "ready",
        "current_state": current_state,
        "selected_transition": transition,
        "selected_tool": selected_tool,
        "selected_action": selected_action,
        "requires_human_review": requires_human_review,
        "priority": priority,
        "reason": reason,
        "route_id": str(route.get("route_id") or strategy.get("route_id") or ""),
        "strategy_fingerprint": str(strategy.get("fingerprint") or ""),
        "ledger_signal": ledger_signal,
        "last_step_audit": last_step_audit,
        "latest_score_route_feedback": latest_feedback,
        "tool_strategy_router_execution_result": router_result,
        "history_driver_fingerprint": str(history_driver.get("fingerprint") or ""),
        "history_match_count": int(history_index.get("matched_count") or 0),
        "target_files": target_files,
        "changed_files": changed_files,
        "validation_commands": validation_commands,
        "search_symbols": search_symbols,
        "evidence": {
            "failure_category": failure_category,
            "audit_tool": audit_tool,
            "audit_stage": audit_stage,
            "audit_status": audit_status,
            "observed_completion": observed_completion,
            "validation_passed": validation_passed,
            "result_status": result_status,
            "pending_step_count": len(pending_steps),
        },
        "guardrails": [
            "recovery_audit_result_drives_next_tool_selection",
            "read_failure_switches_to_search",
            "validation_failure_switches_to_patch",
            "patch_without_validation_switches_to_validation",
            "human_review_preserved_for_permission_or_patch_failures",
            "state_machine_is_advisory_until_next_tool_revalidates_evidence",
        ],
        "fingerprint": hashlib.sha256(
            dumps_json(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16],
        "created_at": datetime.now(UTC).isoformat(),
    }
