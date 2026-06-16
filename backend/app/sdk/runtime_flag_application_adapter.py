"""Disabled SDK runtime flag application adapter.

This module provides the concrete adapter boundary for the future
XAGENT_SDK_WRITE_RUNNER_ENABLED application step. It is intentionally not
wired into /sdk/invoke and cannot apply the flag or invoke the write runner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_RUNTIME_FLAG_NAME = "XAGENT_SDK_WRITE_RUNNER_ENABLED"


@dataclass(frozen=True)
class RuntimeFlagApplicationAdapterInput:
    approval_id: str
    runtime_flag_name: str
    target_state: str
    implementation_preflight_audit_id: str
    idempotency_key: str
    dry_run: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeFlagApplicationAdapterPlan:
    status: str
    runtime_flag_name: str
    target_state: str
    approval_id: str
    implementation_preflight_audit_id: str
    idempotency_key: str
    checks: dict[str, bool]
    known_limits: list[str]
    runtime_flag_enabled: bool = False
    flag_application_performed: bool = False
    implementation_enabled: bool = False
    execute_enabled: bool = False
    write_runner_enabled: bool = False
    adapter_execution_enabled: bool = False
    agent_execution_enabled: bool = False
    write_execution_enabled: bool = False
    runner_invoked: bool = False
    mark_executed: bool = False
    mutation_performed: bool = False
    network_mutation_performed: bool = False
    file_mutation_performed: bool = False
    channel_mutation_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SDKRuntimeFlagApplicationAdapter:
    """Build disabled runtime flag application plans without applying them."""

    def build_plan(
        self,
        request: RuntimeFlagApplicationAdapterInput,
    ) -> RuntimeFlagApplicationAdapterPlan:
        checks = {
            "runtime_flag_name_allowed": request.runtime_flag_name == ALLOWED_RUNTIME_FLAG_NAME,
            "target_state_supported": request.target_state == "enabled",
            "approval_id_present": bool(request.approval_id),
            "implementation_preflight_audit_id_present": bool(request.implementation_preflight_audit_id),
            "idempotency_key_present": bool(request.idempotency_key),
            "dry_run_required": request.dry_run is True,
        }
        ready = all(checks.values())
        return RuntimeFlagApplicationAdapterPlan(
            status="disabled_plan_ready" if ready else "blocked",
            runtime_flag_name=request.runtime_flag_name,
            target_state=request.target_state,
            approval_id=request.approval_id,
            implementation_preflight_audit_id=request.implementation_preflight_audit_id,
            idempotency_key=request.idempotency_key,
            checks=checks,
            known_limits=[
                "This adapter builds a disabled dry-run plan only.",
                "It does not read, write, or apply XAGENT_SDK_WRITE_RUNNER_ENABLED.",
                "It does not invoke the SDK write runner or mark an approval executed.",
            ],
        )
