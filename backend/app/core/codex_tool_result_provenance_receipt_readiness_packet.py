from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_tool_result_provenance_receipt_readiness_packet', 'collection_key': 'receipts', 'required_packet_refs': ['tool_result_policy', 'provenance_policy', 'receipt_policy', 'redaction_policy', 'tool_result_manifest_ref', 'tool_result_governance_ref'], 'packet_missing_refs': ['tool_result_policy_ref', 'provenance_policy_ref', 'receipt_policy_ref', 'redaction_policy_ref', 'tool_result_manifest_ref', 'tool_result_governance_ref'], 'required_item_refs': ['tool_call_ref', 'result_refs', 'source_refs', 'provenance_refs', 'stdout_receipt_refs', 'exit_status_refs', 'redaction_refs', 'validation_receipt_refs', 'artifact_refs'], 'conditional_refs': {'needs_failure_evidence': ['stderr_receipt_refs']}, 'ready_actions': ['share_tool_result_provenance_receipt_readiness_with_mainline'], 'empty_actions': ['provide_codex_tool_result_provenance_receipt_inventory'], 'review_actions': ['wait_for_tool_result_provenance_receipt_completion', 'attach_tool_result_provenance_receipts'], 'prefix': 'codex_tool_result_provenance_receipt_readiness', 'failed_code': 'codex_tool_result_provenance_receipt_status_failed', 'packet_missing_code': 'codex_tool_result_provenance_receipt_packet_missing_evidence', 'live_code': 'codex_tool_result_provenance_receipt_live_operation_blocked', 'summary_ref_field': 'provenance_refs', 'summary_ref_count_key': 'provenance_ref_count'}


def summarize_codex_tool_result_provenance_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_tool_result_provenance_receipt_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
