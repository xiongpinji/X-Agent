from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_manifest_review_digest import (
    build_integration_manifest_review_digest,
    summarize_manifest_review_signal,
)


def test_manifest_review_digest_marks_ready_components_ready() -> None:
    digest = build_integration_manifest_review_digest(
        {
            "digest_id": "digest-1",
            "review_packet_manifest": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "ready_count": 1},
                "entries": [{"candidate_id": "candidate-a"}],
            },
            "stage_label_policy": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "ready_count": 1},
                "decisions": [{"candidate_id": "candidate-a"}],
            },
            "manifest_diff_summary": {
                "ok": True,
                "status": "ready",
                "summary": {"changed_count": 0},
            },
            "review_readiness_gate": {
                "ok": True,
                "status": "ready",
                "summary": {"check_count": 6},
            },
            "conflict_risk_register": {
                "ok": True,
                "status": "ready",
                "summary": {"candidate_count": 1, "blocked_count": 0},
            },
        }
    )

    assert digest["kind"] == "integration_manifest_review_digest"
    assert digest["ok"] is True
    assert digest["status"] == "ready"
    assert digest["summary"]["candidate_count"] == 1
    assert digest["next_actions"] == ["share_manifest_review_digest_with_mainline"]


def test_blocked_component_blocks_digest() -> None:
    digest = build_integration_manifest_review_digest(
        {
            "review_packet_manifest": {"ok": True, "status": "ready", "summary": {"candidate_count": 1}},
            "stage_label_policy": {"ok": False, "status": "blocked", "summary": {"blocked_count": 1}},
            "manifest_diff_summary": {
                "ok": False,
                "status": "needs_review",
                "summary": {"changed_count": 1, "removed_count": 1},
                "changed_candidates": ["candidate-a"],
                "removed_candidates": ["candidate-b"],
            },
            "review_readiness_gate": {"ok": True, "status": "ready"},
            "conflict_risk_register": {"ok": True, "status": "ready"},
        }
    )

    assert digest["status"] == "blocked"
    assert digest["blocked_signals"] == ["stage_policy"]
    assert "diff_summary" in digest["review_signals"]
    assert digest["next_actions"] == [
        "resolve_manifest_review_digest_blockers",
        "rebuild_integration_manifest_review_digest",
    ]


def test_missing_components_need_review() -> None:
    digest = build_integration_manifest_review_digest(
        {
            "review_packet_manifest": {"ok": True, "status": "ready", "summary": {"candidate_count": 1}},
        }
    )

    assert digest["status"] == "needs_review"
    assert set(digest["review_signals"]) == {
        "conflict_risk",
        "diff_summary",
        "readiness_gate",
        "stage_policy",
    }
    assert "provide_stage_policy_payload" in digest["next_actions"]


def test_explicit_signals_are_supported() -> None:
    digest = build_integration_manifest_review_digest(
        {
            "signals": [
                {"signal_id": "manifest", "status": "ready", "severity": "low"},
                {"signal_id": "diff", "status": "needs_review", "next_actions": ["review_diff"]},
            ]
        }
    )

    assert digest["status"] == "needs_review"
    assert digest["review_signals"] == ["diff"]
    assert digest["next_actions"] == [
        "review_manifest_digest_warnings",
        "review_diff",
        "rebuild_integration_manifest_review_digest",
    ]


def test_empty_explicit_signals_request_inputs() -> None:
    digest = build_integration_manifest_review_digest({"signals": []})

    assert digest["status"] == "empty"
    assert digest["ok"] is False
    assert digest["next_actions"] == ["provide_manifest_review_digest_inputs"]


def test_summarize_manifest_review_signal_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Signal:
        signal_id: str
        status: str
        severity: str
        refs: list[str]
        reasons: list[str]
        next_actions: list[str]

    signal = summarize_manifest_review_signal(
        Signal("manifest", "ready", "low", ["candidate-a"], ["manifest ready"], [])
    )

    assert signal.signal_id == "manifest"
    assert signal.status == "ready"
    assert signal.severity == "low"
    assert signal.refs == ("candidate-a",)
