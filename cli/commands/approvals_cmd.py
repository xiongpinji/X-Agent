"""Approval management commands.

Provides commands for listing, inspecting, and deciding on approval requests
created when a tool requires human approval (via policy or a hook returning
ASK). Approvals are backend state, so these commands require HTTP mode.
"""

from __future__ import annotations

import asyncio

import typer

from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.console import print_error, print_info, print_json, print_success, print_table
from cli.state import get_current_config

approvals_app = typer.Typer(
    name="approvals",
    help="Approval request management commands",
    no_args_is_help=True,
)
@approvals_app.command(name="list")
def list_approvals(
    status: str = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: pending | approved | rejected | executed",
    ),
    tenant_id: str = typer.Option(
        None, "--tenant", "-t", help="Filter by tenant id"
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max records to return"),
) -> None:
    """List approval requests.

    Displays approval requests with their id, resource, risk level, and status.
    Use --status pending to see only requests awaiting a decision.

    Example:
        xagent approvals list --status pending
    """
    config = get_current_config()
    try:
        client = create_client(config)
        approvals = asyncio.run(
            client.list_approvals(status=status, tenant_id=tenant_id, limit=limit)
        )

        if not approvals:
            print_info("No approval requests found", config)
            return

        if config.output_format == "json":
            print_json(approvals, config)
            return

        table_data = [
            {
                "ID": str(item.get("id", "N/A"))[:18],
                "Resource": f"{item.get('resource_type', '?')}:{item.get('resource_id', '?')}",
                "Action": item.get("action", "N/A"),
                "Risk": item.get("risk_level", "N/A"),
                "Status": item.get("status", "N/A"),
                "Reason": str(item.get("reason", ""))[:30],
            }
            for item in approvals
        ]
        print_table(table_data, title="Approval Requests", config=config)

    except NotImplementedError as e:
        print_error(f"{e}", config)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to list approvals: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
@approvals_app.command()
def show(
    approval_id: str = typer.Argument(..., help="Approval request id"),
) -> None:
    """Show details of a single approval request.

    Displays full information including arguments preview, timestamps, and
    decision metadata.

    Example:
        xagent approvals show abc123
    """
    config = get_current_config()
    try:
        client = create_client(config)
        record = asyncio.run(client.get_approval(approval_id))

        if config.output_format == "json":
            print_json(record, config)
            return

        print_info(f"Approval: {record.get('id')}", config)
        print_info(f"  Resource: {record.get('resource_type')}:{record.get('resource_id')}", config)
        print_info(f"  Action: {record.get('action')}", config)
        print_info(f"  Risk Level: {record.get('risk_level')}", config)
        print_info(f"  Status: {record.get('status')}", config)
        print_info(f"  Reason: {record.get('reason')}", config)
        print_info(f"  Created: {record.get('created_at')}", config)
        if record.get("decided_by"):
            print_info(f"  Decided By: {record.get('decided_by')}", config)
            print_info(f"  Decided At: {record.get('decided_at')}", config)
            print_info(f"  Decision Reason: {record.get('decision_reason')}", config)
        if record.get("executed_by"):
            print_info(f"  Executed By: {record.get('executed_by')}", config)
            print_info(f"  Executed At: {record.get('executed_at')}", config)
        if record.get("arguments_preview"):
            print_info("  Arguments Preview:", config)
            for k, v in record.get("arguments_preview", {}).items():
                print_info(f"    {k}: {v}", config)

    except NotImplementedError as e:
        print_error(f"{e}", config)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to get approval: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
@approvals_app.command()
def approve(
    approval_id: str = typer.Argument(..., help="Approval request id"),
    by: str = typer.Option("anonymous", "--by", "-b", help="Approver identity"),
    reason: str = typer.Option("", "--reason", "-r", help="Decision reason"),
) -> None:
    """Approve a pending approval request.

    Marks the request approved. Use 'xagent approvals execute' afterwards to
    actually run the approved tool.

    Example:
        xagent approvals approve abc123 --by alice --reason "verified safe"
    """
    config = get_current_config()
    try:
        client = create_client(config)
        record = asyncio.run(
            client.approve_request(approval_id, decided_by=by, reason=reason)
        )
        print_success(
            f"Approved {record.get('id')} (status: {record.get('status')})", config
        )
        if config.output_format == "json":
            print_json(record, config)

    except NotImplementedError as e:
        print_error(f"{e}", config)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to approve request: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
@approvals_app.command()
def reject(
    approval_id: str = typer.Argument(..., help="Approval request id"),
    by: str = typer.Option("anonymous", "--by", "-b", help="Approver identity"),
    reason: str = typer.Option("", "--reason", "-r", help="Decision reason"),
) -> None:
    """Reject a pending approval request.

    Marks the request rejected; the underlying tool will not be executed.

    Example:
        xagent approvals reject abc123 --by alice --reason "too risky"
    """
    config = get_current_config()
    try:
        client = create_client(config)
        record = asyncio.run(
            client.reject_request(approval_id, decided_by=by, reason=reason)
        )
        print_success(
            f"Rejected {record.get('id')} (status: {record.get('status')})", config
        )
        if config.output_format == "json":
            print_json(record, config)

    except NotImplementedError as e:
        print_error(f"{e}", config)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to reject request: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)


@approvals_app.command()
def execute(
    approval_id: str = typer.Argument(..., help="Approved request id to execute"),
) -> None:
    """Execute a tool whose approval has been granted.

    Runs the tool associated with an approved request and reports the tool call
    outcome. The request must already be in the 'approved' state.

    Example:
        xagent approvals execute abc123
    """
    config = get_current_config()
    try:
        client = create_client(config)
        record = asyncio.run(client.execute_approved(approval_id))

        if config.output_format == "json":
            print_json(record, config)
            return

        success = record.get("success", False)
        if success:
            print_success(
                f"Executed tool '{record.get('tool_name')}' "
                f"(latency: {record.get('latency_ms')}ms)",
                config,
            )
        else:
            print_error(
                f"Tool '{record.get('tool_name')}' failed: {record.get('error')}",
                config,
            )
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except NotImplementedError as e:
        print_error(f"{e}", config)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        print_error(f"Failed to execute approved request: {e}", config)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        print_error(f"CLI error: {e}", config)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Unexpected error: {e}", config)
        raise typer.Exit(code=1)
