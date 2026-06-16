"""Plan mode and loop-engineering goal commands."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_json, print_success, print_table
from cli.main import get_current_config

control_app = typer.Typer(
    name="control",
    help="Plan mode and loop-engineering goal commands",
    no_args_is_help=True,
)
plan_app = typer.Typer(name="plan", help="Plan-mode commands", no_args_is_help=True)
goal_app = typer.Typer(name="goal", help="Loop-engineering goal commands", no_args_is_help=True)


@plan_app.command("draft")
def draft_plan(
    task: str = typer.Argument(..., help="Task to plan without executing"),
    root: str = typer.Option(".", "--root", help="Repository or workspace root"),
    context: str | None = typer.Option(None, "--context", help="Extra context as JSON"),
    require_approval: bool = typer.Option(
        True,
        "--require-approval/--no-require-approval",
        help="Require approval before execution",
    ),
) -> None:
    """Create a plan-mode draft."""
    try:
        config = get_current_config()
        client = create_client(config)
        result = asyncio.run(
            client.draft_control_plan(
                task,
                root=root,
                context=_json_object(context, "context"),
                require_approval=require_approval,
            )
        )
        print_json(_plan_summary(result), config)
        print_success("Plan draft created", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to draft plan: {e}", get_current_config())
        raise typer.Exit(code=1)


@plan_app.command("approve")
def approve_plan(
    plan_id: str = typer.Argument(..., help="Plan id"),
    reason: str = typer.Option("", "--reason", help="Approval reason"),
) -> None:
    """Approve a plan-mode draft."""
    try:
        config = get_current_config()
        result = asyncio.run(create_client(config).approve_control_plan(plan_id, reason))
        print_json(_plan_summary(result), config)
        print_success("Plan approved", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to approve plan: {e}", get_current_config())
        raise typer.Exit(code=1)


@plan_app.command("reject")
def reject_plan(
    plan_id: str = typer.Argument(..., help="Plan id"),
    reason: str = typer.Option("", "--reason", help="Rejection reason"),
) -> None:
    """Reject a plan-mode draft."""
    try:
        config = get_current_config()
        result = asyncio.run(create_client(config).reject_control_plan(plan_id, reason))
        print_json(_plan_summary(result), config)
        print_success("Plan rejected", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to reject plan: {e}", get_current_config())
        raise typer.Exit(code=1)


@goal_app.command("create")
def create_goal(
    objective: str = typer.Argument(..., help="Goal objective"),
    title: str = typer.Option("", "--title", help="Goal title"),
    context: str | None = typer.Option(None, "--context", help="Extra context as JSON"),
    max_iterations: int = typer.Option(6, "--max-iterations", min=1, max=100),
    token_budget: int | None = typer.Option(None, "--token-budget", min=1),
    require_plan_approval: bool = typer.Option(
        True,
        "--require-plan-approval/--no-require-plan-approval",
    ),
    auto_execute: bool = typer.Option(False, "--auto-execute/--no-auto-execute"),
) -> None:
    """Create a persistent loop-engineering goal."""
    try:
        config = get_current_config()
        policy = {
            "max_iterations": max_iterations,
            "token_budget": token_budget,
            "require_plan_approval": require_plan_approval,
            "auto_execute": auto_execute,
        }
        result = asyncio.run(
            create_client(config).create_control_goal(
                objective,
                title=title,
                context=_json_object(context, "context"),
                policy={k: v for k, v in policy.items() if v is not None},
            )
        )
        print_json(_goal_summary(result), config)
        print_success("Goal created", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to create goal: {e}", get_current_config())
        raise typer.Exit(code=1)


@goal_app.command("advance")
def advance_goal(
    goal_id: str = typer.Argument(..., help="Goal id"),
    execute: bool = typer.Option(False, "--execute/--plan-only", help="Run one agent iteration"),
    force: bool = typer.Option(False, "--force", help="Bypass approval/closed-state guard where allowed"),
    feedback: str = typer.Option("", "--feedback", help="User feedback for this iteration"),
    context: str | None = typer.Option(None, "--context", help="Extra context as JSON"),
) -> None:
    """Advance a goal by one loop-engineering iteration."""
    try:
        config = get_current_config()
        result = asyncio.run(
            create_client(config).advance_control_goal(
                goal_id,
                execute=execute,
                force=force,
                user_feedback=feedback,
                context=_json_object(context, "context"),
            )
        )
        print_json(_goal_summary(result), config)
        print_success("Goal advanced", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to advance goal: {e}", get_current_config())
        raise typer.Exit(code=1)


@goal_app.command("show")
def show_goal(goal_id: str = typer.Argument(..., help="Goal id")) -> None:
    """Show a goal."""
    try:
        config = get_current_config()
        result = asyncio.run(create_client(config).get_control_goal(goal_id))
        print_json(result, config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to show goal: {e}", get_current_config())
        raise typer.Exit(code=1)


@goal_app.command("list")
def list_goals(limit: int = typer.Option(20, "--limit", min=1, max=100)) -> None:
    """List goals."""
    try:
        config = get_current_config()
        result = asyncio.run(create_client(config).list_control_goals(limit=limit))
        table = [
            {
                "Goal ID": item.get("goal_id"),
                "Status": item.get("status"),
                "Stop Reason": item.get("stop_reason"),
                "Iterations": len(item.get("iterations", [])),
                "Title": item.get("title"),
            }
            for item in result
        ]
        print_table(table, title="Loop Engineering Goals", config=config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to list goals: {e}", get_current_config())
        raise typer.Exit(code=1)


@goal_app.command("cancel")
def cancel_goal(
    goal_id: str = typer.Argument(..., help="Goal id"),
    reason: str = typer.Option("", "--reason", help="Cancellation reason"),
) -> None:
    """Cancel a goal."""
    try:
        config = get_current_config()
        result = asyncio.run(create_client(config).cancel_control_goal(goal_id, reason))
        print_json(_goal_summary(result), config)
        print_success("Goal canceled", config)
    except (ConnectionError, AuthError, APIError, XAgentCLIError) as e:
        print_error(f"Failed to cancel goal: {e}", get_current_config())
        raise typer.Exit(code=1)


def _json_object(raw: str | None, label: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise XAgentCLIError(f"Invalid JSON in --{label}: {exc}") from exc
    if not isinstance(value, dict):
        raise XAgentCLIError(f"--{label} must be a JSON object")
    return value


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    execution_plan = plan.get("execution_plan", {})
    coding_loop = plan.get("coding_loop", {})
    return {
        "plan_id": plan.get("plan_id"),
        "status": plan.get("status"),
        "approval_required": plan.get("approval_required"),
        "steps": execution_plan.get("steps", []),
        "verification_steps": execution_plan.get("verification_steps", []),
        "suggested_test_commands": execution_plan.get("suggested_test_commands", []),
        "loop_phases": coding_loop.get("phases", []),
        "next_action": plan.get("snapshot", {}).get("next_action"),
    }


def _goal_summary(goal: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal_id": goal.get("goal_id"),
        "plan_id": goal.get("plan_id"),
        "status": goal.get("status"),
        "stop_reason": goal.get("stop_reason"),
        "iterations": len(goal.get("iterations", [])),
        "active_trace_id": goal.get("active_trace_id"),
        "next_action": goal.get("snapshot", {}).get("next_action"),
        "title": goal.get("title"),
    }


control_app.add_typer(plan_app, name="plan")
control_app.add_typer(goal_app, name="goal")
