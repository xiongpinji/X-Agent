from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.original_kernel_module_integration_summary import (
    EXPECTED_REPORTS,
    build_report,
    write_report,
)


def test_module_integration_summary_is_ready_for_expected_reports(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _write_expected_reports(reports_dir)

    report = build_report(reports_dir=reports_dir)

    assert report["status"] == "original_kernel_module_integration_summary_ready"
    assert report["evidence_type"] == "original_kernel_module_integration_summary"
    assert report["expected_report_count"] == len(EXPECTED_REPORTS)
    assert report["ready_report_count"] == len(EXPECTED_REPORTS)
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["command_execution_enabled"] is False
    assert report["real_execution_or_mutation_enabled"] is False
    assert report["full_codex_parity_claimed"] is False
    assert report["mainline_wiring_enabled"] is False
    assert report["summary_reads_reports_only"] is True
    assert report["report_file_written"] is False
    assert "module-original-kernel" in report["modules"]

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["expected_reports_present"]["status"] == "passed"
    assert checks["expected_reports_ready"]["status"] == "passed"
    assert checks["no_real_execution_or_mutation_enabled"]["status"] == "passed"
    assert checks["no_full_codex_parity_claimed"]["status"] == "passed"

    summaries = {item["filename"]: item for item in report["report_summaries"]}
    for spec in EXPECTED_REPORTS:
        summary = summaries[spec.filename]
        assert summary["present"] is True
        assert summary["ready"] is True
        assert summary["status"] == spec.ready_status
        assert summary["evidence_type"] == spec.evidence_type
        assert summary["unsafe_true_flags"] == []
        assert summary["full_codex_parity_claimed"] is False


def test_module_integration_summary_blocks_missing_report(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _write_expected_reports(reports_dir, omit={EXPECTED_REPORTS[-1].filename})

    report = build_report(reports_dir=reports_dir)

    assert report["status"] == "failed"
    assert report["ready_report_count"] == len(EXPECTED_REPORTS) - 1
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["expected_reports_present"]["status"] == "failed"
    assert checks["expected_reports_present"]["details"]["missing_reports"] == [
        EXPECTED_REPORTS[-1].filename
    ]


def test_module_integration_summary_blocks_unsafe_report_flags(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    unsafe_filename = EXPECTED_REPORTS[2].filename
    _write_expected_reports(reports_dir, overrides={unsafe_filename: {"agent_execution_enabled": True}})

    report = build_report(reports_dir=reports_dir)

    assert report["status"] == "failed"
    summaries = {item["filename"]: item for item in report["report_summaries"]}
    assert summaries[unsafe_filename]["ready"] is False
    assert summaries[unsafe_filename]["unsafe_true_flags"] == ["agent_execution_enabled"]

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["no_real_execution_or_mutation_enabled"]["status"] == "failed"
    assert checks["no_real_execution_or_mutation_enabled"]["details"]["unsafe_reports"] == {
        unsafe_filename: ["agent_execution_enabled"]
    }


def test_module_integration_summary_blocks_codex_parity_claim(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    parity_filename = EXPECTED_REPORTS[0].filename
    _write_expected_reports(
        reports_dir,
        overrides={parity_filename: {"full_codex_parity_claimed": True}},
    )

    report = build_report(reports_dir=reports_dir)

    assert report["status"] == "failed"
    summaries = {item["filename"]: item for item in report["report_summaries"]}
    assert summaries[parity_filename]["ready"] is False
    assert summaries[parity_filename]["full_codex_parity_claimed"] is True

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["no_full_codex_parity_claimed"]["status"] == "failed"
    assert checks["no_full_codex_parity_claimed"]["details"]["parity_claim_reports"] == [
        parity_filename
    ]


def test_module_integration_summary_write_report_records_report_file_only(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _write_expected_reports(reports_dir)
    output = tmp_path / "original-kernel-module-integration-summary.json"

    report = write_report(output, reports_dir=reports_dir)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_module_integration_summary_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["real_execution_or_mutation_enabled"] is False
    assert payload["mainline_wiring_enabled"] is False


def _write_expected_reports(
    reports_dir: Path,
    *,
    omit: set[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> None:
    omitted = omit or set()
    per_file_overrides = overrides or {}
    for spec in EXPECTED_REPORTS:
        if spec.filename in omitted:
            continue
        payload: dict[str, Any] = {
            "status": spec.ready_status,
            "evidence_type": spec.evidence_type,
            "modules": ["module-original-kernel"],
            "entrypoints_modified": False,
            "api_router_modified": False,
            "control_plane_modified": False,
            "frontend_modified": False,
            "agent_loop_modified": False,
            "backend_core_init_modified": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "command_execution_enabled": False,
            "checks": [{"name": "contract", "status": "passed"}],
            "known_limits": ["No full Codex parity claim is made by this report."],
        }
        payload.update(per_file_overrides.get(spec.filename, {}))
        (reports_dir / spec.filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
