from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_repo_worktree_drift_reconciliation_readiness_packet import (
    build_codex_repo_worktree_drift_reconciliation_readiness_packet,
    summarize_codex_repo_worktree_drift_reconciliation,
)


PACKET_POLICIES = {
    "worktree_policy": "worktree-policy",
    "branch_policy": "branch-policy",
    "drift_policy": "drift-policy",
    "reconciliation_policy": "reconciliation-policy",
    "worktree_drift_manifest_ref": "worktree-drift-manifest",
    "repo_worktree_governance_ref": "repo-worktree-governance",
}


def test_ready_repo_worktree_drift_reconciliation_has_git_evidence() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet(
        {
            **PACKET_POLICIES,
            "reconciliations": [
                {
                    "reconciliation_id": "drift-1",
                    "status": "reconciled",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "dirty_worktree_refs": ["clean-status"],
                    "conflict_refs": ["no-conflict"],
                    "preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_repo_worktree_drift_reconciliation_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["reconciliation_count"] == 1
    assert packet["summary"]["branch_ref_count"] == 1
    assert packet["next_actions"] == ["share_repo_worktree_drift_reconciliation_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet(
        {
            "reconciliations": [
                {
                    "reconciliation_id": "drift-2",
                    "status": "resolved",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "dirty_worktree_refs": ["clean-status"],
                    "conflict_refs": ["no-conflict"],
                    "preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_repo_worktree_drift_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "worktree_policy_ref",
        "branch_policy_ref",
        "drift_policy_ref",
        "reconciliation_policy_ref",
        "worktree_drift_manifest_ref",
        "repo_worktree_governance_ref",
    ]


def test_conflicted_dirty_or_diverged_state_requires_conflict_and_preservation_refs_and_blocks() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet(
        {
            **PACKET_POLICIES,
            "reconciliations": [
                {
                    "reconciliation_id": "drift-3",
                    "status": "diverged",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "dirty_worktree_refs": ["dirty"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    reconciliation = packet["reconciliations"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_repo_worktree_drift_status_failed"
    assert "conflict_refs" in reconciliation["missing_refs"]
    assert "preservation_refs" in reconciliation["missing_refs"]


def test_missing_branch_base_head_dirty_validation_artifact_owner_refs_needs_review() -> None:
    reconciliation = summarize_codex_repo_worktree_drift_reconciliation(
        {
            "reconciliation_id": "drift-4",
            "status": "validated",
            "worktree_ref": "worktree",
        }
    )

    assert reconciliation.readiness_state == "needs_review"
    assert "branch_refs" in reconciliation.missing_refs
    assert "base_refs" in reconciliation.missing_refs
    assert "head_refs" in reconciliation.missing_refs
    assert "dirty_worktree_refs" in reconciliation.missing_refs
    assert "validation_receipt_refs" in reconciliation.missing_refs
    assert "artifact_refs" in reconciliation.missing_refs
    assert "owner_refs" in reconciliation.missing_refs


def test_live_git_staging_checkout_merge_or_rebase_attempt_blocks_candidate() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet(
        {
            **PACKET_POLICIES,
            "reconciliations": [
                {
                    "reconciliation_id": "drift-5",
                    "status": "reconciled",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "dirty_worktree_refs": ["clean-status"],
                    "conflict_refs": ["no-conflict"],
                    "preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "merge_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_repo_worktree_drift_live_operation_blocked"
    assert "live_repo_worktree_reconciliation_operation_attempted" in packet["reconciliations"][0]["blocker_refs"]


def test_empty_payload_requests_repo_worktree_drift_inventory() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_repo_worktree_drift_reconciliation_inventory"]


def test_still_open_state_routes_to_completion_receipts() -> None:
    packet = build_codex_repo_worktree_drift_reconciliation_readiness_packet(
        {
            **PACKET_POLICIES,
            "reconciliations": [
                {
                    "reconciliation_id": "drift-6",
                    "status": "checking",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "dirty_worktree_refs": ["dirty-status"],
                    "conflict_refs": ["no-conflict"],
                    "preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_repo_worktree_drift_still_open"
    assert packet["next_actions"] == [
        "wait_for_repo_worktree_drift_resolution",
        "attach_repo_worktree_drift_receipts",
    ]


def test_dataclass_like_reconciliation_is_accepted_by_summarizer() -> None:
    @dataclass
    class Reconciliation:
        reconciliation_id: str
        status: str
        worktree_ref: str
        branch_refs: list[str]
        base_refs: list[str]
        head_refs: list[str]
        dirty_worktree_refs: list[str]
        conflict_refs: list[str]
        preservation_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    reconciliation = summarize_codex_repo_worktree_drift_reconciliation(
        Reconciliation(
            "drift-7",
            "closed",
            "worktree",
            ["branch"],
            ["base"],
            ["head"],
            ["clean-status"],
            ["no-conflict"],
            ["preservation"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert reconciliation.reconciliation_id == "drift-7"
    assert reconciliation.status == "closed"
    assert reconciliation.readiness_state == "ready"
