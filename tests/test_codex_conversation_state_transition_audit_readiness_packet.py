from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_conversation_state_transition_audit_readiness_packet import (
    build_codex_conversation_state_transition_audit_readiness_packet,
    summarize_codex_conversation_state_transition_audit,
)


PACKET_POLICIES = {
    "state_transition_policy": "state-transition-policy",
    "resume_policy": "resume-policy",
    "compaction_policy": "compaction-policy",
    "audit_policy": "audit-policy",
    "conversation_state_manifest_ref": "conversation-state-manifest",
    "state_transition_governance_ref": "state-transition-governance",
}


def test_ready_conversation_state_transition_has_state_evidence() -> None:
    packet = build_codex_conversation_state_transition_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "transitions": [
                {
                    "transition_id": "transition-1",
                    "status": "continued",
                    "thread_ref": "thread",
                    "previous_state_refs": ["previous-state"],
                    "current_state_refs": ["current-state"],
                    "transition_reason_refs": ["reason"],
                    "resume_refs": ["resume"],
                    "compaction_refs": ["compaction"],
                    "interruption_refs": ["interruption"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_conversation_state_transition_audit_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["transition_count"] == 1
    assert packet["summary"]["resume_ref_count"] == 1
    assert packet["next_actions"] == ["share_conversation_state_transition_audit_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_conversation_state_transition_audit_readiness_packet(
        {
            "transitions": [
                {
                    "transition_id": "transition-2",
                    "status": "recorded",
                    "thread_ref": "thread",
                    "previous_state_refs": ["previous-state"],
                    "current_state_refs": ["current-state"],
                    "transition_reason_refs": ["reason"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_conversation_state_transition_audit_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "state_transition_policy_ref",
        "resume_policy_ref",
        "compaction_policy_ref",
        "audit_policy_ref",
        "conversation_state_manifest_ref",
        "state_transition_governance_ref",
    ]


def test_lost_or_stale_transition_blocks_and_requires_interruption_refs() -> None:
    packet = build_codex_conversation_state_transition_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "transitions": [
                {
                    "transition_id": "transition-3",
                    "status": "lost",
                    "thread_ref": "thread",
                    "previous_state_refs": ["previous-state"],
                    "current_state_refs": ["current-state"],
                    "transition_reason_refs": ["reason"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    transition = packet["transitions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_conversation_state_transition_audit_status_failed"
    assert "interruption_refs" in transition["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_conversation_state_transition_audit_blockers",
        "refresh_conversation_state_transition_audit_readiness",
    ]


def test_missing_previous_current_reason_validation_artifact_and_owner_refs_needs_review() -> None:
    transition = summarize_codex_conversation_state_transition_audit(
        {
            "transition_id": "transition-4",
            "status": "recorded",
            "thread_ref": "thread",
        }
    )

    assert transition.readiness_state == "needs_review"
    assert "previous_state_refs" in transition.missing_refs
    assert "current_state_refs" in transition.missing_refs
    assert "transition_reason_refs" in transition.missing_refs
    assert "validation_receipt_refs" in transition.missing_refs
    assert "artifact_refs" in transition.missing_refs
    assert "owner_refs" in transition.missing_refs


def test_continued_transition_requires_resume_refs() -> None:
    transition = summarize_codex_conversation_state_transition_audit(
        {
            "transition_id": "transition-5",
            "status": "continued",
            "thread_ref": "thread",
            "previous_state_refs": ["previous-state"],
            "current_state_refs": ["current-state"],
            "transition_reason_refs": ["reason"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert transition.readiness_state == "needs_review"
    assert "resume_refs" in transition.missing_refs


def test_compacting_or_stale_transition_requires_compaction_refs() -> None:
    transition = summarize_codex_conversation_state_transition_audit(
        {
            "transition_id": "transition-6",
            "status": "compacting",
            "thread_ref": "thread",
            "previous_state_refs": ["previous-state"],
            "current_state_refs": ["current-state"],
            "transition_reason_refs": ["reason"],
            "interruption_refs": ["interruption"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert transition.readiness_state == "needs_review"
    assert "compaction_refs" in transition.missing_refs
    assert "conversation_state_transition_still_open" in transition.warnings


def test_live_thread_state_resume_or_compaction_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_conversation_state_transition_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "transitions": [
                {
                    "transition_id": "transition-7",
                    "status": "validated",
                    "thread_ref": "thread",
                    "previous_state_refs": ["previous-state"],
                    "current_state_refs": ["current-state"],
                    "transition_reason_refs": ["reason"],
                    "resume_refs": ["resume"],
                    "compaction_refs": ["compaction"],
                    "interruption_refs": ["interruption"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "resume_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_conversation_state_transition_audit_live_operation_blocked"
    assert "live_conversation_state_transition_operation_attempted" in packet["transitions"][0]["blockers"]


def test_empty_payload_requests_conversation_state_transition_inventory() -> None:
    packet = build_codex_conversation_state_transition_audit_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_conversation_state_transition_audit_inventory"]


def test_dataclass_like_conversation_state_transition_is_accepted_by_summarizer() -> None:
    @dataclass
    class ConversationStateTransition:
        transition_id: str
        status: str
        thread_ref: str
        previous_state_refs: list[str]
        current_state_refs: list[str]
        transition_reason_refs: list[str]
        resume_refs: list[str]
        compaction_refs: list[str]
        interruption_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    transition = summarize_codex_conversation_state_transition_audit(
        ConversationStateTransition(
            "transition-8",
            "transitioned",
            "thread",
            ["previous-state"],
            ["current-state"],
            ["reason"],
            ["resume"],
            ["compaction"],
            ["interruption"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert transition.transition_id == "transition-8"
    assert transition.status == "transitioned"
    assert transition.readiness_state == "ready"
