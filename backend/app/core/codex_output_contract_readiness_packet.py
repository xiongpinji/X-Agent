from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_output_contract_readiness_packet', 'collection_key': 'outputs', 'required_packet_refs': ['final_answer_policy', 'command_output_policy', 'file_reference_policy', 'verification_policy', 'output_contract_manifest_ref', 'response_governance_ref'], 'packet_missing_refs': ['final_answer_policy_ref', 'command_output_policy_ref', 'file_reference_policy_ref', 'verification_policy_ref', 'output_contract_manifest_ref', 'response_governance_ref'], 'required_item_refs': ['final_answer_ref', 'command_output_summary_refs', 'file_reference_refs', 'verification_evidence_refs', 'next_step_refs', 'validation_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_disclosure_refs']}, 'ready_actions': ['share_output_contract_readiness_with_mainline'], 'empty_actions': ['provide_codex_output_contract_inventory'], 'prefix': 'codex_output_contract_readiness', 'failed_code': 'codex_output_contract_status_failed', 'packet_missing_code': 'codex_output_contract_packet_missing_evidence', 'live_code': 'codex_output_contract_live_operation_blocked', 'summary_ref_field': 'command_output_summary_refs', 'summary_ref_count_key': 'command_output_summary_ref_count'}


def summarize_codex_output_contract(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_output_contract_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
