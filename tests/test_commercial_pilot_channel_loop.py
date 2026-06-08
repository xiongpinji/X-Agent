from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_channel_loop import build_channel_loop_evidence, write_report
from scripts.commercial_pilot_core_entrypoints import CommandResult


def _result(returncode: int, *, timed_out: bool = False) -> CommandResult:
    return CommandResult(
        command=["python", "-m", "pytest"],
        returncode=returncode,
        duration_seconds=1.25,
        stdout_tail="sample stdout",
        stderr_tail="sample stderr",
        timeout_seconds=180,
        timed_out=timed_out,
    )


def test_channel_loop_evidence_passes_for_zero_returncode() -> None:
    report = build_channel_loop_evidence(command_result=_result(0), pilot_channel="feishu")

    assert report.status == "passed"
    assert report.pilot_channel == "feishu"
    assert report.full_codex_parity_claimed is False
    assert report.checks[0].status == "passed"


def test_channel_loop_evidence_fails_for_nonzero_returncode() -> None:
    report = build_channel_loop_evidence(command_result=_result(1))

    assert report.status == "failed"
    assert report.checks[0].status == "failed"
    assert report.checks[0].details["returncode"] == 1


def test_channel_loop_evidence_fails_for_timeout() -> None:
    report = build_channel_loop_evidence(command_result=_result(124, timed_out=True))

    assert report.status == "failed"
    assert report.checks[0].details["timed_out"] is True


def test_write_report_serializes_channel_loop_evidence(tmp_path: Path) -> None:
    output = tmp_path / "commercial-pilot-channel-loop.json"
    report = build_channel_loop_evidence(command_result=_result(0), pilot_channel="feishu")

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["pilot_channel"] == "feishu"
    assert payload["evidence_type"] == "commercial_pilot_channel_loop"
    assert payload["checks"][0]["name"] == "pytest_pilot_channel_loop"
