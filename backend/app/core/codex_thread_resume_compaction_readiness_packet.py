from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_thread_resume_compaction_readiness_packet', 'collection_key': 'resumes', 'required_packet_refs': ['resume_policy', 'compaction_policy', 'handoff_policy', 'context_budget_policy', 'thread_continuity_manifest_ref', 'resume_governance_ref'], 'packet_missing_refs': ['resume_policy_ref', 'compaction_policy_ref', 'handoff_policy_ref', 'context_budget_policy_ref', 'thread_continuity_manifest_ref', 'resume_governance_ref'], 'required_item_refs': ['handoff_refs', 'compaction_summary_refs', 'continuation_refs', 'resume_token_refs', 'context_budget_refs', 'source_thread_refs', 'resume_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_handoff_refs']}, 'ready_actions': ['share_thread_resume_compaction_readiness_with_mainline'], 'empty_actions': ['provide_codex_thread_resume_compaction_inventory'], 'blocked_actions': ['resolve_thread_resume_compaction_blockers', 'refresh_thread_resume_compaction_readiness'], 'prefix': 'codex_thread_resume_compaction_readiness', 'failed_code': 'codex_thread_resume_compaction_status_failed', 'packet_missing_code': 'codex_thread_resume_compaction_packet_missing_evidence', 'live_code': 'codex_thread_resume_compaction_live_operation_blocked', 'summary_ref_field': 'resume_token_refs', 'summary_ref_count_key': 'resume_token_ref_count'}


def summarize_codex_thread_resume_compaction(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_thread_resume_compaction_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
