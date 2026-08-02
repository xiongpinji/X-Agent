"""CLI skill commands - manage evolved skills."""
from __future__ import annotations

import asyncio

import typer

from cli.console import print_error, print_info

skill_app = typer.Typer(no_args_is_help=True)


@skill_app.command("list")
def skill_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
) -> None:
    """List evolved skills.

    Examples:
        xagent skill list
        xagent skill list --limit 5
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "GET", "/api/v1/evolution/skills", params={"limit": limit}
            )
            skills = response.get("skills", response) if isinstance(response, dict) else response
            if not skills:
                print_info("No evolved skills yet.")
                return
            for i, skill in enumerate(skills, 1):
                if isinstance(skill, dict):
                    name = skill.get("name", "unnamed")
                    desc = skill.get("description", "")[:60]
                    rate = skill.get("success_rate", 0)
                    usage = skill.get("usage_count", 0)
                    typer.echo(f"  {i}. {name} (rate: {rate:.0%}, used: {usage}x)")
                    if desc:
                        typer.echo(f"     {desc}")
                else:
                    typer.echo(f"  {i}. {skill}")

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Skill list failed: {e}")
        raise typer.Exit(code=1)


@skill_app.command("stats")
def skill_stats() -> None:
    """Show evolution engine statistics.

    Examples:
        xagent skill stats
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request("GET", "/api/v1/evolution/stats")
            if isinstance(response, dict):
                print_info("Evolution Engine Statistics:")
                print_info(f"  Total executions: {response.get('total_executions', 0)}")
                print_info(f"  Skill drafts: {response.get('skill_drafts', 0)}")
                print_info(f"  Promoted skills: {response.get('promoted_skills', 0)}")
                names = response.get("skill_names", [])
                if names:
                    print_info(f"  Skills: {', '.join(names[:10])}")
            else:
                typer.echo(str(response))

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Skill stats failed: {e}")
        raise typer.Exit(code=1)


@skill_app.command("match")
def skill_match(
    task: str = typer.Argument(..., help="Task description to match against skills"),
) -> None:
    """Find a matching skill for a task.

    Examples:
        xagent skill match "refactor authentication module"
    """
    from cli.client import create_client
    from cli.state import get_current_config

    try:
        config = get_current_config()
        client = create_client(config)

        async def _run():
            response = await client.request(
                "POST", "/api/v1/evolution/match", json={"task": task}
            )
            skill = response.get("skill") if isinstance(response, dict) else None
            if skill:
                print_info(f"Matched skill: {skill.get('name', 'unknown')}")
                print_info(f"  Description: {skill.get('description', '')}")
                print_info(f"  Tools: {skill.get('tool_sequence', [])}")
            else:
                print_info("No matching skill found.")

        asyncio.run(_run())
    except Exception as e:
        print_error(f"Skill match failed: {e}")
        raise typer.Exit(code=1)
