from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_workspace_diff_readiness_packet import (
    build_codex_workspace_diff_readiness_packet,
    summarize_codex_workspace_diff,
)


PACKET_POLICIES = {
    "diff_policy": "diff-policy",
    "patch_policy": "patch-policy",
    "conflict_policy": "conflict-policy",
    "artifact_policy": "artifact-policy",
    "workspace_manifest_ref": "workspace-manifest",
    "review_matrix_ref": "review-matrix",
}


def test_ready_workspace_diff_has_review_evidence() -> None:
    packet = build_codex_workspace_diff_readiness_packet(
        {
            **PACKET_POLICIES,
            "diffs": [
                {
                    "diff_id": "diff-1",
                    "status": "reviewed",
                    "workspace_ref": "workspace-1",
                    "changed_file_refs": ["backend/app/core/example.py"],
                    "diff_summary_refs": ["diff-summary"],
                    "patch_refs": ["patch"],
                    "conflict_refs": ["no-conflict"],
                    "staged_state_refs": ["staged-clean"],
                    "unstaged_state_refs": ["unstaged-clean"],
                    "generated_artifact_refs": ["generated-artifact"],
                    "file_risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_workspace_diff_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["diff_count"] == 1
    assert packet["summary"]["changed_file_ref_count"] == 1
    assert packet["next_actions"] == ["share_workspace_diff_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_workspace_diff_readiness_packet(
        {
            "diffs": [
                {
                    "diff_id": "diff-1",
                    "status": "reviewed",
                    "workspace_ref": "workspace-1",
                    "changed_file_refs": ["file.py"],
                    "diff_summary_refs": ["summary"],
                    "patch_refs": ["patch"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "generated_artifact_refs": ["generated"],
                    "file_risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_workspace_diff_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "diff_policy_ref",
        "patch_policy_ref",
        "conflict_policy_ref",
        "artifact_policy_ref",
        "workspace_manifest_ref",
        "review_matrix_ref",
    ]


def test_conflicted_workspace_diff_requires_conflict_refs_and_blocks() -> None:
    packet = build_codex_workspace_diff_readiness_packet(
        {
            **PACKET_POLICIES,
            "diffs": [
                {
                    "diff_id": "diff-2",
                    "status": "conflicted",
                    "workspace_ref": "workspace-2",
                    "changed_file_refs": ["file.py"],
                    "diff_summary_refs": ["summary"],
                    "patch_refs": ["patch"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "generated_artifact_refs": ["generated"],
                    "file_risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    diff = packet["diffs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_workspace_diff_status_failed"
    assert "conflict_refs" in diff["missing_refs"]
    assert packet["next_actions"] == ["resolve_workspace_diff_blockers", "refresh_workspace_diff_readiness"]


def test_missing_diff_patch_state_artifact_and_risk_refs_needs_review() -> None:
    diff = summarize_codex_workspace_diff(
        {
            "diff_id": "diff-3",
            "status": "clean",
            "workspace_ref": "workspace-3",
            "changed_file_refs": ["file.py"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert diff.readiness_state == "needs_review"
    assert "diff_summary_refs" in diff.missing_refs
    assert "patch_refs" in diff.missing_refs
    assert "staged_state_refs" in diff.missing_refs
    assert "unstaged_state_refs" in diff.missing_refs
    assert "generated_artifact_refs" in diff.missing_refs
    assert "file_risk_refs" in diff.missing_refs


def test_live_git_or_patch_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_workspace_diff_readiness_packet(
        {
            **PACKET_POLICIES,
            "diffs": [
                {
                    "diff_id": "diff-4",
                    "status": "validated",
                    "workspace_ref": "workspace-4",
                    "changed_file_refs": ["file.py"],
                    "diff_summary_refs": ["summary"],
                    "patch_refs": ["patch"],
                    "conflict_refs": ["no-conflict"],
                    "staged_state_refs": ["staged"],
                    "unstaged_state_refs": ["unstaged"],
                    "generated_artifact_refs": ["generated"],
                    "file_risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "patch_application_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_workspace_diff_live_mutation_blocked"
    assert "live_workspace_mutation_attempted" in packet["diffs"][0]["blockers"]


def test_empty_payload_requests_workspace_diff_inventory() -> None:
    packet = build_codex_workspace_diff_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_workspace_diff_inventory"]


def test_dataclass_like_diff_is_accepted_by_summarizer() -> None:
    @dataclass
    class Diff:
        diff_id: str
        status: str
        workspace_ref: str
        changed_file_refs: list[str]
        diff_summary_refs: list[str]
        patch_refs: list[str]
        conflict_refs: list[str]
        staged_state_refs: list[str]
        unstaged_state_refs: list[str]
        generated_artifact_refs: list[str]
        file_risk_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    diff = summarize_codex_workspace_diff(
        Diff(
            "diff-5",
            "passed",
            "workspace-5",
            ["file.py"],
            ["summary"],
            ["patch"],
            ["no-conflict"],
            ["staged"],
            ["unstaged"],
            ["generated"],
            ["risk"],
            ["validation"],
            ["artifact"],
        )
    )

    assert diff.diff_id == "diff-5"
    assert diff.status == "passed"
    assert diff.readiness_state == "ready"
