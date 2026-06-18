from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet', 'collection_key': 'owner_receipts', 'required_packet_refs': ['followup_archive_export_owner_receipt_policy', 'archive_export_policy', 'receipt_retention_policy', 'owner_receipt_acknowledgement_policy', 'secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref'], 'packet_missing_refs': ['followup_archive_export_owner_receipt_policy_ref', 'archive_export_policy_ref', 'receipt_retention_policy_ref', 'owner_receipt_acknowledgement_policy_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref'], 'required_item_refs': ['export_closeout_refs', 'export_review_refs', 'export_receipt_refs', 'owner_acknowledgement_refs', 'reviewer_acknowledgement_refs', 'closeout_decision_refs', 'validation_refs', 'evidence_refs', 'retention_refs'], 'conditional_refs': {'needs_failure_evidence': ['retention_refs', 'next_action_refs'], 'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_inventory'], 'review_actions': ['review_archive_followup_export_owner_receipt_acknowledgements', 'refresh_archive_followup_export_owner_receipt_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_status_failed', 'missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_missing_evidence', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_live_operation_blocked', 'summary_ref_field': 'export_closeout_refs', 'summary_ref_count_key': 'export_closeout_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_owner_receipt_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
