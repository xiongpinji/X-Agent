"""Project initialization commands.

Provides interactive setup for X-Agent CLI configuration and project structure.
"""

from __future__ import annotations

from pathlib import Path

import typer

from cli.config import load_config, save_config
from cli.console import print_error, print_info, print_success, print_warning

init_app = typer.Typer(
    name="init",
    help="Initialize X-Agent project configuration",
    no_args_is_help=True,
)


@init_app.command()
def setup(
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="API base URL (default: http://localhost:8000)",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key for authentication (optional)",
    ),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Client mode: 'http' or 'local' (default: http)",
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Use interactive mode for setup",
    ),
) -> None:
    """Initialize X-Agent CLI configuration.

    Creates or updates the CLI configuration file at ~/.xagent/config.toml
    with API endpoint and authentication settings.

    Example:
        xagent init setup
        xagent init setup --api-url http://api.example.com --mode http
        xagent init setup --no-interactive --api-url http://localhost:8000
    """
    try:
        config_path = Path.home() / ".xagent" / "config.toml"

        print_info("X-Agent CLI Configuration Setup")
        print_info("=" * 50)

        if config_path.exists():
            print_warning(f"Configuration file already exists: {config_path}")

        if interactive and not api_url and not api_key and not mode:
            print_info("\nEnter configuration values (press Enter for defaults):")

            api_url = (
                typer.prompt(
                    "API Base URL",
                    default="http://localhost:8000",
                )
                or "http://localhost:8000"
            )

            mode = (
                typer.prompt(
                    "Client Mode (http/local)",
                    default="http",
                )
                or "http"
            )

            if mode not in ("http", "local"):
                print_error(f"Invalid mode: {mode}. Must be 'http' or 'local'")
                raise typer.Exit(code=1)

            api_key_input = typer.prompt(
                "API Key (optional)",
                default="",
                hide_input=True,
            )
            if api_key_input:
                api_key = api_key_input

        config = load_config(
            api_base_url=api_url,
            api_key=api_key,
            mode=mode,
        )

        try:
            save_config(config)
            print_success(f"Configuration saved to {config_path}")
            print_info("\nActive Configuration:")
            print_info(f"  API URL: {config.api_base_url}")
            print_info(f"  Mode: {config.mode}")
            print_info(f"  Timeout: {config.timeout}s")
            print_info(f"  Output Format: {config.output_format}")
            if config.api_key:
                print_info(f"  API Key: {'*' * 8}...{config.api_key[-4:]}")

        except Exception as e:
            print_error(f"Failed to save configuration: {e}")
            raise typer.Exit(code=1)

    except typer.Abort:
        print_warning("Setup cancelled")
        raise typer.Exit(code=0)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        raise typer.Exit(code=1)


@init_app.command()
def project(
    name: str | None = typer.Option(
        None,
        "--name",
        help="Project name",
    ),
    path: str = typer.Option(
        ".",
        "--path",
        help="Project directory path",
    ),
) -> None:
    """Initialize a new X-Agent project structure.

    Creates a basic project directory structure with configuration,
    workflows, and tools directories.

    Example:
        xagent init project --name my-project
        xagent init project --path ./my-project --name my-project
    """
    try:
        project_path = Path(path)

        if not name:
            name = typer.prompt("Project name")

        print_info(f"Creating project: {name} at {project_path.absolute()}")

        project_path.mkdir(parents=True, exist_ok=True)

        dirs = [
            project_path / ".xagent",
            project_path / "workflows",
            project_path / "tools",
            project_path / "data",
        ]

        for directory in dirs:
            directory.mkdir(exist_ok=True)
            print_info(f"  Created directory: {directory.relative_to(project_path)}")

        config_file = project_path / ".xagent" / "config.toml"
        if not config_file.exists():
            config_template = """[xagent]
api_base_url = "http://localhost:8000"
mode = "http"
timeout = 30
output_format = "rich"
# api_key = ""
"""
            config_file.write_text(config_template)
            print_info(f"  Created configuration: {config_file.relative_to(project_path)}")

        workflows_example = project_path / "workflows" / "example.json"
        if not workflows_example.exists():
            example_workflow = """{
  "name": "example-workflow",
  "description": "Example workflow template",
  "nodes": [],
  "edges": []
}
"""
            workflows_example.write_text(example_workflow)
            print_info(
                f"  Created example workflow: {workflows_example.relative_to(project_path)}"
            )

        gitignore_file = project_path / ".gitignore"
        if not gitignore_file.exists():
            gitignore_content = """# X-Agent
.xagent/config.toml
*.pyc
__pycache__/
.env
.DS_Store
*.log
"""
            gitignore_file.write_text(gitignore_content)
            print_info("  Created .gitignore")

        print_success(f"Project '{name}' initialized successfully!")
        print_info("\nNext steps:")
        print_info(f"  1. cd {path}")
        print_info("  2. xagent init setup")
        print_info("  3. xagent agent run 'Your task here'")

    except typer.Abort:
        print_warning("Project creation cancelled")
        raise typer.Exit(code=0)
    except Exception as e:
        print_error(f"Failed to create project: {e}")
        raise typer.Exit(code=1)
