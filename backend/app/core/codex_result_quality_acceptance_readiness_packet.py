from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_result_quality_acceptance_readiness_packet', 'collection_key': 'results', 'required_packet_refs': ['result_quality_policy', 'acceptance_policy', 'evidence_policy', 'regression_policy', 'result_quality_manifest_ref', 'acceptance_governance_ref'], 'packet_missing_refs': ['result_quality_policy_ref', 'acceptance_policy_ref', 'evidence_policy_ref', 'regression_policy_ref', 'result_quality_manifest_ref', 'acceptance_governance_ref'], 'required_item_refs': ['mismatch_refs', 'regression_refs', 'expected_result_ref', 'acceptance_criteria_refs', 'result_quality_refs', 'evidence_refs', 'validation_receipt_refs'], 'ready_actions': ['share_result_quality_acceptance_readiness_with_mainline'], 'empty_actions': ['provide_codex_result_quality_acceptance_inventory'], 'prefix': 'codex_result_quality_acceptance_readiness', 'failed_code': 'codex_result_quality_acceptance_status_failed', 'packet_missing_code': 'codex_result_quality_acceptance_packet_missing_evidence', 'live_code': 'codex_result_quality_acceptance_live_operation_blocked', 'summary_ref_field': 'acceptance_criteria_refs', 'summary_ref_count_key': 'acceptance_criteria_ref_count'}


def summarize_codex_result_quality_acceptance(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_result_quality_acceptance_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
