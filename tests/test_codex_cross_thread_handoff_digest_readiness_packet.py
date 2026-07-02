from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_cross_thread_handoff_digest_readiness_packet import (
    build_codex_cross_thread_handoff_digest_readiness_packet,
    summarize_codex_cross_thread_handoff_digest,
)


PACKET_POLICIES = {
    "handoff_digest_policy": "handoff-digest-policy",
    "source_of_truth_policy": "source-of-truth-policy",
    "read_receipt_policy": "read-receipt-policy",
    "stale_handoff_policy": "stale-handoff-policy",
    "cross_thread_handoff_manifest_ref": "cross-thread-handoff-manifest",
    "multi_thread_continuity_governance_ref": "multi-thread-continuity-governance",
}


def test_ready_cross_thread_handoff_digest_has_read_and_source_of_truth_evidence() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "handoff-1",
                    "status": "acknowledged",
                    "source_thread_ref": "secondary-thread",
                    "target_thread_refs": ["mainline-thread"],
                    "handoff_digest_refs": ["digest"],
                    "source_of_truth_refs": ["handoff-doc"],
                    "candidate_refs": ["candidate"],
                    "validation_receipt_refs": ["validation"],
                    "read_receipt_refs": ["read-receipt"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_cross_thread_handoff_digest_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["handoff_count"] == 1
    assert packet["summary"]["read_receipt_ref_count"] == 1
    assert packet["next_actions"] == ["share_cross_thread_handoff_digest_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet(
        {
            "handoffs": [
                {
                    "handoff_id": "handoff-2",
                    "status": "shared",
                    "source_thread_ref": "secondary-thread",
                    "target_thread_refs": ["mainline-thread"],
                    "handoff_digest_refs": ["digest"],
                    "source_of_truth_refs": ["handoff-doc"],
                    "candidate_refs": ["candidate"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_cross_thread_handoff_digest_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "handoff_digest_policy_ref",
        "source_of_truth_policy_ref",
        "read_receipt_policy_ref",
        "stale_handoff_policy_ref",
        "cross_thread_handoff_manifest_ref",
        "multi_thread_continuity_governance_ref",
    ]


def test_missing_or_unreadable_handoff_blocks_candidate() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "handoff-3",
                    "status": "unreadable",
                    "source_thread_ref": "secondary-thread",
                    "target_thread_refs": ["mainline-thread"],
                    "handoff_digest_refs": ["digest"],
                    "source_of_truth_refs": ["handoff-doc"],
                    "candidate_refs": ["candidate"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    handoff = packet["handoffs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_cross_thread_handoff_digest_status_failed"
    assert "cross_thread_handoff_digest_status_failed" in handoff["blockers"]
    assert packet["next_actions"] == [
        "resolve_cross_thread_handoff_digest_blockers",
        "refresh_cross_thread_handoff_digest_readiness",
    ]


def test_missing_source_target_digest_source_of_truth_candidate_validation_artifact_owner_refs_needs_review() -> None:
    handoff = summarize_codex_cross_thread_handoff_digest(
        {
            "handoff_id": "handoff-4",
            "status": "shared",
        }
    )

    assert handoff.readiness_state == "needs_review"
    assert "source_thread_ref" in handoff.missing_refs
    assert "target_thread_refs" in handoff.missing_refs
    assert "handoff_digest_refs" in handoff.missing_refs
    assert "source_of_truth_refs" in handoff.missing_refs
    assert "candidate_refs" in handoff.missing_refs
    assert "validation_receipt_refs" in handoff.missing_refs
    assert "artifact_refs" in handoff.missing_refs
    assert "owner_refs" in handoff.missing_refs


def test_acknowledged_or_accepted_handoff_requires_read_receipts() -> None:
    handoff = summarize_codex_cross_thread_handoff_digest(
        {
            "handoff_id": "handoff-5",
            "status": "accepted",
            "source_thread_ref": "secondary-thread",
            "target_thread_refs": ["mainline-thread"],
            "handoff_digest_refs": ["digest"],
            "source_of_truth_refs": ["handoff-doc"],
            "candidate_refs": ["candidate"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "owner_refs": ["owner"],
        }
    )

    assert handoff.readiness_state == "needs_review"
    assert "read_receipt_refs" in handoff.missing_refs


def test_stale_handoff_warns_and_refreshes_digest() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "handoff-6",
                    "status": "shared",
                    "source_thread_ref": "secondary-thread",
                    "target_thread_refs": ["mainline-thread"],
                    "handoff_digest_refs": ["digest"],
                    "source_of_truth_refs": ["handoff-doc"],
                    "candidate_refs": ["candidate"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "stale_handoff_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_cross_thread_handoff_digest_stale"
    assert packet["next_actions"] == [
        "refresh_cross_thread_handoff_digest",
        "attach_current_handoff_receipts",
    ]


def test_live_thread_messaging_handoff_queue_or_manifest_mutation_blocks_candidate() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet(
        {
            **PACKET_POLICIES,
            "handoffs": [
                {
                    "handoff_id": "handoff-7",
                    "status": "shared",
                    "source_thread_ref": "secondary-thread",
                    "target_thread_refs": ["mainline-thread"],
                    "handoff_digest_refs": ["digest"],
                    "source_of_truth_refs": ["handoff-doc"],
                    "candidate_refs": ["candidate"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "thread_messaging_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_cross_thread_handoff_digest_live_operation_blocked"
    assert "live_cross_thread_handoff_digest_operation_attempted" in packet["handoffs"][0]["blockers"]


def test_empty_payload_requests_cross_thread_handoff_digest_inventory() -> None:
    packet = build_codex_cross_thread_handoff_digest_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_cross_thread_handoff_digest_inventory"]


def test_dataclass_like_cross_thread_handoff_digest_is_accepted_by_summarizer() -> None:
    @dataclass
    class CrossThreadHandoffDigest:
        handoff_id: str
        status: str
        source_thread_ref: str
        target_thread_refs: list[str]
        handoff_digest_refs: list[str]
        source_of_truth_refs: list[str]
        candidate_refs: list[str]
        validation_receipt_refs: list[str]
        read_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    handoff = summarize_codex_cross_thread_handoff_digest(
        CrossThreadHandoffDigest(
            "handoff-8",
            "read",
            "secondary-thread",
            ["mainline-thread"],
            ["digest"],
            ["handoff-doc"],
            ["candidate"],
            ["validation"],
            ["read-receipt"],
            ["artifact"],
            ["owner"],
        )
    )

    assert handoff.handoff_id == "handoff-8"
    assert handoff.status == "read"
    assert handoff.readiness_state == "ready"
