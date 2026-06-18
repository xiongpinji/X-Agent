from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_file_edit_session_readiness_packet', 'collection_key': 'edit_sessions', 'required_packet_refs': ['edit_policy', 'preservation_policy', 'formatting_policy', 'validation_policy', 'edit_session_manifest_ref', 'edit_governance_ref'], 'packet_missing_refs': ['edit_policy_ref', 'preservation_policy_ref', 'formatting_policy_ref', 'validation_policy_ref', 'edit_session_manifest_ref', 'edit_governance_ref'], 'required_item_refs': ['read_before_write_refs', 'user_change_preservation_refs', 'patch_refs', 'formatting_refs', 'validation_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['conflict_refs']}, 'ready_actions': ['share_file_edit_session_readiness_with_mainline'], 'empty_actions': ['provide_codex_file_edit_session_inventory'], 'blocked_actions': ['resolve_file_edit_session_blockers', 'refresh_file_edit_session_readiness'], 'prefix': 'codex_file_edit_session_readiness', 'failed_code': 'codex_file_edit_session_status_failed', 'packet_missing_code': 'codex_file_edit_session_packet_missing_evidence', 'live_code': 'codex_file_edit_session_live_mutation_blocked', 'summary_ref_field': 'read_before_write_refs', 'summary_ref_count_key': 'read_before_write_ref_count'}


def summarize_codex_file_edit_session(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_file_edit_session_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
