from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_receipt_packet', 'collection_key': 'receipts', 'required_packet_refs': ['adoption_decision_receipt_policy', 'owner_receipt_policy', 'mainline_acknowledgement_policy', 'receipt_timestamp_policy', 'secondary_integration_adoption_decision_receipt_manifest_ref', 'secondary_integration_adoption_decision_receipt_governance_ref'], 'packet_missing_refs': ['adoption_decision_receipt_policy_ref', 'owner_receipt_policy_ref', 'mainline_acknowledgement_policy_ref', 'receipt_timestamp_policy_ref', 'secondary_integration_adoption_decision_receipt_manifest_ref', 'secondary_integration_adoption_decision_receipt_governance_ref'], 'required_item_refs': ['decision_ledger_refs', 'owner_receipt_refs', 'mainline_acknowledgement_refs', 'candidate_disposition_refs', 'validation_refs', 'handoff_refs', 'receipt_timestamp_refs'], 'conditional_refs': {'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_receipt_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_receipt_inventory'], 'review_actions': ['attach_adoption_decision_receipt_timestamps', 'refresh_adoption_decision_receipt_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_receipt', 'failed_code': 'codex_secondary_integration_adoption_decision_receipt_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_receipt_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_receipt_live_operation_blocked', 'summary_ref_field': 'mainline_acknowledgement_refs', 'summary_ref_count_key': 'mainline_acknowledgement_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_receipt_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
