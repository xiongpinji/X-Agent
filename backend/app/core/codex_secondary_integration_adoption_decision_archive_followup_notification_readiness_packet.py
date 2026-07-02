from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet', 'collection_key': 'notifications', 'required_packet_refs': ['followup_notification_readiness_policy', 'recipient_policy', 'channel_policy', 'suppression_policy', 'secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_notification_governance_ref'], 'packet_missing_refs': ['followup_notification_readiness_policy_ref', 'recipient_policy_ref', 'channel_policy_ref', 'suppression_policy_ref', 'secondary_integration_adoption_decision_archive_followup_notification_readiness_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_notification_governance_ref'], 'required_item_refs': ['owner_handoff_refs', 'followup_status_rollup_refs', 'recipient_refs', 'channel_policy_refs', 'message_preview_refs', 'validation_refs', 'evidence_refs', 'suppression_refs'], 'conditional_refs': {'needs_failure_evidence': ['next_action_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_inventory'], 'review_actions': ['review_archive_followup_notification_suppressions', 'refresh_archive_followup_notification_readiness_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_notification_readiness', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_live_operation_blocked', 'summary_ref_field': 'message_preview_refs', 'summary_ref_count_key': 'message_preview_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_notification_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
