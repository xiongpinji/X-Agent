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
    ) -> SDKThreadRunContract:
        return self._thread_contract(
            operation="runtime_evidence_read",
            method="runtime/evidence/read",
            params={"report_name": report_name},
            tenant_id=tenant_id,
            user_id=user_id,
            idempotency_key=None,
            approved_approval_id=None,
            dry_run=True,
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
                "Feishu remains the first domestic V1 channel; no new channel send is performed.",
            ],
        )
