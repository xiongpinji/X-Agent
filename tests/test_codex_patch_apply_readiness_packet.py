from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_patch_apply_readiness_packet import (
    build_codex_patch_apply_readiness_packet,
    summarize_codex_patch_apply,
)


PACKET_POLICIES = {
    "patch_policy": "patch-policy",
    "apply_policy": "apply-policy",
    "conflict_policy": "conflict-policy",
    "rollback_policy": "rollback-policy",
    "patch_manifest_ref": "patch-manifest",
    "apply_governance_ref": "apply-governance",
}


def test_ready_patch_apply_has_safe_apply_evidence() -> None:
    packet = build_codex_patch_apply_readiness_packet(
        {
            **PACKET_POLICIES,
            "patches": [
                {
                    "patch_id": "patch-1",
                    "status": "dry-run-passed",
                    "patch_ref": "patch-ref",
                    "target_file_refs": ["target.py"],
                    "preimage_refs": ["preimage"],
                    "postimage_refs": ["postimage"],
                    "conflict_refs": ["conflict-scan"],
                    "dry_run_refs": ["dry-run"],
                    "backup_refs": ["backup-plan"],
                    "rollback_refs": ["rollback-plan"],
                    "apply_transcript_refs": ["apply-transcript"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_patch_apply_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["patch_count"] == 1
    assert packet["summary"]["dry_run_ref_count"] == 1
    assert packet["next_actions"] == ["share_patch_apply_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_patch_apply_readiness_packet(
        {
            "patches": [
                {
                    "patch_id": "patch-1",
                    "status": "validated",
                    "patch_ref": "patch-ref",
                    "target_file_refs": ["target.py"],
                    "preimage_refs": ["preimage"],
                    "postimage_refs": ["postimage"],
                    "dry_run_refs": ["dry-run"],
                    "backup_refs": ["backup"],
                    "rollback_refs": ["rollback"],
                    "apply_transcript_refs": ["apply-transcript"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_patch_apply_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "patch_policy_ref",
        "apply_policy_ref",
        "conflict_policy_ref",
        "rollback_policy_ref",
        "patch_manifest_ref",
        "apply_governance_ref",
    ]


def test_conflicted_or_failed_patch_requires_conflict_ref_and_blocks() -> None:
    packet = build_codex_patch_apply_readiness_packet(
        {
            **PACKET_POLICIES,
            "patches": [
                {
                    "patch_id": "patch-2",
                    "status": "dry-run-failed",
                    "patch_ref": "patch-ref",
                    "target_file_refs": ["target.py"],
                    "preimage_refs": ["preimage"],
                    "postimage_refs": ["postimage"],
                    "dry_run_refs": ["dry-run"],
                    "backup_refs": ["backup"],
                    "rollback_refs": ["rollback"],
                    "apply_transcript_refs": ["apply-transcript"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    patch = packet["patches"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_patch_apply_status_failed"
    assert "conflict_refs" in patch["missing_refs"]
    assert packet["next_actions"] == ["resolve_patch_apply_blockers", "refresh_patch_apply_readiness"]


def test_missing_preimage_dry_run_rollback_and_receipt_refs_needs_review() -> None:
    patch = summarize_codex_patch_apply(
        {
            "patch_id": "patch-3",
            "status": "recorded",
            "patch_ref": "patch-ref",
            "target_file_refs": ["target.py"],
            "artifact_refs": ["artifact"],
        }
    )

    assert patch.readiness_state == "needs_review"
    assert "preimage_refs" in patch.missing_refs
    assert "postimage_refs" in patch.missing_refs
    assert "dry_run_refs" in patch.missing_refs
    assert "backup_refs" in patch.missing_refs
    assert "rollback_refs" in patch.missing_refs
    assert "validation_receipt_refs" in patch.missing_refs


def test_live_patch_application_or_git_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_patch_apply_readiness_packet(
        {
            **PACKET_POLICIES,
            "patches": [
                {
                    "patch_id": "patch-4",
                    "status": "validated",
                    "patch_ref": "patch-ref",
                    "target_file_refs": ["target.py"],
                    "preimage_refs": ["preimage"],
                    "postimage_refs": ["postimage"],
                    "conflict_refs": ["conflict-scan"],
                    "dry_run_refs": ["dry-run"],
                    "backup_refs": ["backup"],
                    "rollback_refs": ["rollback"],
                    "apply_transcript_refs": ["apply-transcript"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "patch_application_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_patch_apply_live_mutation_blocked"
    assert "live_patch_apply_mutation_attempted" in packet["patches"][0]["blockers"]


def test_empty_payload_requests_patch_apply_inventory() -> None:
    packet = build_codex_patch_apply_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_patch_apply_inventory"]


def test_dataclass_like_patch_apply_is_accepted_by_summarizer() -> None:
    @dataclass
    class PatchApply:
        patch_id: str
        status: str
        patch_ref: str
        target_file_refs: list[str]
        preimage_refs: list[str]
        postimage_refs: list[str]
        conflict_refs: list[str]
        dry_run_refs: list[str]
        backup_refs: list[str]
        rollback_refs: list[str]
        apply_transcript_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    patch = summarize_codex_patch_apply(
        PatchApply(
            "patch-5",
            "passed",
            "patch-ref",
            ["target.py"],
            ["preimage"],
            ["postimage"],
            ["conflict-scan"],
            ["dry-run"],
            ["backup"],
            ["rollback"],
            ["apply-transcript"],
            ["validation"],
            ["artifact"],
        )
    )

    assert patch.patch_id == "patch-5"
    assert patch.status == "passed"
    assert patch.readiness_state == "ready"
