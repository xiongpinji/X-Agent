from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secrets_redaction_readiness_packet import (
    build_codex_secrets_redaction_readiness_packet,
    summarize_codex_secrets_redaction,
)


PACKET_POLICIES = {
    "secret_scan_policy": "secret-scan-policy",
    "redaction_policy": "redaction-policy",
    "transcript_policy": "transcript-policy",
    "exposure_policy": "exposure-policy",
    "secrets_manifest_ref": "secrets-manifest",
    "sensitive_data_governance_ref": "sensitive-data-governance",
}


def test_ready_secrets_redaction_review_has_sensitive_data_evidence() -> None:
    packet = build_codex_secrets_redaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "secret_reviews": [
                {
                    "secret_review_id": "secret-1",
                    "status": "redacted",
                    "secret_review_ref": "review",
                    "secret_scan_refs": ["scan"],
                    "redaction_policy_refs": ["redaction"],
                    "transcript_refs": ["transcript"],
                    "artifact_refs": ["artifact"],
                    "exposure_refs": ["exposure"],
                    "validation_receipt_refs": ["validation"],
                    "denylist_refs": ["denylist"],
                    "allowlist_refs": ["allowlist"],
                    "owner_escalation_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secrets_redaction_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["secret_review_count"] == 1
    assert packet["summary"]["redaction_policy_ref_count"] == 1
    assert packet["next_actions"] == ["share_secrets_redaction_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secrets_redaction_readiness_packet(
        {
            "secret_reviews": [
                {
                    "secret_review_id": "secret-2",
                    "status": "recorded",
                    "secret_review_ref": "review",
                    "secret_scan_refs": ["scan"],
                    "redaction_policy_refs": ["redaction"],
                    "transcript_refs": ["transcript"],
                    "artifact_refs": ["artifact"],
                    "validation_receipt_refs": ["validation"],
                    "denylist_refs": ["denylist"],
                    "allowlist_refs": ["allowlist"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secrets_redaction_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "secret_scan_policy_ref",
        "redaction_policy_ref",
        "transcript_policy_ref",
        "exposure_policy_ref",
        "secrets_manifest_ref",
        "sensitive_data_governance_ref",
    ]


def test_exposed_secret_status_requires_exposure_and_owner_refs_and_blocks() -> None:
    packet = build_codex_secrets_redaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "secret_reviews": [
                {
                    "secret_review_id": "secret-3",
                    "status": "exposed",
                    "secret_review_ref": "review",
                    "secret_scan_refs": ["scan"],
                    "redaction_policy_refs": ["redaction"],
                    "transcript_refs": ["transcript"],
                    "artifact_refs": ["artifact"],
                    "validation_receipt_refs": ["validation"],
                    "denylist_refs": ["denylist"],
                    "allowlist_refs": ["allowlist"],
                }
            ],
        }
    )

    review = packet["secret_reviews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secrets_redaction_status_failed"
    assert "exposure_refs" in review["missing_refs"]
    assert "owner_escalation_refs" in review["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_secrets_redaction_blockers",
        "refresh_secrets_redaction_readiness",
    ]


def test_missing_scan_redaction_transcript_validation_and_artifacts_needs_review() -> None:
    review = summarize_codex_secrets_redaction(
        {
            "secret_review_id": "secret-4",
            "status": "recorded",
            "secret_review_ref": "review",
        }
    )

    assert review.readiness_state == "needs_review"
    assert "secret_scan_refs" in review.missing_refs
    assert "redaction_policy_refs" in review.missing_refs
    assert "transcript_refs" in review.missing_refs
    assert "artifact_refs" in review.missing_refs
    assert "validation_receipt_refs" in review.missing_refs


def test_high_risk_exposure_requires_exposure_and_owner_refs() -> None:
    review = summarize_codex_secrets_redaction(
        {
            "secret_review_id": "secret-5",
            "status": "recorded",
            "secret_review_ref": "review",
            "exposure_level": "critical",
            "secret_scan_refs": ["scan"],
            "redaction_policy_refs": ["redaction"],
            "transcript_refs": ["transcript"],
            "artifact_refs": ["artifact"],
            "validation_receipt_refs": ["validation"],
            "denylist_refs": ["denylist"],
            "allowlist_refs": ["allowlist"],
        }
    )

    assert review.readiness_state == "needs_review"
    assert "exposure_refs" in review.missing_refs
    assert "owner_escalation_refs" in review.missing_refs


def test_raw_secret_payload_or_live_secret_operation_blocks_candidate() -> None:
    packet = build_codex_secrets_redaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "secret_reviews": [
                {
                    "secret_review_id": "secret-6",
                    "status": "recorded",
                    "secret_review_ref": "review",
                    "secret_scan_refs": ["scan"],
                    "redaction_policy_refs": ["redaction"],
                    "transcript_refs": ["transcript"],
                    "artifact_refs": ["artifact"],
                    "validation_receipt_refs": ["validation"],
                    "denylist_refs": ["denylist"],
                    "allowlist_refs": ["allowlist"],
                    "owner_escalation_refs": ["owner"],
                    "raw_secret_payload_present": True,
                    "vault_api_call_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secrets_redaction_raw_secret_blocked"
    assert "raw_secret_payload_present" in packet["secret_reviews"][0]["blockers"]
    assert "live_secret_redaction_operation_attempted" in packet["secret_reviews"][0]["blockers"]


def test_empty_payload_requests_secrets_redaction_inventory() -> None:
    packet = build_codex_secrets_redaction_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secrets_redaction_inventory"]


def test_dataclass_like_secret_review_is_accepted_by_summarizer() -> None:
    @dataclass
    class SecretReview:
        secret_review_id: str
        status: str
        secret_review_ref: str
        secret_scan_refs: list[str]
        redaction_policy_refs: list[str]
        transcript_refs: list[str]
        artifact_refs: list[str]
        exposure_refs: list[str]
        validation_receipt_refs: list[str]
        denylist_refs: list[str]
        allowlist_refs: list[str]
        owner_escalation_refs: list[str]

    review = summarize_codex_secrets_redaction(
        SecretReview(
            "secret-7",
            "passed",
            "review",
            ["scan"],
            ["redaction"],
            ["transcript"],
            ["artifact"],
            ["exposure"],
            ["validation"],
            ["denylist"],
            ["allowlist"],
            ["owner"],
        )
    )

    assert review.secret_review_id == "secret-7"
    assert review.status == "passed"
    assert review.readiness_state == "ready"
