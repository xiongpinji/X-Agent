from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.task_environment_contracts import build_task_environment_contract


def test_missing_repository_blocks_task_environment() -> None:
    contract = build_task_environment_contract({})

    assert contract["kind"] == "task_environment_contract"
    assert contract["ok"] is False
    assert contract["status"] == "blocked"
    assert "task_environment_missing_repository" in [issue["code"] for issue in contract["issues"]]
    assert contract["next_actions"][:3] == ["declare_repository", "prepare_isolated_worktree", "prepare_sandbox"]


def test_ready_to_start_when_repository_worktree_and_sandbox_exist_without_diff() -> None:
    contract = build_task_environment_contract(
        {
            "task_id": "task-1",
            "repository": {"full_name": "owner/repo", "url": "https://github.com/owner/repo"},
            "worktree": {"id": "wt-1", "branch": "xagent/task-1"},
            "sandbox": {"profile": "workspace_write", "status": "ready"},
        }
    )

    assert contract["ok"] is True
    assert contract["status"] == "ready_to_start"
    assert contract["summary"]["task_id"] == "task-1"
    assert contract["readiness"]["has_repository"] is True
    assert contract["readiness"]["sandbox_ready"] is True
    assert contract["issues"] == []


def test_running_state_preserves_in_progress_task_without_review() -> None:
    contract = build_task_environment_contract(
        {
            "status": "running",
            "repository": {"name": "repo"},
            "worktree": {"id": "wt-1", "branch": "xagent/running"},
            "sandbox": {"sandbox_profile": "workspace_write", "status": "ready"},
        }
    )

    assert contract["ok"] is True
    assert contract["status"] == "running"
    assert contract["next_actions"] == ["wait_for_task_completion", "refresh_environment_status"]


def test_changed_environment_with_passing_tests_and_pull_request_is_merge_ready() -> None:
    contract = build_task_environment_contract(
        {
            "repository": {"full_name": "owner/repo"},
            "worktree": {"path": "C:/tmp/wt", "branch": "xagent/fix"},
            "sandbox": {"profile": "workspace_write"},
            "diff": {"changed_files": 2, "additions": 10, "deletions": 2},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log", "url": "artifact://pytest"}],
            "pull_request": {"number": 7, "url": "https://github.com/owner/repo/pull/7", "status": "open"},
        }
    )

    assert contract["ok"] is True
    assert contract["status"] == "merge_ready"
    assert contract["next_actions"] == ["review_pull_request", "prepare_merge"]
    assert contract["readiness"]["tests_passed"] is True
    assert contract["summary"]["artifact_count"] == 1


def test_diff_without_pull_request_needs_review() -> None:
    contract = build_task_environment_contract(
        {
            "repository": {"name": "repo"},
            "worktree": {"id": "wt-1", "branch": "xagent/change"},
            "sandbox": {"profile": "workspace_write"},
            "diff": {"files": ["backend/app/core/service.py"]},
            "tests": [{"command": "pytest", "outcome": "success"}],
            "artifacts": [{"name": "report"}],
        }
    )

    assert contract["ok"] is False
    assert contract["status"] == "needs_review"
    assert contract["next_actions"] == ["review_diff", "collect_review_artifacts"]


def test_failed_tests_block_merge_readiness() -> None:
    contract = build_task_environment_contract(
        {
            "repository": {"name": "repo"},
            "worktree": {"id": "wt-1", "branch": "xagent/failing"},
            "sandbox": {"profile": "workspace_write"},
            "diff": {"changed_files": 1},
            "tests": [{"name": "pytest", "status": "failed"}],
            "artifacts": [{"name": "pytest.log"}],
            "pull_request": {"number": 3, "status": "open"},
        }
    )

    assert contract["ok"] is False
    assert contract["status"] == "blocked"
    assert [issue["code"] for issue in contract["issues"]] == ["task_environment_tests_failed"]
    assert contract["next_actions"] == ["fix_or_rerun_tests"]


def test_patch_risk_review_keeps_environment_in_review() -> None:
    contract = build_task_environment_contract(
        {
            "repository": {"name": "repo"},
            "worktree": {"id": "wt-1", "branch": "xagent/risky"},
            "sandbox": {"profile": "workspace_write"},
            "diff": {"changed_files": 1},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
            "pull_request": {"number": 9, "status": "open"},
            "patch_risk": {"kind": "patch_risk_analysis", "status": "review_required"},
        }
    )

    assert contract["ok"] is False
    assert contract["status"] == "needs_review"
    assert [issue["code"] for issue in contract["issues"]] == [
        "task_environment_patch_risk_review_required"
    ]


def test_accepts_dataclass_like_payloads() -> None:
    @dataclass
    class Repo:
        name: str

    contract = build_task_environment_contract(
        {
            "repository": Repo(name="repo"),
            "worktree": {"id": "wt-1", "branch": "xagent/dataclass"},
            "sandbox": {"profile": "workspace_write"},
        }
    )

    assert contract["readiness"]["has_repository"] is True
    assert contract["status"] == "ready_to_start"
