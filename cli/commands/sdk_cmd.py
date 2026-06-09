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


def _emit_or_record_acceptance(payload: dict[str, object], *, execute: bool) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK owner acceptance envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_owner_acceptance(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK owner acceptance recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK owner acceptance recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_receipt(payload: dict[str, object], *, execute: bool) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime enablement receipt envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_enablement_receipt(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime enablement receipt recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime enablement receipt recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_owner_pack_decision(payload: dict[str, object], *, execute: bool) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime enablement owner pack decision envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_enablement_owner_pack_decision(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime enablement owner pack decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime enablement owner pack decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_implementation_lock(payload: dict[str, object], *, execute: bool) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime implementation readiness lock envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_implementation_readiness_lock(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime implementation readiness lock recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime implementation readiness lock recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_implementation_final_decision(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime implementation final decision envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_implementation_final_decision(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime implementation final decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime implementation final decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_enablement(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag enablement envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_enablement(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag enablement recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag enablement recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_preflight(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application preflight envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_preflight(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_owner_approval(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application owner approval envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_owner_approval(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application owner approval recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application owner approval recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_execute_contract(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application execute contract envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_execute_contract(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application execute contract recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application execute contract recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_readiness_plan_decision(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application readiness plan decision envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_readiness_plan_decision(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application readiness plan decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application readiness plan decision recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_implementation_request(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application adapter implementation request envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_adapter_implementation_request(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter implementation request recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter implementation request recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_design_review(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError("SDK runtime flag application adapter design review envelope is missing request payload.")
        result = asyncio.run(client.record_sdk_runtime_flag_application_adapter_design_review(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter design review recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter design review recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_implementation_preflight(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter implementation preflight envelope is missing request payload."
            )
        result = asyncio.run(
            client.record_sdk_runtime_flag_application_adapter_implementation_preflight(request_payload)
        )
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter implementation preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter implementation preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_code_change(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter code-change envelope is missing request payload."
            )
        result = asyncio.run(client.record_sdk_runtime_flag_application_adapter_code_change(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter code-change recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter code-change recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_wiring(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter wiring envelope is missing request payload."
            )
        result = asyncio.run(client.record_sdk_runtime_flag_application_adapter_wiring(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter wiring recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter wiring recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_runtime_preflight(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter runtime preflight envelope is missing request payload."
            )
        result = asyncio.run(client.record_sdk_runtime_flag_application_adapter_runtime_preflight(request_payload))
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter runtime preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter runtime preflight recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_execution_dry_run(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter execution dry-run envelope is missing request payload."
            )
        result = asyncio.run(
            client.record_sdk_runtime_flag_application_adapter_execution_dry_run(request_payload)
        )
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter execution dry-run recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter execution dry-run recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_runtime_flag_application_adapter_execution_gate(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK runtime flag application adapter execution gate envelope is missing request payload."
            )
        result = asyncio.run(
            client.record_sdk_runtime_flag_application_adapter_execution_gate(request_payload)
        )
    except NotImplementedError as e:
        typer.echo(f"SDK runtime flag application adapter execution gate recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK runtime flag application adapter execution gate recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except XAgentCLIError as e:
        typer.echo(f"SDK CLI error: {e}", err=True)
        raise typer.Exit(code=1)
    _emit(result)


def _emit_or_record_live_write_runner_execution_acceptance(
    payload: dict[str, object],
    *,
    execute: bool,
) -> None:
    if not execute:
        _emit(payload)
        return

    config = get_current_config()
    try:
        client = create_client(config)
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise XAgentCLIError(
                "SDK live write-runner execution acceptance envelope is missing request payload."
            )
        result = asyncio.run(
            client.record_sdk_live_write_runner_execution_acceptance(request_payload)
        )
    except NotImplementedError as e:
        typer.echo(f"SDK live write-runner execution acceptance recording failed: {e}", err=True)
        raise typer.Exit(code=1)
    except (ConnectionError, AuthError, APIError) as e:
        typer.echo(f"SDK live write-runner execution acceptance recording failed: {e}", err=True)
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
    evidence_type: Optional[str] = typer.Option(None, "--evidence-type"),
    approval_id: Optional[str] = typer.Option(None, "--approval-id"),
    owner_acceptance_id: Optional[str] = typer.Option(None, "--acceptance-id"),
    audit_id: Optional[str] = typer.Option(None, "--audit-id"),
    readiness_receipt_id: Optional[str] = typer.Option(None, "--readiness-receipt-id"),
    implementation_lock_id: Optional[str] = typer.Option(None, "--implementation-lock-id"),
    owner_pack_decision_id: Optional[str] = typer.Option(None, "--decision-id"),
    method: Optional[str] = typer.Option(None, "--method"),
    execute: bool = typer.Option(False, "--execute", help="Submit the read-only SDK envelope to the backend."),
) -> None:
    contract = _sdk(tenant_id, user_id).read_runtime_evidence(
        report_name,
        evidence_type=evidence_type,
        approval_id=approval_id,
        owner_acceptance_id=owner_acceptance_id,
        readiness_receipt_id=readiness_receipt_id,
        implementation_lock_id=implementation_lock_id,
        owner_pack_decision_id=owner_pack_decision_id,
        audit_id=audit_id,
        method=method,
    )
    _emit_or_invoke(contract.to_dict(), execute=execute)


@sdk_app.command("acceptance-record")
def acceptance_record(
    approval_id: str = typer.Option(..., "--approval-id"),
    owner_acceptance_id: str = typer.Option(..., "--acceptance-id"),
    accepted_by: str = typer.Option(..., "--accepted-by"),
    accepted_at: str = typer.Option(..., "--accepted-at"),
    runbook_acknowledged: bool = typer.Option(False, "--runbook-acknowledged"),
    rollback_plan_acknowledged: bool = typer.Option(False, "--rollback-plan-acknowledged"),
    acceptance_signature: Optional[str] = typer.Option(None, "--acceptance-signature"),
    acceptance_hash: Optional[str] = typer.Option(None, "--acceptance-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record owner acceptance evidence in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_owner_acceptance(
        owner_acceptance_id=owner_acceptance_id,
        approval_id=approval_id,
        accepted_by=accepted_by,
        accepted_at=accepted_at,
        runbook_acknowledged=runbook_acknowledged,
        rollback_plan_acknowledged=rollback_plan_acknowledged,
        acceptance_signature=acceptance_signature,
        acceptance_hash=acceptance_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_acceptance(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-enable-receipt-record")
def runtime_enable_receipt_record(
    approval_id: str = typer.Option(..., "--approval-id"),
    readiness_receipt_id: str = typer.Option(..., "--readiness-receipt-id"),
    owner_acceptance_id: str = typer.Option(..., "--acceptance-id"),
    owner_acceptance_audit_id: str = typer.Option(..., "--acceptance-audit-id"),
    accepted_by: str = typer.Option(..., "--accepted-by"),
    accepted_at: str = typer.Option(..., "--accepted-at"),
    expires_at: str = typer.Option(..., "--expires-at"),
    smoke_runbook_version: str = typer.Option(..., "--smoke-runbook-version"),
    rollback_runbook_version: str = typer.Option(..., "--rollback-runbook-version"),
    smoke_runbook_acknowledged: bool = typer.Option(False, "--smoke-runbook-acknowledged"),
    rollback_runbook_acknowledged: bool = typer.Option(False, "--rollback-runbook-acknowledged"),
    failure_receipt_reviewed: bool = typer.Option(False, "--failure-receipt-reviewed"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    acceptance_signature: Optional[str] = typer.Option(None, "--acceptance-signature"),
    acceptance_hash: Optional[str] = typer.Option(None, "--acceptance-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime enablement readiness receipt in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_enablement_receipt(
        readiness_receipt_id=readiness_receipt_id,
        approval_id=approval_id,
        owner_acceptance_id=owner_acceptance_id,
        owner_acceptance_audit_id=owner_acceptance_audit_id,
        runtime_flag_name=runtime_flag_name,
        smoke_runbook_version=smoke_runbook_version,
        rollback_runbook_version=rollback_runbook_version,
        accepted_by=accepted_by,
        accepted_at=accepted_at,
        expires_at=expires_at,
        smoke_runbook_acknowledged=smoke_runbook_acknowledged,
        rollback_runbook_acknowledged=rollback_runbook_acknowledged,
        failure_receipt_reviewed=failure_receipt_reviewed,
        acceptance_signature=acceptance_signature,
        acceptance_hash=acceptance_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_receipt(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-enable-owner-pack-decision-record")
def runtime_enable_owner_pack_decision_record(
    owner_pack_decision_id: str = typer.Option(..., "--decision-id"),
    decision: str = typer.Option(..., "--decision"),
    approval_id: str = typer.Option(..., "--approval-id"),
    readiness_receipt_id: str = typer.Option(..., "--readiness-receipt-id"),
    readiness_receipt_audit_id: str = typer.Option(..., "--readiness-receipt-audit-id"),
    owner_acceptance_id: str = typer.Option(..., "--acceptance-id"),
    owner_acceptance_audit_id: str = typer.Option(..., "--acceptance-audit-id"),
    decided_by: str = typer.Option(..., "--decided-by"),
    decided_at: str = typer.Option(..., "--decided-at"),
    reason: str = typer.Option(..., "--reason"),
    decision_signature: Optional[str] = typer.Option(None, "--decision-signature"),
    decision_hash: Optional[str] = typer.Option(None, "--decision-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record owner pack accept/reject decision in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_enablement_owner_pack_decision(
        owner_pack_decision_id=owner_pack_decision_id,
        decision=decision,
        approval_id=approval_id,
        readiness_receipt_id=readiness_receipt_id,
        readiness_receipt_audit_id=readiness_receipt_audit_id,
        owner_acceptance_id=owner_acceptance_id,
        owner_acceptance_audit_id=owner_acceptance_audit_id,
        decided_by=decided_by,
        decided_at=decided_at,
        reason=reason,
        decision_signature=decision_signature,
        decision_hash=decision_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_owner_pack_decision(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-implementation-readiness-lock-record")
def runtime_implementation_readiness_lock_record(
    implementation_lock_id: str = typer.Option(..., "--implementation-lock-id"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    approval_id: str = typer.Option(..., "--approval-id"),
    readiness_receipt_id: str = typer.Option(..., "--readiness-receipt-id"),
    readiness_receipt_audit_id: str = typer.Option(..., "--readiness-receipt-audit-id"),
    owner_pack_decision_id: str = typer.Option(..., "--decision-id"),
    owner_pack_decision_audit_id: str = typer.Option(..., "--decision-audit-id"),
    operator_id: str = typer.Option(..., "--operator-id"),
    locked_at: str = typer.Option(..., "--locked-at"),
    lock_reason: str = typer.Option(..., "--lock-reason"),
    lock_signature: Optional[str] = typer.Option(None, "--lock-signature"),
    lock_hash: Optional[str] = typer.Option(None, "--lock-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime implementation readiness lock in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_implementation_readiness_lock(
        implementation_lock_id=implementation_lock_id,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        approval_id=approval_id,
        readiness_receipt_id=readiness_receipt_id,
        readiness_receipt_audit_id=readiness_receipt_audit_id,
        owner_pack_decision_id=owner_pack_decision_id,
        owner_pack_decision_audit_id=owner_pack_decision_audit_id,
        operator_id=operator_id,
        locked_at=locked_at,
        lock_reason=lock_reason,
        lock_signature=lock_signature,
        lock_hash=lock_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_implementation_lock(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-implementation-final-decision-record")
def runtime_implementation_final_decision_record(
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    decision: str = typer.Option(..., "--decision"),
    approval_id: str = typer.Option(..., "--approval-id"),
    implementation_lock_id: str = typer.Option(..., "--implementation-lock-id"),
    implementation_lock_audit_id: str = typer.Option(..., "--implementation-lock-audit-id"),
    readiness_receipt_id: str = typer.Option(..., "--readiness-receipt-id"),
    owner_pack_decision_id: str = typer.Option(..., "--decision-id"),
    decided_by: str = typer.Option(..., "--decided-by"),
    decided_at: str = typer.Option(..., "--decided-at"),
    reason: str = typer.Option(..., "--reason"),
    decision_signature: Optional[str] = typer.Option(None, "--decision-signature"),
    decision_hash: Optional[str] = typer.Option(None, "--decision-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime implementation final decision in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_implementation_final_decision(
        final_decision_id=final_decision_id,
        decision=decision,
        approval_id=approval_id,
        implementation_lock_id=implementation_lock_id,
        implementation_lock_audit_id=implementation_lock_audit_id,
        readiness_receipt_id=readiness_receipt_id,
        owner_pack_decision_id=owner_pack_decision_id,
        decided_by=decided_by,
        decided_at=decided_at,
        reason=reason,
        decision_signature=decision_signature,
        decision_hash=decision_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_implementation_final_decision(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-enable-record")
def runtime_flag_enable_record(
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    final_decision_audit_id: str = typer.Option(..., "--final-decision-audit-id"),
    implementation_lock_id: str = typer.Option(..., "--implementation-lock-id"),
    readiness_receipt_id: str = typer.Option(..., "--readiness-receipt-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    requested_by: str = typer.Option(..., "--requested-by"),
    requested_at: str = typer.Option(..., "--requested-at"),
    enablement_reason: str = typer.Option(..., "--enablement-reason"),
    enablement_signature: Optional[str] = typer.Option(None, "--enablement-signature"),
    enablement_hash: Optional[str] = typer.Option(None, "--enablement-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime flag enablement intent in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_enablement(
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        approval_id=approval_id,
        final_decision_id=final_decision_id,
        final_decision_audit_id=final_decision_audit_id,
        implementation_lock_id=implementation_lock_id,
        readiness_receipt_id=readiness_receipt_id,
        runtime_flag_name=runtime_flag_name,
        requested_by=requested_by,
        requested_at=requested_at,
        enablement_reason=enablement_reason,
        enablement_signature=enablement_signature,
        enablement_hash=enablement_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_flag_enablement(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-application-preflight-record")
def runtime_flag_application_preflight_record(
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    runtime_flag_enablement_audit_id: str = typer.Option(..., "--runtime-flag-enablement-audit-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    target_state: str = typer.Option("enabled", "--target-state"),
    requested_by: str = typer.Option(..., "--requested-by"),
    requested_at: str = typer.Option(..., "--requested-at"),
    preflight_reason: str = typer.Option(..., "--preflight-reason"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    preflight_signature: Optional[str] = typer.Option(None, "--preflight-signature"),
    preflight_hash: Optional[str] = typer.Option(None, "--preflight-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime flag application preflight in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_preflight(
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        approval_id=approval_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        runtime_flag_enablement_audit_id=runtime_flag_enablement_audit_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        target_state=target_state,
        requested_by=requested_by,
        requested_at=requested_at,
        preflight_reason=preflight_reason,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        preflight_signature=preflight_signature,
        preflight_hash=preflight_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_flag_application_preflight(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-application-approval-record")
def runtime_flag_application_approval_record(
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_preflight_audit_id: str = typer.Option(..., "--runtime-flag-preflight-audit-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    decision: str = typer.Option(..., "--decision"),
    decided_by: str = typer.Option(..., "--decided-by"),
    decided_at: str = typer.Option(..., "--decided-at"),
    approval_reason: str = typer.Option(..., "--approval-reason"),
    approval_signature: Optional[str] = typer.Option(None, "--approval-signature"),
    approval_hash: Optional[str] = typer.Option(None, "--approval-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime flag application owner approval in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_owner_approval(
        runtime_flag_approval_id=runtime_flag_approval_id,
        approval_id=approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_preflight_audit_id=runtime_flag_preflight_audit_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        decision=decision,
        decided_by=decided_by,
        decided_at=decided_at,
        approval_reason=approval_reason,
        approval_signature=approval_signature,
        approval_hash=approval_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_flag_application_owner_approval(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-application-execute-contract-record")
def runtime_flag_application_execute_contract_record(
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_approval_audit_id: str = typer.Option(..., "--runtime-flag-approval-audit-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    locked_at: str = typer.Option(..., "--locked-at"),
    execute_contract_reason: str = typer.Option(..., "--execute-contract-reason"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    execute_contract_signature: Optional[str] = typer.Option(None, "--execute-contract-signature"),
    execute_contract_hash: Optional[str] = typer.Option(None, "--execute-contract-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Record runtime flag application execute contract in the backend audit log."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_execute_contract(
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        approval_id=approval_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_approval_audit_id=runtime_flag_approval_audit_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        locked_at=locked_at,
        execute_contract_reason=execute_contract_reason,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        execute_contract_signature=execute_contract_signature,
        execute_contract_hash=execute_contract_hash,
        notes=notes,
        dry_run=not execute,
    )
    _emit_or_record_runtime_flag_application_execute_contract(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-application-readiness-plan-decision-record")
def runtime_flag_application_readiness_plan_decision_record(
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_execute_contract_audit_id: str = typer.Option(..., "--runtime-flag-execute-contract-audit-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    decision: str = typer.Option(..., "--decision"),
    decided_by: str = typer.Option(..., "--decided-by"),
    decided_at: str = typer.Option(..., "--decided-at"),
    reason: str = typer.Option(..., "--reason"),
    decision_signature: Optional[str] = typer.Option(None, "--decision-signature"),
    decision_hash: Optional[str] = typer.Option(None, "--decision-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated readiness plan decision stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_readiness_plan_decision(
        readiness_plan_decision_id=readiness_plan_decision_id,
        approval_id=approval_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_execute_contract_audit_id=runtime_flag_execute_contract_audit_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        decision=decision,
        decided_by=decided_by,
        decided_at=decided_at,
        reason=reason,
        decision_signature=decision_signature,
        decision_hash=decision_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_readiness_plan_decision(contract.to_dict(), execute=execute)


@sdk_app.command("runtime-flag-application-adapter-implementation-request-record")
def runtime_flag_application_adapter_implementation_request_record(
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    readiness_plan_decision_audit_id: str = typer.Option(..., "--readiness-plan-decision-audit-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    requested_by: str = typer.Option(..., "--requested-by"),
    requested_at: str = typer.Option(..., "--requested-at"),
    implementation_request_reason: str = typer.Option(..., "--implementation-request-reason"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    request_signature: Optional[str] = typer.Option(None, "--request-signature"),
    request_hash: Optional[str] = typer.Option(None, "--request-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter implementation request stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_implementation_request(
        adapter_implementation_request_id=adapter_implementation_request_id,
        approval_id=approval_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        readiness_plan_decision_audit_id=readiness_plan_decision_audit_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        requested_by=requested_by,
        requested_at=requested_at,
        implementation_request_reason=implementation_request_reason,
        adapter_design_ref=adapter_design_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        request_signature=request_signature,
        request_hash=request_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_implementation_request(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-design-review-record")
def runtime_flag_application_adapter_design_review_record(
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    adapter_implementation_request_audit_id: str = typer.Option(..., "--adapter-implementation-request-audit-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    review_decision: str = typer.Option(..., "--review-decision"),
    reviewed_by: str = typer.Option(..., "--reviewed-by"),
    reviewed_at: str = typer.Option(..., "--reviewed-at"),
    review_reason: str = typer.Option(..., "--review-reason"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    review_signature: Optional[str] = typer.Option(None, "--review-signature"),
    review_hash: Optional[str] = typer.Option(None, "--review-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter design review stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_design_review(
        adapter_design_review_id=adapter_design_review_id,
        approval_id=approval_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        adapter_implementation_request_audit_id=adapter_implementation_request_audit_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        review_decision=review_decision,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        review_reason=review_reason,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        review_signature=review_signature,
        review_hash=review_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_design_review(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-implementation-preflight-record")
def runtime_flag_application_adapter_implementation_preflight_record(
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_design_review_audit_id: str = typer.Option(..., "--adapter-design-review-audit-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    locked_at: str = typer.Option(..., "--locked-at"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    preflight_signature: Optional[str] = typer.Option(None, "--preflight-signature"),
    preflight_hash: Optional[str] = typer.Option(None, "--preflight-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter preflight stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_implementation_preflight(
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        approval_id=approval_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_design_review_audit_id=adapter_design_review_audit_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        locked_at=locked_at,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        preflight_signature=preflight_signature,
        preflight_hash=preflight_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_implementation_preflight(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-code-change-record")
def runtime_flag_application_adapter_code_change_record(
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_implementation_preflight_audit_id: str = typer.Option(..., "--adapter-implementation-preflight-audit-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    changed_at: str = typer.Option(..., "--changed-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    code_change_signature: Optional[str] = typer.Option(None, "--code-change-signature"),
    code_change_hash: Optional[str] = typer.Option(None, "--code-change-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter code-change stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_code_change(
        adapter_code_change_id=adapter_code_change_id,
        approval_id=approval_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_implementation_preflight_audit_id=adapter_implementation_preflight_audit_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        changed_at=changed_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        code_change_signature=code_change_signature,
        code_change_hash=code_change_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_code_change(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-wiring-record")
def runtime_flag_application_adapter_wiring_record(
    adapter_wiring_id: str = typer.Option(..., "--adapter-wiring-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    adapter_code_change_audit_id: str = typer.Option(..., "--adapter-code-change-audit-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    wired_at: str = typer.Option(..., "--wired-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    wiring_plan_ref: str = typer.Option(..., "--wiring-plan-ref"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    wiring_signature: Optional[str] = typer.Option(None, "--wiring-signature"),
    wiring_hash: Optional[str] = typer.Option(None, "--wiring-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter wiring stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_wiring(
        adapter_wiring_id=adapter_wiring_id,
        approval_id=approval_id,
        adapter_code_change_id=adapter_code_change_id,
        adapter_code_change_audit_id=adapter_code_change_audit_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        wired_at=wired_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        wiring_plan_ref=wiring_plan_ref,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        wiring_signature=wiring_signature,
        wiring_hash=wiring_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_wiring(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-runtime-preflight-record")
def runtime_flag_application_adapter_runtime_preflight_record(
    adapter_runtime_preflight_id: str = typer.Option(..., "--adapter-runtime-preflight-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_wiring_id: str = typer.Option(..., "--adapter-wiring-id"),
    adapter_wiring_audit_id: str = typer.Option(..., "--adapter-wiring-audit-id"),
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    preflighted_at: str = typer.Option(..., "--preflighted-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    runtime_preflight_plan_ref: str = typer.Option(..., "--runtime-preflight-plan-ref"),
    wiring_plan_ref: str = typer.Option(..., "--wiring-plan-ref"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    runtime_preflight_signature: Optional[str] = typer.Option(None, "--runtime-preflight-signature"),
    runtime_preflight_hash: Optional[str] = typer.Option(None, "--runtime-preflight-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter runtime preflight stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_runtime_preflight(
        adapter_runtime_preflight_id=adapter_runtime_preflight_id,
        approval_id=approval_id,
        adapter_wiring_id=adapter_wiring_id,
        adapter_wiring_audit_id=adapter_wiring_audit_id,
        adapter_code_change_id=adapter_code_change_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        preflighted_at=preflighted_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        runtime_preflight_plan_ref=runtime_preflight_plan_ref,
        wiring_plan_ref=wiring_plan_ref,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        runtime_preflight_signature=runtime_preflight_signature,
        runtime_preflight_hash=runtime_preflight_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_runtime_preflight(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-execution-dry-run-record")
def runtime_flag_application_adapter_execution_dry_run_record(
    adapter_execution_dry_run_id: str = typer.Option(..., "--adapter-execution-dry-run-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_runtime_preflight_id: str = typer.Option(..., "--adapter-runtime-preflight-id"),
    adapter_runtime_preflight_audit_id: str = typer.Option(..., "--adapter-runtime-preflight-audit-id"),
    adapter_wiring_id: str = typer.Option(..., "--adapter-wiring-id"),
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    dry_run_started_at: str = typer.Option(..., "--dry-run-started-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    execution_dry_run_plan_ref: str = typer.Option(..., "--execution-dry-run-plan-ref"),
    runtime_preflight_plan_ref: str = typer.Option(..., "--runtime-preflight-plan-ref"),
    wiring_plan_ref: str = typer.Option(..., "--wiring-plan-ref"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    execution_dry_run_signature: Optional[str] = typer.Option(None, "--execution-dry-run-signature"),
    execution_dry_run_hash: Optional[str] = typer.Option(None, "--execution-dry-run-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter execution dry-run stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_execution_dry_run(
        adapter_execution_dry_run_id=adapter_execution_dry_run_id,
        approval_id=approval_id,
        adapter_runtime_preflight_id=adapter_runtime_preflight_id,
        adapter_runtime_preflight_audit_id=adapter_runtime_preflight_audit_id,
        adapter_wiring_id=adapter_wiring_id,
        adapter_code_change_id=adapter_code_change_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        dry_run_started_at=dry_run_started_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        execution_dry_run_plan_ref=execution_dry_run_plan_ref,
        runtime_preflight_plan_ref=runtime_preflight_plan_ref,
        wiring_plan_ref=wiring_plan_ref,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        execution_dry_run_signature=execution_dry_run_signature,
        execution_dry_run_hash=execution_dry_run_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_execution_dry_run(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("runtime-flag-application-adapter-execution-gate-record")
def runtime_flag_application_adapter_execution_gate_record(
    adapter_execution_gate_id: str = typer.Option(..., "--adapter-execution-gate-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_execution_dry_run_id: str = typer.Option(..., "--adapter-execution-dry-run-id"),
    adapter_execution_dry_run_audit_id: str = typer.Option(..., "--adapter-execution-dry-run-audit-id"),
    adapter_runtime_preflight_id: str = typer.Option(..., "--adapter-runtime-preflight-id"),
    adapter_wiring_id: str = typer.Option(..., "--adapter-wiring-id"),
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    operator_id: str = typer.Option(..., "--operator-id"),
    gated_at: str = typer.Option(..., "--gated-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    execution_gate_plan_ref: str = typer.Option(..., "--execution-gate-plan-ref"),
    execution_dry_run_plan_ref: str = typer.Option(..., "--execution-dry-run-plan-ref"),
    runtime_preflight_plan_ref: str = typer.Option(..., "--runtime-preflight-plan-ref"),
    wiring_plan_ref: str = typer.Option(..., "--wiring-plan-ref"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    execution_gate_signature: Optional[str] = typer.Option(None, "--execution-gate-signature"),
    execution_gate_hash: Optional[str] = typer.Option(None, "--execution-gate-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated adapter execution gate stub."),
) -> None:
    contract = ControlPlaneSDK().record_runtime_flag_application_adapter_execution_gate(
        adapter_execution_gate_id=adapter_execution_gate_id,
        approval_id=approval_id,
        adapter_execution_dry_run_id=adapter_execution_dry_run_id,
        adapter_execution_dry_run_audit_id=adapter_execution_dry_run_audit_id,
        adapter_runtime_preflight_id=adapter_runtime_preflight_id,
        adapter_wiring_id=adapter_wiring_id,
        adapter_code_change_id=adapter_code_change_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        operator_id=operator_id,
        gated_at=gated_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        execution_gate_plan_ref=execution_gate_plan_ref,
        execution_dry_run_plan_ref=execution_dry_run_plan_ref,
        runtime_preflight_plan_ref=runtime_preflight_plan_ref,
        wiring_plan_ref=wiring_plan_ref,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        execution_gate_signature=execution_gate_signature,
        execution_gate_hash=execution_gate_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_runtime_flag_application_adapter_execution_gate(
        contract.to_dict(),
        execute=execute,
    )


@sdk_app.command("live-write-runner-execution-acceptance-record")
def live_write_runner_execution_acceptance_record(
    execution_acceptance_id: str = typer.Option(..., "--execution-acceptance-id"),
    approval_id: str = typer.Option(..., "--approval-id"),
    adapter_execution_gate_id: str = typer.Option(..., "--adapter-execution-gate-id"),
    adapter_execution_gate_audit_id: str = typer.Option(..., "--adapter-execution-gate-audit-id"),
    adapter_execution_dry_run_id: str = typer.Option(..., "--adapter-execution-dry-run-id"),
    adapter_runtime_preflight_id: str = typer.Option(..., "--adapter-runtime-preflight-id"),
    adapter_wiring_id: str = typer.Option(..., "--adapter-wiring-id"),
    adapter_code_change_id: str = typer.Option(..., "--adapter-code-change-id"),
    adapter_implementation_preflight_id: str = typer.Option(..., "--adapter-implementation-preflight-id"),
    adapter_design_review_id: str = typer.Option(..., "--adapter-design-review-id"),
    adapter_implementation_request_id: str = typer.Option(..., "--adapter-implementation-request-id"),
    readiness_plan_decision_id: str = typer.Option(..., "--readiness-plan-decision-id"),
    runtime_flag_execute_contract_id: str = typer.Option(..., "--runtime-flag-execute-contract-id"),
    runtime_flag_approval_id: str = typer.Option(..., "--runtime-flag-approval-id"),
    runtime_flag_preflight_id: str = typer.Option(..., "--runtime-flag-preflight-id"),
    runtime_flag_enablement_id: str = typer.Option(..., "--runtime-flag-enablement-id"),
    final_decision_id: str = typer.Option(..., "--final-decision-id"),
    runtime_flag_name: str = typer.Option("XAGENT_SDK_WRITE_RUNNER_ENABLED", "--runtime-flag-name"),
    accepted_by: str = typer.Option(..., "--accepted-by"),
    accepted_at: str = typer.Option(..., "--accepted-at"),
    adapter_module: str = typer.Option(
        "backend.app.sdk.runtime_flag_application_adapter",
        "--adapter-module",
    ),
    adapter_class: str = typer.Option("SDKRuntimeFlagApplicationAdapter", "--adapter-class"),
    execution_acceptance_plan_ref: str = typer.Option(..., "--execution-acceptance-plan-ref"),
    execution_gate_plan_ref: str = typer.Option(..., "--execution-gate-plan-ref"),
    execution_dry_run_plan_ref: str = typer.Option(..., "--execution-dry-run-plan-ref"),
    runtime_preflight_plan_ref: str = typer.Option(..., "--runtime-preflight-plan-ref"),
    wiring_plan_ref: str = typer.Option(..., "--wiring-plan-ref"),
    implementation_branch_ref: str = typer.Option(..., "--implementation-branch-ref"),
    implementation_plan_ref: str = typer.Option(..., "--implementation-plan-ref"),
    adapter_design_ref: str = typer.Option(..., "--adapter-design-ref"),
    security_review_ref: str = typer.Option(..., "--security-review-ref"),
    test_plan_ref: str = typer.Option(..., "--test-plan-ref"),
    rollback_plan_ref: str = typer.Option(..., "--rollback-plan-ref"),
    smoke_runbook_ref: str = typer.Option(..., "--smoke-runbook-ref"),
    runbook_acknowledged: bool = typer.Option(False, "--runbook-acknowledged"),
    rollback_plan_acknowledged: bool = typer.Option(False, "--rollback-plan-acknowledged"),
    smoke_runbook_acknowledged: bool = typer.Option(False, "--smoke-runbook-acknowledged"),
    idempotency_key: str = typer.Option(..., "--idempotency-key"),
    idempotency_hash: str = typer.Option(..., "--idempotency-hash"),
    acceptance_signature: Optional[str] = typer.Option(None, "--acceptance-signature"),
    acceptance_hash: Optional[str] = typer.Option(None, "--acceptance-hash"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    execute: bool = typer.Option(False, "--execute", help="Call the owner-gated live write-runner acceptance stub."),
) -> None:
    contract = ControlPlaneSDK().record_live_write_runner_execution_acceptance(
        execution_acceptance_id=execution_acceptance_id,
        approval_id=approval_id,
        adapter_execution_gate_id=adapter_execution_gate_id,
        adapter_execution_gate_audit_id=adapter_execution_gate_audit_id,
        adapter_execution_dry_run_id=adapter_execution_dry_run_id,
        adapter_runtime_preflight_id=adapter_runtime_preflight_id,
        adapter_wiring_id=adapter_wiring_id,
        adapter_code_change_id=adapter_code_change_id,
        adapter_implementation_preflight_id=adapter_implementation_preflight_id,
        adapter_design_review_id=adapter_design_review_id,
        adapter_implementation_request_id=adapter_implementation_request_id,
        readiness_plan_decision_id=readiness_plan_decision_id,
        runtime_flag_execute_contract_id=runtime_flag_execute_contract_id,
        runtime_flag_approval_id=runtime_flag_approval_id,
        runtime_flag_preflight_id=runtime_flag_preflight_id,
        runtime_flag_enablement_id=runtime_flag_enablement_id,
        final_decision_id=final_decision_id,
        runtime_flag_name=runtime_flag_name,
        accepted_by=accepted_by,
        accepted_at=accepted_at,
        adapter_module=adapter_module,
        adapter_class=adapter_class,
        execution_acceptance_plan_ref=execution_acceptance_plan_ref,
        execution_gate_plan_ref=execution_gate_plan_ref,
        execution_dry_run_plan_ref=execution_dry_run_plan_ref,
        runtime_preflight_plan_ref=runtime_preflight_plan_ref,
        wiring_plan_ref=wiring_plan_ref,
        implementation_branch_ref=implementation_branch_ref,
        implementation_plan_ref=implementation_plan_ref,
        adapter_design_ref=adapter_design_ref,
        security_review_ref=security_review_ref,
        test_plan_ref=test_plan_ref,
        rollback_plan_ref=rollback_plan_ref,
        smoke_runbook_ref=smoke_runbook_ref,
        runbook_acknowledged=runbook_acknowledged,
        rollback_plan_acknowledged=rollback_plan_acknowledged,
        smoke_runbook_acknowledged=smoke_runbook_acknowledged,
        idempotency_key=idempotency_key,
        idempotency_hash=idempotency_hash,
        acceptance_signature=acceptance_signature,
        acceptance_hash=acceptance_hash,
        notes=notes,
        dry_run=True,
    )
    _emit_or_record_live_write_runner_execution_acceptance(
        contract.to_dict(),
        execute=execute,
    )
