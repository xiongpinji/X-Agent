from __future__ import annotations

from typer.testing import CliRunner

from cli.main import app


def test_control_cli_group_is_registered() -> None:
    result = CliRunner().invoke(app, ["control", "--help"])

    assert result.exit_code == 0
    assert "plan" in result.output
    assert "goal" in result.output


def test_control_cli_plan_and_goal_help() -> None:
    runner = CliRunner()

    plan = runner.invoke(app, ["control", "plan", "draft", "--help"])
    goal = runner.invoke(app, ["control", "goal", "advance", "--help"])

    assert plan.exit_code == 0
    assert "Task to plan without executing" in plan.output
    assert goal.exit_code == 0
    assert "--execute" in goal.output
