from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_thread_resume_compaction_readiness_packet import (
    build_codex_thread_resume_compaction_readiness_packet,
    summarize_codex_thread_resume_compaction,
)


PACKET_POLICIES = {
    "resume_policy": "resume-policy",
    "compaction_policy": "compaction-policy",
    "handoff_policy": "handoff-policy",
    "context_budget_policy": "context-budget-policy",
    "thread_continuity_manifest_ref": "thread-continuity-manifest",
    "resume_governance_ref": "resume-governance",
}


def test_ready_thread_resume_compaction_has_continuity_evidence() -> None:
    packet = build_codex_thread_resume_compaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "resumes": [
                {
                    "resume_id": "resume-1",
                    "status": "resumed",
                    "thread_ref": "thread",
                    "compaction_summary_refs": ["summary"],
                    "continuation_refs": ["continuation"],
                    "resume_token_refs": ["resume-token"],
                    "handoff_refs": ["handoff"],
                    "context_budget_refs": ["budget"],
                    "source_thread_refs": ["source-thread"],
                    "resume_receipt_refs": ["resume-receipt"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_thread_resume_compaction_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["resume_count"] == 1
    assert packet["summary"]["resume_token_ref_count"] == 1
    assert packet["next_actions"] == ["share_thread_resume_compaction_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_thread_resume_compaction_readiness_packet(
        {
            "resumes": [
                {
                    "resume_id": "resume-2",
                    "status": "compacted",
                    "thread_ref": "thread",
                    "compaction_summary_refs": ["summary"],
                    "continuation_refs": ["continuation"],
                    "resume_token_refs": ["resume-token"],
                    "handoff_refs": ["handoff"],
                    "context_budget_refs": ["budget"],
                    "source_thread_refs": ["source-thread"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_thread_resume_compaction_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "resume_policy_ref",
        "compaction_policy_ref",
        "handoff_policy_ref",
        "context_budget_policy_ref",
        "thread_continuity_manifest_ref",
        "resume_governance_ref",
    ]


def test_lost_or_stale_resume_blocks_and_requires_handoff_refs() -> None:
    packet = build_codex_thread_resume_compaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "resumes": [
                {
                    "resume_id": "resume-3",
                    "status": "lost",
                    "thread_ref": "thread",
                    "compaction_summary_refs": ["summary"],
                    "continuation_refs": ["continuation"],
                    "resume_token_refs": ["resume-token"],
                    "context_budget_refs": ["budget"],
                    "source_thread_refs": ["source-thread"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    resume = packet["resumes"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_thread_resume_compaction_status_failed"
    assert "handoff_refs" in resume["missing_refs"]
    assert "failure_handoff_refs" in resume["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_thread_resume_compaction_blockers",
        "refresh_thread_resume_compaction_readiness",
    ]


def test_missing_summary_continuation_resume_budget_and_source_refs_needs_review() -> None:
    resume = summarize_codex_thread_resume_compaction(
        {
            "resume_id": "resume-4",
            "status": "compacted",
            "thread_ref": "thread",
            "handoff_refs": ["handoff"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert resume.readiness_state == "needs_review"
    assert "compaction_summary_refs" in resume.missing_refs
    assert "continuation_refs" in resume.missing_refs
    assert "resume_token_refs" in resume.missing_refs
    assert "context_budget_refs" in resume.missing_refs
    assert "source_thread_refs" in resume.missing_refs


def test_resumed_state_requires_resume_receipt_refs() -> None:
    resume = summarize_codex_thread_resume_compaction(
        {
            "resume_id": "resume-5",
            "status": "continued",
            "thread_ref": "thread",
            "compaction_summary_refs": ["summary"],
            "continuation_refs": ["continuation"],
            "resume_token_refs": ["resume-token"],
            "handoff_refs": ["handoff"],
            "context_budget_refs": ["budget"],
            "source_thread_refs": ["source-thread"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert resume.readiness_state == "needs_review"
    assert "resume_receipt_refs" in resume.missing_refs


def test_live_thread_or_compaction_operation_attempt_blocks_candidate() -> None:
    packet = build_codex_thread_resume_compaction_readiness_packet(
        {
            **PACKET_POLICIES,
            "resumes": [
                {
                    "resume_id": "resume-6",
                    "status": "compacted",
                    "thread_ref": "thread",
                    "compaction_summary_refs": ["summary"],
                    "continuation_refs": ["continuation"],
                    "resume_token_refs": ["resume-token"],
                    "handoff_refs": ["handoff"],
                    "context_budget_refs": ["budget"],
                    "source_thread_refs": ["source-thread"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "context_compaction_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_thread_resume_compaction_live_operation_blocked"
    assert "live_thread_resume_compaction_operation_attempted" in packet["resumes"][0]["blockers"]


def test_empty_payload_requests_thread_resume_compaction_inventory() -> None:
    packet = build_codex_thread_resume_compaction_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_thread_resume_compaction_inventory"]


def test_dataclass_like_thread_resume_is_accepted_by_summarizer() -> None:
    @dataclass
    class ThreadResume:
        resume_id: str
        status: str
        thread_ref: str
        compaction_summary_refs: list[str]
        continuation_refs: list[str]
        resume_token_refs: list[str]
        handoff_refs: list[str]
        context_budget_refs: list[str]
        source_thread_refs: list[str]
        resume_receipt_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    resume = summarize_codex_thread_resume_compaction(
        ThreadResume(
            "resume-7",
            "resumed",
            "thread",
            ["summary"],
            ["continuation"],
            ["resume-token"],
            ["handoff"],
            ["budget"],
            ["source-thread"],
            ["resume-receipt"],
            ["validation"],
            ["artifact"],
        )
    )

    assert resume.resume_id == "resume-7"
    assert resume.status == "resumed"
    assert resume.readiness_state == "ready"
