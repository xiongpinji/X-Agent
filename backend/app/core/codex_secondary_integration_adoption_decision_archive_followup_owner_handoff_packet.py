from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet', 'collection_key': 'handoffs', 'required_packet_refs': ['followup_owner_handoff_policy', 'owner_accountability_policy', 'reviewer_accountability_policy', 'handoff_evidence_policy', 'secondary_integration_adoption_decision_archive_followup_owner_handoff_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_owner_governance_ref'], 'packet_missing_refs': ['followup_owner_handoff_policy_ref', 'owner_accountability_policy_ref', 'reviewer_accountability_policy_ref', 'handoff_evidence_policy_ref', 'secondary_integration_adoption_decision_archive_followup_owner_handoff_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_owner_governance_ref'], 'required_item_refs': ['followup_status_rollup_refs', 'owner_refs', 'reviewer_refs', 'open_followup_refs', 'blocked_followup_refs', 'resolved_followup_refs', 'due_window_refs', 'validation_refs', 'evidence_refs', 'owner_handoff_refs'], 'conditional_refs': {'needs_failure_evidence': ['next_action_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_inventory'], 'blocked_actions': ['review_archive_followup_owner_blockers', 'refresh_archive_followup_owner_handoff_packet'], 'review_actions': ['review_archive_followup_owner_assignments', 'refresh_archive_followup_owner_handoff_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_owner_handoff', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_live_operation_blocked', 'summary_ref_field': 'owner_handoff_refs', 'summary_ref_count_key': 'owner_handoff_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_owner_handoff_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
