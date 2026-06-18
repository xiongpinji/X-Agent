from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_workspace_diff_readiness_packet', 'collection_key': 'diffs', 'required_packet_refs': ['diff_policy', 'patch_policy', 'conflict_policy', 'artifact_policy', 'workspace_manifest_ref', 'review_matrix_ref'], 'packet_missing_refs': ['diff_policy_ref', 'patch_policy_ref', 'conflict_policy_ref', 'artifact_policy_ref', 'workspace_manifest_ref', 'review_matrix_ref'], 'required_item_refs': ['diff_summary_refs', 'patch_refs', 'staged_state_refs', 'unstaged_state_refs', 'generated_artifact_refs', 'file_risk_refs'], 'conditional_refs': {'needs_failure_evidence': ['conflict_refs']}, 'ready_actions': ['share_workspace_diff_readiness_with_mainline'], 'empty_actions': ['provide_codex_workspace_diff_inventory'], 'blocked_actions': ['resolve_workspace_diff_blockers', 'refresh_workspace_diff_readiness'], 'prefix': 'codex_workspace_diff_readiness', 'failed_code': 'codex_workspace_diff_status_failed', 'packet_missing_code': 'codex_workspace_diff_packet_missing_evidence', 'live_code': 'codex_workspace_diff_live_mutation_blocked', 'summary_ref_field': 'changed_file_refs', 'summary_ref_count_key': 'changed_file_ref_count'}


def summarize_codex_workspace_diff(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_workspace_diff_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
