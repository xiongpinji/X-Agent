from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.commercial_pilot_readiness import build_pilot_readiness_report, write_report

RC_TAG = "x-agent-commercial-rc-20260608-6"
RC_COMMIT = "592141f35520df62578a00cbb805eeaa7371a940"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_docs(tmp_path: Path) -> tuple[Path, Path, Path]:
    control = tmp_path / "xagent-control-plane-protocol.md"
    control.write_text(
        "thread/start approval/list mcp/tool/call runtime/rc/status\n",
        encoding="utf-8",
    )
    pilot = tmp_path / "COMMERCIAL_PILOT_READINESS.md"
    pilot.write_text(
        "30-Minute Setup Path\nRollback\nKnown Limits\nPilot Evidence Template\n",
        encoding="utf-8",
    )
    plan = tmp_path / "codex-aligned-commercial-delivery.md"
    plan.write_text(
        "Definition Of Done\nWorkstreams\nfull Codex parity\n",
        encoding="utf-8",
    )
    return control, pilot, plan


def _write_rc_delivery(path: Path, *, status: str = "commercial_rc_ready") -> None:
    _write_json(
        path,
        {
            "status": status,
            "tag_name": RC_TAG,
            "expected_commit_sha": RC_COMMIT,
            "checks": [{"name": "expected_commit", "status": "passed"}],
        },
    )


def _write_passed_evidence(path: Path) -> None:
    _write_json(path, {"status": "passed", "checks": [{"name": "sample", "status": "passed"}]})


def test_pilot_report_is_ready_when_all_evidence_passes(tmp_path: Path) -> None:
    control, pilot, plan = _write_docs(tmp_path)
    rc = tmp_path / "rc-delivery-status.json"
    _write_rc_delivery(rc)
    evidence = [tmp_path / f"evidence-{index}.json" for index in range(5)]
    for path in evidence:
        _write_passed_evidence(path)

    report = build_pilot_readiness_report(
        rc_delivery_report_path=rc,
        output_path=tmp_path / "commercial-pilot-readiness.json",
        rc_tag=RC_TAG,
        rc_commit=RC_COMMIT,
        control_plane_doc_path=control,
        commercial_pilot_doc_path=pilot,
        codex_alignment_plan_path=plan,
        core_entrypoints_report_path=evidence[0],
        workbench_thread_report_path=evidence[1],
        pilot_channel_report_path=evidence[2],
        skill_governance_report_path=evidence[3],
        approval_audit_report_path=evidence[4],
    )

    assert report.status == "pilot_ready"
    assert report.full_codex_parity_claimed is False
    assert {check.status for check in report.checks} == {"passed"}


def test_pilot_report_is_pending_when_pilot_evidence_is_missing(tmp_path: Path) -> None:
    control, pilot, plan = _write_docs(tmp_path)
    rc = tmp_path / "rc-delivery-status.json"
    _write_rc_delivery(rc)

    report = build_pilot_readiness_report(
        rc_delivery_report_path=rc,
        output_path=tmp_path / "commercial-pilot-readiness.json",
        control_plane_doc_path=control,
        commercial_pilot_doc_path=pilot,
        codex_alignment_plan_path=plan,
    )

    assert report.status == "pilot_pending"
    checks = {check.name: check.status for check in report.checks}
    assert checks["rc_delivery_status"] == "passed"
    assert checks["core_entrypoints"] == "action_required"
    assert any("commercial_pilot_core_entrypoints.py" in command for command in report.next_commands)


def test_pilot_report_is_blocked_when_rc_delivery_is_not_ready(tmp_path: Path) -> None:
    control, pilot, plan = _write_docs(tmp_path)
    rc = tmp_path / "rc-delivery-status.json"
    _write_rc_delivery(rc, status="failed")

    report = build_pilot_readiness_report(
        rc_delivery_report_path=rc,
        output_path=tmp_path / "commercial-pilot-readiness.json",
        control_plane_doc_path=control,
        commercial_pilot_doc_path=pilot,
        codex_alignment_plan_path=plan,
    )

    assert report.status == "pilot_blocked"
    rc_check = next(check for check in report.checks if check.name == "rc_delivery_status")
    assert rc_check.status == "failed"


def test_write_report_serializes_checks(tmp_path: Path) -> None:
    control, pilot, plan = _write_docs(tmp_path)
    rc = tmp_path / "rc-delivery-status.json"
    output = tmp_path / "commercial-pilot-readiness.json"
    _write_rc_delivery(rc)

    report = build_pilot_readiness_report(
        rc_delivery_report_path=rc,
        output_path=output,
        control_plane_doc_path=control,
        commercial_pilot_doc_path=pilot,
        codex_alignment_plan_path=plan,
    )
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_pending"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["checks"][0]["name"] == "rc_delivery_status"


def test_cli_writes_pending_report_and_returns_nonzero(tmp_path: Path) -> None:
    control, pilot, plan = _write_docs(tmp_path)
    rc = tmp_path / "rc-delivery-status.json"
    output = tmp_path / "commercial-pilot-readiness.json"
    _write_rc_delivery(rc)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/commercial_pilot_readiness.py",
            "--rc-delivery-report",
            str(rc),
            "--output",
            str(output),
            "--control-plane-doc",
            str(control),
            "--commercial-pilot-doc",
            str(pilot),
            "--codex-alignment-plan",
            str(plan),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    assert "Commercial pilot readiness status: pilot_pending" in result.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_pending"
