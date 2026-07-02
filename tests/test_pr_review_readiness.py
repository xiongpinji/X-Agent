from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.pr_review_readiness import build_pr_review_readiness


def test_review_ready_with_diff_tests_artifacts_and_open_pr() -> None:
    report = build_pr_review_readiness(
        {
            "task_environment": {"status": "merge_ready"},
            "diff": {"changed_files": 2},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
            "pull_request": {"number": 7, "status": "open"},
            "patch_risk": {"status": "passed"},
            "redaction": {"status": "passed"},
        }
    )

    assert report["kind"] == "pr_review_readiness"
    assert report["ok"] is True
    assert report["status"] == "review_ready"
    assert report["next_actions"] == ["request_pr_review", "prepare_merge_review"]
    assert report["readiness"]["tests_passed"] is True


def test_missing_diff_blocks_review() -> None:
    report = build_pr_review_readiness(
        {
            "task_environment": {"status": "ready_to_start"},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
        }
    )

    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == ["pr_review_missing_diff"]
    assert report["next_actions"] == ["attach_diff_summary"]


def test_failed_tests_block_review() -> None:
    report = build_pr_review_readiness(
        {
            "diff": {"files": ["backend/app/core/service.py"]},
            "tests": [{"command": "pytest", "status": "failed"}],
            "artifacts": [{"name": "pytest.log"}],
        }
    )

    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == ["pr_review_tests_failed"]
    assert report["next_actions"] == ["fix_or_rerun_tests"]


def test_secret_leak_blocks_review_even_with_passing_tests() -> None:
    report = build_pr_review_readiness(
        {
            "diff": {"changed_files": 1},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
            "redaction": {"status": "leak_detected", "leak_detected": True},
        }
    )

    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == ["pr_review_secret_leak_blocked"]
    assert report["next_actions"] == ["redact_or_rotate_secret"]


def test_patch_risk_and_high_risk_flags_require_human_review() -> None:
    report = build_pr_review_readiness(
        {
            "diff": {"changed_files": 1},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
            "patch_risk": {
                "status": "review_required",
                "issues": [{"code": "patch_sensitive_file_requires_review"}],
            },
            "patch_plan": {
                "risk_flags": ["security_sensitive", "may_affect_authentication"],
            },
        }
    )

    assert report["ok"] is False
    assert report["status"] == "needs_human_review"
    assert [finding["code"] for finding in report["findings"]] == [
        "pr_review_patch_risk_requires_human_review",
        "pr_review_high_risk_patch_plan",
    ]
    assert report["next_actions"] == ["request_human_review"]


def test_missing_tests_and_artifacts_need_human_review() -> None:
    report = build_pr_review_readiness({"diff": {"changed_files": 1}})

    assert report["status"] == "needs_human_review"
    assert [finding["code"] for finding in report["findings"]] == [
        "pr_review_missing_tests",
        "pr_review_missing_artifacts",
    ]
    assert report["next_actions"] == ["collect_test_evidence", "attach_review_artifacts"]


def test_blocked_task_environment_blocks_review() -> None:
    report = build_pr_review_readiness(
        {
            "task_environment": {"status": "blocked"},
            "diff": {"changed_files": 1},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
        }
    )

    assert report["status"] == "blocked"
    assert [finding["code"] for finding in report["findings"]] == [
        "pr_review_task_environment_blocked"
    ]
    assert report["next_actions"] == ["resolve_task_environment_blockers"]


def test_accepts_dataclass_like_pull_request_payload() -> None:
    @dataclass
    class PullRequest:
        number: int
        status: str

    report = build_pr_review_readiness(
        {
            "diff": {"files": ["README.md"]},
            "tests": [{"name": "pytest", "status": "passed"}],
            "artifacts": [{"name": "pytest.log"}],
            "pull_request": PullRequest(number=5, status="open"),
        }
    )

    assert report["readiness"]["has_pull_request"] is True
    assert report["status"] == "review_ready"
