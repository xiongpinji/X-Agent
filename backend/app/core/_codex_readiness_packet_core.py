from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

from ._codex_readiness_packet_specs import SPECS


FAILED_STATUSES = {
    "blocked",
    "conflicted",
    "denied",
    "error",
    "expired",
    "failed",
    "failure",
    "invalid",
    "lost",
    "missing",
    "orphaned",
    "rejected",
    "timed_out",
    "timed-out",
    "unreadable",
    "unreproducible",
    "stale_preimage",
    "stale",
    "outdated",
    "untriaged",
    "mismatched",
    "quota_exceeded",
    "diverged",
    "exposed",
    "stalled",
    "unsafe",
    "policy_violation",
    "exhausted",
    "disabled",
    "not_visible",
    "dry_run_failed",
    "regression_detected",
}
NAME_FIELDS = {
    "approval_policy",
    "approval_profile",
    "component_type",
    "destructive_command_policy",
    "filesystem_scope",
    "gate_status",
    "hook_policy",
    "license_status",
    "network_scope",
    "operator_prompt_policy",
    "patch_policy",
    "provider",
    "queue_state",
    "review_status",
    "risk_level",
    "sandbox_policy",
    "sandbox_profile",
    "scope",
    "shell_policy",
    "source_type",
    "state",
    "status",
    "task_type",
}
CONTROL_FIELDS = NAME_FIELDS | {"dry_run", "enabled", "name", "token_budget"}


