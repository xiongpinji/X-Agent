"""Pure merge gate decisions for long-task parallel subagent flows."""

from __future__ import annotations

import hashlib
from typing import Any

from backend.app.core.storage import dumps_json


def build_validation_evidence_gate(
    *,
    status: str,
    validation_passed: object,
    changed_files: list[str] | None = None,
    validation_commands: list[str] | None = None,
    validation_evidence: list[object] | None = None,
    audit: dict[str, object] | None = None,
    merge_plan: dict[str, object] | None = None,
    source_matrix: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the final validation gate before merge delivery is allowed."""

    audit = audit or {}
    merge_plan = merge_plan or {}
    source_matrix = source_matrix or {}
    changed_files = _unique_strings(changed_files or [])
    commands = _unique_strings(validation_commands or [])
    normalized_evidence, raw_evidence_texts = _normalize_validation_evidence(validation_evidence or [])

    if validation_passed is True and commands:
        passed = _passed_commands(normalized_evidence)
        evidence_text = "\n".join(raw_evidence_texts)
        for command in commands:
            if command in passed:
                continue
            matched_text = next((text for text in raw_evidence_texts if command in text), "")
            normalized_evidence.append(
                {
                    "command": command,
                    "status": "passed",
                    "exit_code": 0,
                    "source": (
                        "parallel_merge_validation_evidence_text"
                        if matched_text
                        else "parallel_merge_validation_passed_flag"
                    ),
                    "output_excerpt": (matched_text or evidence_text or str(audit.get("validation_summary") or ""))[:500],
                }
            )
    elif validation_passed is True and not commands:
        normalized_evidence.append(
            {
                "command": "",
                "status": "passed",
                "exit_code": 0,
                "source": "parallel_merge_validation_passed_flag",
                "output_excerpt": str(audit.get("validation_summary") or "validation_passed=True")[:500],
            }
        )

    passed_commands = _passed_commands(normalized_evidence)
    missing_commands = [command for command in commands if command not in passed_commands]
    clean_status = str(status or "")
    if clean_status in {"failed", "blocked"} or validation_passed is False:
        gate_status = "failed"
        next_action = "rollback_parallel_subagent_merge"
        reason = "Final validation failed; rollback or repair is required."
    elif commands and missing_commands:
        gate_status = "missing_evidence"
        next_action = "collect_parallel_validation_evidence"
        reason = "Validation commands were declared, but passing evidence is missing."
    elif clean_status == "completed" and (validation_passed is True or normalized_evidence):
        gate_status = "passed"
        next_action = "deliver_parallel_subagent_merge"
        reason = "Final validation evidence satisfies the delivery gate."
    elif clean_status == "completed":
        gate_status = "missing_evidence"
        next_action = "collect_parallel_validation_evidence"
        reason = "Merge is completed, but final validation evidence is missing."
    else:
        gate_status = "pending"
        next_action = "continue_parallel_subagent_merge"
        reason = "Final validation has not completed."

    seed = {
        "status": gate_status,
        "audit": audit.get("fingerprint") or "",
        "plan": merge_plan.get("fingerprint") or "",
        "matrix": source_matrix.get("fingerprint") or "",
        "changed_files": changed_files,
        "validation_commands": commands,
        "missing": missing_commands,
        "validation_passed": validation_passed,
    }
    return {
        "kind": "long_task_parallel_merge_final_validation_evidence_gate",
        "status": gate_status,
        "next_action": next_action,
        "reason": reason,
        "fingerprint": hashlib.sha256(
            dumps_json(seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "validation_passed": validation_passed,
        "validation_commands": commands,
        "validation_command_count": len(commands),
        "validation_evidence": normalized_evidence[:20],
        "validation_evidence_count": len(normalized_evidence),
        "passed_validation_command_count": len(passed_commands),
        "missing_validation_evidence_commands": missing_commands[:12],
        "missing_validation_evidence_count": len(missing_commands),
        "failure_reason": (
            str(audit.get("failure_reason") or audit.get("error") or "parallel_merge_validation_failed")
            if gate_status == "failed"
            else ""
        ),
        "guardrails": [
            "final_validation_evidence_required_before_parallel_merge_delivery",
            "changed_files_must_be_bound_to_merge_audit",
            "validation_commands_must_have_passed_evidence_before_delivery",
            "failed_final_validation_routes_to_rollback_or_repair",
        ],
    }


def build_completion_report_merge_gate(final_validation_gate: dict[str, object]) -> dict[str, object]:
    """Convert final validation status into completion, report, and merge permissions."""

    validation_status = str(final_validation_gate.get("status") or "")
    failed_validation_blocks_completion = validation_status in {"failed", "missing_evidence"}
    passed_validation_allows_report_merge = validation_status == "passed"
    return {
        "kind": "long_task_completion_report_merge_gate",
        "validation_status": validation_status,
        "completion_allowed": passed_validation_allows_report_merge,
        "report_allowed": passed_validation_allows_report_merge,
        "merge_allowed": passed_validation_allows_report_merge,
        "failed_validation_blocks_completion": failed_validation_blocks_completion,
        "passed_validation_allows_report_merge": passed_validation_allows_report_merge,
        "next_action": (
            "write_report_or_merge"
            if passed_validation_allows_report_merge
            else "repair_failure_then_rerun_validation"
            if failed_validation_blocks_completion
            else "continue_parallel_subagent_merge"
        ),
    }


def decide_parent_acceptance_gate(
    *,
    matrix: dict[str, object] | None = None,
    audit: dict[str, object] | None = None,
    parent_package: dict[str, object] | None = None,
    merge_authorization: dict[str, object] | None = None,
    merge_result: dict[str, object] | None = None,
    revalidation: dict[str, object] | None = None,
    final_validation_gate: dict[str, object] | None = None,
    strict_patch: dict[str, object] | None = None,
) -> dict[str, object]:
    """Decide the parent acceptance layer before merge execution or delivery."""

    matrix = matrix or {}
    audit = audit or {}
    parent_package = parent_package or {}
    merge_authorization = merge_authorization or {}
    merge_result = merge_result or {}
    revalidation = revalidation or {}
    final_validation_gate = final_validation_gate or {}
    strict_patch = strict_patch or {}

    unit_summary = _dict(audit.get("unit_result_summary"))
    parent_acceptance = _dict(parent_package.get("parent_acceptance"))
    parent_decision = str(parent_acceptance.get("decision") or "")
    execution_status = str(audit.get("status") or matrix.get("execution_audit_status") or "")
    matrix_status = str(matrix.get("status") or "")
    merge_status = str(merge_result.get("status") or matrix.get("merge_execution_status") or "")
    revalidation_status = str(revalidation.get("status") or matrix.get("parent_revalidation_after_revision_status") or "")
    merge_authorized = matrix.get("merge_authorized") is True or merge_authorization.get("status") == "authorized"
    merge_ready = matrix.get("merge_ready") is True
    conflict_count = max(
        int(matrix.get("conflict_count") or 0),
        int(audit.get("conflict_count") or 0),
        int(parent_package.get("conflict_count") or 0),
        int(unit_summary.get("conflict_count") or 0),
    )
    blocked_task_ids = _unique_strings(matrix.get("blocked_task_ids") or [])
    unit_failed_count = int(unit_summary.get("failed_count") or matrix.get("unit_result_failed_count") or 0)
    unit_missing_evidence_count = int(
        unit_summary.get("missing_evidence_count") or matrix.get("unit_result_missing_evidence_count") or 0
    )
    unit_missing_result_count = int(unit_summary.get("missing_result_count") or matrix.get("unit_result_missing_count") or 0)
    final_status = str(final_validation_gate.get("status") or matrix.get("final_validation_gate_status") or "")
    final_next_action = str(final_validation_gate.get("next_action") or matrix.get("final_validation_gate_next_action") or "")
    final_missing_count = int(final_validation_gate.get("missing_validation_evidence_count") or 0)
    missing_validation_evidence = bool(unit_missing_evidence_count or final_status == "missing_evidence" or final_missing_count)
    strict_patch_blocked = strict_patch.get("blocked") is True

    if unit_failed_count:
        status = "unit_result_failed"
        next_action = "execute_subagent_revision_dispatch"
        reason = "Subagent unit results include failures."
    elif unit_missing_result_count:
        status = "unit_result_blocked"
        next_action = "execute_parallel_subagent_run"
        reason = "Subagent unit results are incomplete."
    elif missing_validation_evidence:
        status = "validation_evidence_blocked"
        next_action = "collect_parallel_validation_evidence"
        reason = "Validation evidence is missing before parent merge."
    elif final_status == "failed":
        status = "merge_blocked"
        next_action = final_next_action or "rollback_parallel_subagent_merge"
        reason = "Final merge validation failed."
    elif strict_patch_blocked:
        status, next_action, reason = _strict_patch_blocked_decision(strict_patch)
    elif execution_status in {"failed", "blocked"} or conflict_count or blocked_task_ids:
        status = "blocked"
        next_action = "resolve_parallel_subagent_conflicts"
        reason = "Parallel execution has failures, blockers, or conflicts."
    elif parent_decision == "revision_requested":
        status = "revision_requested"
        next_action = "execute_subagent_revision_dispatch"
        reason = "Parent acceptance requested revisions."
    elif merge_status in {"failed", "blocked"} or matrix_status in {"merge_failed", "merge_blocked"}:
        status = "merge_blocked"
        next_action = "repair_parallel_subagent_merge"
        reason = "Parallel merge is failed or blocked."
    elif merge_status == "completed" and final_status in {"", "passed"}:
        status = "merged"
        next_action = "deliver_parallel_subagent_merge"
        reason = "Parallel subagent results are merged and ready for delivery."
    elif merge_authorized and merge_ready:
        status = "ready_to_merge"
        next_action = "execute_parallel_subagent_merge_sequence"
        reason = "Parent acceptance and merge authorization are ready."
    elif matrix_status == "waiting_parent_acceptance" or (
        execution_status == "completed" and parent_package.get("requires_parent_acceptance") is True
    ):
        status = "waiting_parent_acceptance"
        next_action = "request_parallel_parent_acceptance"
        reason = "Parallel execution is complete and waiting for parent acceptance."
    elif execution_status:
        status = "needs_review"
        next_action = "review_parallel_subagent_gate"
        reason = "Parallel ledger state needs review."
    else:
        status = "waiting_execution"
        next_action = "execute_parallel_subagent_run"
        reason = "Parallel subagent plan is waiting for execution."

    ledger = {
        "matrix_fingerprint": str(matrix.get("fingerprint") or ""),
        "execution_audit_fingerprint": str(audit.get("result_matrix_fingerprint") or audit.get("matrix_fingerprint") or ""),
        "merge_authorization_id": str(merge_authorization.get("id") or ""),
        "parent_acceptance_id": str(parent_acceptance.get("id") or matrix.get("parent_acceptance_id") or ""),
        "merge_execution_audit_fingerprint": str(merge_result.get("merge_execution_audit_fingerprint") or ""),
        "conflict_count": conflict_count,
        "blocked_task_ids": blocked_task_ids,
        "final_validation_evidence_gate_status": final_status,
        "unit_result_failed_count": unit_failed_count,
        "unit_result_missing_evidence_count": unit_missing_evidence_count,
        "unit_result_missing_count": unit_missing_result_count,
        "revalidation_status": revalidation_status,
    }
    return {
        "kind": "long_task_parallel_parent_acceptance_gate_decision",
        "status": status,
        "next_action": next_action,
        "reason": reason,
        "requires_parent_acceptance": parent_package.get("requires_parent_acceptance") is True,
        "parent_acceptance_decision": parent_decision,
        "merge_authorized": merge_authorized,
        "merge_ready": merge_ready,
        "execution_status": execution_status,
        "matrix_status": matrix_status,
        "merge_status": merge_status,
        "conflict_count": conflict_count,
        "ledger": ledger,
        "summary": f"Parallel parent acceptance gate: {status}; next action {next_action}.",
    }


def build_merge_authorization(
    *,
    parent_decision: str,
    phase_id: str,
    phase_title: str,
    parent_acceptance_id: str,
    matrix: dict[str, object],
    audit: dict[str, object] | None = None,
    parent_gate: dict[str, object] | None = None,
    merge_plan: dict[str, object] | None = None,
    authorized_at: str = "",
    authorization_id: str = "",
) -> dict[str, object]:
    """Authorize parallel merge execution only after parent acceptance passes."""

    audit = audit or {}
    parent_gate = parent_gate or {}
    merge_plan = merge_plan or {}
    if parent_decision != "accepted":
        return {
            "kind": "long_task_parallel_subagent_merge_authorization",
            "status": "blocked",
            "phase_id": phase_id,
            "phase_title": phase_title,
            "parent_acceptance_id": parent_acceptance_id,
            "next_action": "request_parallel_parent_acceptance",
            "reason": "Parent acceptance has not passed.",
        }
    if parent_gate.get("status") in {"blocked", "validation_evidence_blocked", "strict_patch_plan_blocked", "merge_blocked"}:
        return {
            "kind": "long_task_parallel_subagent_merge_authorization",
            "status": "blocked",
            "phase_id": phase_id,
            "phase_title": phase_title,
            "parent_acceptance_id": parent_acceptance_id,
            "parent_acceptance_gate_fingerprint": str(parent_gate.get("fingerprint") or ""),
            "next_action": str(parent_gate.get("next_action") or "review_parallel_subagent_gate"),
            "reason": "Parent gate is still blocked.",
        }
    return {
        "id": authorization_id,
        "kind": "long_task_parallel_subagent_merge_authorization",
        "status": "authorized",
        "phase_id": phase_id,
        "phase_title": phase_title,
        "parent_acceptance_id": parent_acceptance_id,
        "matrix_fingerprint": str(matrix.get("fingerprint") or ""),
        "parent_acceptance_gate_fingerprint": str(parent_gate.get("fingerprint") or ""),
        "audit_status": str(audit.get("status") or ""),
        "next_action": "execute_parallel_subagent_merge_sequence",
        "authorized_at": authorized_at,
        "merge_plan_fingerprint": str(merge_plan.get("fingerprint") or ""),
        "merge_step_count": int(merge_plan.get("merge_step_count") or 0),
        "merge_plan_status": str(merge_plan.get("status") or ""),
        "summary": "Parent acceptance passed; merge execution is authorized.",
    }


def _normalize_validation_evidence(values: list[object]) -> tuple[list[dict[str, object]], list[str]]:
    normalized: list[dict[str, object]] = []
    raw_texts: list[str] = []
    for item in values:
        if isinstance(item, dict):
            command = str(item.get("command") or item.get("cmd") or "").strip()
            evidence_status = str(item.get("status") or "").strip().lower()
            normalized.append(
                {
                    "command": command,
                    "status": evidence_status or "reported",
                    "exit_code": item.get("exit_code"),
                    "source": str(item.get("source") or "parallel_merge_validation_evidence"),
                    "output_excerpt": str(item.get("output_excerpt") or item.get("output") or "")[:500],
                }
            )
            continue
        text = str(item).strip()
        if not text:
            continue
        raw_texts.append(text)
        normalized.append(
            {
                "command": "",
                "status": "reported",
                "exit_code": None,
                "source": "parallel_merge_validation_evidence_text",
                "output_excerpt": text[:500],
            }
        )
    return normalized, raw_texts


def _passed_commands(evidence: list[dict[str, object]]) -> set[str]:
    return {
        str(item.get("command") or "")
        for item in evidence
        if str(item.get("command") or "") and (item.get("status") == "passed" or item.get("exit_code") == 0)
    }


def _strict_patch_blocked_decision(strict_patch: dict[str, object]) -> tuple[str, str, str]:
    status = "strict_patch_plan_blocked"
    if strict_patch.get("requires_human_review") is True or strict_patch.get("action") == "rollback_or_manual_review":
        return status, "rollback_or_manual_review", "Strict patch plan requires rollback or human review."
    if strict_patch.get("missing_batch_validation_gates"):
        return status, "run_batch_validation_gate", "Strict patch plan is missing batch validation gates."
    return status, "collect_strict_patch_evidence", "Strict patch plan is missing evidence."


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items: list[object] = [value]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _unique_strings(values: object) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _string_list(values):
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
