from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_worktree_git_state_readiness_packet', 'collection_key': 'states', 'required_packet_refs': ['worktree_policy', 'git_state_policy', 'staging_policy', 'commit_policy', 'worktree_manifest_ref', 'git_state_governance_ref'], 'packet_missing_refs': ['worktree_policy_ref', 'git_state_policy_ref', 'staging_policy_ref', 'commit_policy_ref', 'worktree_manifest_ref', 'git_state_governance_ref'], 'required_item_refs': ['user_change_preservation_refs', 'branch_refs', 'base_refs', 'head_refs', 'staged_state_refs', 'unstaged_state_refs'], 'conditional_refs': {'needs_failure_evidence': ['conflict_refs']}, 'ready_actions': ['share_worktree_git_state_readiness_with_mainline'], 'empty_actions': ['provide_codex_worktree_git_state_inventory'], 'blocked_actions': ['resolve_worktree_git_state_blockers', 'refresh_worktree_git_state_readiness'], 'prefix': 'codex_worktree_git_state_readiness', 'failed_code': 'codex_worktree_git_state_failed', 'packet_missing_code': 'codex_worktree_git_state_packet_missing_evidence', 'live_code': 'codex_worktree_git_state_live_operation_blocked', 'summary_ref_field': 'branch_refs', 'summary_ref_count_key': 'branch_ref_count'}


def summarize_codex_worktree_git_state(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_worktree_git_state_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
