from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_enterprise_usage_log_readiness_packet import (
    build_codex_enterprise_usage_log_readiness_packet,
    summarize_codex_enterprise_usage_log,
)


PACKET_POLICIES = {
    "usage_log_policy": "usage-log-policy",
    "admin_access_policy": "admin-access-policy",
    "privacy_policy": "privacy-policy",
    "retention_policy": "retention-policy",
    "usage_manifest_ref": "usage-manifest",
    "audit_export_policy": "audit-export-policy",
}


def test_ready_enterprise_usage_log_has_governance_evidence() -> None:
    packet = build_codex_enterprise_usage_log_readiness_packet(
        {
            **PACKET_POLICIES,
            "usage_logs": [
                {
                    "usage_id": "usage-1",
                    "status": "audited",
                    "tenant_ref": "tenant-a",
                    "user_ref": "user-a",
                    "account_ref": "account-a",
                    "source": "enterprise-admin",
                    "task_refs": ["task-1"],
                    "run_refs": ["run-1"],
                    "usage_log_export_refs": ["usage-export"],
                    "audit_log_refs": ["audit-log"],
                    "privacy_redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "admin_access_policy_refs": ["admin-access"],
                    "billing_quota_refs": ["quota"],
                    "validation_receipt_refs": ["validation"],
                    "incident_escalation_refs": ["incident-policy"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_enterprise_usage_log_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["usage_log_count"] == 1
    assert packet["summary"]["billing_quota_ref_count"] == 1
    assert packet["next_actions"] == ["share_enterprise_usage_log_readiness_with_mainline"]


def test_missing_packet_governance_policies_needs_review() -> None:
    packet = build_codex_enterprise_usage_log_readiness_packet(
        {
            "usage_logs": [
                {
                    "usage_id": "usage-1",
                    "status": "audited",
                    "tenant_ref": "tenant-a",
                    "user_ref": "user-a",
                    "account_ref": "account-a",
                    "source": "api",
                    "task_refs": ["task"],
                    "run_refs": ["run"],
                    "usage_log_export_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "privacy_redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "admin_access_policy_refs": ["admin"],
                    "billing_quota_refs": ["quota"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_enterprise_usage_log_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "usage_log_policy_ref",
        "admin_access_policy_ref",
        "privacy_policy_ref",
        "retention_policy_ref",
        "usage_manifest_ref",
        "audit_export_policy_ref",
    ]


def test_failed_usage_log_requires_incident_escalation_and_blocks() -> None:
    packet = build_codex_enterprise_usage_log_readiness_packet(
        {
            **PACKET_POLICIES,
            "usage_logs": [
                {
                    "usage_id": "usage-2",
                    "status": "failed",
                    "tenant_ref": "tenant-a",
                    "user_ref": "user-a",
                    "account_ref": "account-a",
                    "source": "audit-export",
                    "task_refs": ["task"],
                    "run_refs": ["run"],
                    "usage_log_export_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "privacy_redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "admin_access_policy_refs": ["admin"],
                    "billing_quota_refs": ["quota"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    usage = packet["usage_logs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_enterprise_usage_log_status_failed"
    assert "incident_escalation_refs" in usage["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_enterprise_usage_log_blockers",
        "refresh_enterprise_usage_log_readiness",
    ]


def test_missing_privacy_admin_and_quota_refs_needs_review() -> None:
    usage = summarize_codex_enterprise_usage_log(
        {
            "usage_id": "usage-3",
            "status": "available",
            "tenant_ref": "tenant-a",
            "user_ref": "user-a",
            "account_ref": "account-a",
            "source": "cli",
            "task_refs": ["task"],
            "run_refs": ["run"],
            "usage_log_export_refs": ["export"],
            "audit_log_refs": ["audit"],
            "retention_policy_refs": ["retention"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert usage.readiness_state == "needs_review"
    assert "privacy_redaction_refs" in usage.missing_refs
    assert "admin_access_policy_refs" in usage.missing_refs
    assert "billing_quota_refs" in usage.missing_refs


def test_live_admin_export_or_billing_mutation_attempt_blocks_secondary_candidate() -> None:
    packet = build_codex_enterprise_usage_log_readiness_packet(
        {
            **PACKET_POLICIES,
            "usage_logs": [
                {
                    "usage_id": "usage-4",
                    "status": "audited",
                    "tenant_ref": "tenant-a",
                    "user_ref": "user-a",
                    "account_ref": "account-a",
                    "source": "enterprise_admin",
                    "task_refs": ["task"],
                    "run_refs": ["run"],
                    "usage_log_export_refs": ["export"],
                    "audit_log_refs": ["audit"],
                    "privacy_redaction_refs": ["redaction"],
                    "retention_policy_refs": ["retention"],
                    "admin_access_policy_refs": ["admin"],
                    "billing_quota_refs": ["quota"],
                    "validation_receipt_refs": ["validation"],
                    "incident_escalation_refs": ["incident"],
                    "artifact_refs": ["artifact"],
                    "admin_api_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_enterprise_usage_log_live_admin_mutation_blocked"
    assert "live_admin_export_or_mutation_attempted" in packet["usage_logs"][0]["blockers"]


def test_empty_payload_requests_enterprise_usage_log_inventory() -> None:
    packet = build_codex_enterprise_usage_log_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_enterprise_usage_log_inventory"]


def test_dataclass_like_usage_log_is_accepted_by_summarizer() -> None:
    @dataclass
    class UsageLog:
        usage_id: str
        status: str
        tenant_ref: str
        user_ref: str
        account_ref: str
        source: str
        task_refs: list[str]
        run_refs: list[str]
        usage_log_export_refs: list[str]
        audit_log_refs: list[str]
        privacy_redaction_refs: list[str]
        retention_policy_refs: list[str]
        admin_access_policy_refs: list[str]
        billing_quota_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    usage = summarize_codex_enterprise_usage_log(
        UsageLog(
            "usage-5",
            "validated",
            "tenant-a",
            "user-a",
            "account-a",
            "custom",
            ["task"],
            ["run"],
            ["export"],
            ["audit"],
            ["redaction"],
            ["retention"],
            ["admin"],
            ["quota"],
            ["validation"],
            ["artifact"],
        )
    )

    assert usage.usage_id == "usage-5"
    assert usage.status == "validated"
    assert usage.readiness_state == "ready"
