from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_task_intake_clarification_readiness_packet import (
    build_codex_task_intake_clarification_readiness_packet,
    summarize_codex_task_intake_clarification,
)


PACKET_POLICIES = {
    "intake_policy": "intake-policy",
    "clarification_policy": "clarification-policy",
    "scope_policy": "scope-policy",
    "acceptance_policy": "acceptance-policy",
    "task_intake_manifest_ref": "task-intake-manifest",
    "request_understanding_governance_ref": "request-understanding-governance",
}


def test_ready_task_intake_has_request_scope_and_acceptance_evidence() -> None:
    packet = build_codex_task_intake_clarification_readiness_packet(
        {
            **PACKET_POLICIES,
            "intakes": [
                {
                    "intake_id": "intake-1",
                    "status": "clarified",
                    "user_request_ref": "request",
                    "ambiguity_refs": ["ambiguity"],
                    "assumption_refs": ["assumption"],
                    "clarification_refs": ["clarification"],
                    "scope_refs": ["scope"],
                    "acceptance_criteria_refs": ["criteria"],
                    "constraint_refs": ["constraints"],
                    "risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "ambiguous_request_detected": True,
                    "assumptions_used": True,
                }
            ],
        }
    )

    assert packet["kind"] == "codex_task_intake_clarification_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["intake_count"] == 1
    assert packet["summary"]["clarification_ref_count"] == 1
    assert packet["next_actions"] == [
        "share_task_intake_clarification_readiness_with_mainline"
    ]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_task_intake_clarification_readiness_packet(
        {
            "intakes": [
                {
                    "intake_id": "intake-2",
                    "status": "clarified",
                    "user_request_ref": "request",
                    "scope_refs": ["scope"],
                    "acceptance_criteria_refs": ["criteria"],
                    "constraint_refs": ["constraints"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == (
        "codex_task_intake_clarification_packet_missing_evidence"
    )
    assert packet["packet_missing_refs"] == [
        "intake_policy_ref",
        "clarification_policy_ref",
        "scope_policy_ref",
        "acceptance_policy_ref",
        "task_intake_manifest_ref",
        "request_understanding_governance_ref",
    ]


def test_ambiguous_request_requires_ambiguity_and_clarification_refs() -> None:
    intake = summarize_codex_task_intake_clarification(
        {
            "intake_id": "intake-3",
            "status": "clarified",
            "user_request_ref": "request",
            "scope_refs": ["scope"],
            "acceptance_criteria_refs": ["criteria"],
            "constraint_refs": ["constraints"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "ambiguous_request_detected": True,
        }
    )

    assert intake.readiness_state == "needs_review"
    assert "ambiguity_refs" in intake.missing_refs
    assert "clarification_refs" in intake.missing_refs


def test_missing_request_scope_acceptance_constraints_and_validation_refs_needs_review() -> None:
    intake = summarize_codex_task_intake_clarification(
        {
            "intake_id": "intake-4",
            "status": "scoped",
            "artifact_refs": ["artifact"],
        }
    )

    assert intake.readiness_state == "needs_review"
    assert "user_request_ref" in intake.missing_refs
    assert "scope_refs" in intake.missing_refs
    assert "acceptance_criteria_refs" in intake.missing_refs
    assert "constraint_refs" in intake.missing_refs
    assert "validation_receipt_refs" in intake.missing_refs


def test_failed_or_risky_intake_requires_risk_refs_and_blocks() -> None:
    packet = build_codex_task_intake_clarification_readiness_packet(
        {
            **PACKET_POLICIES,
            "intakes": [
                {
                    "intake_id": "intake-5",
                    "status": "blocked",
                    "user_request_ref": "request",
                    "scope_refs": ["scope"],
                    "acceptance_criteria_refs": ["criteria"],
                    "constraint_refs": ["constraints"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    intake = packet["intakes"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_task_intake_clarification_status_failed"
    assert "risk_refs" in intake["missing_refs"]


def test_live_user_message_prompt_or_task_dispatch_attempt_blocks_candidate() -> None:
    packet = build_codex_task_intake_clarification_readiness_packet(
        {
            **PACKET_POLICIES,
            "intakes": [
                {
                    "intake_id": "intake-6",
                    "status": "clarified",
                    "user_request_ref": "request",
                    "scope_refs": ["scope"],
                    "acceptance_criteria_refs": ["criteria"],
                    "constraint_refs": ["constraints"],
                    "risk_refs": ["risk"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "prompt_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == (
        "codex_task_intake_clarification_live_operation_blocked"
    )
    assert "live_task_intake_operation_attempted" in packet["intakes"][0]["blockers"]


def test_empty_payload_requests_task_intake_inventory() -> None:
    packet = build_codex_task_intake_clarification_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_task_intake_clarification_inventory"]


def test_dataclass_like_task_intake_is_accepted_by_summarizer() -> None:
    @dataclass
    class TaskIntake:
        intake_id: str
        status: str
        user_request_ref: str
        ambiguity_refs: list[str]
        assumption_refs: list[str]
        clarification_refs: list[str]
        scope_refs: list[str]
        acceptance_criteria_refs: list[str]
        constraint_refs: list[str]
        risk_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    intake = summarize_codex_task_intake_clarification(
        TaskIntake(
            "intake-7",
            "validated",
            "request",
            ["ambiguity"],
            ["assumption"],
            ["clarification"],
            ["scope"],
            ["criteria"],
            ["constraints"],
            ["risk"],
            ["validation"],
            ["artifact"],
        )
    )

    assert intake.intake_id == "intake-7"
    assert intake.status == "validated"
    assert intake.readiness_state == "ready"
