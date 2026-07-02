from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


ACTION_REQUIRED = {"goto", "click", "fill", "extract_text", "wait_for", "screenshot"}
SUCCESS_STATUSES = {"passed", "success", "succeeded", "ok", "ready"}
FAIL_STATUSES = {"failed", "failure", "error", "errored", "blocked", "timeout", "timed_out"}


@dataclass(frozen=True)
class BrowserTaskFinding:
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def build_browser_task_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    session = _as_mapping(data.get("session") or data.get("browser_session"))
    actions = [_as_mapping(item) for item in _as_sequence(data.get("actions") or session.get("actions"))]
    console = _as_mapping(data.get("console") or data.get("console_summary"))
    network = _as_mapping(data.get("network") or data.get("network_summary"))
    screenshot = _as_mapping(data.get("screenshot") or data.get("screenshot_summary"))
    snapshot = _as_mapping(data.get("snapshot") or data.get("page_snapshot"))
    findings = _collect_findings(
        session=session,
        actions=actions,
        console=console,
        network=network,
        screenshot=screenshot,
        snapshot=snapshot,
    )
    status = _status_from_findings(findings)
    blockers = [finding.code for finding in findings if finding.severity in {"critical", "high"}]
    review_items = [finding.code for finding in findings if finding.severity == "medium"]

    return {
        "kind": "browser_task_readiness",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "summary": {
            "session_id": str(session.get("session_id") or session.get("id") or ""),
            "current_url": str(session.get("current_url") or session.get("url") or ""),
            "action_count": len(actions),
            "failed_action_count": len(_failed_actions(actions)),
            "console_error_count": _int(console.get("error_count")),
            "network_failed_response_count": _int(network.get("failed_responses")),
            "blocker_count": len(blockers),
            "review_item_count": len(review_items),
        },
        "readiness": {
            "session_active": bool(session.get("active", True)) if session else False,
            "has_current_url": bool(session.get("current_url") or session.get("url")),
            "has_actions": bool(actions),
            "actions_successful": not _failed_actions(actions),
            "has_screenshot": _has_screenshot(screenshot, actions),
            "console_clear": _console_clear(console),
            "network_clear": _network_clear(network),
            "has_snapshot": bool(snapshot),
        },
        "findings": [finding.as_dict() for finding in findings],
        "next_actions": _next_actions(status, findings),
    }


def _collect_findings(
    *,
    session: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    console: Mapping[str, Any],
    network: Mapping[str, Any],
    screenshot: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> list[BrowserTaskFinding]:
    findings: list[BrowserTaskFinding] = []
    if not session:
        findings.append(
            BrowserTaskFinding(
                "browser_task_missing_session",
                "high",
                "Browser task requires a session summary.",
            )
        )
    elif session.get("active") is False:
        findings.append(
            BrowserTaskFinding(
                "browser_task_session_closed",
                "medium",
                "Browser session is closed.",
            )
        )
    if session and not (session.get("current_url") or session.get("url")):
        findings.append(
            BrowserTaskFinding(
                "browser_task_missing_current_url",
                "medium",
                "Browser session should include the current URL.",
            )
        )
    if not actions:
        findings.append(
            BrowserTaskFinding(
                "browser_task_missing_actions",
                "medium",
                "Browser task should include action evidence.",
            )
        )
    failed_actions = _failed_actions(actions)
    if failed_actions:
        findings.append(
            BrowserTaskFinding(
                "browser_task_action_failed",
                "high",
                "Browser task has failed actions.",
                {"failed_actions": failed_actions},
            )
        )
    if actions and not _has_screenshot(screenshot, actions):
        findings.append(
            BrowserTaskFinding(
                "browser_task_missing_screenshot_evidence",
                "medium",
                "Browser task should include screenshot evidence after actions.",
            )
        )
    if not _console_clear(console):
        findings.append(
            BrowserTaskFinding(
                "browser_task_console_errors",
                "high",
                "Browser console summary indicates errors.",
                {"error_count": _int(console.get("error_count"))},
            )
        )
    if not _network_clear(network):
        findings.append(
            BrowserTaskFinding(
                "browser_task_network_failures",
                "high",
                "Browser network summary indicates failed responses.",
                {"failed_responses": _int(network.get("failed_responses"))},
            )
        )
    if actions and not snapshot:
        findings.append(
            BrowserTaskFinding(
                "browser_task_missing_snapshot",
                "medium",
                "Browser task should include a DOM/accessibility snapshot or equivalent page summary.",
            )
        )
    return findings


def _status_from_findings(findings: Sequence[BrowserTaskFinding]) -> str:
    if any(finding.severity in {"critical", "high"} for finding in findings):
        return "blocked"
    if any(finding.severity == "medium" for finding in findings):
        return "needs_review"
    return "ready"


def _next_actions(status: str, findings: Sequence[BrowserTaskFinding]) -> list[str]:
    if status == "ready":
        return ["attach_browser_evidence", "continue_review"]
    codes = {finding.code for finding in findings}
    actions: list[str] = []
    if "browser_task_missing_session" in codes:
        actions.append("provide_browser_session_summary")
    if "browser_task_session_closed" in codes:
        actions.append("reopen_or_recreate_browser_session")
    if "browser_task_missing_current_url" in codes:
        actions.append("capture_current_url")
    if "browser_task_missing_actions" in codes:
        actions.append("record_browser_actions")
    if "browser_task_action_failed" in codes:
        actions.append("rerun_failed_browser_actions")
    if "browser_task_missing_screenshot_evidence" in codes:
        actions.append("attach_screenshot_evidence")
    if "browser_task_console_errors" in codes:
        actions.append("fix_console_errors")
    if "browser_task_network_failures" in codes:
        actions.append("investigate_network_failures")
    if "browser_task_missing_snapshot" in codes:
        actions.append("attach_page_snapshot")
    return actions or ["review_browser_findings"]


def _failed_actions(actions: Sequence[Mapping[str, Any]]) -> list[str]:
    failed: list[str] = []
    for item in actions:
        ok = item.get("ok")
        status = str(item.get("status") or item.get("outcome") or "").lower()
        if ok is False or status in FAIL_STATUSES:
            failed.append(str(item.get("action") or item.get("name") or "<unnamed>"))
    return failed


def _has_screenshot(screenshot: Mapping[str, Any], actions: Sequence[Mapping[str, Any]]) -> bool:
    if screenshot:
        return bool(screenshot.get("path") or screenshot.get("url") or screenshot.get("present") is True)
    return any(str(action.get("action") or "").lower() == "screenshot" and action.get("ok", True) is not False for action in actions)


def _console_clear(console: Mapping[str, Any]) -> bool:
    if not console:
        return True
    if console.get("has_errors") is True:
        return False
    return _int(console.get("error_count")) == 0


def _network_clear(network: Mapping[str, Any]) -> bool:
    if not network:
        return True
    return _int(network.get("failed_responses")) == 0 and _int(network.get("failed_requests")) == 0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []
