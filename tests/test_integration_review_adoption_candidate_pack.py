from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_adoption_candidate_pack import (
    build_integration_review_adoption_candidate_pack,
    summarize_review_adoption_candidate_pack,
)


def test_review_adoption_candidate_pack_builds_ready_pack() -> None:
    pack = build_integration_review_adoption_candidate_pack(
        {
            "pack_id": "pack-1",
            "acceptance_rollup": {
                "items": [
                    {
                        "candidate_id": "integration_review_acceptance_rollup",
                        "rollup_key": "rollup-a",
                        "verdict": "accepted",
                        "status": "ready",
                        "evidence_refs": ["6 passed"],
                        "handoff_refs": ["handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "file_refs": [
                {
                    "candidate_id": "integration_review_acceptance_rollup",
                    "files": ["backend/app/core/integration_review_acceptance_rollup.py"],
                    "tests": ["tests/test_integration_review_acceptance_rollup.py"],
                }
            ],
        }
    )

    assert pack["kind"] == "integration_review_adoption_candidate_pack"
    assert pack["ok"] is True
    assert pack["status"] == "ready"
    assert pack["summary"]["adoption_ready_count"] == 1
    assert pack["adoption_ready_candidates"] == ["integration_review_acceptance_rollup"]
    assert pack["packs"][0]["adoption_state"] == "adoption_ready"
    assert pack["next_actions"] == ["share_review_adoption_candidate_pack_with_mainline"]


def test_missing_files_tests_and_handoff_need_review() -> None:
    pack = build_integration_review_adoption_candidate_pack(
        {
            "acceptance_rollup": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollup_key": "rollup-a",
                        "verdict": "accepted",
                        "status": "ready",
                        "evidence_refs": ["manual evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert pack["status"] == "needs_review"
    assert pack["review_candidates"] == ["candidate-a"]
    assert "candidate files missing" in pack["packs"][0]["reasons"]
    assert "candidate tests missing" in pack["packs"][0]["reasons"]
    assert "handoff refs missing" in pack["packs"][0]["reasons"]
    assert "attach_adoption_candidate_files" in pack["next_actions"]


def test_blocked_rollup_blocks_adoption_pack() -> None:
    pack = build_integration_review_adoption_candidate_pack(
        {
            "acceptance_rollup": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "rollup_key": "rollup-a",
                        "verdict": "blocked",
                        "status": "blocked",
                        "evidence_refs": ["blocked evidence"],
                        "handoff_refs": ["handoff"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                        "blockers": ["validation timeout"],
                    }
                ]
            },
            "file_refs": {"candidate-a": {"files": ["module.py"], "tests": ["test_module.py"]}},
        }
    )

    assert pack["status"] == "blocked"
    assert pack["blocked_candidates"] == ["candidate-a"]
    assert pack["packs"][0]["adoption_state"] == "blocked"
    assert "candidate source blocked" in pack["packs"][0]["reasons"]
    assert pack["next_actions"] == [
        "resolve_review_adoption_candidate_blockers",
        "attach_adoption_candidate_evidence",
        "rebuild_integration_review_adoption_candidate_pack",
    ]


def test_explicit_pack_payload_can_seed_candidate_bundle() -> None:
    pack = build_integration_review_adoption_candidate_pack(
        {
            "packs": [
                {
                    "candidate_id": "candidate-a",
                    "pack_key": "pack-a",
                    "adoption_state": "adoption_ready",
                    "status": "ready",
                    "files": ["module.py"],
                    "tests": ["test_module.py"],
                    "evidence_refs": ["manual evidence"],
                    "handoff_refs": ["handoff"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert pack["status"] == "ready"
    assert pack["packs"][0]["pack_key"] == "pack-a"
    assert pack["packs"][0]["adoption_state"] == "adoption_ready"


def test_empty_review_adoption_candidate_pack_requests_inputs() -> None:
    pack = build_integration_review_adoption_candidate_pack({})

    assert pack["ok"] is False
    assert pack["status"] == "empty"
    assert pack["next_actions"] == ["provide_review_adoption_candidate_pack_inputs"]


def test_summarize_review_adoption_candidate_pack_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Pack:
        candidate_id: str
        pack_key: str
        adoption_state: str
        status: str
        files: tuple[str, ...]
        tests: tuple[str, ...]
        evidence_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]
        owner: str
        reviewer: str

    item = summarize_review_adoption_candidate_pack(
        Pack(
            candidate_id="candidate-a",
            pack_key="pack-a",
            adoption_state="adoption_ready",
            status="ready",
            files=("module.py",),
            tests=("test_module.py",),
            evidence_refs=("evidence",),
            handoff_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.pack_key == "pack-a"
    assert item.adoption_state == "adoption_ready"
