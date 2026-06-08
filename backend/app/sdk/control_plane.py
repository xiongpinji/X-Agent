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
