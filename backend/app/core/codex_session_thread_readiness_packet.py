from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_session_thread_readiness_packet', 'collection_key': 'sessions', 'required_packet_refs': ['session_policy', 'resume_policy', 'handoff_policy', 'compaction_policy', 'session_manifest_ref', 'continuity_matrix_ref'], 'packet_missing_refs': ['session_policy_ref', 'resume_policy_ref', 'handoff_policy_ref', 'compaction_policy_ref', 'session_manifest_ref', 'continuity_matrix_ref'], 'required_item_refs': ['resume_token_refs', 'handoff_refs', 'branch_worktree_refs', 'compaction_refs'], 'conditional_refs': {'needs_failure_evidence': ['interruption_refs']}, 'ready_actions': ['share_session_thread_readiness_with_mainline'], 'empty_actions': ['provide_codex_session_thread_inventory'], 'blocked_actions': ['resolve_session_thread_blockers', 'refresh_session_thread_readiness'], 'prefix': 'codex_session_thread_readiness', 'failed_code': 'codex_session_thread_status_failed', 'packet_missing_code': 'codex_session_thread_packet_missing_evidence', 'live_code': 'codex_session_thread_live_mutation_blocked', 'summary_ref_field': 'resume_token_refs', 'summary_ref_count_key': 'resume_token_ref_count'}


def summarize_codex_session_thread(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_session_thread_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
