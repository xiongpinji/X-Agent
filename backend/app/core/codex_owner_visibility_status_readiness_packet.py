from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_owner_visibility_status_readiness_packet', 'collection_key': 'visibility_items', 'required_packet_refs': ['candidate_status_policy', 'handoff_digest_policy', 'owner_decision_policy', 'stage_classification_policy', 'owner_visibility_manifest_ref', 'multi_thread_visibility_governance_ref'], 'packet_missing_refs': ['candidate_status_policy_ref', 'handoff_digest_policy_ref', 'owner_decision_policy_ref', 'stage_classification_policy_ref', 'owner_visibility_manifest_ref', 'multi_thread_visibility_governance_ref'], 'required_item_refs': ['notification_refs', 'owner_decision_refs', 'candidate_status_refs', 'handoff_digest_refs', 'stage_classification_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs', 'mainline_thread_refs'], 'ready_actions': ['share_owner_visibility_status_readiness_with_mainline'], 'empty_actions': ['provide_codex_owner_visibility_status_inventory'], 'prefix': 'codex_owner_visibility_status_readiness', 'failed_code': 'codex_owner_visibility_status_failed', 'packet_missing_code': 'codex_owner_visibility_status_packet_missing_evidence', 'live_code': 'codex_owner_visibility_status_live_operation_blocked', 'summary_ref_field': 'candidate_status_refs', 'summary_ref_count_key': 'candidate_status_ref_count'}


def summarize_codex_owner_visibility_status(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_owner_visibility_status_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
