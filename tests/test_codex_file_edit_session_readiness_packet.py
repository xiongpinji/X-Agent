from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_file_edit_session_readiness_packet import (
    build_codex_file_edit_session_readiness_packet,
    summarize_codex_file_edit_session,
)


PACKET_POLICIES = {
    "edit_policy": "edit-policy",
    "preservation_policy": "preservation-policy",
    "formatting_policy": "formatting-policy",
    "validation_policy": "validation-policy",
    "edit_session_manifest_ref": "edit-session-manifest",
    "edit_governance_ref": "edit-governance",
}


def test_ready_file_edit_session_has_edit_governance_evidence() -> None:
    packet = build_codex_file_edit_session_readiness_packet(
        {
            **PACKET_POLICIES,
            "edit_sessions": [
                {
                    "edit_session_id": "edit-1",
                    "status": "validated",
                    "edit_intent_ref": "intent",
                    "target_file_refs": ["target.py"],
                    "read_before_write_refs": ["read-before-write"],
                    "user_change_preservation_refs": ["preservation"],
                    "patch_refs": ["patch"],
                    "formatting_refs": ["formatting"],
                    "conflict_refs": ["conflict-scan"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_file_edit_session_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["edit_session_count"] == 1
    assert packet["summary"]["read_before_write_ref_count"] == 1
    assert packet["next_actions"] == ["share_file_edit_session_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_file_edit_session_readiness_packet(
        {
            "edit_sessions": [
                {
                    "edit_session_id": "edit-1",
                    "status": "validated",
                    "edit_intent_ref": "intent",
                    "target_file_refs": ["target.py"],
                    "read_before_write_refs": ["read-before-write"],
                    "user_change_preservation_refs": ["preservation"],
                    "patch_refs": ["patch"],
                    "formatting_refs": ["formatting"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_file_edit_session_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "edit_policy_ref",
        "preservation_policy_ref",
        "formatting_policy_ref",
        "validation_policy_ref",
        "edit_session_manifest_ref",
        "edit_governance_ref",
    ]


def test_conflicted_or_stale_preimage_session_requires_conflict_ref_and_blocks() -> None:
    packet = build_codex_file_edit_session_readiness_packet(
        {
            **PACKET_POLICIES,
            "edit_sessions": [
                {
                    "edit_session_id": "edit-2",
                    "status": "stale-preimage",
                    "edit_intent_ref": "intent",
                    "target_file_refs": ["target.py"],
                    "read_before_write_refs": ["read-before-write"],
                    "user_change_preservation_refs": ["preservation"],
                    "patch_refs": ["patch"],
                    "formatting_refs": ["formatting"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    session = packet["edit_sessions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_file_edit_session_status_failed"
    assert "conflict_refs" in session["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_file_edit_session_blockers",
        "refresh_file_edit_session_readiness",
    ]


def test_missing_read_preservation_patch_formatting_and_receipt_refs_needs_review() -> None:
    session = summarize_codex_file_edit_session(
        {
            "edit_session_id": "edit-3",
            "status": "recorded",
            "edit_intent_ref": "intent",
            "target_file_refs": ["target.py"],
            "artifact_refs": ["artifact"],
        }
    )

    assert session.readiness_state == "needs_review"
    assert "read_before_write_refs" in session.missing_refs
    assert "user_change_preservation_refs" in session.missing_refs
    assert "patch_refs" in session.missing_refs
    assert "formatting_refs" in session.missing_refs
    assert "validation_receipt_refs" in session.missing_refs


def test_live_file_read_write_or_formatting_attempt_blocks_candidate() -> None:
    packet = build_codex_file_edit_session_readiness_packet(
        {
            **PACKET_POLICIES,
            "edit_sessions": [
                {
                    "edit_session_id": "edit-4",
                    "status": "validated",
                    "edit_intent_ref": "intent",
                    "target_file_refs": ["target.py"],
                    "read_before_write_refs": ["read-before-write"],
                    "user_change_preservation_refs": ["preservation"],
                    "patch_refs": ["patch"],
                    "formatting_refs": ["formatting"],
                    "conflict_refs": ["conflict-scan"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "file_write_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_file_edit_session_live_mutation_blocked"
    assert "live_file_edit_mutation_attempted" in packet["edit_sessions"][0]["blockers"]


def test_empty_payload_requests_file_edit_session_inventory() -> None:
    packet = build_codex_file_edit_session_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_file_edit_session_inventory"]


def test_dataclass_like_file_edit_session_is_accepted_by_summarizer() -> None:
    @dataclass
    class FileEditSession:
        edit_session_id: str
        status: str
        edit_intent_ref: str
        target_file_refs: list[str]
        read_before_write_refs: list[str]
        user_change_preservation_refs: list[str]
        patch_refs: list[str]
        formatting_refs: list[str]
        conflict_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    session = summarize_codex_file_edit_session(
        FileEditSession(
            "edit-5",
            "passed",
            "intent",
            ["target.py"],
            ["read-before-write"],
            ["preservation"],
            ["patch"],
            ["formatting"],
            ["conflict-scan"],
            ["validation"],
            ["artifact"],
        )
    )

    assert session.edit_session_id == "edit-5"
    assert session.status == "passed"
    assert session.readiness_state == "ready"
