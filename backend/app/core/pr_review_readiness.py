from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


PASSING_TEST_STATUSES = {"passed", "success", "succeeded", "ok"}
FAILING_TEST_STATUSES = {"failed", "failure", "error", "errored", "blocked", "timeout", "timed_out"}
HIGH_RISK_FLAGS = {
    "touches_secret_or_credentials",
    "security_sensitive",
    "may_affect_authentication",
    "may_require_database_migration",
}


@dataclass(frozen=True)
class PRReviewFinding:
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


def build_pr_review_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    task_environment = _as_mapping(data.get("task_environment") or data.get("task_environment_contract"))
    patch_risk = _as_mapping(data.get("patch_risk") or data.get("patch_risk_report"))
    redaction = _as_mapping(data.get("redaction") or data.get("output_redaction"))
    diff = _as_mapping(data.get("diff"))
    patch_plan = _as_mapping(data.get("patch_plan"))
    pull_request = _as_mapping(data.get("pull_request") or data.get("pr"))
    artifacts = [_as_mapping(item) for item in _as_sequence(data.get("artifacts"))]
    tests = [_as_mapping(item) for item in _as_sequence(data.get("tests") or data.get("test_results"))]
    findings = _collect_findings(
        task_environment=task_environment,
        patch_risk=patch_risk,
        redaction=redaction,
        diff=diff,
        patch_plan=patch_plan,
        pull_request=pull_request,
        artifacts=artifacts,
        tests=tests,
    )
    status = _status_from_findings(findings)
    blockers = [finding.code for finding in findings if finding.severity in {"critical", "high"}]
    review_items = [finding.code for finding in findings if finding.severity == "medium"]

    return {
        "kind": "pr_review_readiness",
        "version": 1,
        "ok": status == "review_ready",
        "status": status,
        "summary": {
            "blocker_count": len(blockers),
            "review_item_count": len(review_items),
            "test_count": len(tests),
            "artifact_count": len(artifacts),
            "changed_files": _changed_files(diff),
            "risk_flag_count": len(_risk_flags(patch_plan)),
        },
        "readiness": {
            "has_diff": _has_diff(diff),
            "has_tests": bool(tests),
            "tests_passed": _tests_passed(tests),
            "has_artifacts": bool(artifacts),
            "has_pull_request": bool(pull_request.get("url") or pull_request.get("number")),
            "task_environment_ready": task_environment.get("status") in {"merge_ready", "needs_review"},
            "patch_risk_clear": not patch_risk or patch_risk.get("status") == "passed",
            "redaction_clear": _redaction_clear(redaction),
        },
        "findings": [finding.as_dict() for finding in findings],
        "next_actions": _next_actions(status, findings),
        "inputs": {
            "task_environment_status": task_environment.get("status"),
            "patch_risk_status": patch_risk.get("status"),
            "redaction_status": redaction.get("status"),
            "pull_request_status": pull_request.get("status"),
            "risk_flags": _risk_flags(patch_plan),
        },
    }


def _collect_findings(
    *,
    task_environment: Mapping[str, Any],
    patch_risk: Mapping[str, Any],
    redaction: Mapping[str, Any],
    diff: Mapping[str, Any],
    patch_plan: Mapping[str, Any],
    pull_request: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    tests: Sequence[Mapping[str, Any]],
) -> list[PRReviewFinding]:
    findings: list[PRReviewFinding] = []
    if task_environment and task_environment.get("status") == "blocked":
        findings.append(
            PRReviewFinding(
                "pr_review_task_environment_blocked",
                "high",
                "Task environment is blocked.",
                {"task_environment_status": task_environment.get("status")},
            )
        )
    if not _has_diff(diff):
        findings.append(
            PRReviewFinding(
                "pr_review_missing_diff",
                "high",
                "PR review readiness requires a changed diff payload.",
            )
        )
    if not tests:
        findings.append(
            PRReviewFinding(
                "pr_review_missing_tests",
                "medium",
                "PR review should include test evidence.",
            )
        )
    failed_tests = [item for item in tests if _status(item) in FAILING_TEST_STATUSES]
    if failed_tests:
        findings.append(
            PRReviewFinding(
                "pr_review_tests_failed",
                "high",
                "PR review is blocked by failing tests.",
                {"failed": [_test_name(item) for item in failed_tests]},
            )
        )
    if tests and not _tests_passed(tests) and not failed_tests:
        findings.append(
            PRReviewFinding(
                "pr_review_tests_incomplete",
                "medium",
                "PR review has incomplete or pending test evidence.",
            )
        )
    if _has_diff(diff) and not artifacts:
        findings.append(
            PRReviewFinding(
                "pr_review_missing_artifacts",
                "medium",
                "PR review should include logs, reports, screenshots, or other evidence artifacts.",
            )
        )
    if patch_risk and patch_risk.get("status") == "review_required":
        findings.append(
            PRReviewFinding(
                "pr_review_patch_risk_requires_human_review",
                "medium",
                "Patch risk analysis requires human review.",
                {"issue_codes": _issue_codes(patch_risk)},
            )
        )
    if redaction and not _redaction_clear(redaction):
        findings.append(
            PRReviewFinding(
                "pr_review_secret_leak_blocked",
                "critical",
                "Redaction or leak detection report indicates possible secret exposure.",
            )
        )
    high_flags = sorted(set(_risk_flags(patch_plan)).intersection(HIGH_RISK_FLAGS))
    if high_flags:
        findings.append(
            PRReviewFinding(
                "pr_review_high_risk_patch_plan",
                "medium",
                "Patch plan includes risk flags that should be reviewed by a human.",
                {"risk_flags": high_flags},
            )
        )
    if pull_request and str(pull_request.get("status") or "").lower() in {"closed", "merged"}:
        findings.append(
            PRReviewFinding(
                "pr_review_pull_request_not_open",
                "medium",
                "Pull request is not open for review.",
                {"status": pull_request.get("status")},
            )
        )
    return findings


