"""X-Agent CLI main entry point.

Provides Typer-based command-line interface with support for:
- Global options (--api-url, --api-key, --mode, --output, --version)
- Subcommand groups (agent, tools, workflows, etc.)
- Configuration management
"""

from __future__ import annotations

import logging
import sys

import typer

from cli import __version__
from cli.config import load_config
from cli.console import print_error, print_info

# Shared config state lives in cli.state to avoid a circular import between
# this module (which mounts command apps) and cli.commands.* (which read the
# config). Re-exported here for backward compatibility.
from cli.state import get_current_config, set_current_config

__all__ = ["app", "get_current_config", "main_entry", "set_current_config"]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("xagent.cli")


# Create main Typer app
app = typer.Typer(
    name="xagent",
    help="X-Agent CLI - Enterprise-grade intelligent agent framework",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Handle --version flag.

    Args:
        value: Whether version flag was set
    """
    if value:
        typer.echo(f"xagent version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="Base URL for X-Agent API (default: http://localhost:8000)",
        envvar="XAGENT_API_BASE_URL",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key for authentication",
        envvar="XAGENT_API_KEY",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Client mode: 'http' or 'local' (default: http)",
        envvar="XAGENT_MODE",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Output format: 'rich', 'json', or 'plain' (default: rich)",
        envvar="XAGENT_OUTPUT_FORMAT",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """X-Agent CLI - Enterprise-grade intelligent agent framework.

    Global options can be set via command-line flags, environment variables,
    or configuration file (~/.xagent/config.toml).

    Priority (highest to lowest):
    1. Command-line flags
    2. Environment variables (XAGENT_*)
    3. Configuration file
    4. Default values
    """
    try:
        config = load_config(
            api_base_url=api_url,
            api_key=api_key,
            mode=mode,
            output_format=output,
        )
        set_current_config(config)
        logger.debug(f"Loaded config: mode={config.mode}, url={config.api_base_url}")
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        raise typer.Exit(code=1)


# ============================================================================
# SUBCOMMAND GROUPS - Wave 2
# ============================================================================
# Mount command apps implemented in Wave 2.

from cli.commands import (
    agent_app,
    approvals_app,
    chat_app,
    gateway_app,
    github_app,
    hooks_app,
    init_app,
    memory_app,
    review_app,
    skill_app,
    tools_app,
    workflow_app,
)

app.add_typer(agent_app, name="agent", help="Agent management commands")
app.add_typer(tools_app, name="tools", help="Tool management commands")
app.add_typer(workflow_app, name="workflow", help="Workflow commands")
app.add_typer(init_app, name="init", help="Initialize X-Agent configuration")
app.add_typer(hooks_app, name="hooks", help="Hook management commands")
app.add_typer(approvals_app, name="approvals", help="Approval request management commands")
app.add_typer(github_app, name="github", help="GitHub automation commands")
app.add_typer(gateway_app, name="gateway", help="Gateway and scheduler commands")
app.add_typer(chat_app, name="chat", help="Interactive agent chat")
app.add_typer(review_app, name="review", help="Code review commands")
app.add_typer(memory_app, name="memory", help="Memory search and management")
app.add_typer(skill_app, name="skill", help="Evolved skill management")

# ============================================================================
# STANDALONE COMMANDS
# ============================================================================
# Health check and configuration display commands


@app.command()
def health(
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Override client mode for this command: 'http' or 'local'",
    ),
) -> None:
    """Check X-Agent backend health.

    Verifies connectivity to the backend API or local modules.
    """
    try:
        config = get_current_config()
        if mode is not None:
            from cli.state import apply_mode_override

            try:
                config = apply_mode_override(mode)
            except ValueError as e:
                print_error(str(e))
                raise typer.Exit(code=2)
        from cli.client import create_client

        client = create_client(config)

        import asyncio

        result = asyncio.run(client.health_check())

        if result.get("status") == "healthy":
            print_info(f"Backend is healthy (mode: {config.mode}, url: {config.api_base_url})")
            return

        error = result.get("error") or "no status reported by backend"
        hint = result.get("hint")
        print_error(f"Backend is unhealthy: {error}")
        if hint:
            print_error(f"提示: {hint}")
        elif config.mode == "http" and any(
            token in str(error).lower() for token in ("connect", "timeout")
        ):
            print_error(
                f"提示: 无法连接 {config.api_base_url}，请先启动服务: "
                "uvicorn backend.app.main:app --port 8000"
            )
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Health check failed: {e}")
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """Run local environment self-checks (delegates to cli.commands.doctor)."""
    from cli.commands.doctor import doctor as run_doctor

    run_doctor()


@app.command()
def config_show() -> None:
    """Show current CLI configuration.

    Displays the active configuration from all sources (file, env, defaults).
    """
    try:
        config = get_current_config()
        print_info("Current CLI Configuration:")
        print_info(f"  API URL: {config.api_base_url}")
        print_info(f"  Mode: {config.mode}")
        print_info(f"  Timeout: {config.timeout}s")
        print_info(f"  Output Format: {config.output_format}")
        if config.api_key:
            print_info(f"  API Key: {'*' * 8}...{config.api_key[-4:]}")
        else:
            print_info("  API Key: (not set)")
    except Exception as e:
        print_error(f"Failed to show config: {e}")
        raise typer.Exit(code=1)


# ============================================================================
# REPL Command - Wave 2 Interactive Mode
# ============================================================================
@app.command()
def repl() -> None:
    """Start interactive REPL mode.

    Launches an interactive read-eval-print loop for X-Agent operations.
    Supports command history, auto-completion, and agent/workflow management.

    Examples:
        xagent repl
    """
    try:
        config = get_current_config()
        from cli.repl import start_repl

        start_repl(config)
    except Exception as e:
        print_error(f"Error starting REPL: {e}")
        raise typer.Exit(code=1)


def main_entry() -> None:
    """Entry point for CLI.

    Called by setuptools console_scripts entry point.
    """
    try:
        app()
    except KeyboardInterrupt:
        print_error("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error")
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
