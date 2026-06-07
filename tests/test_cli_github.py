from __future__ import annotations

from typer.testing import CliRunner

from cli.config import CLIConfig
from cli.main import app, set_current_config


def test_cli_github_issue_to_pr_dry_run_outputs_plan() -> None:
    set_current_config(CLIConfig(output_format="plain"))
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--output",
            "plain",
            "github",
            "issue-to-pr",
            "--issue",
            "https://github.com/acme/project/issues/42",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert '"branch_name": "xagent/issue-42"' in result.stdout
    assert "dry-run plan generated" in result.stdout


def test_cli_github_issue_to_pr_execute_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("XAGENT_GITHUB_TOKEN", raising=False)
    set_current_config(CLIConfig(output_format="plain"))
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--output",
            "plain",
            "github",
            "issue-to-pr",
            "--issue",
            "https://github.com/acme/project/issues/42",
            "--execute",
        ],
    )

    assert result.exit_code == 1
    assert "GITHUB_TOKEN is required" in result.stdout
