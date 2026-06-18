from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_permission_escalation_audit_readiness_packet import (
    build_codex_permission_escalation_audit_readiness_packet,
    summarize_codex_permission_escalation_audit,
)


PACKET_POLICIES = {
    "approval_policy": "approval-policy",
    "sandbox_policy": "sandbox-policy",
    "command_prefix_policy": "command-prefix-policy",
    "escalation_policy": "escalation-policy",
    "permission_escalation_manifest_ref": "permission-escalation-manifest",
    "controlled_escalation_governance_ref": "controlled-escalation-governance",
}


def test_ready_permission_escalation_audit_has_controlled_evidence() -> None:
    packet = build_codex_permission_escalation_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "audit_id": "audit-1",
                    "status": "approved",
                    "risk_level": "medium",
                    "approval_request_refs": ["approval-request"],
                    "sandbox_profile_refs": ["sandbox-profile"],
                    "command_prefix_refs": ["command-prefix"],
                    "escalation_justification_refs": ["justification"],
                    "approval_decision_refs": ["decision"],
                    "denial_refs": ["denial-policy"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_permission_escalation_audit_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["audit_count"] == 1
    assert packet["summary"]["command_prefix_ref_count"] == 1
    assert packet["next_actions"] == ["share_permission_escalation_audit_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_permission_escalation_audit_readiness_packet(
        {
            "audits": [
                {
                    "audit_id": "audit-2",
                    "status": "recorded",
                    "risk_level": "low",
                    "approval_request_refs": ["approval-request"],
                    "sandbox_profile_refs": ["sandbox-profile"],
                    "command_prefix_refs": ["command-prefix"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_permission_escalation_audit_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "approval_policy_ref",
        "sandbox_policy_ref",
        "command_prefix_policy_ref",
        "escalation_policy_ref",
        "permission_escalation_manifest_ref",
        "controlled_escalation_governance_ref",
    ]


def test_failed_or_expired_permission_escalation_blocks() -> None:
    packet = build_codex_permission_escalation_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "audit_id": "audit-3",
                    "status": "timed-out",
                    "risk_level": "high",
                    "approval_request_refs": ["approval-request"],
                    "sandbox_profile_refs": ["sandbox-profile"],
                    "command_prefix_refs": ["command-prefix"],
                    "escalation_justification_refs": ["justification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_permission_escalation_audit_status_failed"
    assert packet["next_actions"] == [
        "resolve_permission_escalation_audit_blockers",
        "refresh_permission_escalation_audit_readiness",
    ]


def test_high_risk_escalation_requires_justification_and_decision_refs() -> None:
    audit = summarize_codex_permission_escalation_audit(
        {
            "audit_id": "audit-4",
            "status": "validated",
            "risk_level": "critical",
            "approval_request_refs": ["approval-request"],
            "sandbox_profile_refs": ["sandbox-profile"],
            "command_prefix_refs": ["command-prefix"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert audit.readiness_state == "needs_review"
    assert "escalation_justification_refs" in audit.missing_refs
    assert "approval_decision_refs" in audit.missing_refs


def test_denied_escalation_requires_denial_refs() -> None:
    audit = summarize_codex_permission_escalation_audit(
        {
            "audit_id": "audit-5",
            "status": "denied",
            "risk_level": "medium",
            "approval_request_refs": ["approval-request"],
            "sandbox_profile_refs": ["sandbox-profile"],
            "command_prefix_refs": ["command-prefix"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert audit.readiness_state == "needs_review"
    assert "permission_escalation_denied" in audit.warnings
    assert "denial_refs" in audit.missing_refs


def test_live_approval_command_sandbox_or_permission_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_permission_escalation_audit_readiness_packet(
        {
            **PACKET_POLICIES,
            "audits": [
                {
                    "audit_id": "audit-6",
                    "status": "recorded",
                    "risk_level": "medium",
                    "approval_request_refs": ["approval-request"],
                    "sandbox_profile_refs": ["sandbox-profile"],
                    "command_prefix_refs": ["command-prefix"],
                    "escalation_justification_refs": ["justification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "command_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_permission_escalation_audit_live_operation_blocked"
    assert "live_permission_escalation_operation_attempted" in packet["audits"][0]["blockers"]


def test_empty_payload_requests_permission_escalation_audit_inventory() -> None:
    packet = build_codex_permission_escalation_audit_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_permission_escalation_audit_inventory"]


def test_dataclass_like_permission_escalation_audit_is_accepted_by_summarizer() -> None:
    @dataclass
    class PermissionEscalationAudit:
        audit_id: str
        status: str
        risk_level: str
        approval_request_refs: list[str]
        sandbox_profile_refs: list[str]
        command_prefix_refs: list[str]
        escalation_justification_refs: list[str]
        approval_decision_refs: list[str]
        denial_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    audit = summarize_codex_permission_escalation_audit(
        PermissionEscalationAudit(
            "audit-7",
            "passed",
            "medium",
            ["approval-request"],
            ["sandbox-profile"],
            ["command-prefix"],
            ["justification"],
            ["decision"],
            ["denial-policy"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert audit.audit_id == "audit-7"
    assert audit.status == "passed"
    assert audit.readiness_state == "ready"