@dataclass(frozen=True)
class ReadinessItem:
    data: dict[str, Any]
    missing_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    readiness_state: str
    finding_codes: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()

    def __getattr__(self, name: str) -> Any:
        if name in self.data:
            value = self.data[name]
            return tuple(value) if isinstance(value, list) else value
        raise AttributeError(name)

    def as_packet_item(self) -> dict[str, Any]:
        item = dict(self.data)
        item["missing_refs"] = list(self.missing_refs)
        item["blockers"] = list(self.blockers)
        item["warnings"] = list(self.warnings)
        item["readiness_state"] = self.readiness_state
        return item


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def normalize_name(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower().replace("-", "_")
    return value


def present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def as_mapping(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        return dict(item)
    if is_dataclass(item):
        return asdict(item)
    values: dict[str, Any] = {}
    for name in dir(item):
        if name.startswith("_"):
            continue
        try:
            value = getattr(item, name)
        except Exception:
            continue
        if not callable(value):
            values[name] = value
    return values


def normalize_data(item: Mapping[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in item.items():
        data[key] = normalize_name(value) if key in NAME_FIELDS else value
    return data


def spec(domain: str) -> dict[str, Any]:
    return SPECS[domain]


def code_containing(domain: str, marker: str, fallback: str) -> str:
    for code in spec(domain).get("codes", []):
        if marker in code:
            return code
    return fallback


def packet_missing_code(domain: str) -> str:
    return code_containing(
        domain, "packet_missing_evidence", f"codex_{domain}_packet_missing_evidence"
    )


def item_missing_code(domain: str) -> str:
    special = {
        "permission_sandbox": "codex_permission_sandbox_missing_evidence",
        "review_comment": "codex_review_comment_missing_evidence",
        "tool_runtime": "codex_tool_runtime_missing_evidence",
    }
    if domain in special:
        return special[domain]
    for code in spec(domain).get("codes", []):
        if "missing_evidence" in code and "packet_missing_evidence" not in code:
            return code
    return packet_missing_code(domain)


def status_code(domain: str) -> str:
    special = {
        "background_task": "codex_background_task_terminal_failure",
        "ci_gate": "codex_ci_gate_check_failed",
        "eval_repair": "codex_eval_repair_state_blocked",
        "pr_delivery": "codex_pr_delivery_ci_failed",
        "review_comment": "codex_review_comment_response_blocked",
        "worktree_git_state": "codex_worktree_git_state_failed",
    }
    if domain in special:
        return special[domain]
    for code in spec(domain).get("codes", []):
        if "status_failed" in code or code.endswith("_failed"):
            return code
    return f"codex_{domain}_status_failed"


def live_code(domain: str) -> str:
    special = {
        "human_approval_escalation": "codex_human_approval_live_dispatch_blocked",
        "observability_trace": "codex_observability_live_export_blocked",
        "workspace_diff": "codex_workspace_diff_live_mutation_blocked",
        "worktree_git_state": "codex_worktree_git_state_live_operation_blocked",
    }
    if domain in special:
        return special[domain]
    for code in spec(domain).get("codes", []):
        if "live" in code and code.endswith("blocked"):
            return code
    return f"codex_{domain}_live_operation_blocked"


def live_blocker(domain: str) -> str:
    special = {
        "collaboration_subagent": "live_collaboration_subagent_execution_attempted",
        "conversation_state_transition_audit": "live_conversation_state_transition_operation_attempted",
        "code_review_findings": "live_code_review_output_attempted",
        "enterprise_usage_log": "live_admin_export_or_mutation_attempted",
        "external_source_freshness": "live_external_source_operation_attempted",
        "file_edit_session": "live_file_edit_mutation_attempted",
        "gap_matrix_traceability": "live_codex_gap_matrix_traceability_operation_attempted",
        "human_approval_escalation": "live_human_approval_dispatch_attempted",
        "local_runtime_dependency": "live_runtime_dependency_operation_attempted",
        "mcp_tool_contract": "live_mcp_tool_mutation_attempted",
        "model_router": "live_model_call_or_router_mutation_attempted",
        "multi_agent_delegation_receipt": "live_multi_agent_delegation_operation_attempted",
        "multimodal_browser_desktop": "live_browser_desktop_execution_attempted",
        "observability_trace": "live_export_or_mutation_attempted",
        "open_source_candidate_evaluation": "live_open_source_candidate_operation_attempted",
        "output_contract": "live_output_operation_attempted",
        "owner_visibility_status": "live_owner_visibility_operation_attempted",
        "patch_apply": "live_patch_apply_mutation_attempted",
        "permission_escalation_audit": "live_permission_escalation_operation_attempted",
        "planning_goal": "live_planning_goal_mutation_attempted",
        "repo_worktree_drift_reconciliation": "live_repo_worktree_reconciliation_operation_attempted",
        "result_quality_acceptance": "live_result_quality_operation_attempted",
        "search_context": "live_search_context_execution_attempted",
        "secrets_redaction": "live_secret_redaction_operation_attempted",
        "session_thread": "live_session_mutation_attempted",
        "task_intake_clarification": "live_task_intake_operation_attempted",
        "terminal_command": "live_command_execution_attempted",
        "tool_result_provenance_receipt": "live_tool_result_operation_attempted",
        "workspace_diff": "live_workspace_mutation_attempted",
        "worktree_git_state": "live_git_or_worktree_operation_attempted",
    }
    if "followup_closure" in domain:
        return "live_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_operation_attempted"
    if "followup_notification" in domain:
        return "live_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_operation_attempted"
    return special.get(domain, f"live_{domain}_operation_attempted")


def item_ref(domain: str, item: ReadinessItem) -> str:
    field = spec(domain).get("item_id_field") or "name"
    return str(item.data.get(field) or item.data.get("name") or "unknown")


def finding(code: str, domain: str, item: ReadinessItem | None = None) -> dict[str, Any]:
    result = {"code": code}
    if item is not None:
        result["item_ref"] = item_ref(domain, item)
    return result


def failure_status(data: Mapping[str, Any]) -> bool:
    return any(
        normalize_name(data.get(key)) in FAILED_STATUSES
        for key in ("status", "state", "gate_status", "review_status", "response_status")
    )


def live_attempted(data: Mapping[str, Any]) -> bool:
    return any(
        value is True
        and (
            key.endswith("_attempted")
            or key.endswith("_dispatched")
            or "mutation" in key
            or "live" in key
        )
        for key, value in data.items()
    )


def base_missing(domain: str, data: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in spec(domain).get("required_fields", []):
        if field in CONTROL_FIELDS:
            continue
        if domain == "local_runtime_dependency" and field in {
            "python_runtime_refs",
            "node_runtime_refs",
            "version_mismatch_refs",
        }:
            continue
        if "followup_closure" in domain and field == "unresolved_blocker_refs":
            continue
        if domain == "output_contract" and field == "failure_disclosure_refs" and not failure_status(data):
            continue
        if domain == "background_task" and field == "resumable":
            if not present(data.get(field)):
                missing.append("resumability_ref")
            continue
        if domain == "background_task" and field == "diff_refs":
            if not present(data.get("diff_refs")) and not present(data.get("pr_refs")):
                missing.append("diff_or_pr_refs")
            continue
        if not present(data.get(field)):
            missing.append(field)
    if domain == "local_runtime_dependency" and not (
        present(data.get("python_runtime_refs")) or present(data.get("node_runtime_refs"))
    ):
        missing.append("runtime_version_refs")
    return missing


def add_conditional_rules(
    domain: str,
    data: Mapping[str, Any],
    missing: list[str],
    blockers: list[str],
    warnings: list[str],
    finding_codes: list[str],
    warning_codes: list[str],
) -> None:
    # These mappings describe payload states only; this layer must not execute
    # tools, mutate files, or promote detached evidence to runtime capability.
    status = normalize_name(data.get("status"))
    state = normalize_name(data.get("state"))

    status_blockers = {
        "model_router": "model_route_status_failed",
        "multi_agent_delegation_receipt": "multi_agent_delegation_status_failed",
    }

    denied_is_review = domain in {"human_approval_escalation", "permission_escalation_audit"} and status in {
        "denied",
        "rejected",
    }
    if failure_status(data) and not denied_is_review:
        code = status_code(domain)
        if "followup_closure" in domain or "followup_notification" in domain:
            blocker_code = code
        else:
            blocker_code = status_blockers.get(domain, code.removeprefix("codex_"))
        blockers.append(blocker_code)
        finding_codes.append(code)

    if live_attempted(data):
        blockers.append(live_blocker(domain))
        if domain != "secrets_redaction" or data.get("raw_secret_payload_present") is not True:
            finding_codes.append(live_code(domain))

    if data.get("enabled") is False:
        blockers.append(f"{domain}_disabled")
        finding_codes.append(status_code(domain))

    if domain == "artifact_evidence_index":
        if data.get("integrity_claimed") is True or data.get("checksum_claimed") is True:
            if not present(data.get("integrity_refs")):
                missing.append("integrity_refs")
        if failure_status(data):
            missing.extend(["handoff_refs", "failure_handoff_refs"])

    if domain == "background_task" and normalize_name(data.get("queue_state")) == "orphaned":
        blockers.append("queue_state_not_recoverable")
        finding_codes.append(status_code(domain))
    if domain == "background_task" and normalize_name(data.get("task_type")) == "cloud" and not present(
        data.get("remote_execution_ref")
    ):
        missing.append("remote_execution_ref")

    if domain == "ci_gate":
        check_states = {normalize_name(value) for value in data.get("check_states", [])}
        if check_states & {"failed", "failure", "cancelled", "error"}:
            missing.extend(["failure_summaries", "retry_or_rerun_refs"])
            blockers.append("ci_check_state_failed")
            finding_codes.append("codex_ci_gate_check_failed")
        if normalize_name(data.get("gate_status")) == "running" or check_states & {
            "pending",
            "running",
        }:
            warnings.extend(["ci_gate_still_running", "ci_check_state_needs_review"])

    if domain == "environment_repro":
        if failure_status(data) and not present(data.get("failure_reproduction_refs")):
            missing.append("failure_reproduction_refs")
        if live_attempted(data):
            blockers.append("live_environment_mutation_attempted")

    if domain == "enterprise_usage_log" and failure_status(data):
        if not present(data.get("incident_escalation_refs")):
            missing.append("incident_escalation_refs")

    if domain == "file_edit_session":
        if normalize_name(data.get("status")) in {"conflicted", "stale_preimage"}:
            if not present(data.get("conflict_refs")):
                missing.append("conflict_refs")
            blockers.append("file_edit_session_status_failed")
            finding_codes.append("codex_file_edit_session_status_failed")
        if live_attempted(data):
            blockers.append("live_file_edit_mutation_attempted")

    if domain == "conversation_state_transition_audit":
        if status in {"continued", "transitioned"} and not present(data.get("resume_refs")):
            missing.append("resume_refs")
        if status in {"compacting", "stale"}:
            if not present(data.get("compaction_refs")):
                missing.append("compaction_refs")
            warnings.append("conversation_state_transition_still_open")

    if domain == "cross_thread_handoff_digest":
        if status in {"accepted", "acknowledged", "read"} and not present(
            data.get("read_receipt_refs")
        ):
            missing.append("read_receipt_refs")
        if data.get("stale_handoff_detected") is True:
            warning_codes.append("codex_cross_thread_handoff_digest_stale")

    if domain == "eval_repair":
        confidence = data.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < 0.8:
            warnings.append("confidence_below_threshold")
        if status in {"open", "running", "needs_repair"} or state in {"open", "running", "needs_repair"} or data.get("loop_open") is True:
            warnings.append("eval_repair_loop_open")
        if state == "regression_detected" or data.get("regression_detected") is True or data.get("regression") is True:
            if not present(data.get("rollback_refs")):
                missing.append("rollback_refs")
            blockers.append("eval_repair_regression_detected")
            finding_codes.append(status_code(domain))

    if domain == "gap_matrix_traceability" and data.get("residual_gap_detected") is True:
        if not present(data.get("residual_gap_refs")):
            missing.append("residual_gap_refs")
        warning_codes.append("codex_gap_matrix_traceability_residual_gap")
    if domain == "gap_matrix_traceability" and (
        status in {"unmapped", "regressed"} or data.get("regression_detected") is True
    ):
        blockers.append("codex_gap_matrix_traceability_status_failed")
        finding_codes.append(status_code(domain))

    if domain == "human_approval_escalation":
        if normalize_name(data.get("risk_level")) in {"high", "critical"}:
            for ref in ("escalation_refs", "decision_receipt_refs"):
                if not present(data.get(ref)):
                    missing.append(ref)
        if status in {"denied", "rejected"}:
            warnings.append("human_approval_denied")
            if not present(data.get("denial_refs")):
                missing.append("denial_refs")

    if domain == "interruption_recovery" and data.get("recovery_failed") is True:
        blockers.append("interruption_recovery_failed")
        finding_codes.append(status_code(domain))

    if domain == "local_runtime_dependency":
        if status == "mismatched" and not present(data.get("version_mismatch_refs")):
            missing.append("version_mismatch_refs")
        if data.get("version_mismatch_detected") is True or data.get("version_mismatch") is True:
            if not present(data.get("version_mismatch_refs")):
                missing.append("version_mismatch_refs")
            blockers.append("local_runtime_dependency_version_mismatch_detected")
            finding_codes.append("codex_local_runtime_dependency_version_mismatch")

    if domain == "mcp_tool_contract" and failure_status(data):
        if not present(data.get("failure_taxonomy_refs")):
            missing.append("failure_taxonomy_refs")

    if domain == "multi_agent_delegation_receipt" and status in {"open", "running", "pending"}:
        warning_codes.append("codex_multi_agent_delegation_receipt_still_open")
        warnings.append("multi_agent_delegation_receipt_still_open")

    if domain == "long_running_task_supervision":
        if data.get("heartbeat_stale") is True or data.get("heartbeat_stale_detected") is True:
            blockers.append("long_running_task_heartbeat_stale")
            finding_codes.append(status_code(domain))

    if domain == "open_source_candidate_evaluation":
        if normalize_name(data.get("license_status")) in {"blocked", "incompatible"} or data.get("license_incompatible") is True:
            blockers.append("open_source_candidate_license_incompatible")
            finding_codes.append("codex_open_source_candidate_evaluation_license_blocked")
        if data.get("security_risk_detected") is True:
            blockers.append("open_source_candidate_security_risk_detected")
        if data.get("maintenance_risk_detected") is True or data.get("unmaintained_detected") is True:
            warning_codes.append("codex_open_source_candidate_evaluation_maintenance_risk")

    if domain == "pr_delivery":
        if data.get("dry_run") is False:
            blockers.append("non_dry_run_delivery_requires_mainline_execution")
            finding_codes.append("codex_pr_delivery_non_dry_run_blocked")
        if {normalize_name(value) for value in data.get("ci_states", [])} & {
            "cancelled",
            "error",
            "failed",
            "failure",
        }:
            blockers.append("pr_delivery_ci_failed")
            finding_codes.append("codex_pr_delivery_ci_failed")
        high_risk = {"destructive", "privacy", "security"}
        if high_risk & {normalize_name(value) for value in data.get("risk_labels", [])}:
            if not present(data.get("reviewer_handoff_refs")):
                missing.append("reviewer_handoff_refs")
                warnings.append("pr_delivery_lacks_reviewer_handoff")

    if domain == "review_comment":
        response_status = normalize_name(data.get("response_status"))
        if status in {"open", "unresolved", "changes_requested"} or response_status in {
            "open",
            "unresolved",
            "requested_changes",
            "changes_requested",
        }:
            warnings.append("review_feedback_open")
            for ref in ("owner_assignment_refs", "fix_validation_refs", "reviewer_handoff_refs"):
                if not present(data.get(ref)):
                    missing.append(ref)
        if data.get("response_blocked") is True or response_status in FAILED_STATUSES:
            blockers.append("review_comment_response_blocked")
            finding_codes.append("codex_review_comment_response_blocked")

    if domain == "result_quality_acceptance" and data.get("regression_detected") is True:
        blockers.append("result_quality_regression_detected")
        finding_codes.append("codex_result_quality_acceptance_status_failed")

    if domain == "session_budget_guard":
        if status == "exhausted":
            if not present(data.get("interruption_refs")):
                missing.append("interruption_refs")
            if not present(data.get("cancellation_policy_refs")):
                missing.append("cancellation_policy_refs")
        if data.get("over_budget_detected") is True or data.get("budget_exhausted") is True:
            blockers.append("session_budget_exhausted")
            finding_codes.append("codex_session_budget_guard_exhausted")

    if domain == "task_progress_event_timeline" and status in {"open", "running"}:
        warning_codes.append("codex_task_progress_event_timeline_still_open")
        warnings.append("task_progress_event_timeline_still_open")

    if domain == "owner_visibility_status" and status in {"not_visible", "blocked", "missing"}:
        if not present(data.get("notification_refs")):
            missing.append("notification_refs")
        if not present(data.get("owner_decision_refs")):
            missing.append("owner_decision_refs")

    if domain == "patch_apply" and failure_status(data):
        if not present(data.get("conflict_refs")):
            missing.append("conflict_refs")

    if domain == "permission_escalation_audit" and status in {"denied", "rejected"}:
        warnings.append("permission_escalation_denied")

    if domain == "thread_resume_compaction" and failure_status(data):
        if not present(data.get("failure_handoff_refs")):
            missing.append("failure_handoff_refs")

    if domain == "tool_result_provenance_receipt":
        receipt_status = normalize_name(data.get("receipt_status"))
        if status in {"open", "running", "pending", "capturing"} or receipt_status in {"open", "running", "pending", "capturing"}:
            warning_codes.append("codex_tool_result_provenance_receipt_still_open")
            warnings.append("tool_result_provenance_receipt_still_open")

    if "followup_closure" in domain:
        if data.get("owner_signoff_review_required") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_owner_signoff_review_required"
            )
        if data.get("owner_signoff_needs_review") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_owner_signoff_review_required"
            )
        if data.get("unresolved_blockers_detected") is True and not present(data.get("unresolved_blocker_refs")):
            missing.append("unresolved_blocker_refs")
        if status in {"open", "pending", "running", "needs_review"}:
            warnings.append(
                "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_still_open"
            )

    if "followup_notification" in domain:
        if data.get("recipient_review_required") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_recipient_review_required"
            )
        if data.get("recipient_needs_review") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_recipient_review_required"
            )
        if data.get("suppression_review_required") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_suppression_review_required"
            )
        if data.get("suppression_conflict_detected") is True:
            warning_codes.append(
                "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_suppression_review_required"
            )
        if status in {"open", "pending", "running", "needs_review"}:
            warnings.append(
                "codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_still_open"
            )

    if domain == "repo_worktree_drift_reconciliation":
        if status in {"conflicted", "dirty", "diverged"}:
            if not present(data.get("conflict_refs")):
                missing.append("conflict_refs")
            if not present(data.get("preservation_refs")):
                missing.append("preservation_refs")
        if status in {"checking", "running", "open"}:
            warning_codes.append("codex_repo_worktree_drift_still_open")
            warnings.append("repo_worktree_drift_still_open")

    if domain == "secrets_redaction":
        if data.get("raw_secret_payload_present") is True:
            blockers.append("raw_secret_payload_present")
            finding_codes.append("codex_secrets_redaction_raw_secret_blocked")
        if status == "exposed" or normalize_name(data.get("exposure_level")) in {"high", "critical"}:
            for ref in ("exposure_refs", "owner_escalation_refs"):
                if not present(data.get(ref)):
                    missing.append(ref)

    if domain == "model_router" and normalize_name(data.get("reasoning_profile")) in {"", "unknown"}:
        missing.append("reasoning_profile")

    if domain == "tool_result_provenance_receipt" and status in {"open", "running", "pending"}:
        warning_codes.append("codex_tool_result_provenance_receipt_still_open")
        warnings.append("tool_result_provenance_receipt_still_open")

    if domain == "workspace_diff":
        if status == "conflicted" and not present(data.get("conflict_refs")):
            missing.append("conflict_refs")

    if domain == "worktree_git_state":
        if status in {"conflicted", "dirty"} and not present(data.get("conflict_refs")):
            missing.append("conflict_refs")
        if status in {"dirty", "recorded"} or state in {"dirty", "unstaged"}:
            if not present(data.get("user_change_preservation_refs")):
                missing.append("user_change_preservation_refs")


