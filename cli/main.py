"""X-Agent CLI main entry point.

Provides Typer-based command-line interface with support for:
- Global options (--api-url, --api-key, --mode, --output, --version)
- Subcommand groups (agent, tools, workflows, etc.)
- Configuration management
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import typer

from cli import __version__
from cli.config import CLIConfig, load_config
from cli.console import print_error, print_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("xagent.cli")

# Global state for CLI context
_current_config: CLIConfig | None = None


def get_current_config() -> CLIConfig:
    """Get current CLI configuration.

    Returns:
        Current CLIConfig instance

    Raises:
        RuntimeError: If config not initialized
    """
    if _current_config is None:
        raise RuntimeError("CLI config not initialized")
    return _current_config


def set_current_config(config: CLIConfig) -> None:
    """Set current CLI configuration.

    Args:
        config: CLIConfig instance to set
    """
    global _current_config
    _current_config = config


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
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help="Base URL for X-Agent API (default: http://localhost:8000)",
        envvar="XAGENT_API_BASE_URL",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API key for authentication",
        envvar="XAGENT_API_KEY",
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help="Client mode: 'http' or 'local' (default: http)",
        envvar="XAGENT_MODE",
    ),
    output: Optional[str] = typer.Option(
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

from cli.commands import agent_app, init_app, tools_app, workflow_app, hooks_app, approvals_app, control_app, github_app, gateway_app, sdk_app

app.add_typer(agent_app, name="agent", help="Agent management commands")
app.add_typer(tools_app, name="tools", help="Tool management commands")
app.add_typer(workflow_app, name="workflow", help="Workflow commands")
app.add_typer(init_app, name="init", help="Initialize X-Agent configuration")
app.add_typer(hooks_app, name="hooks", help="Hook management commands")
app.add_typer(approvals_app, name="approvals", help="Approval request management commands")
app.add_typer(control_app, name="control", help="Plan mode and loop-engineering goal commands")
app.add_typer(github_app, name="github", help="GitHub automation commands")
app.add_typer(gateway_app, name="gateway", help="Gateway and scheduler commands")
app.add_typer(sdk_app, name="sdk", help="SDK and non-interactive control-plane commands")

# ============================================================================
# STANDALONE COMMANDS
# ============================================================================
# Health check and configuration display commands


@app.command()
def health() -> None:
    """Check X-Agent backend health.

    Verifies connectivity to the backend API or local modules.
    """
    try:
        config = get_current_config()
        from cli.client import create_client

        client = create_client(config)

        import asyncio

        result = asyncio.run(client.health_check())

        if result.get("status") == "healthy":
            print_info(f"Backend is healthy (mode: {config.mode})")
        else:
            error = result.get("error", "Unknown error")
            print_error(f"Backend is unhealthy: {error}")
            raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Health check failed: {e}")
        raise typer.Exit(code=1)


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
