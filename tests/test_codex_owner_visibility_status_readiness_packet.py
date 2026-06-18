from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_owner_visibility_status_readiness_packet import (
    build_codex_owner_visibility_status_readiness_packet,
    summarize_codex_owner_visibility_status,
)


PACKET_POLICIES = {
    "candidate_status_policy": "candidate-status-policy",
    "handoff_digest_policy": "handoff-digest-policy",
    "owner_decision_policy": "owner-decision-policy",
    "stage_classification_policy": "stage-classification-policy",
    "owner_visibility_manifest_ref": "owner-visibility-manifest",
    "multi_thread_visibility_governance_ref": "multi-thread-visibility-governance",
}


def test_ready_owner_visibility_has_all_mainline_evidence() -> None:
    packet = build_codex_owner_visibility_status_readiness_packet(
        {
            **PACKET_POLICIES,
            "visibility_items": [
                {
                    "visibility_id": "visibility-1",
                    "status": "visible",
                    "candidate_ref": "candidate",
                    "candidate_status_refs": ["candidate-status"],
                    "handoff_digest_refs": ["handoff"],
                    "notification_refs": ["notification"],
                    "owner_decision_refs": ["owner-decision"],
                    "stage_classification_refs": ["stage-classification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "mainline_thread_refs": ["mainline-thread"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_owner_visibility_status_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["visibility_count"] == 1
    assert packet["summary"]["candidate_status_ref_count"] == 1
    assert packet["next_actions"] == ["share_owner_visibility_status_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_owner_visibility_status_readiness_packet(
        {
            "visibility_items": [
                {
                    "visibility_id": "visibility-2",
                    "status": "visible",
                    "candidate_ref": "candidate",
                    "candidate_status_refs": ["candidate-status"],
                    "handoff_digest_refs": ["handoff"],
                    "notification_refs": ["notification"],
                    "owner_decision_refs": ["owner-decision"],
                    "stage_classification_refs": ["stage-classification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "mainline_thread_refs": ["mainline-thread"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_owner_visibility_status_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "candidate_status_policy_ref",
        "handoff_digest_policy_ref",
        "owner_decision_policy_ref",
        "stage_classification_policy_ref",
        "owner_visibility_manifest_ref",
        "multi_thread_visibility_governance_ref",
    ]


def test_blocked_or_missing_visibility_requires_notification_and_owner_decision_refs() -> None:
    packet = build_codex_owner_visibility_status_readiness_packet(
        {
            **PACKET_POLICIES,
            "visibility_items": [
                {
                    "visibility_id": "visibility-3",
                    "status": "not_visible",
                    "candidate_ref": "candidate",
                    "candidate_status_refs": ["candidate-status"],
                    "handoff_digest_refs": ["handoff"],
                    "stage_classification_refs": ["stage-classification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "mainline_thread_refs": ["mainline-thread"],
                }
            ],
        }
    )

    visibility = packet["visibility_items"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_owner_visibility_status_failed"
    assert "notification_refs" in visibility["missing_refs"]
    assert "owner_decision_refs" in visibility["missing_refs"]


def test_missing_candidate_handoff_stage_validation_artifact_refs_needs_review() -> None:
    visibility = summarize_codex_owner_visibility_status(
        {
            "visibility_id": "visibility-4",
            "status": "reviewed",
            "candidate_ref": "candidate",
            "notification_refs": ["notification"],
            "owner_decision_refs": ["owner-decision"],
            "owner_refs": ["owner"],
            "mainline_thread_refs": ["mainline-thread"],
        }
    )

    assert visibility.readiness_state == "needs_review"
    assert "candidate_status_refs" in visibility.missing_refs
    assert "handoff_digest_refs" in visibility.missing_refs
    assert "stage_classification_refs" in visibility.missing_refs
    assert "validation_receipt_refs" in visibility.missing_refs
    assert "artifact_refs" in visibility.missing_refs


def test_live_notification_dispatch_or_owner_stage_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_owner_visibility_status_readiness_packet(
        {
            **PACKET_POLICIES,
            "visibility_items": [
                {
                    "visibility_id": "visibility-5",
                    "status": "visible",
                    "candidate_ref": "candidate",
                    "candidate_status_refs": ["candidate-status"],
                    "handoff_digest_refs": ["handoff"],
                    "notification_refs": ["notification"],
                    "owner_decision_refs": ["owner-decision"],
                    "stage_classification_refs": ["stage-classification"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "mainline_thread_refs": ["mainline-thread"],
                    "notification_dispatch_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_owner_visibility_status_live_operation_blocked"
    assert "live_owner_visibility_operation_attempted" in packet["visibility_items"][0]["blockers"]


def test_empty_payload_requests_owner_visibility_inventory() -> None:
    packet = build_codex_owner_visibility_status_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_owner_visibility_status_inventory"]


def test_missing_owner_and_mainline_refs_needs_review() -> None:
    visibility = summarize_codex_owner_visibility_status(
        {
            "visibility_id": "visibility-6",
            "status": "acknowledged",
            "candidate_ref": "candidate",
            "candidate_status_refs": ["candidate-status"],
            "handoff_digest_refs": ["handoff"],
            "notification_refs": ["notification"],
            "owner_decision_refs": ["owner-decision"],
            "stage_classification_refs": ["stage-classification"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert visibility.readiness_state == "needs_review"
    assert "owner_refs" in visibility.missing_refs
    assert "mainline_thread_refs" in visibility.missing_refs


def test_dataclass_like_visibility_is_accepted_by_summarizer() -> None:
    @dataclass
    class Visibility:
        visibility_id: str
        status: str
        candidate_ref: str
        candidate_status_refs: list[str]
        handoff_digest_refs: list[str]
        notification_refs: list[str]
        owner_decision_refs: list[str]
        stage_classification_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]
        mainline_thread_refs: list[str]

    visibility = summarize_codex_owner_visibility_status(
        Visibility(
            "visibility-7",
            "classified",
            "candidate",
            ["candidate-status"],
            ["handoff"],
            ["notification"],
            ["owner-decision"],
            ["stage-classification"],
            ["validation"],
            ["artifact"],
            ["owner"],
            ["mainline-thread"],
        )
    )

    assert visibility.visibility_id == "visibility-7"
    assert visibility.status == "classified"
    assert visibility.readiness_state == "ready"
