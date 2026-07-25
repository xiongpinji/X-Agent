"""GitHub workflow commands."""

from __future__ import annotations

import os

import typer

from backend.app.core.pipelines.issue_to_pr import dry_run_issue_to_pr
from cli.console import print_error, print_json, print_success
from cli.state import get_current_config

github_app = typer.Typer(
    name="github",
    help="GitHub issue and pull-request automation",
    no_args_is_help=True,
)


@github_app.command("issue-to-pr")
def issue_to_pr(
    issue: str = typer.Option(..., "--issue", help="GitHub issue URL"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Plan without writes by default"),
) -> None:
    """Create a deterministic issue-to-PR plan.

    Dry-run mode performs no network writes. Execute mode is intentionally
    guarded and only reports readiness unless a backend runner is configured.
    """

    config = get_current_config()
    try:
        result = dry_run_issue_to_pr({"issue_url": issue}).to_dict()
    except ValueError as exc:
        print_error(str(exc), config)
        raise typer.Exit(code=1)

    if not dry_run:
        token = os.getenv("GITHUB_TOKEN") or os.getenv("XAGENT_GITHUB_TOKEN")
        if not token:
            print_error("GITHUB_TOKEN is required for execute mode.", config)
            raise typer.Exit(code=1)
        result["execute_requested"] = True
        result["execute_guard"] = "token_present_backend_runner_required"

    print_json(result, config)
    if dry_run:
        print_success("Issue-to-PR dry-run plan generated", config)
    else:
        print_success("Issue-to-PR execute preflight generated", config)
