"""CLI code review command."""
from __future__ import annotations

import asyncio
from typing import Optional

import typer

from cli.console import print_error, print_info

review_app = typer.Typer(no_args_is_help=True)


@review_app.command("pr")
def review_pr(
    pr_number: int = typer.Argument(..., help="Pull request number to review"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Repository (owner/name)"),
    focus: Optional[str] = typer.Option(None, "--focus", "-f", help="Focus area: logic, security, style, tests"),
) -> None:
    """Review a pull request.

    Examples:
        xagent review pr 123
        xagent review pr 456 --repo myorg/myrepo --focus security
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "POST",
                "/api/v1/code-review/review",
                json={
                    "pr_number": pr_number,
                    "repo": repo,
                    "focus": focus,
                },
            )
            _print_review_result(response)

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Review failed: {e}")
        raise typer.Exit(code=1)


@review_app.command("diff")
def review_diff(
    diff_file: str = typer.Argument(..., help="Path to diff file or '-' for stdin"),
) -> None:
    """Review a diff file.

    Examples:
        xagent review diff changes.patch
        git diff | xagent review diff -
    """
    import sys

    try:
        if diff_file == "-":
            diff_content = sys.stdin.read()
        else:
            from pathlib import Path
            diff_content = Path(diff_file).read_text(encoding="utf-8")

        if not diff_content.strip():
            print_error("Empty diff")
            raise typer.Exit(code=1)

        from cli.client import create_client
        from cli.state import get_current_config

        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "POST",
                "/api/v1/code-review/review-diff",
                json={"diff": diff_content},
            )
            _print_review_result(response)

        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Review failed: {e}")
        raise typer.Exit(code=1)


def _print_review_result(result: dict) -> None:
    """Print review results in a readable format."""
    if isinstance(result, dict):
        issues = result.get("issues", [])
        summary = result.get("summary", "")

        if summary:
            print_info(f"Summary: {summary}")

        if not issues:
            print_info("No issues found. LGTM!")
            return

        severity_icons = {"critical": "!!", "warning": "! ", "info": "  ", "suggestion": "  "}
        for issue in issues:
            severity = issue.get("severity", "info")
            icon = severity_icons.get(severity, "  ")
            line = issue.get("line", "?")
            message = issue.get("message", "")
            typer.echo(f"  {icon} L{line}: [{severity}] {message}")
    else:
        typer.echo(str(result))