def _status_from_findings(findings: Sequence[PRReviewFinding]) -> str:
    if any(finding.severity in {"critical", "high"} for finding in findings):
        return "blocked"
    if any(finding.severity == "medium" for finding in findings):
        return "needs_human_review"
    return "review_ready"


def _next_actions(status: str, findings: Sequence[PRReviewFinding]) -> list[str]:
    if status == "review_ready":
        return ["request_pr_review", "prepare_merge_review"]
    codes = {finding.code for finding in findings}
    actions: list[str] = []
    if "pr_review_task_environment_blocked" in codes:
        actions.append("resolve_task_environment_blockers")
    if "pr_review_missing_diff" in codes:
        actions.append("attach_diff_summary")
    if "pr_review_tests_failed" in codes:
        actions.append("fix_or_rerun_tests")
    if "pr_review_secret_leak_blocked" in codes:
        actions.append("redact_or_rotate_secret")
    if "pr_review_missing_tests" in codes or "pr_review_tests_incomplete" in codes:
        actions.append("collect_test_evidence")
    if "pr_review_missing_artifacts" in codes:
        actions.append("attach_review_artifacts")
    if "pr_review_patch_risk_requires_human_review" in codes or "pr_review_high_risk_patch_plan" in codes:
        actions.append("request_human_review")
    if "pr_review_pull_request_not_open" in codes:
        actions.append("open_or_reopen_pull_request")
    return actions or ["review_findings"]


def _redaction_clear(redaction: Mapping[str, Any]) -> bool:
    if not redaction:
        return True
    if redaction.get("leak_detected") is True or redaction.get("has_secret_leak") is True:
        return False
    status = str(redaction.get("status") or "").lower()
    return status not in {"failed", "blocked", "leak_detected", "secret_leak_detected"}


def _tests_passed(tests: Sequence[Mapping[str, Any]]) -> bool:
    return bool(tests) and all(_status(item) in PASSING_TEST_STATUSES for item in tests)


def _has_diff(diff: Mapping[str, Any]) -> bool:
    return _changed_files(diff) > 0


def _changed_files(diff: Mapping[str, Any]) -> int:
    for key in ("changed_files", "files_changed"):
        value = diff.get(key)
        if isinstance(value, int):
            return max(value, 0)
    files = diff.get("files")
    if isinstance(files, Sequence) and not isinstance(files, (str, bytes)):
        return len(files)
    return 1 if diff.get("has_diff") is True else 0


def _risk_flags(patch_plan: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in _as_sequence(patch_plan.get("risk_flags")) if str(item)]


def _issue_codes(report: Mapping[str, Any]) -> list[str]:
    return [
        str(item.get("code"))
        for item in (_as_mapping(entry) for entry in _as_sequence(report.get("issues")))
        if str(item.get("code") or "")
    ]


def _status(item: Mapping[str, Any]) -> str:
    return str(item.get("status") or item.get("outcome") or "").strip().lower()


def _test_name(item: Mapping[str, Any]) -> str:
    return str(item.get("name") or item.get("command") or item.get("id") or "<unnamed>")


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
