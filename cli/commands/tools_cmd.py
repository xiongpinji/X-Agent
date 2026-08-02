"""Tool management commands.

Provides commands for listing and inspecting available tools.
"""

from __future__ import annotations

import asyncio

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_table
from cli.state import get_current_config

tools_app = typer.Typer(
    name="tools",
    help="Tool management commands",
    no_args_is_help=True,
)


@tools_app.command("list")
def list_tools(
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Override client mode for this command: 'http' or 'local'",
    ),
) -> None:
    """List all available tools.

    Displays all tools registered in the X-Agent system with their
    descriptions, categories, and other metadata.

    Example:
        xagent tools list
    """
    try:
        config = get_current_config()
        if mode is not None:
            from cli.state import apply_mode_override

            try:
                config = apply_mode_override(mode)
            except ValueError as e:
                print_error(str(e), config)
                raise typer.Exit(code=2)
        client = create_client(config)

        tools = asyncio.run(client.list_tools())

        if not tools:
            print_error("No tools found", config)
            return

        table_data = [
            {
                "Name": tool.get("name", "N/A"),
                "Description": str(tool.get("description", "N/A"))[:40],
                "Risk": tool.get("risk_level", "N/A"),
                "Scope": tool.get("required_scope", "N/A"),
            }
            for tool in tools
        ]

        print_table(table_data, title=f"Available Tools ({config.mode} mode)", config=config)

    except typer.Exit:
        raise
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list tools: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
