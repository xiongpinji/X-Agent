from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_index_packet', 'collection_key': 'archives', 'required_packet_refs': ['adoption_decision_archive_policy', 'archive_index_policy', 'retention_policy', 'lookup_key_policy', 'secondary_integration_adoption_decision_archive_index_manifest_ref', 'secondary_integration_adoption_decision_archive_governance_ref'], 'packet_missing_refs': ['adoption_decision_archive_policy_ref', 'archive_index_policy_ref', 'retention_policy_ref', 'lookup_key_policy_ref', 'secondary_integration_adoption_decision_archive_index_manifest_ref', 'secondary_integration_adoption_decision_archive_governance_ref'], 'required_item_refs': ['adoption_decision_receipt_refs', 'decision_ledger_refs', 'candidate_disposition_refs', 'validation_refs', 'handoff_refs', 'archive_refs', 'lookup_keys', 'retention_refs'], 'conditional_refs': {'residual_risk_detected': ['residual_risk_refs'], }, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_index_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_index_inventory'], 'review_actions': ['review_stale_secondary_integration_archive_index', 'refresh_archive_index_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_index', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_index_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_index_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_index_live_operation_blocked'}


def summarize_codex_secondary_integration_adoption_decision_archive_index(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_index_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
