from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_code_review_findings_readiness_packet import (
    build_codex_code_review_findings_readiness_packet,
    summarize_codex_code_review_finding,
)


PACKET_POLICIES = {
    "review_policy": "review-policy",
    "severity_policy": "severity-policy",
    "evidence_policy": "evidence-policy",
    "suppression_policy": "suppression-policy",
    "review_findings_manifest_ref": "review-findings-manifest",
    "review_output_governance_ref": "review-output-governance",
}


def test_ready_code_review_finding_has_review_output_evidence() -> None:
    packet = build_codex_code_review_findings_readiness_packet(
        {
            **PACKET_POLICIES,
            "findings": [
                {
                    "finding_id": "finding-1",
                    "status": "triaged",
                    "severity": "medium",
                    "finding_ref": "finding",
                    "file_line_refs": ["app.py:10"],
                    "evidence_refs": ["evidence"],
                    "suggested_fix_refs": ["fix"],
                    "validation_receipt_refs": ["validation"],
                    "suppression_refs": ["suppression-policy"],
                    "owner_refs": ["owner"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_code_review_findings_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["finding_count"] == 1
    assert packet["summary"]["file_line_ref_count"] == 1
    assert packet["next_actions"] == ["share_code_review_findings_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_code_review_findings_readiness_packet(
        {
            "findings": [
                {
                    "finding_id": "finding-1",
                    "status": "recorded",
                    "severity": "low",
                    "finding_ref": "finding",
                    "file_line_refs": ["app.py:10"],
                    "evidence_refs": ["evidence"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert (
        packet["review_findings"][0]["code"]
        == "codex_code_review_findings_packet_missing_evidence"
    )
    assert packet["packet_missing_refs"] == [
        "review_policy_ref",
        "severity_policy_ref",
        "evidence_policy_ref",
        "suppression_policy_ref",
        "review_findings_manifest_ref",
        "review_output_governance_ref",
    ]


def test_invalid_or_untriaged_finding_blocks() -> None:
    packet = build_codex_code_review_findings_readiness_packet(
        {
            **PACKET_POLICIES,
            "findings": [
                {
                    "finding_id": "finding-2",
                    "status": "untriaged",
                    "severity": "critical",
                    "finding_ref": "finding",
                    "file_line_refs": ["app.py:10"],
                    "evidence_refs": ["evidence"],
                    "suggested_fix_refs": ["fix"],
                    "owner_refs": ["owner"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["review_findings"][0]["code"] == "codex_code_review_finding_status_failed"
    assert packet["next_actions"] == [
        "resolve_code_review_finding_blockers",
        "refresh_code_review_findings_readiness",
    ]


def test_high_severity_finding_requires_fix_owner_and_location_refs() -> None:
    finding = summarize_codex_code_review_finding(
        {
            "finding_id": "finding-3",
            "status": "recorded",
            "severity": "high",
            "finding_ref": "finding",
            "evidence_refs": ["evidence"],
            "artifact_refs": ["artifact"],
        }
    )

    assert finding.readiness_state == "needs_review"
    assert "file_line_refs" in finding.missing_refs
    assert "suggested_fix_refs" in finding.missing_refs
    assert "owner_refs" in finding.missing_refs


def test_live_review_inline_comment_or_github_attempt_blocks_candidate() -> None:
    packet = build_codex_code_review_findings_readiness_packet(
        {
            **PACKET_POLICIES,
            "findings": [
                {
                    "finding_id": "finding-4",
                    "status": "recorded",
                    "severity": "medium",
                    "finding_ref": "finding",
                    "file_line_refs": ["app.py:10"],
                    "evidence_refs": ["evidence"],
                    "suggested_fix_refs": ["fix"],
                    "artifact_refs": ["artifact"],
                    "inline_comment_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["review_findings"][0]["code"] == "codex_code_review_findings_live_output_blocked"
    assert "live_code_review_output_attempted" in packet["findings"][0]["blockers"]


def test_empty_payload_requests_code_review_findings_inventory() -> None:
    packet = build_codex_code_review_findings_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_code_review_findings_inventory"]


def test_dataclass_like_code_review_finding_is_accepted_by_summarizer() -> None:
    @dataclass
    class Finding:
        finding_id: str
        status: str
        severity: str
        finding_ref: str
        file_line_refs: list[str]
        evidence_refs: list[str]
        suggested_fix_refs: list[str]
        validation_receipt_refs: list[str]
        suppression_refs: list[str]
        owner_refs: list[str]
        artifact_refs: list[str]

    finding = summarize_codex_code_review_finding(
        Finding(
            "finding-5",
            "passed",
            "medium",
            "finding",
            ["app.py:10"],
            ["evidence"],
            ["fix"],
            ["validation"],
            ["suppression"],
            ["owner"],
            ["artifact"],
        )
    )

    assert finding.finding_id == "finding-5"
    assert finding.status == "passed"
    assert finding.readiness_state == "ready"
