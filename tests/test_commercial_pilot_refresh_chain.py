from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_refresh_chain import (
    RefreshChainReport,
    RefreshStep,
    _error_from_payload,
    _run_step,
    _status_from_payload,
    write_report,
)


def test_status_from_payload_accepts_passed_and_pilot_ready() -> None:
    assert _status_from_payload({"status": "passed"}) == "passed"
    assert _status_from_payload({"status": "pilot_ready"}) == "passed"
    assert _status_from_payload({"status": "ready_with_owner_gates"}) == "passed"
    assert _status_from_payload({"status": "failed"}) == "failed"


def test_error_from_payload_uses_nested_check_errors() -> None:
    assert _error_from_payload({"status": "passed"}) is None
    assert _error_from_payload({"status": "ready_with_owner_gates"}) is None
    error = _error_from_payload(
        {
            "status": "failed",
            "checks": [
                {"name": "one", "status": "failed", "error": "first"},
                {"name": "two", "status": "failed", "error": "second"},
            ],
        }
    )
    assert error == "first; second"


def test_run_step_records_success(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"

    def runner() -> tuple[str, Path, dict[str, object]]:
        return "passed", output, {"status": "passed"}

    step = _run_step("sample", runner)

    assert step.name == "sample"
    assert step.status == "passed"
    assert step.report_path == str(output)
    assert step.error is None


def test_run_step_records_exception() -> None:
    def runner() -> tuple[str, Path, dict[str, object]]:
        raise RuntimeError("boom")

    step = _run_step("sample", runner)

    assert step.status == "failed"
    assert step.error == "boom"


def test_write_report_serializes_refresh_chain(tmp_path: Path) -> None:
    output = tmp_path / "commercial-pilot-refresh-chain.json"
    report = RefreshChainReport(
        status="pilot_ready",
        generated_at="2026-06-08T00:00:00Z",
        pilot_channel="feishu",
        readiness_report_path="ready.json",
        full_codex_parity_claimed=False,
        steps=[
            RefreshStep(
                name="sample",
                status="passed",
                report_path="sample.json",
                duration_seconds=1.0,
            )
        ],
        next_commands=["review"],
        known_limits=["limit"],
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_ready"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["steps"][0]["name"] == "sample"
