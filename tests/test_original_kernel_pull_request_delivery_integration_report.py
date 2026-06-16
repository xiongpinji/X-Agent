from __future__ import annotations

import json

from scripts.original_kernel_pull_request_delivery_integration_report import build_report, write_report


def test_pull_request_delivery_integration_report_is_ready_without_external_mutation(tmp_path) -> None:
    report = build_report(workspace_path=tmp_path)

    assert report["status"] == "original_kernel_pull_request_delivery_integration_ready"
    assert report["evidence_type"] == "original_kernel_pull_request_delivery_integration"
    assert report["modules"] == ["pull_request_delivery"]
    assert report["workspace_path"] == str(tmp_path.resolve())
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["network_mutation_performed"] is False
    assert report["external_provider_http_performed"] is False
    assert report["git_push_performed"] is False
    assert report["real_pull_request_created"] is False
    assert report["command_execution_performed"] is False
    assert report["subprocess_execution_performed"] is False
    assert report["fake_runner_used"] is True
    assert report["fake_http_client_used"] is True
    assert report["dry_run_first_contract_verified"] is True
    assert report["explicit_execute_required"] is True
    assert report["supported_providers"] == ["github", "gitlab", "gitee"]

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["dry_run_default_contract"]["status"] == "passed"
    assert checks["dry_run_default_contract"]["details"]["push_attempted"] is False
    assert checks["dry_run_default_contract"]["details"]["http_call_count"] == 0
    assert checks["explicit_execute_guard_contract"]["status"] == "passed"
    assert checks["explicit_execute_guard_contract"]["details"]["missing_credentials_issues"] == [
        "credential_missing"
    ]
    assert checks["provider_plan_contract"]["status"] == "passed"
    assert checks["provider_plan_contract"]["details"]["gitlab_status"] == "planned"
    assert checks["provider_plan_contract"]["details"]["gitee_status"] == "planned"
    assert checks["unsupported_remote_contract"]["status"] == "passed"
    assert checks["unsupported_remote_contract"]["details"]["issue_codes"] == ["provider_unsupported"]


def test_pull_request_delivery_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-pull-request-delivery-integration.json"

    report = write_report(output, workspace_path=tmp_path)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_pull_request_delivery_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["external_provider_http_performed"] is False
    assert payload["git_push_performed"] is False
    assert payload["real_pull_request_created"] is False
