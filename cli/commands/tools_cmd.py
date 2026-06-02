"""Tool management commands.

Provides commands for listing and inspecting available tools.
"""

from __future__ import annotations

import asyncio

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_table
from cli.main import get_current_config

tools_app = typer.Typer(
    name="tools",
    help="Tool management commands",
    no_args_is_help=True,
)


@tools_app.command("list")
def list_tools() -> None:
    """List all available tools.

    Displays all tools registered in the X-Agent system with their
    descriptions, categories, and other metadata.

    Example:
        xagent tools list
    """
    try:
        config = get_current_config()
        client = create_client(config)

        tools = asyncio.run(client.list_tools())

        if not tools:
            print_error("No tools found", config)
            return

        table_data = [
            {
                "Name": tool.get("name", "N/A"),
                "Description": str(tool.get("description", "N/A"))[:40],
                "Category": tool.get("category", "N/A"),
                "Status": tool.get("status", "active"),
            }
            for tool in tools
        ]

        print_table(table_data, title="Available Tools", config=config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list tools: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
