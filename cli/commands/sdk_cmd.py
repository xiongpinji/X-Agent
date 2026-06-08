"""SDK and non-interactive control-plane commands."""

from __future__ import annotations

import json
from typing import Optional

import typer

from backend.app.sdk import ControlPlaneSDK

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


@sdk_app.command("thread-start")
def thread_start(
    task: str = typer.Argument(..., help="Task text for the new thread."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    scope: list[str] = typer.Option([], "--scope", help="Permission scope."),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).start_thread(
        task,
        permission_scope=scope or None,
        idempotency_key=idempotency_key,
        dry_run=not execute,
    )
    _emit(contract.to_dict())


@sdk_app.command("thread-resume")
def thread_resume(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    input_text: Optional[str] = typer.Option(None, "--input"),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).resume_thread(
        thread_id,
        input_text=input_text,
        idempotency_key=idempotency_key,
        dry_run=not execute,
    )
    _emit(contract.to_dict())


@sdk_app.command("turn-run")
def turn_run(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    input_text: str = typer.Argument(..., help="Turn input text."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key"),
    execute: bool = typer.Option(False, "--execute", help="Build an execute-intent envelope instead of dry-run."),
) -> None:
    contract = _sdk(tenant_id, user_id).run_turn(
        thread_id,
        input_text,
        idempotency_key=idempotency_key,
        dry_run=not execute,
    )
    _emit(contract.to_dict())


@sdk_app.command("thread-read")
def thread_read(
    thread_id: str = typer.Argument(..., help="Existing thread identifier."),
    tenant_id: Optional[str] = typer.Option(None, "--tenant-id"),
    user_id: Optional[str] = typer.Option(None, "--user-id"),
) -> None:
    contract = _sdk(tenant_id, user_id).read_thread(thread_id)
    _emit(contract.to_dict())
