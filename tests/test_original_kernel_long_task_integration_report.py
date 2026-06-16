from __future__ import annotations

import json

from scripts.original_kernel_long_task_integration_report import build_report, write_report


def test_long_task_integration_report_is_ready() -> None:
    report = build_report()

    assert report["status"] == "original_kernel_long_task_integration_ready"
    assert report["evidence_type"] == "original_kernel_long_task_integration"
    assert report["modules"] == [
        "long_task_models",
        "long_task_state_machine",
        "long_task_merge_gates",
    ]
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["long_task_worker_enabled"] is False
    assert report["subagent_execution_enabled"] is False
    assert report["workflow_execution_enabled"] is False
    assert report["merge_execution_enabled"] is False
    assert report["command_execution_enabled"] is False
    assert report["real_validation_execution_performed"] is False
    assert report["simulated_records_only"] is True

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["long_task_models_contract"]["status"] == "passed"
    assert checks["long_task_models_contract"]["details"]["record_status"] == "queued"
    assert checks["long_task_state_machine_contract"]["status"] == "passed"
    assert checks["long_task_state_machine_contract"]["details"]["final_state"] == "succeeded"
    assert checks["long_task_state_machine_contract"]["details"]["illegal_terminal_transition_blocked"] is True
    assert checks["long_task_merge_gates_contract"]["status"] == "passed"
    assert checks["long_task_merge_gates_contract"]["details"]["validation_gate_status"] == "passed"
    assert checks["long_task_merge_gates_contract"]["details"]["authorization_status"] == "authorized"
    assert checks["long_task_merge_gates_contract"]["details"]["blocked_parent_gate_status"] == (
        "validation_evidence_blocked"
    )


def test_long_task_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-long-task-integration.json"

    report = write_report(output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_long_task_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["agent_execution_enabled"] is False
    assert payload["long_task_worker_enabled"] is False
    assert payload["merge_execution_enabled"] is False
    assert payload["command_execution_enabled"] is False
