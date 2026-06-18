from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


TERMINAL_TEST_STATUSES = {"passed", "failed", "blocked", "skipped"}
PASSING_TEST_STATUSES = {"passed", "success", "succeeded", "ok"}
FAILING_TEST_STATUSES = {"failed", "failure", "error", "errored", "blocked", "timeout", "timed_out"}
RUNNING_STATUSES = {"running", "in_progress", "queued", "starting", "pending"}


@dataclass(frozen=True)
class TaskEnvironmentIssue:
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


def build_task_environment_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    repository = _as_mapping(data.get("repository"))
    worktree = _as_mapping(data.get("worktree"))
    sandbox = _as_mapping(data.get("sandbox"))
    pull_request = _as_mapping(data.get("pull_request") or data.get("pr"))
    diff = _as_mapping(data.get("diff"))
    patch_risk = _as_mapping(data.get("patch_risk") or data.get("patch_risk_report"))
    artifacts = [_as_mapping(item) for item in _as_sequence(data.get("artifacts"))]
    tests = [_as_mapping(item) for item in _as_sequence(data.get("tests") or data.get("test_results"))]
    issues = _collect_issues(
        repository=repository,
        worktree=worktree,
        sandbox=sandbox,
        pull_request=pull_request,
        diff=diff,
        patch_risk=patch_risk,
        artifacts=artifacts,
        tests=tests,
    )
    lifecycle_state = _lifecycle_state(data, issues=issues, diff=diff, tests=tests, pull_request=pull_request)
    blockers = [issue.code for issue in issues if issue.severity in {"critical", "high"}]
    review_items = [issue.code for issue in issues if issue.severity == "medium"]

    return {
        "kind": "task_environment_contract",
        "version": 1,
        "ok": lifecycle_state in {"ready_to_start", "running", "merge_ready"},
        "status": lifecycle_state,
        "summary": {
            "task_id": str(data.get("task_id") or data.get("id") or ""),
            "repository": str(repository.get("name") or repository.get("full_name") or repository.get("url") or ""),
            "branch": str(worktree.get("branch") or ""),
            "sandbox_profile": str(sandbox.get("profile") or sandbox.get("sandbox_profile") or ""),
            "artifact_count": len(artifacts),
            "test_count": len(tests),
            "blocker_count": len(blockers),
            "review_item_count": len(review_items),
        },
        "readiness": {
            "has_repository": bool(repository.get("url") or repository.get("name") or repository.get("full_name")),
            "has_branch": bool(worktree.get("branch")),
            "has_worktree": bool(worktree.get("path") or worktree.get("id")),
            "sandbox_ready": _sandbox_ready(sandbox),
            "tests_passed": _tests_passed(tests),
            "has_artifacts": bool(artifacts),
            "has_pull_request": bool(pull_request.get("url") or pull_request.get("number")),
            "has_diff": _has_diff(diff),
        },
        "issues": [issue.as_dict() for issue in issues],
        "next_actions": _next_actions(lifecycle_state, issues),
        "inputs": {
            "repository": repository,
            "worktree": worktree,
            "sandbox": sandbox,
            "pull_request": pull_request,
            "diff": diff,
            "patch_risk_status": patch_risk.get("status"),
        },
    }


