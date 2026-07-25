"""Workflow management commands.

Provides commands for creating, listing, running, and monitoring workflows.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_json, print_success, print_table
from cli.state import get_current_config

workflow_app = typer.Typer(
    name="workflow",
    help="Workflow management commands",
    no_args_is_help=True,
)


@workflow_app.command("list")
def list_workflows() -> None:
    """List all workflows.

    Displays all workflows available in the system with their IDs, names,
    node counts, and edge counts.

    Example:
        xagent workflow list
    """
    try:
        config = get_current_config()
        client = create_client(config)

        workflows = asyncio.run(client.list_workflows())

        if not workflows:
            print_error("No workflows found", config)
            return

        table_data = [
            {
                "ID": workflow.get("id", workflow.get("workflow_id", "N/A")),
                "Name": workflow.get("name", "N/A"),
                "Nodes": len(workflow.get("nodes", [])),
                "Edges": len(workflow.get("edges", [])),
                "Status": workflow.get("status", "draft"),
            }
            for workflow in workflows
        ]

        print_table(table_data, title="Workflows", config=config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list workflows: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


@workflow_app.command()
def create(
    file: Optional[str] = typer.Option(
        None,
        "--file",
        help="Path to workflow spec file (JSON or YAML)",
    ),
    spec: Optional[str] = typer.Option(
        None,
        "--spec",
        help="Workflow spec as JSON string",
    ),
) -> None:
    """Create a new workflow.

    Accepts workflow specification from either a file or JSON string.
    The spec must be a valid workflow definition.

    Example:
        xagent workflow create --file workflow.json
        xagent workflow create --spec '{"name": "my-workflow", "nodes": [], "edges": []}'
    """
    try:
        config = get_current_config()
        client = create_client(config)

        workflow_spec: dict[str, Any] = {}

        if file:
            file_path = Path(file)
            if not file_path.exists():
                print_error(f"File not found: {file}", config)
                raise typer.Exit(code=1)

            try:
                with open(file_path, "r") as f:
                    if file_path.suffix.lower() == ".json":
                        workflow_spec = json.load(f)
                    elif file_path.suffix.lower() in (".yaml", ".yml"):
                        try:
                            import yaml

                            workflow_spec = yaml.safe_load(f)
                        except ImportError:
                            print_error(
                                "YAML support requires 'pyyaml' package",
                                config,
                            )
                            raise typer.Exit(code=1)
                    else:
                        print_error(
                            f"Unsupported file format: {file_path.suffix}",
                            config,
                        )
                        raise typer.Exit(code=1)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in file: {e}", config)
                raise typer.Exit(code=1)
            except Exception as e:
                print_error(f"Failed to read file: {e}", config)
                raise typer.Exit(code=1)

        elif spec:
            try:
                workflow_spec = json.loads(spec)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in --spec: {e}", config)
                raise typer.Exit(code=1)

        else:
            print_error("Either --file or --spec must be provided", config)
            raise typer.Exit(code=1)

        result = asyncio.run(client.create_workflow(workflow_spec))

        print_json(
            {
                "workflow_id": result.get("id", result.get("workflow_id", "N/A")),
                "name": result.get("name", "N/A"),
                "status": result.get("status", "created"),
            },
            config,
        )
        print_success("Workflow created successfully", config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to create workflow: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


@workflow_app.command()
def run(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to run"),
    inputs: Optional[str] = typer.Option(
        None,
        "--inputs",
        help="Workflow inputs as JSON string",
    ),
) -> None:
    """Run a workflow.

    Executes a workflow with optional input parameters.

    Example:
        xagent workflow run my-workflow-id
        xagent workflow run my-workflow-id --inputs '{"param1": "value1"}'
    """
    try:
        config = get_current_config()
        client = create_client(config)

        workflow_inputs: dict[str, Any] = {}
        if inputs:
            try:
                workflow_inputs = json.loads(inputs)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in --inputs: {e}", config)
                raise typer.Exit(code=1)

        result = asyncio.run(
            client.run_workflow(workflow_id, inputs=workflow_inputs)
        )

        print_json(
            {
                "run_id": result.get("run_id", result.get("id", "N/A")),
                "workflow_id": result.get("workflow_id", workflow_id),
                "status": result.get("status", "running"),
            },
            config,
        )
        print_success("Workflow execution started", config)

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to run workflow: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


@workflow_app.command()
def status(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to check"),
) -> None:
    """Get workflow status.

    Retrieves the current status of a workflow execution.

    Example:
        xagent workflow status my-workflow-id
    """
    try:
        config = get_current_config()
        client = create_client(config)

        result = asyncio.run(client.get_workflow_status(workflow_id))

        print_json(
            {
                "workflow_id": result.get("workflow_id", workflow_id),
                "status": result.get("status", "unknown"),
                "run_count": result.get("run_count", 0),
                "latest_run_id": result.get("latest_run_id"),
            },
            config,
        )

    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to get workflow status: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
