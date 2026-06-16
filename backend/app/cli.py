"""
X-Agent CLI tool - Command-line interface for X-Agent.
Provides commands for task execution, configuration, and system management.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel


# Initialize CLI app and console
app = typer.Typer(
    name="xagent",
    help="X-Agent: Advanced AI Agent Execution System",
    no_args_is_help=True,
)
console = Console()


class CommandStatus(str, Enum):
    """Command execution status."""
    SUCCESS = "success"
    RUNNING = "running"
    FAILED = "failed"
    PENDING = "pending"


# ============================================================================
# Core Commands
# ============================================================================

@app.command()
def run(
    task: str = typer.Argument(..., help="Task description or ID"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent name"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Timeout in seconds"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run a task with X-Agent."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_id = progress.add_task(f"Running task: {task}", total=None)

        try:
            # Simulate task execution
            console.print(f"[green]✓[/green] Task started: {task}")
            if agent:
                console.print(f"  Agent: {agent}")
            console.print(f"  Timeout: {timeout}s")

            # In real implementation, this would call the actual agent
            progress.update(task_id, completed=True)
            console.print(f"[green]✓[/green] Task completed successfully")

        except Exception as e:
            console.print(f"[red]✗[/red] Task failed: {str(e)}")
            sys.exit(1)


@app.command()
def chat(
    interactive: bool = typer.Option(True, "--interactive", "-i", help="Interactive mode"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent name"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Context file"),
) -> None:
    """Start interactive chat with X-Agent."""
    console.print(Panel.fit(
        "[bold cyan]X-Agent Interactive Chat[/bold cyan]\n"
        "Type 'help' for commands, 'exit' to quit",
        border_style="cyan"
    ))

    if agent:
        console.print(f"[dim]Agent: {agent}[/dim]")

    if interactive:
        while True:
            try:
                user_input = console.input("[bold cyan]You:[/bold cyan] ")

                if user_input.lower() in ("exit", "quit"):
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                if user_input.lower() == "help":
                    _show_chat_help()
                    continue

                # In real implementation, send to agent
                console.print(f"[cyan]Agent:[/cyan] Processing: {user_input}")

            except KeyboardInterrupt:
                console.print("\n[yellow]Chat interrupted[/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {str(e)}")


@app.command()
def tools(
    action: str = typer.Argument("list", help="Action: list, info, install, uninstall"),
    tool_name: Optional[str] = typer.Option(None, "--name", "-n", help="Tool name"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search query"),
) -> None:
    """Manage X-Agent tools."""
    if action == "list":
        _list_tools(search)
    elif action == "info":
        if not tool_name:
            console.print("[red]Error:[/red] --name required for info action")
            sys.exit(1)
        _show_tool_info(tool_name)
    elif action == "install":
        if not tool_name:
            console.print("[red]Error:[/red] --name required for install action")
            sys.exit(1)
        _install_tool(tool_name)
    elif action == "uninstall":
        if not tool_name:
            console.print("[red]Error:[/red] --name required for uninstall action")
            sys.exit(1)
        _uninstall_tool(tool_name)
    else:
        console.print(f"[red]Unknown action:[/red] {action}")
        sys.exit(1)


@app.command()
def config(
    action: str = typer.Argument("show", help="Action: show, set, get, validate"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Config key"),
    value: Optional[str] = typer.Option(None, "--value", "-v", help="Config value"),
) -> None:
    """Manage X-Agent configuration."""
    if action == "show":
        _show_config()
    elif action == "get":
        if not key:
            console.print("[red]Error:[/red] --key required for get action")
            sys.exit(1)
        _get_config(key)
    elif action == "set":
        if not key or not value:
            console.print("[red]Error:[/red] --key and --value required for set action")
            sys.exit(1)
        _set_config(key, value)
    elif action == "validate":
        _validate_config()
    else:
        console.print(f"[red]Unknown action:[/red] {action}")
        sys.exit(1)


@app.command()
def logs(
    level: str = typer.Option("INFO", "--level", "-l", help="Log level"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines"),
) -> None:
    """View X-Agent logs."""
    console.print(f"[dim]Showing last {lines} log lines (level: {level})[/dim]")

    # Simulate log output
    log_entries = [
        "[2026-05-27 10:30:45] [INFO] X-Agent started",
        "[2026-05-27 10:30:46] [INFO] Loading configuration",
        "[2026-05-27 10:30:47] [INFO] Initializing database",
        "[2026-05-27 10:30:48] [INFO] Starting API server",
        "[2026-05-27 10:30:49] [INFO] Ready to accept requests",
    ]

    for entry in log_entries[-lines:]:
        console.print(entry)

    if follow:
        console.print("[dim]Following logs (Ctrl+C to stop)...[/dim]")
        try:
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Log following stopped[/yellow]")


@app.command()
def status() -> None:
    """Show X-Agent system status."""
    table = Table(title="X-Agent System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")

    # Simulate status check
    components = [
        ("API Server", "✓ Running", "Port 8000"),
        ("Database", "✓ Connected", "PostgreSQL"),
        ("Vector DB", "✓ Connected", "Qdrant"),
        ("LLM Backend", "✓ Ready", "OpenAI"),
        ("Memory System", "✓ Operational", "Multi-layer"),
        ("Observability", "✓ Active", "Langfuse"),
    ]

    for component, status, details in components:
        table.add_row(component, status, details)

    console.print(table)


# ============================================================================
# Admin Commands
# ============================================================================

@app.command()
def admin(
    action: str = typer.Argument(..., help="Admin action"),
) -> None:
    """Administrative commands."""
    if action == "init":
        _admin_init()
    elif action == "migrate":
        _admin_migrate()
    elif action == "backup":
        _admin_backup()
    elif action == "restore":
        _admin_restore()
    else:
        console.print(f"[red]Unknown admin action:[/red] {action}")
        sys.exit(1)


# ============================================================================
# Database Commands
# ============================================================================

@app.command()
def db_migrate() -> None:
    """Run database migrations to latest version.

    This command runs pending Alembic migrations to bring the database
    schema up to date with the latest application code.

    Usage:
        xagent db-migrate
    """
    try:
        # Get project root
        project_root = Path(__file__).parent.parent.parent

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("Running database migrations...", total=None)

            # Run alembic upgrade
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300,
            )

            progress.update(task_id, completed=True)

        if result.returncode == 0:
            console.print("[green]OK[/green] Database migrations completed successfully")
            if result.stdout:
                console.print("[dim]" + result.stdout + "[/dim]")
        else:
            console.print("[red]FAIL[/red] Migration failed")
            console.print(f"[red]{result.stderr}[/red]")
            sys.exit(1)

    except FileNotFoundError:
        console.print(
            "[red]Error: alembic not found. Install it with:[/red]\n"
            "  pip install alembic"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]✗[/red] Migration timed out after 300 seconds")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Migration error: {e}")
        sys.exit(1)


@app.command()
def db_status() -> None:
    """Show current database migration status.

    Displays the current schema version and available migrations.

    Usage:
        xagent db-status
    """
    try:
        # Get project root
        project_root = Path(__file__).parent.parent.parent

        # Run alembic current
        result = subprocess.run(
            ["alembic", "current"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            current = result.stdout.strip() if result.stdout.strip() else "No migrations applied"
            console.print(
                Panel(
                    f"[cyan]Current Schema Version:[/cyan]\n{current}",
                    title="Database Status",
                    border_style="cyan",
                )
            )

            # Also show migration history
            history_result = subprocess.run(
                ["alembic", "history", "--indicate-current"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if history_result.returncode == 0 and history_result.stdout.strip():
                console.print("\n[cyan]Migration History:[/cyan]")
                console.print(history_result.stdout)
        else:
            console.print("[red]✗[/red] Failed to get database status")
            console.print(f"[red]{result.stderr}[/red]")
            sys.exit(1)

    except FileNotFoundError:
        console.print(
            "[red]Error: alembic not found. Install it with:[/red]\n"
            "  pip install alembic"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]✗[/red] Status check timed out")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error checking status: {e}")
        sys.exit(1)



@app.command()
def db_migrate() -> None:
    """Run database migrations to latest version."""
    try:
        project_root = Path(__file__).parent.parent.parent
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task("Running database migrations...", total=None)
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300,
            )
            progress.update(task_id, completed=True)
        if result.returncode == 0:
            console.print("[green]OK[/green] Database migrations completed successfully")
            if result.stdout:
                console.print("[dim]" + result.stdout + "[/dim]")
        else:
            console.print("[red]FAIL[/red] Migration failed")
            console.print(f"[red]{result.stderr}[/red]")
            sys.exit(1)
    except FileNotFoundError:
        console.print(
            "[red]Error: alembic not found. Install it with:[/red]\n"
            "  pip install alembic"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]FAIL[/red] Migration timed out after 300 seconds")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]FAIL[/red] Migration error: {e}")
        sys.exit(1)


@app.command()
def db_status() -> None:
    """Show current database migration status."""
    try:
        project_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["alembic", "current"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            current = result.stdout.strip() if result.stdout.strip() else "No migrations applied"
            console.print(
                Panel(
                    f"[cyan]Current Schema Version:[/cyan]\n{current}",
                    title="Database Status",
                    border_style="cyan",
                )
            )
            history_result = subprocess.run(
                ["alembic", "history", "--indicate-current"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if history_result.returncode == 0 and history_result.stdout.strip():
                console.print("\n[cyan]Migration History:[/cyan]")
                console.print(history_result.stdout)
        else:
            console.print("[red]FAIL[/red] Failed to get database status")
            console.print(f"[red]{result.stderr}[/red]")
            sys.exit(1)
    except FileNotFoundError:
        console.print(
            "[red]Error: alembic not found. Install it with:[/red]\n"
            "  pip install alembic"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]FAIL[/red] Status check timed out")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]FAIL[/red] Error checking status: {e}")
        sys.exit(1)


@app.command()
def db_new_migration(
    message: str = typer.Argument(..., help="Description of the migration"),
    autogenerate: bool = typer.Option(False, "--autogenerate", help="Auto-generate from model changes"),
) -> None:
    """Create a new database migration."""
    try:
        project_root = Path(__file__).parent.parent.parent
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"Creating migration: {message}...", total=None)
            cmd = ["alembic", "revision"]
            if autogenerate:
                cmd.append("--autogenerate")
            cmd.extend(["-m", message])
            result = subprocess.run(
                cmd,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            progress.update(task_id, completed=True)
        if result.returncode == 0:
            console.print("[green]OK[/green] Migration created successfully")
            if result.stdout:
                console.print("[dim]" + result.stdout + "[/dim]")
        else:
            console.print("[red]FAIL[/red] Failed to create migration")
            console.print(f"[red]{result.stderr}[/red]")
            sys.exit(1)
    except FileNotFoundError:
        console.print(
            "[red]Error: alembic not found. Install it with:[/red]\n"
            "  pip install alembic"
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("[red]FAIL[/red] Migration creation timed out")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]FAIL[/red] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
