from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_repo_worktree_drift_reconciliation_readiness_packet', 'collection_key': 'reconciliations', 'required_packet_refs': ['worktree_policy', 'branch_policy', 'drift_policy', 'reconciliation_policy', 'worktree_drift_manifest_ref', 'repo_worktree_governance_ref'], 'packet_missing_refs': ['worktree_policy_ref', 'branch_policy_ref', 'drift_policy_ref', 'reconciliation_policy_ref', 'worktree_drift_manifest_ref', 'repo_worktree_governance_ref'], 'required_item_refs': ['preservation_refs', 'branch_refs', 'base_refs', 'head_refs', 'dirty_worktree_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs'], 'conditional_refs': {'needs_failure_evidence': ['conflict_refs']}, 'ready_actions': ['share_repo_worktree_drift_reconciliation_readiness_with_mainline'], 'empty_actions': ['provide_codex_repo_worktree_drift_reconciliation_inventory'], 'review_actions': ['wait_for_repo_worktree_drift_resolution', 'attach_repo_worktree_drift_receipts'], 'prefix': 'codex_repo_worktree_drift_reconciliation_readiness', 'failed_code': 'codex_repo_worktree_drift_status_failed', 'packet_missing_code': 'codex_repo_worktree_drift_packet_missing_evidence', 'live_code': 'codex_repo_worktree_drift_live_operation_blocked', 'summary_ref_field': 'branch_refs', 'summary_ref_count_key': 'branch_ref_count'}


def summarize_codex_repo_worktree_drift_reconciliation(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_repo_worktree_drift_reconciliation_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
