"""SDK and non-interactive control-plane commands."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer

from backend.app.sdk import ControlPlaneSDK
from cli.client import APIError, AuthError, ConnectionError, XAgentCLIError, create_client
from cli.main import get_current_config

sdk_app = typer.Typer(
    name="sdk",
    help="SDK-style non-interactive control-plane wrappers",
    no_args_is_help=True,
)


def _sdk(tenant_id: str | None, user_id: str | None) -> ControlPlaneSDK:
    return ControlPlaneSDK(
        default_tenant_id=tenant_id or "default",
        default_user_id=user_id or "anonymous",
    )


def _emit(payload: dict[str, object]) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_or_invoke(payload: dict[str, object], *, execute: bool) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        result = asyncio.run(client.invoke_sdk_contract(payload))
    except NotImplementedError as e:
        typer.echo(f"SDK backend invocation failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK backend invocation failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


@sdk_app.command("thread-start")
def thread_start(
    task: str = typer.Argument(..., help="Task text for the new thread."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    scope: list[str] = typer.Option([], "--scope", help="Permission scope."),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    approved_approval_id: Optional[str] = typer.Option(None, "--approved-approval-id"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).start_thread(
        task,
        permission_scope=scope or None,
        idempotency_key=idempotency_key,
        approved_approval_id=approved_approval_id,
        dry_run=not execute,
    )
    _emit_or_invoke(contract.to_dict(), execute=execute)


@sdk_app.command("thread-resume")
def thread_resume(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    input_text: Optional[str] = typer.Option(None, "--input"),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    approved_approval_id: Optional[str] = typer.Option(None, "--approved-approval-id"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).resume_thread(
        thread_id,
        input_text=input_text,
        idempotency_key=idempotency_key,
        approved_approval_id=approved_approval_id,
        dry_run=not execute,
    )
    _emit_or_invoke(contract.to_dict(), execute=execute)


@sdk_app.command("turn-run")
def turn_run(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    input_text: str = typer.Argument(..., help="Turn input text."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    approved_approval_id: Optional[str] = typer.Option(None, "--approved-approval-id"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).run_turn(
        thread_id,
        input_text,
        idempotency_key=idempotency_key,
        approved_approval_id=approved_approval_id,
        dry_run=not execute,
    )
    _emit_or_invoke(contract.to_dict(), execute=execute)


@sdk_app.command("thread-read")
def thread_read(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    execute: bool = typer.Option(False, "--execute", help="Submit the read-only SDK envelope to the backend."),
) -> None:
    contract = _sdk(tenant_id, user_id).read_thread(thread_id)
    _emit_or_invoke(contract.to_dict(), execute=execute)


@sdk_app.command("evidence-read")
def evidence_read(
    report_name: str = typer.Argument(..., help="Runtime evidence JSON report filename."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    execute: bool = typer.Option(False, "--execute", help="Submit the read-only SDK envelope to the backend."),
) -> None:
    contract = _sdk(tenant_id, user_id).read_runtime_evidence(report_name)
    _emit_or_invoke(contract.to_dict(), execute=execute)
