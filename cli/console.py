"""Rich console wrapper for unified output formatting.

Provides consistent output across different formats (rich, json, plain)
and helper functions for common output patterns.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from cli.config import CLIConfig

# Global console instance
_console: Console | None = None


def get_console(config: CLIConfig | None = None) -> Console:
    """Get or create global console instance.

    Args:
        config: CLI configuration (used on first call)

    Returns:
        Rich Console instance
    """
    global _console
    if _console is None:
        force_terminal = True
        if config and config.output_format != "rich":
            force_terminal = False
        _console = Console(force_terminal=force_terminal)
    return _console


def set_output_format(format_type: str) -> None:
    """Set output format for console.

    Args:
        format_type: 'rich', 'json', or 'plain'
    """
    global _console
    if format_type != "rich":
        _console = Console(force_terminal=False)
    else:
        _console = Console(force_terminal=True)


def print_success(message: str, config: CLIConfig | None = None) -> None:
    """Print success message.

    Args:
        message: Message to print
        config: CLI configuration
    """
    console = get_console(config)
    if config and config.output_format == "json":
        print(json.dumps({"status": "success", "message": message}))
    elif config and config.output_format == "plain":
        print(f"✓ {message}")
    else:
        console.print(f"[green]✓ {message}[/green]")


def print_error(message: str, config: CLIConfig | None = None) -> None:
    """Print error message.

    Args:
        message: Message to print
        config: CLI configuration
    """
    console = get_console(config)
    if config and config.output_format == "json":
        print(json.dumps({"status": "error", "message": message}))
    elif config and config.output_format == "plain":
        print(f"✗ {message}")
    else:
        console.print(f"[red]✗ {message}[/red]")


def print_warning(message: str, config: CLIConfig | None = None) -> None:
    """Print warning message.

    Args:
        message: Message to print
        config: CLI configuration
    """
    console = get_console(config)
    if config and config.output_format == "json":
        print(json.dumps({"status": "warning", "message": message}))
    elif config and config.output_format == "plain":
        print(f"⚠ {message}")
    else:
        console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str, config: CLIConfig | None = None) -> None:
    """Print info message.

    Args:
        message: Message to print
        config: CLI configuration
    """
    console = get_console(config)
    if config and config.output_format == "json":
        print(json.dumps({"status": "info", "message": message}))
    elif config and config.output_format == "plain":
        print(f"ℹ {message}")
    else:
        console.print(f"[blue]ℹ {message}[/blue]")


def print_json(data: dict[str, Any] | list[Any], config: CLIConfig | None = None) -> None:
    """Print data as JSON.

    Args:
        data: Data to print
        config: CLI configuration
    """
    if config and config.output_format == "plain":
        print(json.dumps(data, indent=2))
    elif config and config.output_format == "json":
        print(json.dumps(data))
    else:
        console = get_console(config)
        json_str = json.dumps(data, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        console.print(syntax)


def print_table(
    data: list[dict[str, Any]],
    title: str | None = None,
    config: CLIConfig | None = None,
) -> None:
    """Print data as table.

    Args:
        data: List of dictionaries to display
        title: Optional table title
        config: CLI configuration
    """
    if not data:
        print_info("No data to display", config)
        return

    if config and config.output_format == "json":
        print(json.dumps(data))
        return

    if config and config.output_format == "plain":
        for row in data:
            print(" | ".join(f"{k}: {v}" for k, v in row.items()))
        return

    console = get_console(config)
    table = Table(title=title)

    # Add columns from first row
    for key in data[0]:
        table.add_column(key, style="cyan")

    # Add rows
    for row in data:
        table.add_row(*[str(v) for v in row.values()])

    console.print(table)


def print_code(
    code: str,
    language: str = "python",
    config: CLIConfig | None = None,
) -> None:
    """Print code with syntax highlighting.

    Args:
        code: Code to print
        language: Programming language
        config: CLI configuration
    """
    if config and config.output_format in ("json", "plain"):
        print(code)
        return

    console = get_console(config)
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    console.print(syntax)