def summarize_readiness_item(domain: str, item: Any) -> ReadinessItem:
    if domain == "memory_context":
        return summarize_memory_context_source(item)
    if domain == "permission_sandbox":
        return summarize_permission_sandbox_policy(item)
    if domain == "tool_runtime":
        return summarize_tool_runtime_component(item)

    data = normalize_data(as_mapping(item))
    missing = base_missing(domain, data)
    blockers: list[str] = []
    warnings: list[str] = []
    finding_codes: list[str] = []
    warning_codes: list[str] = []
    add_conditional_rules(domain, data, missing, blockers, warnings, finding_codes, warning_codes)
    missing = dedupe(missing)
    blockers = dedupe(blockers)
    warnings = dedupe(warnings)
    finding_codes = dedupe(finding_codes)
    warning_codes = dedupe(warning_codes)
    state = "blocked" if blockers else "needs_review" if missing or warnings or warning_codes else "ready"
    return ReadinessItem(
        data=data,
        missing_refs=tuple(missing),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        readiness_state=state,
        finding_codes=tuple(finding_codes),
        warning_codes=tuple(warning_codes),
    )


def packet_missing_refs(domain: str, payload: Mapping[str, Any]) -> list[str]:
    keys = spec(domain).get("packet_policy_keys", [])
    refs = spec(domain).get("packet_missing_refs", [])
    missing: list[str] = []
    for index, ref in enumerate(refs):
        key = keys[index] if index < len(keys) else ref
        if not present(payload.get(key)):
            missing.append(ref)
    return missing


