"""Agent management commands.

Provides commands for running agents, listing available agents, and managing
agent execution with permission scopes and context.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_json, print_success, print_table
from cli.state import get_current_config

agent_app = typer.Typer(
    name="agent",
    help="Agent management commands",
    no_args_is_help=True,
)


@agent_app.command()
def run(
    task: str = typer.Argument(..., help="Task description for the agent to execute"),
    scope: Optional[list[str]] = typer.Option(
        None,
        "--scope",
        help="Permission scopes (can be used multiple times)",
    ),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        help="Extra context as JSON string",
    ),
    stream: bool = typer.Option(
        False,
        "--stream/--no-stream",
        help="Stream results as they arrive",
    ),
) -> None:
    """Run an agent with the given task.

    Example:
        xagent agent run "Analyze the market trends"
        xagent agent run "Search for Python tutorials" --scope tools:read --scope memory:read
        xagent agent run "Process data" --context '{"format": "json"}'
    """
    try:
        config = get_current_config()
        client = create_client(config)

        permission_scope = scope or ["tools:read", "memory:read", "memory:write"]

        extra_context: dict[str, Any] = {}
        if context:
            try:
                extra_context = json.loads(context)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in --context: {e}", config)
                raise typer.Exit(code=1)

        result = asyncio.run(
            client.run_agent(
                task=task,
                permission_scope=permission_scope,
                extra_context=extra_context,
                stream=stream,
            )
        )

        display_result = {
            "trace_id": result.get("trace_id", "N/A"),
            "status": result.get("status", "N/A"),
            "task": result.get("task", task)[:50],
            "tool_calls": len(result.get("tool_calls", [])),
        }

        print_json(display_result, config)

        # Display the actual answer prominently
        answer = result.get("answer", "")
        if answer:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            console = Console()
            console.print()
            console.print(Panel(
                Text(answer[:2000], style="green"),
                title="\u2713 Answer",
                border_style="green",
                padding=(0, 1),
            ))

        print_success("Agent execution completed", config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Agent execution failed: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


@agent_app.command("list")
def list_agents() -> None:
    """List all available agents.

    Example:
        xagent agent list
    """
    try:
        config = get_current_config()
        client = create_client(config)

        result = asyncio.run(client.list_agents())

        agents = result.get("data", []) if isinstance(result, dict) else result

        if not agents:
            print_error("No agents found", config)
            return

        table_data = [
            {
                "ID": agent.get("id", "N/A"),
                "Name": agent.get("name", "N/A"),
                "Status": agent.get("status", "N/A"),
                "Capabilities": ", ".join(agent.get("capabilities", [])),
            }
            for agent in agents
        ]

        print_table(table_data, title="Available Agents", config=config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list agents: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
