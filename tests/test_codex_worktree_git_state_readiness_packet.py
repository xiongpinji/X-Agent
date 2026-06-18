from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_worktree_git_state_readiness_packet import (
    build_codex_worktree_git_state_readiness_packet,
    summarize_codex_worktree_git_state,
)


PACKET_POLICIES = {
    "worktree_policy": "worktree-policy",
    "git_state_policy": "git-state-policy",
    "staging_policy": "staging-policy",
    "commit_policy": "commit-policy",
    "worktree_manifest_ref": "worktree-manifest",
    "git_state_governance_ref": "git-state-governance",
}


def test_ready_worktree_git_state_has_repository_state_evidence() -> None:
    packet = build_codex_worktree_git_state_readiness_packet(
        {
            **PACKET_POLICIES,
            "states": [
                {
                    "state_id": "git-1",
                    "status": "clean",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "user_change_preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_worktree_git_state_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["state_count"] == 1
    assert packet["summary"]["branch_ref_count"] == 1
    assert packet["next_actions"] == ["share_worktree_git_state_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_worktree_git_state_readiness_packet(
        {
            "states": [
                {
                    "state_id": "git-2",
                    "status": "recorded",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "user_change_preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_worktree_git_state_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "worktree_policy_ref",
        "git_state_policy_ref",
        "staging_policy_ref",
        "commit_policy_ref",
        "worktree_manifest_ref",
        "git_state_governance_ref",
    ]


def test_conflicted_or_dirty_state_requires_conflict_or_dirty_refs_and_blocks() -> None:
    packet = build_codex_worktree_git_state_readiness_packet(
        {
            **PACKET_POLICIES,
            "states": [
                {
                    "state_id": "git-3",
                    "status": "conflicted",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    state = packet["states"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_worktree_git_state_failed"
    assert "conflict_refs" in state["missing_refs"]
    assert "user_change_preservation_refs" in state["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_worktree_git_state_blockers",
        "refresh_worktree_git_state_readiness",
    ]


def test_missing_branch_base_head_and_state_refs_needs_review() -> None:
    state = summarize_codex_worktree_git_state(
        {
            "state_id": "git-4",
            "status": "recorded",
            "worktree_ref": "worktree",
        }
    )

    assert state.readiness_state == "needs_review"
    assert "branch_refs" in state.missing_refs
    assert "base_refs" in state.missing_refs
    assert "head_refs" in state.missing_refs
    assert "staged_state_refs" in state.missing_refs
    assert "unstaged_state_refs" in state.missing_refs


def test_dirty_or_unstaged_state_requires_user_change_preservation_refs() -> None:
    state = summarize_codex_worktree_git_state(
        {
            "state_id": "git-5",
            "status": "recorded",
            "worktree_ref": "worktree",
            "branch_refs": ["branch"],
            "base_refs": ["base"],
            "head_refs": ["head"],
            "staged_state_refs": ["staged"],
            "unstaged_state_refs": ["unstaged"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert state.readiness_state == "needs_review"
    assert "user_change_preservation_refs" in state.missing_refs


def test_live_git_or_worktree_operation_attempt_blocks_candidate() -> None:
    packet = build_codex_worktree_git_state_readiness_packet(
        {
            **PACKET_POLICIES,
            "states": [
                {
                    "state_id": "git-6",
                    "status": "recorded",
                    "worktree_ref": "worktree",
                    "branch_refs": ["branch"],
                    "base_refs": ["base"],
                    "head_refs": ["head"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "user_change_preservation_refs": ["preservation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "git_command_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_worktree_git_state_live_operation_blocked"
    assert "live_git_or_worktree_operation_attempted" in packet["states"][0]["blockers"]


def test_empty_payload_requests_worktree_git_state_inventory() -> None:
    packet = build_codex_worktree_git_state_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_worktree_git_state_inventory"]


def test_dataclass_like_worktree_state_is_accepted_by_summarizer() -> None:
    @dataclass
    class WorktreeState:
        state_id: str
        status: str
        worktree_ref: str
        branch_refs: list[str]
        base_refs: list[str]
        head_refs: list[str]
        staged_state_refs: list[str]
        unstaged_state_refs: list[str]
        user_change_preservation_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    state = summarize_codex_worktree_git_state(
        WorktreeState(
            "git-7",
            "passed",
            "worktree",
            ["branch"],
            ["base"],
            ["head"],
            ["staged"],
            ["unstaged"],
            ["preservation"],
            ["validation"],
            ["artifact"],
        )
    )

    assert state.state_id == "git-7"
    assert state.status == "passed"
    assert state.readiness_state == "ready"
