from __future__ import annotations

from backend.app.sdk.runtime_flag_application_adapter import (
    ALLOWED_RUNTIME_FLAG_NAME,
    RuntimeFlagApplicationAdapterInput,
    SDKRuntimeFlagApplicationAdapter,
)


def test_runtime_flag_application_adapter_builds_disabled_plan_only() -> None:
    plan = SDKRuntimeFlagApplicationAdapter().build_plan(
        RuntimeFlagApplicationAdapterInput(
            approval_id="approval-1",
            runtime_flag_name=ALLOWED_RUNTIME_FLAG_NAME,
            target_state="enabled",
            implementation_preflight_audit_id="audit-preflight-1",
            idempotency_key="flag-application-1",
        )
    ).to_dict()

    assert plan["status"] == "disabled_plan_ready"
    assert plan["checks"]["runtime_flag_name_allowed"] is True
    assert plan["checks"]["dry_run_required"] is True
    assert plan["runtime_flag_enabled"] is False
    assert plan["flag_application_performed"] is False
    assert plan["implementation_enabled"] is False
    assert plan["execute_enabled"] is False
    assert plan["write_runner_enabled"] is False
    assert plan["adapter_execution_enabled"] is False
    assert plan["agent_execution_enabled"] is False
    assert plan["write_execution_enabled"] is False
    assert plan["runner_invoked"] is False
    assert plan["mark_executed"] is False
    assert plan["mutation_performed"] is False
    assert plan["network_mutation_performed"] is False
    assert plan["file_mutation_performed"] is False
    assert plan["channel_mutation_performed"] is False


def test_runtime_flag_application_adapter_blocks_non_dry_run() -> None:
    plan = SDKRuntimeFlagApplicationAdapter().build_plan(
        RuntimeFlagApplicationAdapterInput(
            approval_id="approval-1",
            runtime_flag_name=ALLOWED_RUNTIME_FLAG_NAME,
            target_state="enabled",
            implementation_preflight_audit_id="audit-preflight-1",
            idempotency_key="flag-application-1",
            dry_run=False,
        )
    )

    payload = plan.to_dict()
    assert payload["status"] == "blocked"
    assert payload["checks"]["dry_run_required"] is False
    assert payload["runtime_flag_enabled"] is False
    assert payload["runner_invoked"] is False
    assert payload["mutation_performed"] is False
