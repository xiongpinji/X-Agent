from __future__ import annotations

import json

from scripts.original_kernel_shell_job_runner_integration_report import build_report, write_report


async def test_shell_job_runner_integration_report_is_ready_without_command_execution(tmp_path) -> None:
    sandbox = tmp_path / "sandbox"

    report = await build_report(sandbox_path=sandbox)

    assert report["status"] == "original_kernel_shell_job_runner_integration_ready"
    assert report["evidence_type"] == "original_kernel_shell_job_runner_integration"
    assert report["modules"] == ["shell_job_runner"]
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["sandbox_directory_prepared"] is False
    assert report["sandbox_path_resolved"] == str(sandbox.resolve())
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["shell_command_execution_performed"] is False
    assert report["subprocess_execution_performed"] is False
    assert report["valid_command_payload_executed"] is False
    assert report["real_engineering_task_execution_performed"] is False

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["payload_parser_contract"]["status"] == "passed"
    assert checks["payload_parser_contract"]["details"]["malformed_json_rejected"] is True
    assert checks["pre_execution_guard_contract"]["status"] == "passed"
    assert checks["pre_execution_guard_contract"]["details"]["missing_command_rejected_before_execution"] is True
    assert checks["pre_execution_guard_contract"]["details"]["outside_cwd_rejected_before_execution"] is True
    assert checks["pre_execution_guard_contract"]["details"]["subprocess_reached"] is False
    assert checks["result_encoding_contract"]["status"] == "passed"
    assert checks["result_encoding_contract"]["details"]["prefix_valid"] is True


async def test_shell_job_runner_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-shell-job-runner-integration.json"
    sandbox = tmp_path / "sandbox"

    report = await write_report(output, sandbox_path=sandbox)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_shell_job_runner_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["agent_execution_enabled"] is False
    assert payload["shell_command_execution_performed"] is False
    assert payload["subprocess_execution_performed"] is False
    assert payload["real_engineering_task_execution_performed"] is False
