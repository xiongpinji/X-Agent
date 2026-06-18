from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet', 'collection_key': 'closeouts', 'required_packet_refs': ['followup_archive_export_final_closeout_policy', 'archive_export_policy', 'receipt_retention_policy', 'final_closeout_decision_policy', 'secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref'], 'packet_missing_refs': ['followup_archive_export_final_closeout_policy_ref', 'archive_export_policy_ref', 'receipt_retention_policy_ref', 'final_closeout_decision_policy_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_ref', 'secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref'], 'required_item_refs': ['final_receipt_refs', 'final_audit_refs', 'owner_closeout_refs', 'owner_receipt_refs', 'audit_decision_refs', 'validation_refs', 'evidence_refs', 'closeout_decision_refs', 'retention_refs'], 'conditional_refs': {'needs_failure_evidence': ['retention_refs', 'owner_signoff_refs', 'next_action_refs'], 'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_inventory'], 'review_actions': ['review_archive_followup_export_final_closeouts', 'refresh_archive_followup_export_final_closeout_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_status_failed', 'missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_missing_evidence', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_live_operation_blocked', 'summary_ref_field': 'closeout_decision_refs', 'summary_ref_count_key': 'closeout_decision_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_final_closeout_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
