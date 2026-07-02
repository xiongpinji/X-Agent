from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_cross_thread_handoff_digest_readiness_packet', 'collection_key': 'handoffs', 'required_packet_refs': ['handoff_digest_policy', 'source_of_truth_policy', 'read_receipt_policy', 'stale_handoff_policy', 'cross_thread_handoff_manifest_ref', 'multi_thread_continuity_governance_ref'], 'packet_missing_refs': ['handoff_digest_policy_ref', 'source_of_truth_policy_ref', 'read_receipt_policy_ref', 'stale_handoff_policy_ref', 'cross_thread_handoff_manifest_ref', 'multi_thread_continuity_governance_ref'], 'required_item_refs': ['source_thread_ref', 'target_thread_refs', 'handoff_digest_refs', 'source_of_truth_refs', 'candidate_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs', 'read_receipt_refs'], 'ready_actions': ['share_cross_thread_handoff_digest_readiness_with_mainline'], 'empty_actions': ['provide_codex_cross_thread_handoff_digest_inventory'], 'blocked_actions': ['resolve_cross_thread_handoff_digest_blockers', 'refresh_cross_thread_handoff_digest_readiness'], 'review_actions': ['refresh_cross_thread_handoff_digest', 'attach_current_handoff_receipts'], 'prefix': 'codex_cross_thread_handoff_digest_readiness', 'failed_code': 'codex_cross_thread_handoff_digest_status_failed', 'packet_missing_code': 'codex_cross_thread_handoff_digest_packet_missing_evidence', 'live_code': 'codex_cross_thread_handoff_digest_live_operation_blocked', 'summary_ref_field': 'read_receipt_refs', 'summary_ref_count_key': 'read_receipt_ref_count'}


def summarize_codex_cross_thread_handoff_digest(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_cross_thread_handoff_digest_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
