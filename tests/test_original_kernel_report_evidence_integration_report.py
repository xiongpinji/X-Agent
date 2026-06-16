from __future__ import annotations

import json

from scripts.original_kernel_report_evidence_integration_report import build_report, write_report


def test_report_evidence_integration_report_is_ready_without_broad_pytest() -> None:
    report = build_report()

    assert report["status"] == "original_kernel_report_evidence_integration_ready"
    assert report["evidence_type"] == "original_kernel_report_evidence_integration"
    assert report["modules"] == [
        "run_pytest_evidence",
        "check_report_hygiene",
        "normalize_report_count_aliases",
    ]
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["existing_reports_modified"] is False
    assert report["temporary_files_written"] is True
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["broad_pytest_execution_performed"] is False
    assert report["real_pytest_execution_performed"] is False
    assert report["fake_pytest_runner_used"] is True
    assert report["count_alias_normalization_dry_run"] is True
    assert report["report_hygiene_scan_performed"] is True

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["pytest_evidence_fake_runner_contract"]["status"] == "passed"
    assert checks["pytest_evidence_fake_runner_contract"]["details"]["real_pytest_execution_performed"] is False
    assert checks["pytest_evidence_fake_runner_contract"]["details"]["passed_shards"] == 2
    assert checks["report_hygiene_contract"]["status"] == "passed"
    assert checks["report_hygiene_contract"]["details"]["clean_status"] == "passed"
    assert checks["report_hygiene_contract"]["details"]["dirty_status"] == "failed"
    assert checks["count_alias_normalization_dry_run_contract"]["status"] == "passed"
    assert checks["count_alias_normalization_dry_run_contract"]["details"]["source_report_preserved"] is True


def test_report_evidence_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-report-evidence-integration.json"

    report = write_report(output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_report_evidence_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["existing_reports_modified"] is False
    assert payload["broad_pytest_execution_performed"] is False
    assert payload["real_pytest_execution_performed"] is False
