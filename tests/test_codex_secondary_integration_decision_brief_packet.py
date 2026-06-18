from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_decision_brief_packet import (
    build_codex_secondary_integration_decision_brief_packet,
    summarize_codex_secondary_integration_decision_brief,
)


PACKET_POLICIES = {
    "decision_brief_policy": "decision-brief-policy",
    "recommended_decision_policy": "recommended-decision-policy",
    "batch_snapshot_policy": "batch-snapshot-policy",
    "secondary_integration_policy": "secondary-integration-policy",
    "secondary_integration_decision_brief_manifest_ref": "decision-brief-manifest",
    "secondary_integration_decision_governance_ref": "decision-governance",
}


def test_ready_secondary_integration_decision_brief_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-1",
                    "status": "recommended",
                    "decision_brief_ref": "decision-brief",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "recommended_decision_refs": ["recommended-decision"],
                    "next_step_refs": ["next-step"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_decision_brief_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["brief_count"] == 1
    assert packet["summary"]["recommended_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_decision_brief_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet(
        {
            "briefs": [
                {
                    "brief_id": "brief-2",
                    "status": "approved",
                    "decision_brief_ref": "decision-brief",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "recommended_decision_refs": ["recommended-decision"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_decision_brief_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "decision_brief_policy_ref",
        "recommended_decision_policy_ref",
        "batch_snapshot_policy_ref",
        "secondary_integration_policy_ref",
        "secondary_integration_decision_brief_manifest_ref",
        "secondary_integration_decision_governance_ref",
    ]


def test_rejected_or_regressed_decision_brief_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-3",
                    "status": "rejected",
                    "decision_brief_ref": "decision-brief",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                }
            ],
        }
    )

    brief = packet["briefs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_decision_brief_status_failed"
    assert "codex_secondary_integration_decision_brief_status_failed" in brief["blockers"]


def test_missing_brief_refs_needs_review() -> None:
    brief = summarize_codex_secondary_integration_decision_brief(
        {
            "brief_id": "brief-4",
            "status": "recommended",
            "decision_brief_ref": "decision-brief",
        }
    )

    assert brief.readiness_state == "needs_review"
    assert "batch_snapshot_refs" in brief.missing_refs
    assert "adoption_readiness_refs" in brief.missing_refs
    assert "risk_refs" in brief.missing_refs
    assert "validation_refs" in brief.missing_refs
    assert "skipped_item_refs" in brief.missing_refs
    assert "owner_mainline_review_refs" in brief.missing_refs
    assert "recommended_decision_refs" in brief.missing_refs


def test_open_decision_brief_requires_next_step_refs() -> None:
    brief = summarize_codex_secondary_integration_decision_brief(
        {
            "brief_id": "brief-5",
            "status": "needs-review",
            "decision_brief_ref": "decision-brief",
            "batch_snapshot_refs": ["batch-snapshot"],
            "adoption_readiness_refs": ["adoption-readiness"],
            "risk_refs": ["risk"],
            "validation_refs": ["validation"],
            "skipped_item_refs": ["skipped-items"],
            "owner_mainline_review_refs": ["owner-mainline-review"],
        }
    )

    assert brief.readiness_state == "needs_review"
    assert "next_step_refs" in brief.missing_refs
    assert "codex_secondary_integration_decision_brief_still_open" in brief.warnings


def test_integration_risk_warning_drives_recommendation_revision() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-6",
                    "status": "recommended",
                    "decision_brief_ref": "decision-brief",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "recommended_decision_refs": ["recommended-decision"],
                    "next_step_refs": ["next-step"],
                    "integration_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_decision_brief_risk"
    assert packet["next_actions"] == [
        "review_secondary_integration_decision_risks",
        "revise_recommended_secondary_decision",
    ]


def test_live_decision_batch_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-7",
                    "status": "accepted",
                    "decision_brief_ref": "decision-brief",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "risk_refs": ["risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "recommended_decision_refs": ["recommended-decision"],
                    "decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_decision_brief_live_operation_blocked"
    assert "live_codex_secondary_integration_decision_brief_operation_attempted" in packet["briefs"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_decision_brief_inventory() -> None:
    packet = build_codex_secondary_integration_decision_brief_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_decision_brief_inventory"]


def test_dataclass_like_decision_brief_is_accepted_by_summarizer() -> None:
    @dataclass
    class Brief:
        brief_id: str
        status: str
        decision_brief_ref: str
        batch_snapshot_refs: list[str]
        adoption_readiness_refs: list[str]
        risk_refs: list[str]
        validation_refs: list[str]
        skipped_item_refs: list[str]
        owner_mainline_review_refs: list[str]
        recommended_decision_refs: list[str]
        next_step_refs: list[str]

    brief = summarize_codex_secondary_integration_decision_brief(
        Brief(
            "brief-8",
            "validated",
            "decision-brief",
            ["batch-snapshot"],
            ["adoption-readiness"],
            ["risk"],
            ["validation"],
            ["skipped-items"],
            ["owner-mainline-review"],
            ["recommended-decision"],
            ["next-step"],
        )
    )

    assert brief.brief_id == "brief-8"
    assert brief.status == "validated"
    assert brief.readiness_state == "ready"
