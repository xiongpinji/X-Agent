"""Hook management commands.

Provides commands for listing, validating, and inspecting hook definitions
from the project-local `.xagent/hooks.json` configuration file.

Unlike agent/tools/workflow commands that call the backend API, hooks
commands operate directly on the local configuration file since hooks
are project-local configuration, not backend state.
"""

from __future__ import annotations

from pathlib import Path

import typer

from cli.console import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from cli.main import get_current_config

hooks_app = typer.Typer(
    name="hooks",
    help="Hook management commands",
    no_args_is_help=True,
)


def _get_hooks_config_path(project_path: str = ".") -> Path:
    """Resolve the hooks configuration file path.

    Args:
        project_path: Project root directory (default: cwd)

    Returns:
        Path to .xagent/hooks.json
    """
    return Path(project_path) / ".xagent" / "hooks.json"


def _load_hooks_config(config_path: Path):
    """Load HooksConfig from the given path.

    Imports HooksConfig lazily to avoid backend dependency at CLI import time.

    Args:
        config_path: Path to hooks.json

    Returns:
        HooksConfig instance
    """
    from backend.app.core.hooks.config import HooksConfig

    return HooksConfig(config_path)


@hooks_app.command("list")
def list_hooks(
    project_path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Project directory path (default: current directory)",
    ),
    all_hooks: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include disabled hooks",
    ),
) -> None:
    """List all configured hooks.

    Displays hooks defined in .xagent/hooks.json with their name, type,
    events, priority, and enabled status.

    Example:
        xagent hooks list
        xagent hooks list --all
        xagent hooks list --path ./my-project
    """
    try:
        config = get_current_config()
        config_path = _get_hooks_config_path(project_path)

        if not config_path.exists():
            print_warning(
                f"No hooks configuration found at {config_path}",
                config,
            )
            print_info(
                "Run 'xagent init project' to create project structure, "
                "then add hooks to .xagent/hooks.json",
                config,
            )
            return

        hooks_config = _load_hooks_config(config_path)

        if all_hooks:
            hooks = hooks_config.hooks
        else:
            hooks = hooks_config.enabled_hooks()

        if not hooks:
            if all_hooks:
                print_info("No hooks defined in configuration", config)
            else:
                print_info(
                    "No enabled hooks found. Use --all to show disabled hooks.",
                    config,
                )
            return

        table_data = [
            {
                "Name": hook.name,
                "Type": hook.type,
                "Events": ", ".join(hook.events),
                "Priority": str(hook.priority),
                "Enabled": "✓" if hook.enabled else "✗",
            }
            for hook in hooks
        ]

        title = "Configured Hooks" if all_hooks else "Enabled Hooks"
        print_table(table_data, title=title, config=config)

    except Exception as e:
        config = get_current_config()
        print_error(f"Failed to list hooks: {e}", config)
        raise typer.Exit(code=1)


@hooks_app.command("validate")
def validate_hooks(
    project_path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Project directory path (default: current directory)",
    ),
) -> None:
    """Validate hooks configuration.

    Checks .xagent/hooks.json for syntax errors, missing required fields,
    invalid event names, and duplicate hook names.

    Example:
        xagent hooks validate
        xagent hooks validate --path ./my-project
    """
    try:
        config = get_current_config()
        config_path = _get_hooks_config_path(project_path)

        if not config_path.exists():
            print_error(
                f"No hooks configuration found at {config_path}",
                config,
            )
            raise typer.Exit(code=1)

        hooks_config = _load_hooks_config(config_path)

        is_valid, errors = hooks_config.validate()

        if is_valid:
            hook_count = len(hooks_config.hooks)
            enabled_count = len(hooks_config.enabled_hooks())
            print_success(
                f"Configuration is valid: {hook_count} hook(s) defined, "
                f"{enabled_count} enabled",
                config,
            )
        else:
            print_error(
                f"Configuration has {len(errors)} error(s):",
                config,
            )
            for error in errors:
                print_error(f"  • {error}", config)
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        config = get_current_config()
        print_error(f"Failed to validate hooks: {e}", config)
        raise typer.Exit(code=1)


