from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.browser_task_readiness import build_browser_task_readiness


def test_browser_task_ready_with_actions_screenshot_snapshot_and_clean_summaries() -> None:
    report = build_browser_task_readiness(
        {
            "session": {"session_id": "s1", "current_url": "https://example.com", "active": True},
            "actions": [
                {"action": "goto", "ok": True},
                {"action": "click", "ok": True},
                {"action": "screenshot", "ok": True},
            ],
            "console": {"error_count": 0, "has_errors": False},
            "network": {"failed_responses": 0},
            "snapshot": {"label": "after-click"},
        }
    )

    assert report["kind"] == "browser_task_readiness"
    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["next_actions"] == ["attach_browser_evidence", "continue_review"]
    assert report["readiness"]["has_screenshot"] is True


def test_missing_session_blocks_browser_task() -> None:
    report = build_browser_task_readiness({})

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]][:1] == [
        "browser_task_missing_session"
    ]
    assert "provide_browser_session_summary" in report["next_actions"]


def test_failed_action_blocks_browser_task() -> None:
    report = build_browser_task_readiness(
        {
            "session": {"session_id": "s1", "current_url": "https://example.com", "active": True},
            "actions": [{"action": "click", "ok": False}],
            "console": {"error_count": 0},
            "network": {"failed_responses": 0},
            "screenshot": {"present": True},
            "snapshot": {"label": "after-click"},
        }
    )

    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == [
        "browser_task_action_failed"
    ]
    assert report["next_actions"] == ["rerun_failed_browser_actions"]


def test_console_and_network_errors_block_browser_task() -> None:
    report = build_browser_task_readiness(
        {
            "session": {"session_id": "s1", "current_url": "https://example.com", "active": True},
            "actions": [{"action": "goto", "ok": True}, {"action": "screenshot", "ok": True}],
            "console": {"error_count": 2, "has_errors": True},
            "network": {"failed_responses": 1},
            "snapshot": {"label": "after-load"},
        }
    )

    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == [
        "browser_task_console_errors",
        "browser_task_network_failures",
    ]
    assert report["next_actions"] == ["fix_console_errors", "investigate_network_failures"]


def test_missing_evidence_needs_review() -> None:
    report = build_browser_task_readiness(
        {
            "session": {"session_id": "s1", "current_url": "https://example.com", "active": True},
            "actions": [{"action": "goto", "ok": True}],
        }
    )

    assert report["status"] == "needs_review"
    assert [finding["code"] for finding in report["findings"]] == [
        "browser_task_missing_screenshot_evidence",
        "browser_task_missing_snapshot",
    ]
    assert report["next_actions"] == ["attach_screenshot_evidence", "attach_page_snapshot"]


def test_closed_session_needs_review() -> None:
    report = build_browser_task_readiness(
        {
            "session": {"session_id": "s1", "current_url": "https://example.com", "active": False},
            "actions": [{"action": "screenshot", "ok": True}],
            "snapshot": {"label": "closed"},
        }
    )

    assert report["status"] == "needs_review"
    assert [finding["code"] for finding in report["findings"]] == [
        "browser_task_session_closed"
    ]
    assert report["next_actions"] == ["reopen_or_recreate_browser_session"]


def test_accepts_dataclass_like_session() -> None:
    @dataclass
    class Session:
        session_id: str
        current_url: str
        active: bool

    report = build_browser_task_readiness(
        {
            "session": Session("s1", "https://example.com", True),
            "actions": [{"action": "screenshot", "ok": True}],
            "snapshot": {"label": "after"},
        }
    )

    assert report["summary"]["session_id"] == "s1"
    assert report["status"] == "ready"
