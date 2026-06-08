from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_acceptance_gate import build_acceptance_gate_report, write_report


PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _final_gate_payload(*, parity: bool = False, mutation: bool = False) -> dict[str, object]:
    return {
        "status": "final_gate_ready",
        "evidence_type": "commercial_pilot_final_gate",
        "pilot_channel": "feishu",
        "full_codex_parity_claimed": parity,
        "mutation_performed": mutation,
        "outbound_message_sent": mutation,
    }


def _receipt_payload(*, parity: bool = False, mutation: bool = False) -> dict[str, object]:
    return {
        "status": "delivery_receipt_ready",
        "evidence_type": "commercial_pilot_delivery_receipt",
        "pilot_channel": "feishu",
        "pilot_tag_name": PILOT_TAG,
        "pilot_commit_sha": PILOT_SHA,
        "rc_tag_name": RC_TAG,
        "rc_commit_sha": RC_SHA,
        "full_codex_parity_claimed": parity,
        "mutation_performed": mutation,
        "outbound_message_sent": mutation,
    }


def _handoff_payload(*, status: str = "pilot_handoff_ready") -> dict[str, object]:
    return {
        "status": status,
        "evidence_type": "commercial_pilot_handoff_status",
        "pilot_tag_name": PILOT_TAG,
        "expected_pilot_commit_sha": PILOT_SHA,
        "rc_tag_name": RC_TAG,
        "expected_rc_commit_sha": RC_SHA,
        "full_codex_parity_claimed": False,
    }


def _ops_payload(*, outbound: str = "preview") -> dict[str, object]:
    return {
        "status": "pilot_ops_ready",
        "evidence_type": "commercial_pilot_ops_status",
        "pilot_channel": "feishu",
        "pilot_tag_name": PILOT_TAG,
        "pilot_commit_sha": PILOT_SHA,
        "rc_tag_name": RC_TAG,
        "rc_commit_sha": RC_SHA,
        "inbound_live_status": "passed",
        "outbound_owner_gate_status": outbound,
        "full_codex_parity_claimed": False,
    }


def _manifest_payload() -> dict[str, object]:
    return {
        "status": "delivery_manifest_ready",
        "evidence_type": "commercial_pilot_delivery_manifest",
        "pilot_channel": "feishu",
        "full_codex_parity_claimed": False,
        "artifacts": [{"name": "acceptance_gate_script", "status": "present"}],
    }


def _live_payload(*, mutation: bool = False, signature_mode: str = "lark_sha256") -> dict[str, object]:
    return {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_id": "200a6a4679c9192722309edf45478364",
        "event_type": "im.message.receive_v1",
        "tenant_key_present": True,
        "message_id_present": True,
        "chat_id_present": True,
        "content_present": True,
        "signature_mode": signature_mode,
        "encrypted_callback": True,
        "mutation_performed": mutation,
        "outbound_message_sent": mutation,
    }


def _write_all_reports(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "final_gate": tmp_path / "commercial-pilot-final-gate.json",
        "receipt": tmp_path / "commercial-pilot-delivery-receipt.json",
        "handoff": tmp_path / "commercial-pilot-handoff-status.json",
        "ops": tmp_path / "commercial-pilot-ops-status.json",
        "manifest": tmp_path / "commercial-pilot-delivery-manifest.json",
        "live": tmp_path / "commercial-pilot-feishu-live.json",
    }
    _write_json(paths["final_gate"], _final_gate_payload())
    _write_json(paths["receipt"], _receipt_payload())
    _write_json(paths["handoff"], _handoff_payload())
    _write_json(paths["ops"], _ops_payload())
    _write_json(paths["manifest"], _manifest_payload())
    _write_json(paths["live"], _live_payload())
    return paths


def _build(paths: dict[str, Path]):
    return build_acceptance_gate_report(
        final_gate_report_path=paths["final_gate"],
        delivery_receipt_report_path=paths["receipt"],
        handoff_report_path=paths["handoff"],
        ops_status_report_path=paths["ops"],
        delivery_manifest_report_path=paths["manifest"],
        feishu_live_report_path=paths["live"],
    )


def test_acceptance_gate_ready_from_existing_evidence(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)

    report = _build(paths)

    assert report.status == "pilot_acceptance_ready"
    assert report.pilot_channel == "feishu"
    assert report.pilot_tag_name == PILOT_TAG
    assert report.pilot_commit_sha == PILOT_SHA
    assert report.full_codex_parity_claimed is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert {check.status for check in report.checks} == {"passed"}
    assert all(source.sha256 for source in report.source_reports)


def test_acceptance_gate_action_required_when_source_report_missing(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    paths["receipt"].unlink()

    report = _build(paths)

    assert report.status == "pilot_acceptance_action_required"
    source_check = next(check for check in report.checks if check.name == "source_reports_available")
    assert source_check.status == "action_required"
    assert "delivery_receipt" in source_check.details["failed_sources"]


def test_acceptance_gate_action_required_when_handoff_not_ready(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    _write_json(paths["handoff"], _handoff_payload(status="pilot_tag_action_required"))

    report = _build(paths)

    assert report.status == "pilot_acceptance_action_required"
    handoff = next(check for check in report.checks if check.name == "handoff_ready")
    assert handoff.status == "action_required"


def test_acceptance_gate_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    _write_json(paths["receipt"], _receipt_payload(parity=True))

    report = _build(paths)

    assert report.status == "pilot_acceptance_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "delivery_receipt" in parity.details["claiming_reports"]


def test_acceptance_gate_blocks_final_gate_or_live_mutation(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    _write_json(paths["final_gate"], _final_gate_payload(mutation=True))
    _write_json(paths["live"], _live_payload(mutation=True))

    report = _build(paths)

    assert report.status == "pilot_acceptance_blocked"
    no_mutation = next(check for check in report.checks if check.name == "no_acceptance_gate_mutation")
    live_audit = next(check for check in report.checks if check.name == "feishu_inbound_event_audit")
    assert no_mutation.status == "failed"
    assert live_audit.status == "failed"


def test_acceptance_gate_blocks_identity_mismatch(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    bad = _receipt_payload()
    bad["pilot_commit_sha"] = "0" * 40
    _write_json(paths["receipt"], bad)

    report = _build(paths)

    assert report.status == "pilot_acceptance_blocked"
    identity = next(check for check in report.checks if check.name == "identity_consistency")
    assert identity.status == "failed"
    assert "receipt_pilot_commit_sha" in identity.details["mismatches"]


def test_write_report_serializes_acceptance_gate(tmp_path: Path) -> None:
    paths = _write_all_reports(tmp_path)
    report = _build(paths)
    output = tmp_path / "commercial-pilot-acceptance-gate.json"

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_acceptance_ready"
    assert payload["evidence_type"] == "commercial_pilot_acceptance_gate"
    assert payload["source_reports"][0]["sha256"]
