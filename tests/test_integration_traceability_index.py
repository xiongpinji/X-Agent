from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_traceability_index import (
    analyze_traceability_record,
    build_integration_traceability_index,
)


def test_traceability_index_marks_complete_record_ready() -> None:
    index = build_integration_traceability_index(
        {
            "index_id": "trace-1",
            "candidates": [
                {
                    "candidate_id": "sequence-plan",
                    "owner": "mainline",
                    "files": ["backend/app/core/integration_sequence_plan.py"],
                    "tests": ["tests/test_integration_sequence_plan.py"],
                    "validation_commands": ["python -m pytest tests/test_integration_sequence_plan.py -q"],
                    "handoff_refs": ["docs/original-kernel-secondary-handoff.md#integration-sequence-plan"],
                    "decisions": ["accepted"],
                    "evidence_refs": ["237 passed", "py_compile passed"],
                    "validation_statuses": ["passed"],
                }
            ],
        }
    )

    assert index["kind"] == "integration_traceability_index"
    assert index["ok"] is True
    assert index["status"] == "ready"
    assert index["summary"]["ready_count"] == 1
    assert index["coverage"]["test_coverage"] == 1.0
    assert index["next_actions"] == ["prepare_auditable_integration_review"]


def test_traceability_index_flags_missing_refs_for_review() -> None:
    index = build_integration_traceability_index(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "owner": "mainline",
                    "files": ["backend/app/core/candidate_a.py"],
                    "decisions": ["accepted"],
                    "evidence_refs": ["handoff"],
                }
            ]
        }
    )

    assert index["status"] == "needs_review"
    assert index["issues"][0]["code"] == "traceability_tests_missing"
    assert index["issues"][1]["code"] == "traceability_validation_commands_missing"
    assert index["issues"][2]["code"] == "traceability_handoff_refs_missing"
    assert index["next_actions"] == [
        "add_candidate_file_and_test_refs",
        "attach_passing_validation_evidence",
        "attach_handoff_references",
        "rebuild_integration_traceability_index",
    ]


def test_failed_validation_blocks_traceability_record() -> None:
    index = build_integration_traceability_index(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "owner": "mainline",
                    "files": ["backend/app/core/candidate_a.py"],
                    "tests": ["tests/test_candidate_a.py"],
                    "validation_commands": ["python -m pytest tests/test_candidate_a.py -q"],
                    "handoff_refs": ["handoff"],
                    "decisions": ["accepted"],
                    "evidence_refs": ["failed validation"],
                    "validation_statuses": ["failed"],
                }
            ]
        }
    )

    assert index["status"] == "blocked"
    assert index["records"][0]["status"] == "blocked"
    assert index["issues"][0]["code"] == "traceability_validation_blocked"
    assert index["next_actions"] == [
        "resolve_blocked_traceability_records",
        "attach_passing_validation_evidence",
        "rebuild_integration_traceability_index",
    ]


def test_index_merges_sequence_scorecard_decision_and_ref_collections() -> None:
    index = build_integration_traceability_index(
        {
            "sequence_plan": {
                "candidates": [{"candidate_id": "candidate-a", "owner": "mainline"}],
            },
            "scorecard": {
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "files": ["backend/app/core/candidate_a.py"],
                        "tests": ["tests/test_candidate_a.py"],
                        "evidence": ["scorecard"],
                    }
                ]
            },
            "decision_audit": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "decision": "accepted",
                        "evidence_refs": ["decision-audit"],
                    }
                ]
            },
            "validations": [
                {
                    "candidate_id": "candidate-a",
                    "command": "python -m pytest tests/test_candidate_a.py -q",
                    "status": "passed",
                }
            ],
            "handoff_refs": [
                {
                    "candidate_id": "candidate-a",
                    "ref": "docs/original-kernel-secondary-handoff.md#candidate-a",
                }
            ],
        }
    )

    assert index["status"] == "ready"
    record = index["records"][0]
    assert record["candidate_id"] == "candidate-a"
    assert record["validation_commands"] == ["python -m pytest tests/test_candidate_a.py -q"]
    assert record["handoff_refs"] == ["docs/original-kernel-secondary-handoff.md#candidate-a"]
    assert record["decisions"] == ["accepted"]


def test_accepts_dataclass_like_record() -> None:
    @dataclass
    class Record:
        candidate_id: str
        owner: str
        files: list[str]
        tests: list[str]
        validation_commands: list[str]
        handoff_refs: list[str]
        decisions: list[str]
        evidence_refs: list[str]
        validation_statuses: list[str]

    index = build_integration_traceability_index(
        {
            "records": [
                Record(
                    "candidate-a",
                    "mainline",
                    ["backend/app/core/candidate_a.py"],
                    ["tests/test_candidate_a.py"],
                    ["python -m pytest tests/test_candidate_a.py -q"],
                    ["handoff#candidate-a"],
                    ["accepted"],
                    ["tests passed"],
                    ["passed"],
                )
            ]
        }
    )

    assert index["status"] == "ready"
    assert index["records"][0]["candidate_id"] == "candidate-a"


def test_analyze_record_marks_rejected_decision_blocked() -> None:
    record = analyze_traceability_record(
        {
            "candidate_id": "candidate-a",
            "owner": "mainline",
            "files": ["backend/app/core/candidate_a.py"],
            "tests": ["tests/test_candidate_a.py"],
            "validation_commands": ["python -m pytest tests/test_candidate_a.py -q"],
            "handoff_refs": ["handoff#candidate-a"],
            "decisions": ["rejected"],
            "evidence_refs": ["decision audit"],
            "validation_statuses": ["passed"],
        }
    )

    assert record.status == "blocked"
    assert "integration decision rejected or blocked" in record.reasons


def test_empty_traceability_index_requests_records() -> None:
    index = build_integration_traceability_index({})

    assert index["status"] == "empty"
    assert index["ok"] is False
    assert index["next_actions"] == ["provide_traceability_records"]
