"""REPL command for X-Agent CLI.

Provides the 'xagent repl' command to start interactive REPL mode.
"""

from __future__ import annotations

import typer

from cli.repl import start_repl
from cli.state import get_current_config

repl_app = typer.Typer(
    name="repl",
    help="Interactive REPL mode for X-Agent",
    no_args_is_help=False,
)


@repl_app.command()
def repl_command() -> None:
    """Start interactive REPL mode.

    Launches an interactive read-eval-print loop for X-Agent operations.
    Supports command history, auto-completion, and agent/workflow management.

    Examples:
        xagent repl
    """
    try:
        config = get_current_config()
        start_repl(config)
    except Exception as e:
        typer.echo(f"Error starting REPL: {e}", err=True)
        raise typer.Exit(code=1)
