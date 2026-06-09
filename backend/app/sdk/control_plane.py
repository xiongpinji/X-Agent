"""SDK-style wrappers over the X-Agent control-plane contract.

The wrappers build stable request envelopes for clients and non-interactive
CLI usage. They do not execute HTTP calls or mutate backend state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SDKControlPlaneRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKThreadRunContract:
    operation: str
    request: SDKControlPlaneRequest
    expected_response_shape: dict[str, Any]
    owner_gate: dict[str, Any]
    channel_strategy: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["request"] = self.request.to_dict()
        approved_approval_id = self.owner_gate.get("approved_approval_id")
        if approved_approval_id:
            payload["approved_approval_id"] = approved_approval_id
            payload["owner_approved"] = True
        return payload


@dataclass(frozen=True)
class SDKOwnerAcceptanceRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeEnablementReceiptRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeEnablementOwnerPackDecisionRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeImplementationReadinessLockRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeImplementationFinalDecisionRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagEnablementRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationPreflightRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationOwnerApprovalRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationExecuteContractRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationReadinessPlanDecisionRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterImplementationRequestRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterDesignReviewRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterImplementationPreflightRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterCodeChangeRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        payload["file_mutation_performed"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterWiringRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        payload["file_mutation_performed"] = False
        payload["wired_into_sdk_invoke"] = False
        payload["adapter_runtime_wired"] = False
        return payload


@dataclass(frozen=True)
class SDKRuntimeFlagApplicationAdapterRuntimePreflightRecordContract:
    operation: str
    endpoint: str
    request: dict[str, Any]
    owner_gate: dict[str, Any]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_performed"] = False
        payload["network_mutation_performed"] = False
        payload["file_mutation_performed"] = False
        payload["wired_into_sdk_invoke"] = False
        payload["adapter_runtime_wired"] = False
        return payload


class ControlPlaneSDK:
    """Build SDK-compatible control-plane request envelopes."""

    _READ_ONLY_METHODS = {"thread/read", "thread/search", "runtime/evidence/read"}

    def __init__(
        self,
        *,
        default_tenant_id: str = "default",
        default_user_id: str = "anonymous",
    ) -> None:
        self.default_tenant_id = default_tenant_id
        self.default_user_id = default_user_id

    def start_thread(
        self,
        task: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        permission_scope: list[str] | None = None,
        extra_context: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        approved_approval_id: str | None = None,
        dry_run: bool = True,
    ) -> SDKThreadRunContract:
        return self._thread_contract(
            operation="thread_start",
            method="thread/start",
            params={
                "task": task,
                "permission_scope": permission_scope or ["tools:read", "memory:read"],
                "extra_context": extra_context or {},
            },
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            approved_approval_id=approved_approval_id,
            dry_run=dry_run,
        )

    def resume_thread(
        self,
        thread_id: str,
        *,
        input_text: str | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        idempotency_key: str | None = None,
        approved_approval_id: str | None = None,
        dry_run: bool = True,
    ) -> SDKThreadRunContract:
        params: dict[str, Any] = {"thread_id": thread_id}
        if input_text:
            params["input"] = input_text
        return self._thread_contract(
            operation="thread_resume",
            method="thread/resume",
            params=params,
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            approved_approval_id=approved_approval_id,
            dry_run=dry_run,
        )

    def run_turn(
        self,
        thread_id: str,
        input_text: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        idempotency_key: str | None = None,
        approved_approval_id: str | None = None,
        dry_run: bool = True,
    ) -> SDKThreadRunContract:
        return self._thread_contract(
            operation="turn_start",
            method="turn/start",
            params={"thread_id": thread_id, "input": input_text},
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            approved_approval_id=approved_approval_id,
            dry_run=dry_run,
        )

    def read_thread(
        self,
        thread_id: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> SDKThreadRunContract:
        return self._thread_contract(
            operation="thread_read",
            method="thread/read",
            params={"thread_id": thread_id},
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=None,
            approved_approval_id=None,
            dry_run=True,
        )

    def read_runtime_evidence(
        self,
        report_name: str,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        evidence_type: str | None = None,
        approval_id: str | None = None,
        owner_acceptance_id: str | None = None,
        readiness_receipt_id: str | None = None,
        implementation_lock_id: str | None = None,
        owner_pack_decision_id: str | None = None,
        audit_id: str | None = None,
        method: str | None = None,
    ) -> SDKThreadRunContract:
        params: dict[str, Any] = {"report_name": report_name}
        if evidence_type:
            params["evidence_type"] = evidence_type
        if approval_id:
            params["approval_id"] = approval_id
        if owner_acceptance_id:
            params["owner_acceptance_id"] = owner_acceptance_id
        if readiness_receipt_id:
            params["readiness_receipt_id"] = readiness_receipt_id
        if implementation_lock_id:
            params["implementation_lock_id"] = implementation_lock_id
        if owner_pack_decision_id:
            params["owner_pack_decision_id"] = owner_pack_decision_id
        if audit_id:
            params["audit_id"] = audit_id
        if method:
            params["method"] = method
        return self._thread_contract(
            operation="runtime_evidence_read",
            method="runtime/evidence/read",
            params=params,
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=None,
            approved_approval_id=None,
            dry_run=True,
        )

    def record_runtime_enablement_receipt(
        self,
        *,
        readiness_receipt_id: str,
        approval_id: str,
        owner_acceptance_id: str,
        owner_acceptance_audit_id: str,
        smoke_runbook_version: str,
        rollback_runbook_version: str,
        accepted_by: str,
        accepted_at: str,
        expires_at: str,
        smoke_runbook_acknowledged: bool,
        rollback_runbook_acknowledged: bool,
        failure_receipt_reviewed: bool,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        acceptance_signature: str | None = None,
        acceptance_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeEnablementReceiptRecordContract:
        return SDKRuntimeEnablementReceiptRecordContract(
            operation="runtime_enablement_receipt_record",
            endpoint="/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            request={
                "readiness_receipt_id": readiness_receipt_id,
                "approval_id": approval_id,
                "owner_acceptance_id": owner_acceptance_id,
                "owner_acceptance_audit_id": owner_acceptance_audit_id,
                "runtime_flag_name": runtime_flag_name,
                "smoke_runbook_version": smoke_runbook_version,
                "rollback_runbook_version": rollback_runbook_version,
                "accepted_by": accepted_by,
                "accepted_at": accepted_at,
                "expires_at": expires_at,
                "smoke_runbook_acknowledged": smoke_runbook_acknowledged,
                "rollback_runbook_acknowledged": rollback_runbook_acknowledged,
                "failure_receipt_reviewed": failure_receipt_reviewed,
                "acceptance_signature": acceptance_signature,
                "acceptance_hash": acceptance_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_owner_acceptance_audit_record": True,
                "requires_signature_or_hash": True,
                "requires_expiry": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records runtime enablement readiness evidence only.",
                "It does not enable runtime flags or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_enablement_owner_pack_decision(
        self,
        *,
        owner_pack_decision_id: str,
        decision: str,
        approval_id: str,
        readiness_receipt_id: str,
        readiness_receipt_audit_id: str,
        owner_acceptance_id: str,
        owner_acceptance_audit_id: str,
        decided_by: str,
        decided_at: str,
        reason: str,
        decision_signature: str | None = None,
        decision_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeEnablementOwnerPackDecisionRecordContract:
        return SDKRuntimeEnablementOwnerPackDecisionRecordContract(
            operation="runtime_enablement_owner_pack_decision_record",
            endpoint="/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
            request={
                "owner_pack_decision_id": owner_pack_decision_id,
                "decision": decision,
                "approval_id": approval_id,
                "readiness_receipt_id": readiness_receipt_id,
                "readiness_receipt_audit_id": readiness_receipt_audit_id,
                "owner_acceptance_id": owner_acceptance_id,
                "owner_acceptance_audit_id": owner_acceptance_audit_id,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "reason": reason,
                "decision_signature": decision_signature,
                "decision_hash": decision_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_enablement_readiness_receipt": True,
                "requires_decision_accept_or_reject": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records an owner pack accept/reject decision only.",
                "It does not enable runtime flags or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_implementation_readiness_lock(
        self,
        *,
        implementation_lock_id: str,
        idempotency_key: str,
        idempotency_hash: str,
        approval_id: str,
        readiness_receipt_id: str,
        readiness_receipt_audit_id: str,
        owner_pack_decision_id: str,
        owner_pack_decision_audit_id: str,
        operator_id: str,
        locked_at: str,
        lock_reason: str,
        lock_signature: str | None = None,
        lock_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeImplementationReadinessLockRecordContract:
        return SDKRuntimeImplementationReadinessLockRecordContract(
            operation="runtime_implementation_readiness_lock_record",
            endpoint="/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            request={
                "implementation_lock_id": implementation_lock_id,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "approval_id": approval_id,
                "readiness_receipt_id": readiness_receipt_id,
                "readiness_receipt_audit_id": readiness_receipt_audit_id,
                "owner_pack_decision_id": owner_pack_decision_id,
                "owner_pack_decision_audit_id": owner_pack_decision_audit_id,
                "operator_id": operator_id,
                "locked_at": locked_at,
                "lock_reason": lock_reason,
                "lock_signature": lock_signature,
                "lock_hash": lock_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_enablement_readiness_receipt": True,
                "requires_accepted_owner_pack_decision": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records a readiness lock and idempotency receipt only.",
                "It does not enable runtime flags or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_implementation_final_decision(
        self,
        *,
        final_decision_id: str,
        decision: str,
        approval_id: str,
        implementation_lock_id: str,
        implementation_lock_audit_id: str,
        readiness_receipt_id: str,
        owner_pack_decision_id: str,
        decided_by: str,
        decided_at: str,
        reason: str,
        decision_signature: str | None = None,
        decision_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeImplementationFinalDecisionRecordContract:
        return SDKRuntimeImplementationFinalDecisionRecordContract(
            operation="runtime_implementation_final_decision_record",
            endpoint="/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            request={
                "final_decision_id": final_decision_id,
                "decision": decision,
                "approval_id": approval_id,
                "implementation_lock_id": implementation_lock_id,
                "implementation_lock_audit_id": implementation_lock_audit_id,
                "readiness_receipt_id": readiness_receipt_id,
                "owner_pack_decision_id": owner_pack_decision_id,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "reason": reason,
                "decision_signature": decision_signature,
                "decision_hash": decision_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_implementation_readiness_lock": True,
                "requires_decision_accept_or_reject": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records a final implementation decision only.",
                "Accepted decisions do not enable runtime flags or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_flag_enablement(
        self,
        *,
        runtime_flag_enablement_id: str,
        approval_id: str,
        final_decision_id: str,
        final_decision_audit_id: str,
        implementation_lock_id: str,
        readiness_receipt_id: str,
        requested_by: str,
        requested_at: str,
        enablement_reason: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        enablement_signature: str | None = None,
        enablement_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagEnablementRecordContract:
        return SDKRuntimeFlagEnablementRecordContract(
            operation="runtime_flag_enablement_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            request={
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "approval_id": approval_id,
                "final_decision_id": final_decision_id,
                "final_decision_audit_id": final_decision_audit_id,
                "implementation_lock_id": implementation_lock_id,
                "readiness_receipt_id": readiness_receipt_id,
                "runtime_flag_name": runtime_flag_name,
                "requested_by": requested_by,
                "requested_at": requested_at,
                "enablement_reason": enablement_reason,
                "enablement_signature": enablement_signature,
                "enablement_hash": enablement_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_implementation_final_decision": True,
                "requires_final_decision_accepted": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records explicit owner runtime flag enablement intent only.",
                "It does not set XAGENT_SDK_WRITE_RUNNER_ENABLED or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_flag_application_preflight(
        self,
        *,
        runtime_flag_preflight_id: str,
        approval_id: str,
        runtime_flag_enablement_id: str,
        runtime_flag_enablement_audit_id: str,
        final_decision_id: str,
        requested_by: str,
        requested_at: str,
        preflight_reason: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        target_state: str = "enabled",
        preflight_signature: str | None = None,
        preflight_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationPreflightRecordContract:
        return SDKRuntimeFlagApplicationPreflightRecordContract(
            operation="runtime_flag_application_preflight_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            request={
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "approval_id": approval_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "runtime_flag_enablement_audit_id": runtime_flag_enablement_audit_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "target_state": target_state,
                "requested_by": requested_by,
                "requested_at": requested_at,
                "preflight_reason": preflight_reason,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "preflight_signature": preflight_signature,
                "preflight_hash": preflight_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_flag_enablement_intent": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_target_state": "enabled",
                "requires_rollback_plan": True,
                "requires_smoke_runbook": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records runtime flag application preflight evidence only.",
                "It does not set XAGENT_SDK_WRITE_RUNNER_ENABLED or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_flag_application_owner_approval(
        self,
        *,
        runtime_flag_approval_id: str,
        approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_preflight_audit_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        decision: str,
        decided_by: str,
        decided_at: str,
        approval_reason: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        approval_signature: str | None = None,
        approval_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationOwnerApprovalRecordContract:
        return SDKRuntimeFlagApplicationOwnerApprovalRecordContract(
            operation="runtime_flag_application_owner_approval_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            request={
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "approval_id": approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_preflight_audit_id": runtime_flag_preflight_audit_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "decision": decision,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "approval_reason": approval_reason,
                "approval_signature": approval_signature,
                "approval_hash": approval_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_flag_application_preflight": True,
                "requires_decision_accept_or_reject": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records owner approval intent for runtime flag application only.",
                "It does not set XAGENT_SDK_WRITE_RUNNER_ENABLED or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_flag_application_execute_contract(
        self,
        *,
        runtime_flag_execute_contract_id: str,
        approval_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_approval_audit_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        operator_id: str,
        locked_at: str,
        execute_contract_reason: str,
        idempotency_key: str,
        idempotency_hash: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        execute_contract_signature: str | None = None,
        execute_contract_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationExecuteContractRecordContract:
        return SDKRuntimeFlagApplicationExecuteContractRecordContract(
            operation="runtime_flag_application_execute_contract_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
            request={
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "approval_id": approval_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_approval_audit_id": runtime_flag_approval_audit_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "operator_id": operator_id,
                "locked_at": locked_at,
                "execute_contract_reason": execute_contract_reason,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "execute_contract_signature": execute_contract_signature,
                "execute_contract_hash": execute_contract_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_flag_application_owner_approval": True,
                "requires_owner_approval_decision": "accepted",
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_rollback_plan": True,
                "requires_smoke_runbook": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records the live runtime flag application execute contract only.",
                "It does not apply XAGENT_SDK_WRITE_RUNNER_ENABLED or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def record_runtime_flag_application_readiness_plan_decision(
        self,
        *,
        readiness_plan_decision_id: str,
        approval_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_execute_contract_audit_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        decision: str,
        decided_by: str,
        decided_at: str,
        reason: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        decision_signature: str | None = None,
        decision_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationReadinessPlanDecisionRecordContract:
        return SDKRuntimeFlagApplicationReadinessPlanDecisionRecordContract(
            operation="runtime_flag_application_readiness_plan_decision_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-readiness-plan/decision/record",
            request={
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "approval_id": approval_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_execute_contract_audit_id": runtime_flag_execute_contract_audit_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "decision": decision,
                "decided_by": decided_by,
                "decided_at": decided_at,
                "reason": reason,
                "decision_signature": decision_signature,
                "decision_hash": decision_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_runtime_flag_application_execute_contract": True,
                "requires_readiness_plan_review": True,
                "requires_decision_accept_or_reject": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records an owner decision for the readiness plan only.",
                "Accepted decisions do not apply XAGENT_SDK_WRITE_RUNNER_ENABLED or enable the adapter.",
                "It does not mark an approval executed or invoke the write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_implementation_request(
        self,
        *,
        adapter_implementation_request_id: str,
        approval_id: str,
        readiness_plan_decision_id: str,
        readiness_plan_decision_audit_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        requested_by: str,
        requested_at: str,
        implementation_request_reason: str,
        adapter_design_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        request_signature: str | None = None,
        request_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterImplementationRequestRecordContract:
        return SDKRuntimeFlagApplicationAdapterImplementationRequestRecordContract(
            operation="runtime_flag_application_adapter_implementation_request_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-request/record",
            request={
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "approval_id": approval_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "readiness_plan_decision_audit_id": readiness_plan_decision_audit_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "requested_by": requested_by,
                "requested_at": requested_at,
                "implementation_request_reason": implementation_request_reason,
                "adapter_design_ref": adapter_design_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "request_signature": request_signature,
                "request_hash": request_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_readiness_plan_decision": True,
                "requires_readiness_plan_decision_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_adapter_design_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
            },
            known_limits=[
                "This SDK contract records an explicit owner request to implement the adapter only.",
                "It does not apply XAGENT_SDK_WRITE_RUNNER_ENABLED or enable adapter execution.",
                "It does not import, instantiate, or invoke the SDK write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_design_review(
        self,
        *,
        adapter_design_review_id: str,
        approval_id: str,
        adapter_implementation_request_id: str,
        adapter_implementation_request_audit_id: str,
        readiness_plan_decision_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        review_decision: str,
        reviewed_by: str,
        reviewed_at: str,
        review_reason: str,
        adapter_design_ref: str,
        security_review_ref: str,
        test_plan_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        review_signature: str | None = None,
        review_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterDesignReviewRecordContract:
        return SDKRuntimeFlagApplicationAdapterDesignReviewRecordContract(
            operation="runtime_flag_application_adapter_design_review_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/design-review/record",
            request={
                "adapter_design_review_id": adapter_design_review_id,
                "approval_id": approval_id,
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "adapter_implementation_request_audit_id": adapter_implementation_request_audit_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "review_decision": review_decision,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "review_reason": review_reason,
                "adapter_design_ref": adapter_design_ref,
                "security_review_ref": security_review_ref,
                "test_plan_ref": test_plan_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "review_signature": review_signature,
                "review_hash": review_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_adapter_implementation_request": True,
                "requires_adapter_implementation_request_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_review_decision_accept_or_reject": True,
                "requires_adapter_design_ref": True,
                "requires_security_review_ref": True,
                "requires_test_plan_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
            },
            known_limits=[
                "This SDK contract records owner design review for the future adapter only.",
                "It does not apply XAGENT_SDK_WRITE_RUNNER_ENABLED or enable adapter execution.",
                "It does not import, instantiate, or invoke the SDK write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_implementation_preflight(
        self,
        *,
        adapter_implementation_preflight_id: str,
        approval_id: str,
        adapter_design_review_id: str,
        adapter_design_review_audit_id: str,
        adapter_implementation_request_id: str,
        readiness_plan_decision_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        operator_id: str,
        locked_at: str,
        implementation_branch_ref: str,
        implementation_plan_ref: str,
        adapter_design_ref: str,
        security_review_ref: str,
        test_plan_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        idempotency_key: str,
        idempotency_hash: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        preflight_signature: str | None = None,
        preflight_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterImplementationPreflightRecordContract:
        return SDKRuntimeFlagApplicationAdapterImplementationPreflightRecordContract(
            operation="runtime_flag_application_adapter_implementation_preflight_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-preflight/record",
            request={
                "adapter_implementation_preflight_id": adapter_implementation_preflight_id,
                "approval_id": approval_id,
                "adapter_design_review_id": adapter_design_review_id,
                "adapter_design_review_audit_id": adapter_design_review_audit_id,
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "operator_id": operator_id,
                "locked_at": locked_at,
                "implementation_branch_ref": implementation_branch_ref,
                "implementation_plan_ref": implementation_plan_ref,
                "adapter_design_ref": adapter_design_ref,
                "security_review_ref": security_review_ref,
                "test_plan_ref": test_plan_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "preflight_signature": preflight_signature,
                "preflight_hash": preflight_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_adapter_design_review": True,
                "requires_adapter_design_review_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_implementation_branch_ref": True,
                "requires_implementation_plan_ref": True,
                "requires_adapter_design_ref": True,
                "requires_security_review_ref": True,
                "requires_test_plan_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
            },
            known_limits=[
                "This SDK contract records implementation preflight for the future adapter only.",
                "It does not apply XAGENT_SDK_WRITE_RUNNER_ENABLED or enable adapter execution.",
                "It does not implement, import, instantiate, or invoke the SDK write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_code_change(
        self,
        *,
        adapter_code_change_id: str,
        approval_id: str,
        adapter_implementation_preflight_id: str,
        adapter_implementation_preflight_audit_id: str,
        adapter_design_review_id: str,
        adapter_implementation_request_id: str,
        readiness_plan_decision_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        operator_id: str,
        changed_at: str,
        implementation_branch_ref: str,
        implementation_plan_ref: str,
        adapter_design_ref: str,
        security_review_ref: str,
        test_plan_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        idempotency_key: str,
        idempotency_hash: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        adapter_module: str = "backend.app.sdk.runtime_flag_application_adapter",
        adapter_class: str = "SDKRuntimeFlagApplicationAdapter",
        code_change_signature: str | None = None,
        code_change_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterCodeChangeRecordContract:
        return SDKRuntimeFlagApplicationAdapterCodeChangeRecordContract(
            operation="runtime_flag_application_adapter_code_change_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/code-change/record",
            request={
                "adapter_code_change_id": adapter_code_change_id,
                "approval_id": approval_id,
                "adapter_implementation_preflight_id": adapter_implementation_preflight_id,
                "adapter_implementation_preflight_audit_id": adapter_implementation_preflight_audit_id,
                "adapter_design_review_id": adapter_design_review_id,
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "operator_id": operator_id,
                "changed_at": changed_at,
                "adapter_module": adapter_module,
                "adapter_class": adapter_class,
                "implementation_branch_ref": implementation_branch_ref,
                "implementation_plan_ref": implementation_plan_ref,
                "adapter_design_ref": adapter_design_ref,
                "security_review_ref": security_review_ref,
                "test_plan_ref": test_plan_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "code_change_signature": code_change_signature,
                "code_change_hash": code_change_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_adapter_implementation_preflight": True,
                "requires_adapter_implementation_preflight_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_adapter_module": "backend.app.sdk.runtime_flag_application_adapter",
                "requires_adapter_class": "SDKRuntimeFlagApplicationAdapter",
                "requires_implementation_branch_ref": True,
                "requires_implementation_plan_ref": True,
                "requires_adapter_design_ref": True,
                "requires_security_review_ref": True,
                "requires_test_plan_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
            },
            known_limits=[
                "This SDK contract records the disabled adapter code-change gate only.",
                "It does not wire the adapter into /sdk/invoke or apply XAGENT_SDK_WRITE_RUNNER_ENABLED.",
                "It does not instantiate the adapter or invoke the SDK write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_wiring(
        self,
        *,
        adapter_wiring_id: str,
        approval_id: str,
        adapter_code_change_id: str,
        adapter_code_change_audit_id: str,
        adapter_implementation_preflight_id: str,
        adapter_design_review_id: str,
        adapter_implementation_request_id: str,
        readiness_plan_decision_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        operator_id: str,
        wired_at: str,
        wiring_plan_ref: str,
        implementation_branch_ref: str,
        implementation_plan_ref: str,
        adapter_design_ref: str,
        security_review_ref: str,
        test_plan_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        idempotency_key: str,
        idempotency_hash: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        adapter_module: str = "backend.app.sdk.runtime_flag_application_adapter",
        adapter_class: str = "SDKRuntimeFlagApplicationAdapter",
        wiring_signature: str | None = None,
        wiring_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterWiringRecordContract:
        return SDKRuntimeFlagApplicationAdapterWiringRecordContract(
            operation="runtime_flag_application_adapter_wiring_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/wiring/record",
            request={
                "adapter_wiring_id": adapter_wiring_id,
                "approval_id": approval_id,
                "adapter_code_change_id": adapter_code_change_id,
                "adapter_code_change_audit_id": adapter_code_change_audit_id,
                "adapter_implementation_preflight_id": adapter_implementation_preflight_id,
                "adapter_design_review_id": adapter_design_review_id,
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "operator_id": operator_id,
                "wired_at": wired_at,
                "adapter_module": adapter_module,
                "adapter_class": adapter_class,
                "wiring_plan_ref": wiring_plan_ref,
                "implementation_branch_ref": implementation_branch_ref,
                "implementation_plan_ref": implementation_plan_ref,
                "adapter_design_ref": adapter_design_ref,
                "security_review_ref": security_review_ref,
                "test_plan_ref": test_plan_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "wiring_signature": wiring_signature,
                "wiring_hash": wiring_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_adapter_code_change": True,
                "requires_adapter_code_change_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_adapter_module": "backend.app.sdk.runtime_flag_application_adapter",
                "requires_adapter_class": "SDKRuntimeFlagApplicationAdapter",
                "requires_wiring_plan_ref": True,
                "requires_implementation_branch_ref": True,
                "requires_implementation_plan_ref": True,
                "requires_adapter_design_ref": True,
                "requires_security_review_ref": True,
                "requires_test_plan_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
                "wired_into_sdk_invoke": False,
                "adapter_runtime_wired": False,
                "imports_adapter_in_sdk_invoke": False,
                "instantiates_adapter_in_sdk_invoke": False,
            },
            known_limits=[
                "This SDK contract records owner-approved adapter wiring intent only.",
                "It does not wire the adapter into /sdk/invoke or apply XAGENT_SDK_WRITE_RUNNER_ENABLED.",
                "It does not import, instantiate, execute the adapter, or invoke the SDK write runner.",
            ],
        )

    def record_runtime_flag_application_adapter_runtime_preflight(
        self,
        *,
        adapter_runtime_preflight_id: str,
        approval_id: str,
        adapter_wiring_id: str,
        adapter_wiring_audit_id: str,
        adapter_code_change_id: str,
        adapter_implementation_preflight_id: str,
        adapter_design_review_id: str,
        adapter_implementation_request_id: str,
        readiness_plan_decision_id: str,
        runtime_flag_execute_contract_id: str,
        runtime_flag_approval_id: str,
        runtime_flag_preflight_id: str,
        runtime_flag_enablement_id: str,
        final_decision_id: str,
        operator_id: str,
        preflighted_at: str,
        runtime_preflight_plan_ref: str,
        wiring_plan_ref: str,
        implementation_branch_ref: str,
        implementation_plan_ref: str,
        adapter_design_ref: str,
        security_review_ref: str,
        test_plan_ref: str,
        rollback_plan_ref: str,
        smoke_runbook_ref: str,
        idempotency_key: str,
        idempotency_hash: str,
        runtime_flag_name: str = "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        adapter_module: str = "backend.app.sdk.runtime_flag_application_adapter",
        adapter_class: str = "SDKRuntimeFlagApplicationAdapter",
        runtime_preflight_signature: str | None = None,
        runtime_preflight_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKRuntimeFlagApplicationAdapterRuntimePreflightRecordContract:
        return SDKRuntimeFlagApplicationAdapterRuntimePreflightRecordContract(
            operation="runtime_flag_application_adapter_runtime_preflight_record",
            endpoint="/api/v1/control-plane/sdk/runtime-flag/application-adapter/runtime-preflight/record",
            request={
                "adapter_runtime_preflight_id": adapter_runtime_preflight_id,
                "approval_id": approval_id,
                "adapter_wiring_id": adapter_wiring_id,
                "adapter_wiring_audit_id": adapter_wiring_audit_id,
                "adapter_code_change_id": adapter_code_change_id,
                "adapter_implementation_preflight_id": adapter_implementation_preflight_id,
                "adapter_design_review_id": adapter_design_review_id,
                "adapter_implementation_request_id": adapter_implementation_request_id,
                "readiness_plan_decision_id": readiness_plan_decision_id,
                "runtime_flag_execute_contract_id": runtime_flag_execute_contract_id,
                "runtime_flag_approval_id": runtime_flag_approval_id,
                "runtime_flag_preflight_id": runtime_flag_preflight_id,
                "runtime_flag_enablement_id": runtime_flag_enablement_id,
                "final_decision_id": final_decision_id,
                "runtime_flag_name": runtime_flag_name,
                "operator_id": operator_id,
                "preflighted_at": preflighted_at,
                "adapter_module": adapter_module,
                "adapter_class": adapter_class,
                "runtime_preflight_plan_ref": runtime_preflight_plan_ref,
                "wiring_plan_ref": wiring_plan_ref,
                "implementation_branch_ref": implementation_branch_ref,
                "implementation_plan_ref": implementation_plan_ref,
                "adapter_design_ref": adapter_design_ref,
                "security_review_ref": security_review_ref,
                "test_plan_ref": test_plan_ref,
                "rollback_plan_ref": rollback_plan_ref,
                "smoke_runbook_ref": smoke_runbook_ref,
                "idempotency_key": idempotency_key,
                "idempotency_hash": idempotency_hash,
                "runtime_preflight_signature": runtime_preflight_signature,
                "runtime_preflight_hash": runtime_preflight_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_accepted_adapter_wiring": True,
                "requires_adapter_wiring_audit": True,
                "requires_runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requires_adapter_module": "backend.app.sdk.runtime_flag_application_adapter",
                "requires_adapter_class": "SDKRuntimeFlagApplicationAdapter",
                "requires_runtime_preflight_plan_ref": True,
                "requires_wiring_plan_ref": True,
                "requires_implementation_branch_ref": True,
                "requires_implementation_plan_ref": True,
                "requires_adapter_design_ref": True,
                "requires_security_review_ref": True,
                "requires_test_plan_ref": True,
                "requires_rollback_plan_ref": True,
                "requires_smoke_runbook_ref": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "requires_signature_or_hash": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "flag_application_performed": False,
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
                "file_mutation_performed": False,
                "channel_mutation_performed": False,
                "runtime_flag_writer_enabled": False,
                "adapter_import_allowed": False,
                "adapter_execution_allowed": False,
                "wired_into_sdk_invoke": False,
                "adapter_runtime_wired": False,
                "imports_adapter_in_sdk_invoke": False,
                "instantiates_adapter_in_sdk_invoke": False,
            },
            known_limits=[
                "This SDK contract records disabled adapter runtime preflight intent only.",
                "It does not wire the adapter into /sdk/invoke or apply XAGENT_SDK_WRITE_RUNNER_ENABLED.",
                "It does not import, instantiate, execute the adapter, or invoke the SDK write runner.",
            ],
        )

    def record_owner_acceptance(
        self,
        *,
        owner_acceptance_id: str,
        approval_id: str,
        accepted_by: str,
        accepted_at: str,
        runbook_acknowledged: bool,
        rollback_plan_acknowledged: bool,
        acceptance_signature: str | None = None,
        acceptance_hash: str | None = None,
        notes: str | None = None,
        dry_run: bool = True,
    ) -> SDKOwnerAcceptanceRecordContract:
        return SDKOwnerAcceptanceRecordContract(
            operation="owner_acceptance_record",
            endpoint="/api/v1/control-plane/sdk/owner-acceptance/record",
            request={
                "owner_acceptance_id": owner_acceptance_id,
                "approval_id": approval_id,
                "accepted_by": accepted_by,
                "accepted_at": accepted_at,
                "runbook_acknowledged": runbook_acknowledged,
                "rollback_plan_acknowledged": rollback_plan_acknowledged,
                "acceptance_signature": acceptance_signature,
                "acceptance_hash": acceptance_hash,
                "notes": notes,
                "dry_run": dry_run,
            },
            owner_gate={
                "requires_approved_sdk_approval": True,
                "requires_signature_or_hash": True,
                "requires_runbook_acknowledged": True,
                "requires_rollback_plan_acknowledged": True,
                "marks_approval_executed": False,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            known_limits=[
                "This SDK contract records owner acceptance evidence only.",
                "It does not enable runtime flags or invoke the write runner.",
                "It does not mark an approval executed.",
            ],
        )

    def _thread_contract(
        self,
        *,
        operation: str,
        method: str,
        params: dict[str, Any],
        tenant_id: str | None,
        user_id: str | None,
        idempotency_key: str | None,
        approved_approval_id: str | None,
        dry_run: bool,
    ) -> SDKThreadRunContract:
        request = SDKControlPlaneRequest(
            method=method,
            params=params,
            context={
                "tenant_id": tenant_id or self.default_tenant_id,
                "user_id": user_id or self.default_user_id,
                "sdk_surface": "python",
                "non_interactive": True,
            },
            idempotency_key=idempotency_key,
            dry_run=dry_run,
        )
        return SDKThreadRunContract(
            operation=operation,
            request=request,
            expected_response_shape={
                "status": "queued|running|waiting_for_approval|completed|failed",
                "thread_id": "string",
                "trace_id": "string",
                "turns": "array",
                "approval_summary": "object",
                "evidence_links": "object",
            },
            owner_gate={
                "required_for_write_methods": method not in self._READ_ONLY_METHODS,
                "approved_approval_id": approved_approval_id,
                "owner_approved": bool(approved_approval_id),
                "execution_adapter_contract": "owner_approved_preflight",
                "read_only_runner_contract": method in self._READ_ONLY_METHODS,
                "write_runner_safety_contract": method not in self._READ_ONLY_METHODS,
                "write_runner_execute_gate_contract": method not in self._READ_ONLY_METHODS,
                "write_runner_adapter_review_contract": method not in self._READ_ONLY_METHODS,
                "write_runner_adapter_review_enabled": False,
                "write_runner_runtime_flag_contract": method not in self._READ_ONLY_METHODS,
                "owner_acceptance_evidence_required": method not in self._READ_ONLY_METHODS,
                "owner_acceptance_recording_contract": method not in self._READ_ONLY_METHODS,
                "owner_acceptance_readback_contract": method not in self._READ_ONLY_METHODS,
                "owner_acceptance_record_present": False,
                "runtime_enablement_review_contract": method not in self._READ_ONLY_METHODS,
                "runtime_enablement_review_enabled": False,
                "write_runner_implementation_plan_contract": method not in self._READ_ONLY_METHODS,
                "write_runner_implementation_plan_enabled": False,
                "runtime_smoke_runbook_contract": method not in self._READ_ONLY_METHODS,
                "runtime_smoke_runbook_enabled": False,
                "runtime_enablement_receipt_contract": method not in self._READ_ONLY_METHODS,
                "runtime_enablement_receipt_enabled": False,
                "runtime_implementation_preflight_contract": method not in self._READ_ONLY_METHODS,
                "runtime_implementation_preflight_enabled": False,
                "runtime_flag_enabled": False,
                "runner_invoked": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "adapter_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            channel_strategy={
                "pilot_channel": "feishu",
                "domestic_v1_primary": "feishu",
                "telegram_required": False,
                "slack_blocking": False,
                "dingtalk_or_wechat_work_next": "after_feishu_pilot_acceptance",
            },
            known_limits=[
                "This SDK wrapper builds request envelopes only.",
                "The CLI can submit this envelope to /api/v1/control-plane/sdk/invoke when --execute is set.",
                "No control-plane HTTP request is sent by this contract object itself.",
                "Thread write methods remain owner-gated by the control-plane adapter.",
                "Providing approved_approval_id enables backend readback/preflight only, not real execution.",
                "The write runner adapter review contract declares the future runner target but remains disabled.",
                "The runtime write-runner flag and owner acceptance evidence are declared but not enabled by this SDK wrapper.",
                "Owner acceptance evidence recording/readback is contract-ready but no acceptance record is created by this SDK wrapper.",
                "Runtime enablement review is declared but remains disabled by this SDK wrapper.",
                "The concrete write-runner implementation plan is declared but remains disabled by this SDK wrapper.",
                "Runtime smoke/runbook enablement is declared but remains disabled by this SDK wrapper.",
                "Runtime enablement readiness receipt is declared but remains disabled by this SDK wrapper.",
                "Feishu remains the first domestic V1 channel; no new channel send is performed.",
            ],
        )
