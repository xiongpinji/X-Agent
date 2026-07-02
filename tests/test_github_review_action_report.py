from __future__ import annotations

import json
from pathlib import Path

from scripts.github_review_action_report import (
    build_github_review_action_report,
    main,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def test_github_review_action_report_default_is_read_only() -> None:
    report = build_github_review_action_report()
    payload = report.to_dict()

    assert report.status == "github_review_action_report_ready"
    assert report.evidence_type == "github_review_action"
    assert report.full_codex_parity_claimed is False
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.owner_gate_required is True
    assert report.issue["repo_full_name"] == "xiongpinji/X-Agent"
    assert report.issue["issue_number"] == 1
    assert report.branch["planned_head"] == "xagent/issue-1"
    assert report.branch["push_performed"] is False
    assert report.pull_request["create_pr_performed"] is False
    assert report.pull_request["comment_performed"] is False
    assert report.review["review_posted"] is False
    assert report.action_gate["requires_owner_approval"] is True
    assert "git_push" in report.action_gate["blocked_mutations"]
    assert {check["status"] for check in payload["checks"]} == {"passed"}


def test_github_review_action_report_maps_issue_pr_ci_and_review_evidence() -> None:
    report = build_github_review_action_report(
        {
            "issue_url": "https://github.com/acme/project/issues/42",
            "title": "Security auth regression in backend/app/auth.py",
            "body": "Please fix backend/app/auth.py and add tests.",
            "labels": ["security", "test"],
            "default_branch": "main",
        }
    )

    assert report.issue["repo_full_name"] == "acme/project"
    assert report.issue["issue_number"] == 42
    assert report.branch["base"] == "main"
    assert report.branch["planned_head"] == "xagent/issue-42"
    assert "backend/app/auth.py" in report.patch_plan["touched_file_candidates"]
    assert "may_affect_authentication" in report.patch_plan["risk_flags"]
    assert "security_sensitive" in report.patch_plan["risk_flags"]
    assert report.ci["test_command"] == "pytest -q"
    assert report.ci["required_before_execute"] is True
    assert report.review["trigger"] == "@codex review compatible"
    assert report.review["comment_priorities"] == ["P0", "P1"]
    assert report.action_gate["execute_allowed"] is False


def test_github_review_action_report_redacts_secret_like_issue_content() -> None:
    report = build_github_review_action_report(
        {
            "issue_url": "https://github.com/acme/project/issues/7",
            "title": "Do not leak " + "sk-" + "test1234567890abcdef",
            "body": "Bearer abcdefghijklmnopqrstuvwxyz must not appear.",
        }
    )
    rendered = json.dumps(report.to_dict(), ensure_ascii=False)

    assert "sk-test" not in rendered
    assert "Bearer abcdef" not in rendered
    assert "<redacted>" in rendered


def test_write_github_review_action_report_json_and_markdown(tmp_path: Path) -> None:
    report = build_github_review_action_report(
        {"issue_url": "https://github.com/acme/project/issues/9", "title": "Review CI"}
    )
    json_output = tmp_path / "github-review-action-report.json"
    markdown_output = tmp_path / "github-review-action-report.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "github_review_action_report_ready"
    assert payload["network_mutation_performed"] is False
    assert payload["full_codex_parity_claimed"] is False
    assert "# X-Agent GitHub Review Action Report" in markdown
    assert "acme/project" in render_markdown_report(report)


def test_github_review_action_report_cli_writes_read_only_report(tmp_path: Path, monkeypatch) -> None:
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"
    issue_json = tmp_path / "issue.json"
    issue_json.write_text(
        json.dumps(
            {
                "issue_url": "https://github.com/acme/project/issues/88",
                "title": "Patch docs/README.md",
                "body": "Documentation update only.",
                "labels": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "github_review_action_report.py",
            "--issue-json",
            str(issue_json),
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    assert main() == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["issue"]["issue_number"] == 88
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert markdown_output.exists()
