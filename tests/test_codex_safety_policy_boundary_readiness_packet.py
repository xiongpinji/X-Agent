from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_safety_policy_boundary_readiness_packet import (
    build_codex_safety_policy_boundary_readiness_packet,
    summarize_codex_safety_policy_boundary,
)


PACKET_POLICIES = {
    "safety_policy": "safety-policy",
    "refusal_policy": "refusal-policy",
    "risky_operation_policy": "risky-operation-policy",
    "escalation_policy": "escalation-policy",
    "safety_boundary_manifest_ref": "safety-boundary-manifest",
    "policy_governance_ref": "policy-governance",
}


def test_ready_safety_policy_boundary_has_policy_and_audit_evidence() -> None:
    packet = build_codex_safety_policy_boundary_readiness_packet(
        {
            **PACKET_POLICIES,
            "boundaries": [
                {
                    "boundary_id": "boundary-1",
                    "status": "approved",
                    "subject_ref": "operation",
                    "refusal_refs": ["refusal"],
                    "risky_operation_refs": ["risk"],
                    "policy_decision_refs": ["decision"],
                    "escalation_refs": ["escalation"],
                    "user_approval_refs": ["approval"],
                    "sandbox_policy_refs": ["sandbox"],
                    "audit_refs": ["audit"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "risky_operation_detected": True,
                    "approval_required": True,
                }
            ],
        }
    )

    assert packet["kind"] == "codex_safety_policy_boundary_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["boundary_count"] == 1
    assert packet["summary"]["policy_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_safety_policy_boundary_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_safety_policy_boundary_readiness_packet(
        {
            "boundaries": [
                {
                    "boundary_id": "boundary-2",
                    "status": "approved",
                    "subject_ref": "operation",
                    "policy_decision_refs": ["decision"],
                    "sandbox_policy_refs": ["sandbox"],
                    "audit_refs": ["audit"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == (
        "codex_safety_policy_boundary_packet_missing_evidence"
    )
    assert packet["packet_missing_refs"] == [
        "safety_policy_ref",
        "refusal_policy_ref",
        "risky_operation_policy_ref",
        "escalation_policy_ref",
        "safety_boundary_manifest_ref",
        "policy_governance_ref",
    ]


def test_risky_operation_requires_risk_and_policy_decision_refs() -> None:
    boundary = summarize_codex_safety_policy_boundary(
        {
            "boundary_id": "boundary-3",
            "status": "reviewed",
            "subject_ref": "operation",
            "sandbox_policy_refs": ["sandbox"],
            "audit_refs": ["audit"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "risky_operation_detected": True,
        }
    )

    assert boundary.readiness_state == "needs_review"
    assert "risky_operation_refs" in boundary.missing_refs
    assert "policy_decision_refs" in boundary.missing_refs


def test_refused_or_escalated_boundary_requires_refusal_and_escalation_refs() -> None:
    boundary = summarize_codex_safety_policy_boundary(
        {
            "boundary_id": "boundary-4",
            "status": "refused",
            "subject_ref": "operation",
            "policy_decision_refs": ["decision"],
            "sandbox_policy_refs": ["sandbox"],
            "audit_refs": ["audit"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "refusal_required": True,
            "escalation_required": True,
        }
    )

    assert boundary.readiness_state == "needs_review"
    assert "refusal_refs" in boundary.missing_refs
    assert "escalation_refs" in boundary.missing_refs


def test_policy_violation_or_unsafe_status_blocks_candidate() -> None:
    packet = build_codex_safety_policy_boundary_readiness_packet(
        {
            **PACKET_POLICIES,
            "boundaries": [
                {
                    "boundary_id": "boundary-5",
                    "status": "unsafe",
                    "subject_ref": "operation",
                    "policy_decision_refs": ["decision"],
                    "sandbox_policy_refs": ["sandbox"],
                    "audit_refs": ["audit"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_safety_policy_boundary_status_failed"
    assert "safety_policy_boundary_status_failed" in packet["boundaries"][0]["blockers"]


def test_live_policy_enforcement_refusal_or_tool_execution_blocks_candidate() -> None:
    packet = build_codex_safety_policy_boundary_readiness_packet(
        {
            **PACKET_POLICIES,
            "boundaries": [
                {
                    "boundary_id": "boundary-6",
                    "status": "approved",
                    "subject_ref": "operation",
                    "policy_decision_refs": ["decision"],
                    "sandbox_policy_refs": ["sandbox"],
                    "audit_refs": ["audit"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "tool_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == (
        "codex_safety_policy_boundary_live_operation_blocked"
    )
    assert "live_safety_policy_boundary_operation_attempted" in packet["boundaries"][0][
        "blockers"
    ]


def test_empty_payload_requests_safety_policy_boundary_inventory() -> None:
    packet = build_codex_safety_policy_boundary_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_safety_policy_boundary_inventory"]


def test_dataclass_like_safety_policy_boundary_is_accepted_by_summarizer() -> None:
    @dataclass
    class SafetyBoundary:
        boundary_id: str
        status: str
        subject_ref: str
        refusal_refs: list[str]
        risky_operation_refs: list[str]
        policy_decision_refs: list[str]
        escalation_refs: list[str]
        user_approval_refs: list[str]
        sandbox_policy_refs: list[str]
        audit_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    boundary = summarize_codex_safety_policy_boundary(
        SafetyBoundary(
            "boundary-7",
            "validated",
            "operation",
            ["refusal"],
            ["risk"],
            ["decision"],
            ["escalation"],
            ["approval"],
            ["sandbox"],
            ["audit"],
            ["validation"],
            ["artifact"],
        )
    )

    assert boundary.boundary_id == "boundary-7"
    assert boundary.status == "validated"
    assert boundary.readiness_state == "ready"
