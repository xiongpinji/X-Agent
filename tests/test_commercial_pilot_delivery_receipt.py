from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_delivery_receipt import (
    build_delivery_receipt_report,
    render_markdown_receipt,
    write_markdown_receipt,
    write_report,
)


PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _final_gate_payload(
    *,
    status: str = "final_gate_ready",
    parity: bool = False,
    mutation_performed: bool = False,
    outbound_message_sent: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "evidence_type": "commercial_pilot_final_gate",
        "pilot_channel": "feishu",
        "ops_status": "pilot_ops_ready",
        "delivery_manifest_status": "delivery_manifest_ready",
        "full_codex_parity_claimed": parity,
        "mutation_performed": mutation_performed,
        "outbound_message_sent": outbound_message_sent,
    }


def _ops_payload(*, status: str = "pilot_ops_ready", parity: bool = False) -> dict[str, object]:
    return {
        "status": status,
        "pilot_channel": "feishu",
        "pilot_tag_name": PILOT_TAG,
        "pilot_commit_sha": PILOT_SHA,
        "rc_tag_name": RC_TAG,
        "rc_commit_sha": RC_SHA,
        "outbound_owner_gate_status": "preview",
        "full_codex_parity_claimed": parity,
    }


def _manifest_payload(*, status: str = "delivery_manifest_ready", parity: bool = False) -> dict[str, object]:
    return {
        "status": status,
        "evidence_type": "commercial_pilot_delivery_manifest",
        "pilot_channel": "feishu",
        "full_codex_parity_claimed": parity,
        "artifacts": [
            {"name": "ops_status_report", "status": "passed"},
            {"name": "delivery_manifest_script", "status": "present"},
        ],
    }


def _write_all_reports(tmp_path: Path) -> tuple[Path, Path, Path]:
    final_gate = tmp_path / "commercial-pilot-final-gate.json"
    ops = tmp_path / "commercial-pilot-ops-status.json"
    manifest = tmp_path / "commercial-pilot-delivery-manifest.json"
    _write_json(final_gate, _final_gate_payload())
    _write_json(ops, _ops_payload())
    _write_json(manifest, _manifest_payload())
    return final_gate, ops, manifest


def test_delivery_receipt_ready_from_final_gate_ops_and_manifest(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)

    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )

    assert report.status == "delivery_receipt_ready"
    assert report.pilot_channel == "feishu"
    assert report.pilot_tag_name == PILOT_TAG
    assert report.final_gate_status == "final_gate_ready"
    assert report.delivery_manifest_status == "delivery_manifest_ready"
    assert report.artifact_count == 2
    assert report.full_codex_parity_claimed is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert {check.status for check in report.checks} == {"passed"}
    assert all(source.sha256 for source in report.source_reports)


def test_delivery_receipt_blocks_missing_source_report(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)
    final_gate.unlink()

    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )

    assert report.status == "delivery_receipt_blocked"
    source_check = next(check for check in report.checks if check.name == "source_reports_available")
    assert source_check.status == "failed"
    assert "final_gate" in source_check.details["failed_sources"]


def test_delivery_receipt_blocks_non_ready_final_gate(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)
    _write_json(final_gate, _final_gate_payload(status="final_gate_blocked"))

    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )

    assert report.status == "delivery_receipt_blocked"
    gate = next(check for check in report.checks if check.name == "final_gate_ready")
    assert gate.status == "failed"


def test_delivery_receipt_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)
    _write_json(ops, _ops_payload(parity=True))

    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )

    assert report.status == "delivery_receipt_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"


def test_delivery_receipt_blocks_final_gate_mutation(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)
    _write_json(final_gate, _final_gate_payload(mutation_performed=True, outbound_message_sent=True))

    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )

    assert report.status == "delivery_receipt_blocked"
    mutation = next(check for check in report.checks if check.name == "no_final_gate_mutation")
    outbound = next(check for check in report.checks if check.name == "no_final_gate_outbound_send")
    assert mutation.status == "failed"
    assert outbound.status == "failed"


def test_write_receipt_json_and_markdown(tmp_path: Path) -> None:
    final_gate, ops, manifest = _write_all_reports(tmp_path)
    report = build_delivery_receipt_report(
        final_gate_report_path=final_gate,
        ops_status_report_path=ops,
        delivery_manifest_report_path=manifest,
    )
    json_output = tmp_path / "commercial-pilot-delivery-receipt.json"
    markdown_output = tmp_path / "commercial-pilot-delivery-receipt.md"

    write_report(report, json_output)
    write_markdown_receipt(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "delivery_receipt_ready"
    assert payload["evidence_type"] == "commercial_pilot_delivery_receipt"
    assert "# X-Agent Feishu Pilot V1 Delivery Receipt" in markdown
    assert "Final gate: `final_gate_ready`" in markdown
    assert PILOT_TAG in render_markdown_receipt(report)
