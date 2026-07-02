from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_routing_packet', 'collection_key': 'routes', 'required_packet_refs': ['archive_followup_routing_policy', 'owner_reviewer_policy', 'due_window_policy', 'routing_evidence_policy', 'secondary_integration_adoption_decision_archive_followup_routing_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_governance_ref'], 'packet_missing_refs': ['archive_followup_routing_policy_ref', 'owner_reviewer_policy_ref', 'due_window_policy_ref', 'routing_evidence_policy_ref', 'secondary_integration_adoption_decision_archive_followup_routing_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_governance_ref'], 'required_item_refs': ['archive_answer_brief_refs', 'owner_followup_refs', 'reviewer_refs', 'unresolved_result_refs', 'citation_review_refs', 'validation_refs', 'routing_refs', 'due_window_refs'], 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_routing_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_routing_inventory'], 'review_actions': ['review_archive_owner_followups', 'refresh_archive_followup_routing_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_routing', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_routing_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_routing_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_routing_live_operation_blocked', 'summary_ref_field': 'owner_followup_refs', 'summary_ref_count_key': 'owner_followup_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_routing(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
