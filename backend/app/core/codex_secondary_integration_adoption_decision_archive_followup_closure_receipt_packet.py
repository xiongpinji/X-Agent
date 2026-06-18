from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet', 'collection_key': 'receipts', 'required_packet_refs': ['followup_closure_receipt_policy', 'closure_evidence_policy', 'residual_risk_policy', 'receipt_retention_policy', 'secondary_integration_adoption_decision_archive_followup_closure_receipt_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_receipt_governance_ref'], 'packet_missing_refs': ['followup_closure_receipt_policy_ref', 'closure_evidence_policy_ref', 'residual_risk_policy_ref', 'receipt_retention_policy_ref', 'secondary_integration_adoption_decision_archive_followup_closure_receipt_manifest_ref', 'secondary_integration_adoption_decision_archive_followup_receipt_governance_ref'], 'required_item_refs': ['closure_readiness_refs', 'disposition_preview_refs', 'closure_criteria_refs', 'validation_refs', 'evidence_refs', 'receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['owner_signoff_refs', 'next_action_refs'], 'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_inventory'], 'review_actions': ['review_archive_followup_receipt_retention', 'refresh_archive_followup_closure_receipt_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_status_failed', 'missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_missing_evidence', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_live_operation_blocked', 'summary_ref_field': 'residual_risk_refs', 'summary_ref_count_key': 'residual_risk_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
