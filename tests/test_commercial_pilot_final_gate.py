from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_delivery_manifest import DeliveryManifestReport
from scripts.commercial_pilot_final_gate import build_final_gate_report, write_report
from scripts.commercial_pilot_ops_status import PilotOpsStatusReport


def _ops_report(*, status: str = "pilot_ops_ready", parity: bool = False) -> PilotOpsStatusReport:
    return PilotOpsStatusReport(
        status=status,
        generated_at="2026-06-08T00:00:00Z",
        pilot_channel="feishu",
        pilot_tag_name="x-agent-commercial-pilot-feishu-20260608",
        pilot_commit_sha="765d44b69da061caba6585a4cee0105bbf3310a7",
        rc_tag_name="x-agent-commercial-rc-20260608-6",
        rc_commit_sha="592141f35520df62578a00cbb805eeaa7371a940",
        handoff_status="pilot_handoff_ready",
        channel_readiness_status="ready_with_owner_gates",
        inbound_live_status="passed",
        outbound_owner_gate_status="preview",
        rc_baseline_status="commercial_rc_ready",
        full_codex_parity_claimed=parity,
        reports={},
        checks=[],
        next_commands=[],
        known_limits=[],
    )


def _manifest_report(
    *,
    status: str = "delivery_manifest_ready",
    parity: bool = False,
    artifact_count: int = 20,
) -> DeliveryManifestReport:
    return DeliveryManifestReport(
        status=status,
        generated_at="2026-06-08T00:00:01Z",
        evidence_type="commercial_pilot_delivery_manifest",
        pilot_channel="feishu",
        full_codex_parity_claimed=parity,
        artifacts=[object()] * artifact_count,  # type: ignore[list-item]
        checks=[],
        next_commands=[],
        known_limits=[],
    )


def test_final_gate_ready_refreshes_ops_before_manifest(tmp_path: Path) -> None:
    events: list[str] = []

    def ops_builder(**_kwargs):  # noqa: ANN001
        events.append("build_ops")
        return _ops_report()

    def manifest_builder(**_kwargs):  # noqa: ANN001
        events.append("build_manifest")
        return _manifest_report()

    def ops_writer(report, output_path):  # noqa: ANN001
        events.append(f"write_ops:{output_path.name}")

    def manifest_writer(report, output_path):  # noqa: ANN001
        events.append(f"write_manifest:{output_path.name}")

    report = build_final_gate_report(
        ops_output_path=tmp_path / "commercial-pilot-ops-status.json",
        manifest_output_path=tmp_path / "commercial-pilot-delivery-manifest.json",
        ops_builder=ops_builder,
        manifest_builder=manifest_builder,
        ops_writer=ops_writer,
        manifest_writer=manifest_writer,
    )

    assert report.status == "final_gate_ready"
    assert events == [
        "build_ops",
        "write_ops:commercial-pilot-ops-status.json",
        "build_manifest",
        "write_manifest:commercial-pilot-delivery-manifest.json",
    ]
    assert [step.name for step in report.steps] == ["operator_status", "delivery_manifest"]
    assert {check.status for check in report.checks} == {"passed"}
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False


def test_final_gate_blocks_when_ops_status_is_not_ready(tmp_path: Path) -> None:
    report = build_final_gate_report(
        ops_output_path=tmp_path / "ops.json",
        manifest_output_path=tmp_path / "manifest.json",
        ops_builder=lambda **_kwargs: _ops_report(status="pilot_ops_action_required"),
        manifest_builder=lambda **_kwargs: _manifest_report(),
        ops_writer=lambda _report, _output: None,
        manifest_writer=lambda _report, _output: None,
    )

    assert report.status == "final_gate_blocked"
    ops = next(check for check in report.checks if check.name == "operator_status_ready")
    assert ops.status == "failed"
    assert report.ops_status == "pilot_ops_action_required"


def test_final_gate_blocks_when_manifest_is_not_ready(tmp_path: Path) -> None:
    report = build_final_gate_report(
        ops_output_path=tmp_path / "ops.json",
        manifest_output_path=tmp_path / "manifest.json",
        ops_builder=lambda **_kwargs: _ops_report(),
        manifest_builder=lambda **_kwargs: _manifest_report(status="delivery_manifest_blocked"),
        ops_writer=lambda _report, _output: None,
        manifest_writer=lambda _report, _output: None,
    )

    assert report.status == "final_gate_blocked"
    manifest = next(check for check in report.checks if check.name == "delivery_manifest_ready")
    assert manifest.status == "failed"
    assert report.delivery_manifest_status == "delivery_manifest_blocked"


def test_final_gate_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    report = build_final_gate_report(
        ops_output_path=tmp_path / "ops.json",
        manifest_output_path=tmp_path / "manifest.json",
        ops_builder=lambda **_kwargs: _ops_report(parity=True),
        manifest_builder=lambda **_kwargs: _manifest_report(),
        ops_writer=lambda _report, _output: None,
        manifest_writer=lambda _report, _output: None,
    )

    assert report.status == "final_gate_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "operator_status" in parity.details["claiming_reports"]


def test_write_report_serializes_final_gate(tmp_path: Path) -> None:
    output = tmp_path / "commercial-pilot-final-gate.json"
    report = build_final_gate_report(
        ops_output_path=tmp_path / "ops.json",
        manifest_output_path=tmp_path / "manifest.json",
        ops_builder=lambda **_kwargs: _ops_report(),
        manifest_builder=lambda **_kwargs: _manifest_report(),
        ops_writer=lambda _report, _output: None,
        manifest_writer=lambda _report, _output: None,
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "final_gate_ready"
    assert payload["evidence_type"] == "commercial_pilot_final_gate"
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["steps"][0]["name"] == "operator_status"
