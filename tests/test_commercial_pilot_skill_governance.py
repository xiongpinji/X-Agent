from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_core_entrypoints import CommandResult
from scripts.commercial_pilot_skill_governance import build_skill_governance_evidence, write_report


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


def test_skill_governance_evidence_passes_for_zero_returncode() -> None:
    report = build_skill_governance_evidence(command_result=_result(0))

    assert report.status == "passed"
    assert report.full_codex_parity_claimed is False
    assert report.checks[0].status == "passed"
    assert report.checks[0].error is None


def test_skill_governance_evidence_fails_for_nonzero_returncode() -> None:
    report = build_skill_governance_evidence(command_result=_result(1))

    assert report.status == "failed"
    assert report.checks[0].status == "failed"
    assert report.checks[0].details["returncode"] == 1


def test_skill_governance_evidence_fails_for_timeout() -> None:
    report = build_skill_governance_evidence(command_result=_result(124, timed_out=True))

    assert report.status == "failed"
    assert report.checks[0].details["timed_out"] is True


def test_write_report_serializes_skill_governance_evidence(tmp_path: Path) -> None:
    output = tmp_path / "commercial-pilot-skill-governance.json"
    report = build_skill_governance_evidence(command_result=_result(0))

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "commercial_pilot_skill_governance"
    assert payload["checks"][0]["name"] == "pytest_skill_governance"
