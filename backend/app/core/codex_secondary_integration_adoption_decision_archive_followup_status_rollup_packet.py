from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet', 'collection_key': 'rollups', 'required_packet_refs': ['followup_status_rollup_policy', 'owner_status_policy', 'due_window_status_policy', 'status_evidence_policy', 'secondary_integration_adoption_decision_archive_followup_status_rollup_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_status_governance_ref'], 'packet_missing_refs': ['followup_status_rollup_policy_ref', 'owner_status_policy_ref', 'due_window_status_policy_ref', 'status_evidence_policy_ref', 'secondary_integration_adoption_decision_archive_followup_status_rollup_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_status_governance_ref'], 'required_item_refs': ['followup_routing_refs', 'owner_followup_refs', 'reviewer_refs', 'open_followup_refs', 'blocked_followup_refs', 'resolved_followup_refs', 'due_window_refs', 'validation_refs', 'evidence_refs'], 'conditional_refs': {'needs_failure_evidence': ['next_action_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_inventory'], 'blocked_actions': ['review_archive_blocked_followups', 'refresh_archive_followup_status_rollup_packet'], 'review_actions': ['review_archive_followup_due_status', 'refresh_archive_followup_status_rollup_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_status_rollup', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_status_rollup_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_status_rollup_live_operation_blocked', 'summary_ref_field': 'blocked_followup_refs', 'summary_ref_count_key': 'blocked_followup_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_status_rollup(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_status_rollup_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
