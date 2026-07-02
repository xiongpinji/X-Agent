from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet', 'collection_key': 'previews', 'required_packet_refs': ['followup_disposition_preview_policy', 'preview_decision_policy', 'candidate_disposition_policy', 'evidence_review_policy', 'secondary_integration_adoption_decision_archive_followup_disposition_preview_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_disposition_governance_ref'], 'packet_missing_refs': ['followup_disposition_preview_policy_ref', 'preview_decision_policy_ref', 'candidate_disposition_policy_ref', 'evidence_review_policy_ref', 'secondary_integration_adoption_decision_archive_followup_disposition_preview_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_disposition_governance_ref'], 'required_item_refs': ['notification_readiness_refs', 'owner_handoff_refs', 'followup_status_rollup_refs', 'open_followup_refs', 'blocked_followup_refs', 'resolved_followup_refs', 'validation_refs', 'evidence_refs', 'preview_decision_refs'], 'conditional_refs': {'needs_failure_evidence': ['next_action_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_inventory'], 'blocked_actions': ['review_archive_followup_disposition_blockers', 'refresh_archive_followup_disposition_preview_packet'], 'review_actions': ['review_archive_followup_disposition_preview_decisions', 'refresh_archive_followup_disposition_preview_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_disposition_preview', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_live_operation_blocked', 'summary_ref_field': 'preview_decision_refs', 'summary_ref_count_key': 'preview_decision_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_disposition_preview_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
