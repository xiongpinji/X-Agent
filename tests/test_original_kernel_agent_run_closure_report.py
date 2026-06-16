from __future__ import annotations

import json

from scripts.original_kernel_agent_run_closure_report import build_report, write_report


def test_agent_run_closure_integration_report_is_ready() -> None:
    report = build_report()

    assert report["status"] == "original_kernel_agent_run_closure_integration_ready"
    assert report["evidence_type"] == "original_kernel_agent_run_closure_integration"
    assert report["modules"] == ["agent_run_closure"]
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
    assert report["command_execution_enabled"] is False
    assert report["write_runner_invoked"] is False
    assert report["real_tool_execution_performed"] is False
    assert report["simulated_tool_records_only"] is True

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["ready_handoff_contract"]["status"] == "passed"
    assert checks["ready_handoff_contract"]["details"]["ready_for_handoff"] is True
    assert checks["missing_validation_contract"]["status"] == "passed"
    assert "validation_missing" in checks["missing_validation_contract"]["details"]["blocking_reasons"]
    assert checks["failed_validation_repair_contract"]["status"] == "passed"
    assert checks["failed_validation_repair_contract"]["details"]["first_suggestion"]["category"] == "test_failed"

    assert report["artifacts"]["ready_handoff"]["status"] == "ready_for_handoff"
    assert report["artifacts"]["missing_validation"]["status"] == "needs_followup"
    assert report["artifacts"]["failed_validation"]["status"] == "needs_followup"


def test_agent_run_closure_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-agent-run-closure-integration.json"

    report = write_report(output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_agent_run_closure_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["agent_execution_enabled"] is False
    assert payload["command_execution_enabled"] is False
    assert payload["real_tool_execution_performed"] is False
