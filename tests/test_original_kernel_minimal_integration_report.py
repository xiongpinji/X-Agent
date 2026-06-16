from __future__ import annotations

import json
import logging

from scripts.original_kernel_minimal_integration_report import build_report, write_report


def test_minimal_integration_report_is_ready_without_root_logging_mutation() -> None:
    root_logger = logging.getLogger()
    root_handlers_before = list(root_logger.handlers)
    root_level_before = root_logger.level

    report = build_report()

    assert list(root_logger.handlers) == root_handlers_before
    assert root_logger.level == root_level_before
    assert report["status"] == "original_kernel_minimal_integration_ready"
    assert report["evidence_type"] == "original_kernel_minimal_integration"
    assert report["modules"] == ["structured_logging", "permission_profiles"]
    assert report["entrypoints_modified"] is False
    assert report["global_logging_configured"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["write_runner_invoked"] is False

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["structured_logging_contract"]["status"] == "passed"
    assert checks["structured_logging_contract"]["details"]["root_handlers_preserved"] is True
    assert checks["permission_profiles_contract"]["status"] == "passed"
    assert checks["permission_profiles_contract"]["details"]["deny_precedence_verified"] is True


def test_write_report_records_report_file_only(tmp_path) -> None:
    output = tmp_path / "original-kernel-minimal-integration.json"

    report = write_report(output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_minimal_integration_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False
    assert payload["agent_execution_enabled"] is False