def _collect_issues(
    *,
    repository: Mapping[str, Any],
    worktree: Mapping[str, Any],
    sandbox: Mapping[str, Any],
    pull_request: Mapping[str, Any],
    diff: Mapping[str, Any],
    patch_risk: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    tests: Sequence[Mapping[str, Any]],
) -> list[TaskEnvironmentIssue]:
    issues: list[TaskEnvironmentIssue] = []
    if not (repository.get("url") or repository.get("name") or repository.get("full_name")):
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_missing_repository",
                "critical",
                "Task environment requires repository identity before execution can start.",
            )
        )
    if not worktree.get("branch"):
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_missing_branch",
                "high",
                "Task environment should declare a branch for review and merge tracking.",
            )
        )
    if not (worktree.get("path") or worktree.get("id")):
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_missing_worktree",
                "high",
                "Task environment should identify the isolated worktree or equivalent workspace.",
            )
        )
    if not _sandbox_ready(sandbox):
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_sandbox_not_ready",
                "high",
                "Sandbox profile is missing or not ready.",
                {"status": sandbox.get("status"), "profile": sandbox.get("profile") or sandbox.get("sandbox_profile")},
            )
        )
    failed_tests = [item for item in tests if _status(item) in FAILING_TEST_STATUSES]
    if failed_tests:
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_tests_failed",
                "high",
                "Task environment has failing or blocked tests.",
                {"failed": [_test_name(item) for item in failed_tests]},
            )
        )
    if tests and not _tests_passed(tests) and not failed_tests:
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_tests_incomplete",
                "medium",
                "Task environment has tests that are not complete yet.",
            )
        )
    if _has_diff(diff) and not artifacts:
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_missing_artifacts",
                "medium",
                "Changed task environment should include artifacts or evidence for review.",
            )
        )
    if patch_risk and patch_risk.get("status") == "review_required":
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_patch_risk_review_required",
                "medium",
                "Patch risk analysis requires human review before merge readiness.",
                {"patch_risk_kind": patch_risk.get("kind")},
            )
        )
    if pull_request and str(pull_request.get("status") or "").lower() in {"closed", "merged"}:
        issues.append(
            TaskEnvironmentIssue(
                "task_environment_pr_not_open",
                "medium",
                "Pull request is not open for active review.",
                {"status": pull_request.get("status")},
            )
        )
    return issues


def _lifecycle_state(
    payload: Mapping[str, Any],
    *,
    issues: Sequence[TaskEnvironmentIssue],
    diff: Mapping[str, Any],
    tests: Sequence[Mapping[str, Any]],
    pull_request: Mapping[str, Any],
) -> str:
    explicit = str(payload.get("status") or payload.get("state") or "").lower()
    if explicit in {"blocked", "failed", "error"}:
        return "blocked"
    if any(issue.severity in {"critical", "high"} for issue in issues):
        return "blocked"
    if explicit in RUNNING_STATUSES:
        return "running"
    if _has_diff(diff) and _tests_passed(tests) and not any(issue.severity == "medium" for issue in issues):
        if pull_request.get("url") or pull_request.get("number"):
            return "merge_ready"
        return "needs_review"
    if _has_diff(diff):
        return "needs_review"
    return "ready_to_start"


def _next_actions(state: str, issues: Sequence[TaskEnvironmentIssue]) -> list[str]:
    if state == "merge_ready":
        return ["review_pull_request", "prepare_merge"]
    if state == "running":
        return ["wait_for_task_completion", "refresh_environment_status"]
    if state == "needs_review":
        return ["review_diff", "collect_review_artifacts"]
    actions: list[str] = []
    issue_codes = {issue.code for issue in issues}
    if "task_environment_missing_repository" in issue_codes:
        actions.append("declare_repository")
    if "task_environment_missing_branch" in issue_codes or "task_environment_missing_worktree" in issue_codes:
        actions.append("prepare_isolated_worktree")
    if "task_environment_sandbox_not_ready" in issue_codes:
        actions.append("prepare_sandbox")
    if "task_environment_tests_failed" in issue_codes:
        actions.append("fix_or_rerun_tests")
    if not actions:
        actions.append("start_task")
    return actions


def _sandbox_ready(sandbox: Mapping[str, Any]) -> bool:
    profile = sandbox.get("profile") or sandbox.get("sandbox_profile")
    status = str(sandbox.get("status") or "ready").lower() if sandbox else ""
    return bool(profile) and status not in {"missing", "failed", "blocked", "not_ready"}


def _tests_passed(tests: Sequence[Mapping[str, Any]]) -> bool:
    return bool(tests) and all(_status(item) in PASSING_TEST_STATUSES for item in tests)


def _has_diff(diff: Mapping[str, Any]) -> bool:
    if not diff:
        return False
    for key in ("changed_files", "files_changed", "additions", "deletions"):
        value = diff.get(key)
        if isinstance(value, int) and value > 0:
            return True
    files = diff.get("files")
    return isinstance(files, Sequence) and not isinstance(files, (str, bytes)) and bool(files)


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
