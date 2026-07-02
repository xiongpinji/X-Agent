from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_post_adoption_monitor import (
    build_integration_post_adoption_monitor,
    summarize_post_adoption_signal,
)


def test_post_adoption_monitor_ready_with_rollout_validation_owner_and_low_risk() -> None:
    monitor = build_integration_post_adoption_monitor(
        {
            "monitor_id": "monitor-1",
            "rollout_guardrails": {
                "kind": "integration_rollout_guardrails",
                "status": "ready",
                "ok": True,
                "safe_to_rollout": True,
            },
            "owner_digest": {
                "kind": "integration_owner_digest",
                "status": "ready",
                "ok": True,
                "owners": [
                    {
                        "owner": "mainline",
                        "status": "ready",
                        "blocked_count": 0,
                        "evidence_refs": ["owner evidence"],
                    }
                ],
            },
            "validation": {
                "commands": ["python -m pytest tests/test_integration_rollout_guardrails.py -q"],
                "results": ["6 passed"],
            },
            "risks": [{"code": "low_surface_area", "severity": "low", "evidence_refs": ["risk notes"]}],
        }
    )

    assert monitor["kind"] == "integration_post_adoption_monitor"
    assert monitor["ok"] is True
    assert monitor["status"] == "ready"
    assert monitor["summary"]["signal_count"] == 4
    assert monitor["alert_candidates"] == []
    assert monitor["owner_watchlist"] == {"mainline": ["owner_watch_mainline"]}
    assert monitor["next_actions"] == ["review_post_adoption_watchlist_with_mainline"]


def test_validation_failure_creates_alert_candidate() -> None:
    monitor = build_integration_post_adoption_monitor(
        {
            "rollout_guardrails": {
                "kind": "integration_rollout_guardrails",
                "status": "ready",
                "ok": True,
                "safe_to_rollout": True,
            },
            "owner_digest": {
                "owners": [{"owner": "mainline", "status": "ready", "blocked_count": 0}],
            },
            "validation": {
                "commands": ["python -m pytest tests/test_integration_rollout_guardrails.py -q"],
                "results": ["1 failed"],
            },
            "risks": [{"code": "low_surface_area", "severity": "low"}],
        }
    )

    assert monitor["status"] == "blocked"
    assert monitor["alert_candidates"] == ["validation_result_watch"]
    assert monitor["issues"][0]["code"] == "post_adoption_signal_alert"
    assert monitor["next_actions"] == [
        "resolve_post_adoption_alerts",
        "rebuild_integration_post_adoption_monitor",
    ]


def test_blocked_owner_blocks_post_adoption_monitor() -> None:
    monitor = build_integration_post_adoption_monitor(
        {
            "rollout_guardrails": {"status": "ready", "ok": True, "safe_to_rollout": True},
            "owner_digest": {
                "owners": [{"owner": "mainline", "status": "blocked", "blocked_count": 2}],
            },
            "validation": {"commands": ["pytest"], "results": ["passed"]},
            "risks": [{"code": "low_surface_area", "severity": "low"}],
        }
    )

    assert monitor["status"] == "blocked"
    assert monitor["alert_candidates"] == ["owner_watch_mainline"]
    assert monitor["watch_signals"][0]["reasons"] == ["owner has blocked followups"]


def test_high_risk_summary_creates_alert() -> None:
    monitor = build_integration_post_adoption_monitor(
        {
            "rollout_guardrails": {"status": "ready", "ok": True, "safe_to_rollout": True},
            "owner_digest": {"owners": [{"owner": "mainline", "status": "ready"}]},
            "validation": {"commands": ["pytest"], "results": ["passed"]},
            "risks": [{"code": "critical_surface", "severity": "critical"}],
        }
    )

    assert monitor["status"] == "blocked"
    assert monitor["alert_candidates"] == ["risk_watch_critical-surface"]
    assert monitor["issues"][0]["signal_id"] == "risk_watch_critical-surface"


def test_explicit_signals_are_used_when_provided() -> None:
    monitor = build_integration_post_adoption_monitor(
        {
            "signals": [
                {
                    "signal_id": "latency",
                    "source_kind": "manual",
                    "status": "watch",
                    "severity": "medium",
                    "owner": "runtime",
                    "metric": "p95_latency",
                    "threshold": "< 2s",
                    "evidence_refs": ["runbook"],
                }
            ]
        }
    )

    assert monitor["status"] == "needs_review"
    assert monitor["summary"]["signal_count"] == 1
    assert monitor["watch_signals"][0]["signal_id"] == "latency"
    assert monitor["owner_watchlist"] == {"runtime": ["latency"]}


def test_summarize_post_adoption_signal_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Signal:
        signal_id: str
        source_kind: str
        status: str
        severity: str
        owner: str

    signal = summarize_post_adoption_signal(
        Signal("errors", "manual", "alert", "high", "runtime")
    )

    assert signal.signal_id == "errors"
    assert signal.status == "alert"
    assert signal.severity == "high"
    assert signal.reasons == ("high signal requires attention",)
