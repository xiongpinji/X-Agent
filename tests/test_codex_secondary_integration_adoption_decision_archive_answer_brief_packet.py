from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_answer_brief_packet import (
    build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_answer_brief,
)


PACKET_POLICIES = {
    "archive_answer_brief_policy": "archive-answer-brief-policy",
    "query_result_policy": "query-result-policy",
    "source_citation_policy": "source-citation-policy",
    "owner_followup_policy": "owner-followup-policy",
    "secondary_integration_adoption_decision_archive_answer_brief_manifest_ref": "answer-brief-manifest",
    "secondary_integration_adoption_decision_archive_answer_governance_ref": "answer-governance",
}


def test_ready_secondary_integration_archive_answer_brief_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-1",
                    "status": "answered",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "unresolved_result_refs": ["none"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["brief_count"] == 1
    assert packet["summary"]["citation_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_answer_brief_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            "briefs": [
                {
                    "brief_id": "brief-2",
                    "status": "briefed",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "archive_answer_brief_policy_ref",
        "query_result_policy_ref",
        "source_citation_policy_ref",
        "owner_followup_policy_ref",
        "secondary_integration_adoption_decision_archive_answer_brief_manifest_ref",
        "secondary_integration_adoption_decision_archive_answer_governance_ref",
    ]


def test_failed_or_stale_answer_brief_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-3",
                    "status": "stale",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                }
            ],
        }
    )

    brief = packet["briefs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_answer_brief_status_failed" in brief["blockers"]


def test_missing_archive_answer_brief_refs_needs_review() -> None:
    brief = summarize_codex_secondary_integration_adoption_decision_archive_answer_brief(
        {
            "brief_id": "brief-4",
            "status": "answered",
            "archive_answer_brief_ref": "answer-brief",
        }
    )

    assert brief.readiness_state == "needs_review"
    assert "archive_query_preview_refs" in brief.missing_refs
    assert "query_result_refs" in brief.missing_refs
    assert "answer_refs" in brief.missing_refs
    assert "source_refs" in brief.missing_refs
    assert "citation_refs" in brief.missing_refs
    assert "validation_refs" in brief.missing_refs
    assert "owner_followup_refs" in brief.missing_refs


def test_open_archive_answer_brief_warns_until_brief_receipts_attach() -> None:
    brief = summarize_codex_secondary_integration_adoption_decision_archive_answer_brief(
        {
            "brief_id": "brief-5",
            "status": "needs-review",
            "archive_answer_brief_ref": "answer-brief",
            "archive_query_preview_refs": ["query-preview"],
            "query_result_refs": ["query-result"],
            "answer_refs": ["answer"],
            "source_refs": ["source"],
            "citation_refs": ["citation"],
            "validation_refs": ["validation"],
            "owner_followup_refs": ["owner-followup"],
        }
    )

    assert brief.readiness_state == "needs_review"
    assert brief.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_answer_brief_still_open" in brief.warnings


def test_unresolved_results_warning_requires_unresolved_result_refs() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-6",
                    "status": "answered",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                    "unresolved_results_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_missing_evidence"
    assert "unresolved_result_refs" in packet["briefs"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_answer_brief_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_answer_brief_packet",
    ]


def test_citation_review_warning_drives_citation_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-7",
                    "status": "answered",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                    "citation_review_required": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_citation_review_required"
    assert packet["next_actions"] == [
        "review_archive_answer_citations",
        "refresh_archive_answer_brief_packet",
    ]


def test_live_query_report_database_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(
        {
            **PACKET_POLICIES,
            "briefs": [
                {
                    "brief_id": "brief-8",
                    "status": "answered",
                    "archive_answer_brief_ref": "answer-brief",
                    "archive_query_preview_refs": ["query-preview"],
                    "query_result_refs": ["query-result"],
                    "answer_refs": ["answer"],
                    "source_refs": ["source"],
                    "citation_refs": ["citation"],
                    "validation_refs": ["validation"],
                    "owner_followup_refs": ["owner-followup"],
                    "report_persistence_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_answer_brief_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_answer_brief_operation_attempted" in packet["briefs"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_answer_brief_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_answer_brief_inventory"]


def test_dataclass_like_archive_answer_brief_is_accepted_by_summarizer() -> None:
    @dataclass
    class AnswerBrief:
        brief_id: str
        status: str
        archive_answer_brief_ref: str
        archive_query_preview_refs: list[str]
        query_result_refs: list[str]
        answer_refs: list[str]
        source_refs: list[str]
        citation_refs: list[str]
        unresolved_result_refs: list[str]
        validation_refs: list[str]
        owner_followup_refs: list[str]

    brief = summarize_codex_secondary_integration_adoption_decision_archive_answer_brief(
        AnswerBrief(
            "brief-9",
            "complete",
            "answer-brief",
            ["query-preview"],
            ["query-result"],
            ["answer"],
            ["source"],
            ["citation"],
            ["none"],
            ["validation"],
            ["owner-followup"],
        )
    )

    assert brief.brief_id == "brief-9"
    assert brief.status == "complete"
    assert brief.readiness_state == "ready"
