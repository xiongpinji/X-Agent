from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_human_approval_escalation_readiness_packet import (
    build_codex_human_approval_escalation_readiness_packet,
    summarize_codex_human_approval_escalation,
)


PACKET_POLICIES = {
    "approval_policy": "approval-policy",
    "escalation_policy": "escalation-policy",
    "timeout_policy": "timeout-policy",
    "decision_policy": "decision-policy",
    "approval_manifest_ref": "approval-manifest",
    "approval_governance_ref": "approval-governance",
}


def test_ready_human_approval_has_guarded_decision_evidence() -> None:
    packet = build_codex_human_approval_escalation_readiness_packet(
        {
            **PACKET_POLICIES,
            "approvals": [
                {
                    "approval_id": "approval-1",
                    "status": "approved",
                    "risk_level": "medium",
                    "approval_request_ref": "request",
                    "approver_refs": ["approver"],
                    "risk_refs": ["risk"],
                    "timeout_refs": ["timeout"],
                    "escalation_refs": ["escalation"],
                    "decision_receipt_refs": ["decision"],
                    "denial_refs": ["denial-policy"],
                    "notification_refs": ["notification"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_human_approval_escalation_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["approval_count"] == 1
    assert packet["summary"]["decision_receipt_ref_count"] == 1
    assert packet["next_actions"] == ["share_human_approval_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_human_approval_escalation_readiness_packet(
        {
            "approvals": [
                {
                    "approval_id": "approval-1",
                    "status": "recorded",
                    "risk_level": "low",
                    "approval_request_ref": "request",
                    "approver_refs": ["approver"],
                    "risk_refs": ["risk"],
                    "timeout_refs": ["timeout"],
                    "notification_refs": ["notification"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_human_approval_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "approval_policy_ref",
        "escalation_policy_ref",
        "timeout_policy_ref",
        "decision_policy_ref",
        "approval_manifest_ref",
        "approval_governance_ref",
    ]


def test_expired_or_timed_out_approval_blocks() -> None:
    packet = build_codex_human_approval_escalation_readiness_packet(
        {
            **PACKET_POLICIES,
            "approvals": [
                {
                    "approval_id": "approval-2",
                    "status": "timed-out",
                    "risk_level": "high",
                    "approval_request_ref": "request",
                    "approver_refs": ["approver"],
                    "risk_refs": ["risk"],
                    "timeout_refs": ["timeout"],
                    "escalation_refs": ["escalation"],
                    "notification_refs": ["notification"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_human_approval_status_failed"
    assert packet["next_actions"] == [
        "resolve_human_approval_blockers",
        "refresh_human_approval_readiness",
    ]


def test_high_risk_approval_requires_escalation_and_decision_refs() -> None:
    approval = summarize_codex_human_approval_escalation(
        {
            "approval_id": "approval-3",
            "status": "accepted",
            "risk_level": "critical",
            "approval_request_ref": "request",
            "approver_refs": ["approver"],
            "risk_refs": ["risk"],
            "timeout_refs": ["timeout"],
            "notification_refs": ["notification"],
            "artifact_refs": ["artifact"],
        }
    )

    assert approval.readiness_state == "needs_review"
    assert "escalation_refs" in approval.missing_refs
    assert "decision_receipt_refs" in approval.missing_refs


def test_denied_approval_requires_denial_refs() -> None:
    approval = summarize_codex_human_approval_escalation(
        {
            "approval_id": "approval-4",
            "status": "rejected",
            "risk_level": "medium",
            "approval_request_ref": "request",
            "approver_refs": ["approver"],
            "risk_refs": ["risk"],
            "timeout_refs": ["timeout"],
            "notification_refs": ["notification"],
            "artifact_refs": ["artifact"],
        }
    )

    assert approval.readiness_state == "needs_review"
    assert "human_approval_denied" in approval.warnings
    assert "denial_refs" in approval.missing_refs


def test_live_approval_dispatch_or_notification_attempt_blocks_candidate() -> None:
    packet = build_codex_human_approval_escalation_readiness_packet(
        {
            **PACKET_POLICIES,
            "approvals": [
                {
                    "approval_id": "approval-5",
                    "status": "recorded",
                    "risk_level": "medium",
                    "approval_request_ref": "request",
                    "approver_refs": ["approver"],
                    "risk_refs": ["risk"],
                    "timeout_refs": ["timeout"],
                    "notification_refs": ["notification"],
                    "artifact_refs": ["artifact"],
                    "approval_dispatch_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_human_approval_live_dispatch_blocked"
    assert "live_human_approval_dispatch_attempted" in packet["approvals"][0]["blockers"]


def test_empty_payload_requests_human_approval_inventory() -> None:
    packet = build_codex_human_approval_escalation_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_human_approval_inventory"]


def test_dataclass_like_human_approval_is_accepted_by_summarizer() -> None:
    @dataclass
    class HumanApproval:
        approval_id: str
        status: str
        risk_level: str
        approval_request_ref: str
        approver_refs: list[str]
        risk_refs: list[str]
        timeout_refs: list[str]
        escalation_refs: list[str]
        decision_receipt_refs: list[str]
        denial_refs: list[str]
        notification_refs: list[str]
        artifact_refs: list[str]

    approval = summarize_codex_human_approval_escalation(
        HumanApproval(
            "approval-6",
            "passed",
            "medium",
            "request",
            ["approver"],
            ["risk"],
            ["timeout"],
            ["escalation"],
            ["decision"],
            ["denial-policy"],
            ["notification"],
            ["artifact"],
        )
    )

    assert approval.approval_id == "approval-6"
    assert approval.status == "passed"
    assert approval.readiness_state == "ready"