@hooks_app.command("show")
def show_hook(
    name: str = typer.Argument(
        ...,
        help="Name of the hook to display",
    ),
    project_path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Project directory path (default: current directory)",
    ),
) -> None:
    """Show details of a specific hook.

    Displays full configuration for a hook including command/target,
    tool matcher pattern, timeout, and all other settings.

    Example:
        xagent hooks show my-hook
        xagent hooks show audit-logger --path ./my-project
    """
    try:
        config = get_current_config()
        config_path = _get_hooks_config_path(project_path)

        if not config_path.exists():
            print_error(
                f"No hooks configuration found at {config_path}",
                config,
            )
            raise typer.Exit(code=1)

        hooks_config = _load_hooks_config(config_path)

        # Find the hook by name
        hook = next((h for h in hooks_config.hooks if h.name == name), None)

        if hook is None:
            print_error(f"Hook '{name}' not found", config)
            available = [h.name for h in hooks_config.hooks]
            if available:
                print_info(f"Available hooks: {', '.join(available)}", config)
            raise typer.Exit(code=1)

        # Build detail dict for display
        from dataclasses import asdict

        hook_dict = asdict(hook)

        # Format for display
        print_info(f"Hook: {hook.name}", config)
        print_info("-" * 40, config)

        # Core fields
        print_info(f"  Type: {hook.type}", config)
        print_info(f"  Events: {', '.join(hook.events)}", config)
        print_info(f"  Priority: {hook.priority}", config)
        print_info(f"  Enabled: {'Yes' if hook.enabled else 'No'}", config)

        # Type-specific fields
        if hook.type == "command":
            cmd_str = " ".join(hook.command) if hook.command else "(not set)"
            print_info(f"  Command: {cmd_str}", config)
            print_info(f"  Timeout: {hook.timeout_seconds}s", config)
        elif hook.type == "python":
            print_info(f"  Target: {hook.target or '(not set)'}", config)

        # Optional fields
        if hook.tool_matcher:
            print_info(f"  Tool Matcher: {hook.tool_matcher}", config)

        # Validation status
        errors = hook.validate()
        if errors:
            print_warning("  Validation errors:", config)
            for error in errors:
                print_warning(f"    • {error}", config)

    except typer.Exit:
        raise
    except Exception as e:
        config = get_current_config()
        print_error(f"Failed to show hook: {e}", config)
        raise typer.Exit(code=1)


@hooks_app.command("init")
def init_hooks(
    project_path: str = typer.Option(
        ".",
        "--path",
        "-p",
        help="Project directory path (default: current directory)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing hooks.json",
    ),
) -> None:
    """Initialize hooks configuration file.

    Creates a starter .xagent/hooks.json with example hook definitions.

    Example:
        xagent hooks init
        xagent hooks init --force
    """
    try:
        config = get_current_config()
        config_path = _get_hooks_config_path(project_path)

        if config_path.exists() and not force:
            print_warning(
                f"Hooks configuration already exists at {config_path}",
                config,
            )
            print_info("Use --force to overwrite", config)
            return

        # Create .xagent directory if needed
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write example configuration
        example_config = """{
  "hooks": [
    {
      "name": "example-guard",
      "type": "command",
      "events": ["pre_tool_use"],
      "command": ["python", ".xagent/hooks/guard.py"],
      "tool_matcher": "write_file|delete_file",
      "priority": 10,
      "timeout_seconds": 5.0,
      "enabled": false
    },
    {
      "name": "example-audit",
      "type": "python",
      "events": ["post_tool_use"],
      "target": "myproject.hooks:AuditHook",
      "priority": 100,
      "enabled": false
    }
  ]
}
"""
        config_path.write_text(example_config, encoding="utf-8")
        print_success(f"Created hooks configuration at {config_path}", config)
        print_info(
            "Edit the file to configure your hooks, then enable them by "
            "setting 'enabled': true",
            config,
        )

    except Exception as e:
        config = get_current_config()
        print_error(f"Failed to initialize hooks: {e}", config)
        raise typer.Exit(code=1)
