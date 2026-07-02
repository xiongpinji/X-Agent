from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_conversation_state_transition_audit_readiness_packet', 'collection_key': 'transitions', 'required_packet_refs': ['state_transition_policy', 'resume_policy', 'compaction_policy', 'audit_policy', 'conversation_state_manifest_ref', 'state_transition_governance_ref'], 'packet_missing_refs': ['state_transition_policy_ref', 'resume_policy_ref', 'compaction_policy_ref', 'audit_policy_ref', 'conversation_state_manifest_ref', 'state_transition_governance_ref'], 'required_item_refs': ['previous_state_refs', 'current_state_refs', 'transition_reason_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs', 'resume_refs', 'compaction_refs'], 'conditional_refs': {'needs_failure_evidence': ['interruption_refs']}, 'ready_actions': ['share_conversation_state_transition_audit_readiness_with_mainline'], 'empty_actions': ['provide_codex_conversation_state_transition_audit_inventory'], 'blocked_actions': ['resolve_conversation_state_transition_audit_blockers', 'refresh_conversation_state_transition_audit_readiness'], 'prefix': 'codex_conversation_state_transition_audit_readiness', 'failed_code': 'codex_conversation_state_transition_audit_status_failed', 'packet_missing_code': 'codex_conversation_state_transition_audit_packet_missing_evidence', 'live_code': 'codex_conversation_state_transition_audit_live_operation_blocked', 'summary_ref_field': 'resume_refs', 'summary_ref_count_key': 'resume_ref_count'}


def summarize_codex_conversation_state_transition_audit(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_conversation_state_transition_audit_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
