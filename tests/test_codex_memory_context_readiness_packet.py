from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_memory_context_readiness_packet import (
    build_codex_memory_context_readiness_packet,
    summarize_codex_memory_context_source,
)


BOUNDARIES = [
    "redaction",
    "source_attribution",
    "stale_context_warning",
    "prompt_injection_guard",
]


def test_ready_packet_with_project_memory_session_and_retrieval_sources() -> None:
    packet = build_codex_memory_context_readiness_packet(
        {
            "context_budget_policy": "budget-v1",
            "stale_context_policy": "stale-v1",
            "redaction_policy": "redaction-v1",
            "project_instructions": {
                "name": "AGENTS.md",
                "status": "ready",
                "scope": "project",
                "token_budget": 1200,
                "instruction_refs": ["AGENTS.md"],
                "redaction_refs": ["redaction-v1"],
                "validation_refs": ["instruction-receipt"],
                "boundaries": BOUNDARIES,
            },
            "repo_local_memory": {
                "name": "repo-memory",
                "status": "fresh",
                "scope": "repo",
                "token_budget": 1800,
                "memory_refs": ["memory/repo.json"],
                "retrieval_refs": ["index/repo"],
                "redaction_refs": ["redaction-v1"],
                "validation_refs": ["memory-receipt"],
                "boundaries": BOUNDARIES,
            },
            "session_summary": {
                "name": "session-summary",
                "status": "ready",
                "scope": "session",
                "token_budget": 900,
                "memory_refs": ["session/summary.md"],
                "redaction_refs": ["redaction-v1"],
                "validation_refs": ["session-receipt"],
                "boundaries": BOUNDARIES,
            },
            "retrieval": {
                "name": "codegraph-index",
                "status": "ready",
                "scope": "repo",
                "token_budget": 1000,
                "retrieval_refs": ["codegraph"],
                "redaction_refs": ["redaction-v1"],
                "validation_refs": ["retrieval-receipt"],
                "boundaries": BOUNDARIES,
            },
        }
    )

    assert packet["kind"] == "codex_memory_context_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["source_count"] == 4
    assert packet["summary"]["total_token_budget"] == 4900
    assert packet["next_actions"] == ["share_memory_context_readiness_with_mainline"]


def test_missing_packet_level_policies_needs_review() -> None:
    packet = build_codex_memory_context_readiness_packet(
        {
            "project_instructions": {
                "name": "AGENTS.md",
                "status": "ready",
                "token_budget": 1000,
                "instruction_refs": ["AGENTS.md"],
                "redaction_refs": ["redaction"],
                "validation_refs": ["validation"],
                "boundaries": BOUNDARIES,
            },
            "session_summary": {
                "name": "summary",
                "status": "ready",
                "token_budget": 500,
                "memory_refs": ["summary.md"],
                "redaction_refs": ["redaction"],
                "validation_refs": ["validation"],
                "boundaries": BOUNDARIES,
            },
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_memory_context_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "context_budget_policy",
        "stale_context_policy",
        "redaction_policy",
    ]
    assert packet["next_actions"] == [
        "attach_packet_level_context_policies",
        "refresh_memory_context_readiness",
    ]


def test_memory_source_missing_retrieval_redaction_and_boundaries_needs_review() -> None:
    packet = build_codex_memory_context_readiness_packet(
        {
            "context_budget_policy": "budget",
            "stale_context_policy": "stale",
            "redaction_policy": "redaction",
            "project_instructions": {
                "name": "AGENTS.md",
                "status": "ready",
                "token_budget": 1000,
                "instruction_refs": ["AGENTS.md"],
                "redaction_refs": ["redaction"],
                "validation_refs": ["validation"],
                "boundaries": BOUNDARIES,
            },
            "repo_local_memory": {
                "name": "repo-memory",
                "status": "ready",
                "token_budget": 900,
                "memory_refs": ["memory.json"],
                "boundaries": ["source_attribution"],
            },
            "session_summary": {
                "name": "summary",
                "status": "ready",
                "token_budget": 500,
                "memory_refs": ["summary.md"],
                "redaction_refs": ["redaction"],
                "validation_refs": ["validation"],
                "boundaries": BOUNDARIES,
            },
        }
    )

    memory_source = packet["sources"][1]
    assert packet["status"] == "needs_review"
    assert "retrieval_refs" in memory_source["missing_refs"]
    assert "redaction_refs" in memory_source["missing_refs"]
    assert "validation_refs" in memory_source["missing_refs"]
    assert "boundary_redaction" in memory_source["missing_refs"]
    assert "retrieved_context_lacks_prompt_injection_guard" in memory_source["warnings"]


def test_disabled_context_source_blocks_packet() -> None:
    packet = build_codex_memory_context_readiness_packet(
        {
            "context_budget_policy": "budget",
            "stale_context_policy": "stale",
            "redaction_policy": "redaction",
            "project_instructions": {
                "name": "AGENTS.md",
                "status": "ready",
                "enabled": False,
                "token_budget": 1000,
                "instruction_refs": ["AGENTS.md"],
                "redaction_refs": ["redaction"],
                "validation_refs": ["validation"],
                "boundaries": BOUNDARIES,
            },
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_memory_context_packet_missing_evidence"
    assert packet["findings"][1]["code"] == "codex_memory_context_source_disabled"
    assert packet["next_actions"] == ["restore_required_context_sources", "review_memory_context_scope"]


def test_stale_session_summary_needs_review() -> None:
    source = summarize_codex_memory_context_source(
        {
            "source_type": "session_summary",
            "name": "summary",
            "status": "stale",
            "token_budget": 500,
            "memory_refs": ["summary.md"],
            "redaction_refs": ["redaction"],
            "validation_refs": ["validation"],
            "boundaries": BOUNDARIES,
        }
    )

    assert source.readiness_state == "needs_review"
    assert "context_source_stale" in source.warnings


def test_empty_payload_requests_inventory() -> None:
    packet = build_codex_memory_context_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_memory_context_inventory"]


def test_dataclass_like_source_is_accepted_by_summarizer() -> None:
    @dataclass
    class Source:
        name: str
        source_type: str
        status: str
        scope: str
        token_budget: int
        instruction_refs: list[str]
        redaction_refs: list[str]
        validation_refs: list[str]
        boundaries: list[str]

    source = summarize_codex_memory_context_source(
        Source(
            "AGENTS.md",
            "project_instructions",
            "ready",
            "project",
            1000,
            ["AGENTS.md"],
            ["redaction"],
            ["validation"],
            BOUNDARIES,
        )
    )

    assert source.name == "AGENTS.md"
    assert source.source_type == "project_instructions"
    assert source.readiness_state == "ready"
