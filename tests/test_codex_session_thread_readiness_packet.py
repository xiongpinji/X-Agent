from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_session_thread_readiness_packet import (
    build_codex_session_thread_readiness_packet,
    summarize_codex_session_thread,
)


PACKET_POLICIES = {
    "session_policy": "session-policy",
    "resume_policy": "resume-policy",
    "handoff_policy": "handoff-policy",
    "compaction_policy": "compaction-policy",
    "session_manifest_ref": "session-manifest",
    "continuity_matrix_ref": "continuity-matrix",
}


def test_ready_session_thread_has_continuity_evidence() -> None:
    packet = build_codex_session_thread_readiness_packet(
        {
            **PACKET_POLICIES,
            "sessions": [
                {
                    "session_id": "session-1",
                    "status": "resumable",
                    "thread_ref": "thread-1",
                    "task_ref": "task-1",
                    "conversation_state_refs": ["conversation-state"],
                    "resume_token_refs": ["resume-token"],
                    "task_continuation_refs": ["continuation"],
                    "handoff_refs": ["handoff"],
                    "branch_worktree_refs": ["worktree"],
                    "interruption_refs": ["interruption-policy"],
                    "compaction_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_session_thread_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["session_count"] == 1
    assert packet["summary"]["resume_token_ref_count"] == 1
    assert packet["next_actions"] == ["share_session_thread_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_session_thread_readiness_packet(
        {
            "sessions": [
                {
                    "session_id": "session-1",
                    "status": "resumable",
                    "thread_ref": "thread-1",
                    "task_ref": "task-1",
                    "conversation_state_refs": ["conversation"],
                    "resume_token_refs": ["resume"],
                    "task_continuation_refs": ["continuation"],
                    "handoff_refs": ["handoff"],
                    "branch_worktree_refs": ["worktree"],
                    "compaction_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_session_thread_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "session_policy_ref",
        "resume_policy_ref",
        "handoff_policy_ref",
        "compaction_policy_ref",
        "session_manifest_ref",
        "continuity_matrix_ref",
    ]


def test_lost_session_requires_interruption_refs_and_blocks() -> None:
    packet = build_codex_session_thread_readiness_packet(
        {
            **PACKET_POLICIES,
            "sessions": [
                {
                    "session_id": "session-2",
                    "status": "lost",
                    "thread_ref": "thread-2",
                    "task_ref": "task-2",
                    "conversation_state_refs": ["conversation"],
                    "resume_token_refs": ["resume"],
                    "task_continuation_refs": ["continuation"],
                    "handoff_refs": ["handoff"],
                    "branch_worktree_refs": ["worktree"],
                    "compaction_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    session = packet["sessions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_session_thread_status_failed"
    assert "interruption_refs" in session["missing_refs"]
    assert packet["next_actions"] == ["resolve_session_thread_blockers", "refresh_session_thread_readiness"]


def test_missing_resume_handoff_worktree_and_compaction_refs_needs_review() -> None:
    session = summarize_codex_session_thread(
        {
            "session_id": "session-3",
            "status": "continued",
            "thread_ref": "thread-3",
            "task_ref": "task-3",
            "conversation_state_refs": ["conversation"],
            "task_continuation_refs": ["continuation"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert session.readiness_state == "needs_review"
    assert "resume_token_refs" in session.missing_refs
    assert "handoff_refs" in session.missing_refs
    assert "branch_worktree_refs" in session.missing_refs
    assert "compaction_refs" in session.missing_refs


def test_live_session_mutation_or_resume_execution_attempt_blocks_candidate() -> None:
    packet = build_codex_session_thread_readiness_packet(
        {
            **PACKET_POLICIES,
            "sessions": [
                {
                    "session_id": "session-4",
                    "status": "validated",
                    "thread_ref": "thread-4",
                    "task_ref": "task-4",
                    "conversation_state_refs": ["conversation"],
                    "resume_token_refs": ["resume"],
                    "task_continuation_refs": ["continuation"],
                    "handoff_refs": ["handoff"],
                    "branch_worktree_refs": ["worktree"],
                    "interruption_refs": ["interruption"],
                    "compaction_refs": ["compaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "resume_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_session_thread_live_mutation_blocked"
    assert "live_session_mutation_attempted" in packet["sessions"][0]["blockers"]


def test_empty_payload_requests_session_thread_inventory() -> None:
    packet = build_codex_session_thread_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_session_thread_inventory"]


def test_dataclass_like_session_is_accepted_by_summarizer() -> None:
    @dataclass
    class Session:
        session_id: str
        status: str
        thread_ref: str
        task_ref: str
        conversation_state_refs: list[str]
        resume_token_refs: list[str]
        task_continuation_refs: list[str]
        handoff_refs: list[str]
        branch_worktree_refs: list[str]
        interruption_refs: list[str]
        compaction_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    session = summarize_codex_session_thread(
        Session(
            "session-5",
            "handoff-ready",
            "thread-5",
            "task-5",
            ["conversation"],
            ["resume"],
            ["continuation"],
            ["handoff"],
            ["worktree"],
            ["interruption"],
            ["compaction"],
            ["validation"],
            ["artifact"],
        )
    )

    assert session.session_id == "session-5"
    assert session.status == "handoff_ready"
    assert session.readiness_state == "ready"
