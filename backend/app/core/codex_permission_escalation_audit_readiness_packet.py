from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_permission_escalation_audit_readiness_packet', 'collection_key': 'audits', 'required_packet_refs': ['approval_policy', 'sandbox_policy', 'command_prefix_policy', 'escalation_policy', 'permission_escalation_manifest_ref', 'controlled_escalation_governance_ref'], 'packet_missing_refs': ['approval_policy_ref', 'sandbox_policy_ref', 'command_prefix_policy_ref', 'escalation_policy_ref', 'permission_escalation_manifest_ref', 'controlled_escalation_governance_ref'], 'required_item_refs': ['escalation_justification_refs', 'approval_decision_refs', 'denial_refs'], 'ready_actions': ['share_permission_escalation_audit_readiness_with_mainline'], 'empty_actions': ['provide_codex_permission_escalation_audit_inventory'], 'blocked_actions': ['resolve_permission_escalation_audit_blockers', 'refresh_permission_escalation_audit_readiness'], 'prefix': 'codex_permission_escalation_audit_readiness', 'failed_code': 'codex_permission_escalation_audit_status_failed', 'packet_missing_code': 'codex_permission_escalation_audit_packet_missing_evidence', 'live_code': 'codex_permission_escalation_audit_live_operation_blocked', 'summary_ref_field': 'command_prefix_refs', 'summary_ref_count_key': 'command_prefix_ref_count'}


def summarize_codex_permission_escalation_audit(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_permission_escalation_audit_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
