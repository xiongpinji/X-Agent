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