def collection(domain: str, payload: Mapping[str, Any]) -> list[Any]:
    key = spec(domain).get("collection_key")
    value = payload.get(key) if key else None
    if isinstance(value, list):
        return list(value)
    if domain == "environment_repro" and isinstance(payload.get("repros"), list):
        return list(payload["repros"])
    for alias in spec(domain).get("aliases", []):
        alias_value = payload.get(alias)
        if isinstance(alias_value, list):
            return list(alias_value)
    return []


def summary(domain: str, items: list[ReadinessItem]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in spec(domain).get("summary_keys", []):
        if key == "by_component_type":
            result[key] = dict(Counter(str(item.data.get("component_type", "unknown")) for item in items))
        elif key == "component_count":
            result[key] = len(items)
        elif key == "ready_count":
            result[key] = sum(item.readiness_state == "ready" for item in items)
        elif key == "needs_review_count":
            result[key] = sum(item.readiness_state == "needs_review" for item in items)
        elif key == "missing_ref_count":
            result[key] = sum(len(item.missing_refs) for item in items)
        elif key == "total_token_budget":
            result[key] = sum(int(item.data.get("token_budget") or 0) for item in items)
        elif key == "remote_task_count":
            result[key] = sum(
                bool(item.data.get("remote_execution_ref"))
                or item.data.get("task_type") in {"cloud", "remote"}
                for item in items
            )
        elif key == "high_confidence_count":
            result[key] = sum(float(item.data.get("confidence") or 0) >= 0.8 for item in items)
        elif key.endswith("_ref_count"):
            ref_key = key[: -len("_count")] + "s"
            tokens = [token for token in ref_key.removesuffix("s").split("_") if token]
            total = 0
            for item in items:
                direct = item.data.get(ref_key)
                if isinstance(direct, (list, tuple, set)):
                    total += len(direct)
                    continue
                for data_key, value in item.data.items():
                    if not data_key.endswith("_refs"):
                        continue
                    if all(token in data_key for token in tokens):
                        total += len(value or [])
                        break
            result[key] = total
        else:
            result[key] = len(items)
    return result


def ready_actions(domain: str) -> list[str]:
    special = {
        "gap_matrix_traceability": ["share_codex_gap_matrix_traceability_readiness_with_mainline"],
        "tool_runtime": ["share_codex_tool_runtime_readiness_with_mainline"],
    }
    if domain in special:
        return special[domain]
    for action in spec(domain).get("actions", []):
        if action.startswith("share_"):
            return [action]
    return [f"share_{domain}_readiness_with_mainline"]


def empty_actions(domain: str) -> list[str]:
    if domain == "permission_sandbox":
        return ["provide_codex_permission_sandbox_policy"]
    for action in spec(domain).get("actions", []):
        if action.startswith("provide_"):
            return [action]
    return [f"provide_codex_{domain}_inventory"]


def blocked_actions(domain: str, code: str) -> list[str]:
    if domain == "permission_sandbox" and code == "codex_permission_sandbox_autonomous_approval":
        return ["tighten_approval_and_sandbox_policy", "remove_dangerous_runtime_bypass"]
    if domain == "tool_runtime" and code == "codex_tool_runtime_high_risk_without_manual_approval":
        return ["block_unsafe_runtime_surfaces", "review_permission_and_sandbox_policy"]
    resolve = [a for a in spec(domain).get("actions", []) if a.startswith("resolve_")]
    refresh = [a for a in spec(domain).get("actions", []) if a.startswith("refresh_") and a.endswith("readiness")]
    if resolve and refresh:
        return [resolve[0], refresh[0]]
    return [f"resolve_{domain}_blockers", f"refresh_{domain}_readiness"]


def review_actions(domain: str, code: str) -> list[str]:
    if domain == "memory_context" and code == "codex_memory_context_packet_missing_evidence":
        return ["attach_packet_level_context_policies", "refresh_memory_context_readiness"]
    if code == "codex_cross_thread_handoff_digest_stale":
        return ["refresh_cross_thread_handoff_digest", "attach_current_handoff_receipts"]
    if code == "codex_gap_matrix_traceability_residual_gap":
        return ["review_codex_gap_matrix_residual_gaps", "decide_next_gap_candidate"]
    if code == "codex_open_source_candidate_evaluation_maintenance_risk":
        return ["review_open_source_candidate_maintenance_risk", "decide_adoption_guardrail"]
    if "owner_signoff_review_required" in code:
        return ["review_archive_followup_owner_signoffs", "refresh_archive_followup_closure_readiness_packet"]
    if code == "codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_missing_evidence":
        return [
            "attach_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_evidence",
            "refresh_codex_secondary_integration_adoption_decision_archive_followup_closure_readiness_packet",
        ]
    if "recipient_review_required" in code:
        return ["review_archive_followup_notification_recipients", "refresh_archive_followup_notification_readiness_packet"]
    if "suppression_review_required" in code:
        return ["review_archive_followup_notification_suppressions", "refresh_archive_followup_notification_readiness_packet"]
    if code == "codex_repo_worktree_drift_still_open":
        return ["wait_for_repo_worktree_drift_resolution", "attach_repo_worktree_drift_receipts"]
    if code == "codex_task_progress_event_timeline_still_open":
        return ["wait_for_task_progress_event_timeline_completion", "attach_task_timeline_receipts"]
    if code == "codex_multi_agent_delegation_receipt_still_open":
        return ["wait_for_multi_agent_delegation_completion", "attach_multi_agent_delegation_receipts"]
    if code == "codex_tool_result_provenance_receipt_still_open":
        return ["wait_for_tool_result_provenance_receipt_completion", "attach_tool_result_provenance_receipts"]
    attach = [a for a in spec(domain).get("actions", []) if a.startswith("attach_")]
    refresh = [a for a in spec(domain).get("actions", []) if a.startswith("refresh_")]
    if attach and refresh:
        return [attach[0], refresh[0]]
    if refresh:
        return [refresh[0]]
    return ready_actions(domain)


def findings_for(
    domain: str, items: list[ReadinessItem], packet_missing: list[str]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in items:
        findings.extend(finding(code, domain, item) for code in item.finding_codes)
    for item in items:
        findings.extend(finding(code, domain, item) for code in item.warning_codes)
    if packet_missing:
        packet_finding = {"code": packet_missing_code(domain), "missing_refs": list(packet_missing)}
        if findings:
            findings.append(packet_finding)
        else:
            findings.insert(0, packet_finding)
    if not findings:
        for item in items:
            if item.missing_refs:
                findings.append(finding(item_missing_code(domain), domain, item))
                break
    return findings


def build_readiness_packet(domain: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if domain == "memory_context":
        return build_memory_context_packet(payload)
    if domain == "permission_sandbox":
        return build_permission_sandbox_packet(payload)
    if domain == "tool_runtime":
        return build_tool_runtime_packet(payload)

    payload = dict(payload or {})
    raw_items = collection(domain, payload)
    key = spec(domain).get("collection_key") or "items"
    if not raw_items:
        return {
            "kind": spec(domain)["module"],
            "ok": False,
            "status": "empty",
            "summary": summary(domain, []),
            key: [],
            "findings": [],
            "packet_missing_refs": [],
            "next_actions": empty_actions(domain),
        }

    items = [summarize_readiness_item(domain, item) for item in raw_items]
    packet_missing = packet_missing_refs(domain, payload)
    findings = findings_for(domain, items, packet_missing)
    if any(item.readiness_state == "blocked" for item in items):
        status = "blocked"
    elif packet_missing or any(item.readiness_state == "needs_review" for item in items) or findings:
        status = "needs_review"
    else:
        status = "ready"

    first_code = findings[0]["code"] if findings else ""
    packet = {
        "kind": spec(domain)["module"],
        "ok": status == "ready",
        "status": status,
        "summary": summary(domain, items),
        key: [item.as_packet_item() for item in items],
        "findings": findings,
        "packet_missing_refs": packet_missing,
        "next_actions": ready_actions(domain)
        if status == "ready"
        else blocked_actions(domain, first_code)
        if status == "blocked"
        else review_actions(domain, first_code),
    }
    if domain == "code_review_findings":
        packet["review_findings"] = findings
        packet["findings"] = [item.as_packet_item() for item in items]
    if domain == "repo_worktree_drift_reconciliation":
        for item in packet.get(key, []):
            item["blocker_refs"] = list(item.get("blockers", []))
    return packet


def summarize_memory_context_source(item: Any) -> ReadinessItem:
    data = normalize_data(as_mapping(item))
    data.setdefault("source_type", data.get("name") or "source")
    missing: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    codes: list[str] = []
    if data.get("enabled") is False:
        blockers.append("context_source_disabled")
        codes.append("codex_memory_context_source_disabled")
    if normalize_name(data.get("status")) == "stale":
        warnings.append("context_source_stale")
    if not present(data.get("redaction_refs")):
        missing.append("redaction_refs")
    if not present(data.get("validation_refs")):
        missing.append("validation_refs")
    source_type = normalize_name(data.get("source_type"))
    if source_type in {"repo", "repo_local_memory", "retrieval"} and not present(
        data.get("retrieval_refs")
    ):
        missing.append("retrieval_refs")
    boundaries = set(data.get("boundaries") or [])
    if "redaction" not in boundaries:
        missing.append("boundary_redaction")
    if source_type in {"repo", "repo_local_memory", "retrieval"} and "prompt_injection_guard" not in boundaries:
        warnings.append("retrieved_context_lacks_prompt_injection_guard")
    state = "blocked" if blockers else "needs_review" if missing or warnings else "ready"
    return ReadinessItem(
        data=data,
        missing_refs=tuple(dedupe(missing)),
        blockers=tuple(dedupe(blockers)),
        warnings=tuple(dedupe(warnings)),
        readiness_state=state,
        finding_codes=tuple(dedupe(codes)),
    )


def build_memory_context_packet(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    sources: list[ReadinessItem] = []
    for key in ("project_instructions", "repo_local_memory", "session_summary", "retrieval"):
        if isinstance(payload.get(key), Mapping):
            item = dict(payload[key])
            item.setdefault("source_type", key)
            sources.append(summarize_memory_context_source(item))
    if not sources:
        return {
            "kind": "codex_memory_context_readiness_packet",
            "ok": False,
            "status": "empty",
            "summary": {"source_count": 0, "total_token_budget": 0},
            "sources": [],
            "findings": [],
            "packet_missing_refs": [],
            "next_actions": ["provide_codex_memory_context_inventory"],
        }
    packet_missing = [
        ref for ref in spec("memory_context").get("packet_missing_refs", []) if not present(payload.get(ref))
    ]
    findings = []
    if packet_missing:
        findings.append({"code": "codex_memory_context_packet_missing_evidence", "missing_refs": packet_missing})
    for source in sources:
        if source.finding_codes:
            findings.extend(finding(code, "memory_context", source) for code in source.finding_codes)
    if not findings:
        for source in sources:
            if source.missing_refs:
                findings.append(finding("codex_memory_context_packet_missing_evidence", "memory_context", source))
                break
    blocked = any(source.readiness_state == "blocked" for source in sources)
    if blocked and (not findings or findings[0]["code"] != "codex_memory_context_packet_missing_evidence"):
        findings.insert(0, {"code": "codex_memory_context_packet_missing_evidence"})
    status = "blocked" if blocked else "needs_review" if packet_missing or any(source.readiness_state == "needs_review" for source in sources) else "ready"
    next_actions = (
        ["restore_required_context_sources", "review_memory_context_scope"]
        if blocked
        else ["attach_packet_level_context_policies", "refresh_memory_context_readiness"]
        if status == "needs_review"
        else ["share_memory_context_readiness_with_mainline"]
    )
    return {
        "kind": "codex_memory_context_readiness_packet",
        "ok": status == "ready",
        "status": status,
        "summary": summary("memory_context", sources),
        "sources": [source.as_packet_item() for source in sources],
        "findings": findings,
        "packet_missing_refs": packet_missing,
        "next_actions": next_actions,
    }


def summarize_permission_sandbox_policy(item: Any) -> ReadinessItem:
    data = normalize_data(as_mapping(item))
    missing: list[str] = []
    blockers: list[str] = []
    codes: list[str] = []
    if data.get("approval_policy") == "never" and data.get("sandbox_policy") == "danger_full_access":
        blockers.append("dangerous_sandbox_without_external_isolation")
        codes.append("codex_permission_sandbox_autonomous_approval")
    if data.get("filesystem_scope") == "unrestricted":
        blockers.append("unrestricted_filesystem_scope")
    if "bypass" in str(data.get("hook_policy") or ""):
        blockers.append("hook_trust_bypass_enabled")
        codes.append("codex_permission_sandbox_hook_trust_bypass")
    if data.get("sandbox_policy") == "workspace_write" and not present(data.get("allowed_write_roots")):
        missing.append("allowed_write_roots")
    if data.get("shell_policy") == "enabled" and not present(data.get("validation_refs")):
        missing.append("shell_validation_refs")
    if data.get("patch_policy") == "enabled" and not present(data.get("validation_refs")):
        missing.append("patch_validation_refs")
    if data.get("hook_policy") == "enabled" and not present(data.get("trusted_hook_refs")):
        missing.append("trusted_hook_refs")
    state = "blocked" if blockers else "needs_review" if missing else "ready"
    return ReadinessItem(
        data=data,
        missing_refs=tuple(dedupe(missing)),
        blockers=tuple(dedupe(blockers)),
        warnings=(),
        readiness_state=state,
        finding_codes=tuple(dedupe(codes)),
    )


def build_permission_sandbox_packet(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    if not payload:
        return {
            "kind": "codex_permission_sandbox_readiness_packet",
            "ok": False,
            "status": "empty",
            "summary": {"ready_count": 0},
            "policies": [],
            "findings": [],
            "packet_missing_refs": [],
            "next_actions": ["provide_codex_permission_sandbox_policy"],
        }
    policy = summarize_permission_sandbox_policy(payload)
    findings = []
    if policy.finding_codes:
        findings.append(finding(policy.finding_codes[0], "permission_sandbox", policy))
    elif policy.missing_refs:
        findings.append(finding("codex_permission_sandbox_missing_evidence", "permission_sandbox", policy))
    status = policy.readiness_state
    first_code = findings[0]["code"] if findings else ""
    return {
        "kind": "codex_permission_sandbox_readiness_packet",
        "ok": status == "ready",
        "status": status,
        "summary": {"ready_count": 1 if status == "ready" else 0},
        "policies": [policy.as_packet_item()],
        "findings": findings,
        "packet_missing_refs": [],
        "next_actions": ["share_permission_sandbox_readiness_with_mainline"]
        if status == "ready"
        else blocked_actions("permission_sandbox", first_code)
        if status == "blocked"
        else ["attach_permission_sandbox_evidence", "refresh_permission_sandbox_readiness"],
    }


def summarize_tool_runtime_component(item: Any) -> ReadinessItem:
    data = normalize_data(as_mapping(item))
    data.setdefault("component_type", data.get("type") or "component")
    data["component_type"] = normalize_name(data["component_type"])
    missing: list[str] = []
    blockers: list[str] = []
    codes: list[str] = []
    if data["component_type"] in {"mcp", "plugin", "skill"}:
        for ref in ("manifest_ref", "source_ref", "version_ref", "schema_ref"):
            if not present(data.get(ref)):
                missing.append(ref)
    if data["component_type"] in {"browser", "computer_use"}:
        if not any(
            present(data.get(ref))
            for ref in ("session_ref", "visual_evidence_ref", "screenshot_refs", "ui_snapshot_refs")
        ):
            missing.append("session_or_visual_evidence_ref")
    if normalize_name(data.get("risk_level")) in {"high", "critical"}:
        if data.get("approval_profile") not in {"ask", "manual", "on_request"} or not present(data.get("sandbox_profile")):
            blockers.append("high_risk_component_without_sandbox")
            codes.append("codex_tool_runtime_high_risk_without_manual_approval")
    state = "blocked" if blockers else "needs_review" if missing else "ready"
    return ReadinessItem(
        data=data,
        missing_refs=tuple(dedupe(missing)),
        blockers=tuple(dedupe(blockers)),
        warnings=(),
        readiness_state=state,
        finding_codes=tuple(dedupe(codes)),
    )


def build_tool_runtime_packet(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})
    components: list[ReadinessItem] = []
    for key, component_type in (("mcp_tools", "mcp"), ("plugins", "plugin"), ("skills", "skill")):
        for raw in payload.get(key) or []:
            item = dict(raw)
            item.setdefault("component_type", component_type)
            components.append(summarize_tool_runtime_component(item))
    for key in ("browser", "shell", "patch", "computer_use"):
        if isinstance(payload.get(key), Mapping):
            item = dict(payload[key])
            item.setdefault("component_type", key)
            components.append(summarize_tool_runtime_component(item))
    if not components:
        return {
            "kind": "codex_tool_runtime_readiness_packet",
            "ok": False,
            "status": "empty",
            "summary": {"component_count": 0, "ready_count": 0, "needs_review_count": 0, "missing_ref_count": 0, "by_component_type": {}},
            "components": [],
            "findings": [],
            "packet_missing_refs": [],
            "next_actions": ["provide_codex_tool_runtime_inventory"],
        }
    findings = findings_for("tool_runtime", components, [])
    status = "blocked" if any(item.readiness_state == "blocked" for item in components) else "needs_review" if any(item.readiness_state == "needs_review" for item in components) else "ready"
    first_code = findings[0]["code"] if findings else ""
    return {
        "kind": "codex_tool_runtime_readiness_packet",
        "ok": status == "ready",
        "status": status,
        "summary": summary("tool_runtime", components),
        "components": [component.as_packet_item() for component in components],
        "findings": findings,
        "packet_missing_refs": [],
        "next_actions": ["share_codex_tool_runtime_readiness_with_mainline"]
        if status == "ready"
        else blocked_actions("tool_runtime", first_code)
        if status == "blocked"
        else ["review_permission_and_sandbox_policy"],
    }
