from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.api.commercial_pilot as commercial_pilot


PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _runtime_payload(
    status: str,
    *,
    evidence_type: str | None = None,
    parity: bool = False,
    mutation: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "full_codex_parity_claimed": parity,
    }
    if evidence_type:
        payload["evidence_type"] = evidence_type
    if status in {
        "pilot_acceptance_ready",
        "handoff_index_ready",
        "final_gate_ready",
        "delivery_receipt_ready",
        "passed",
    }:
        payload["mutation_performed"] = mutation
        payload["outbound_message_sent"] = mutation
    return payload


def _write_all_reports(report_dir: Path) -> None:
    _write_json(
        report_dir / "commercial-pilot-acceptance-gate.json",
        _runtime_payload("pilot_acceptance_ready", evidence_type="commercial_pilot_acceptance_gate")
        | {
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-handoff-index.json",
        _runtime_payload("handoff_index_ready", evidence_type="commercial_pilot_handoff_index"),
    )
    _write_json(
        report_dir / "commercial-pilot-final-gate.json",
        _runtime_payload("final_gate_ready", evidence_type="commercial_pilot_final_gate"),
    )
    _write_json(
        report_dir / "commercial-pilot-delivery-receipt.json",
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt"),
    )
    _write_json(report_dir / "commercial-pilot-handoff-status.json", {"status": "pilot_handoff_ready"})
    _write_json(
        report_dir / "commercial-pilot-ops-status.json",
        {
            "status": "pilot_ops_ready",
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
            "outbound_owner_gate_status": "preview",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        report_dir / "commercial-pilot-delivery-manifest.json",
        _runtime_payload("delivery_manifest_ready", evidence_type="commercial_pilot_delivery_manifest"),
    )
    _write_json(
        report_dir / "commercial-pilot-feishu-live.json",
        _runtime_payload("passed", evidence_type="commercial_pilot_feishu_live")
        | {
            "channel": "feishu",
            "event_id": "200a6a4679c9192722309edf45478364",
            "event_type": "im.message.receive_v1",
            "tenant_key_present": True,
            "message_id_present": True,
            "chat_id_present": True,
            "content_present": True,
            "signature_mode": "lark_sha256",
            "encrypted_callback": True,
        },
    )
    _write_json(report_dir / "commercial-pilot-channel-readiness.json", {"status": "ready_with_owner_gates"})
    _write_json(report_dir / "rc-delivery-status.json", {"status": "commercial_rc_ready"})


def _client(report_dir: Path, monkeypatch) -> TestClient:  # noqa: ANN001
    monkeypatch.setattr(commercial_pilot, "REPORT_DIR", report_dir)
    app = FastAPI()
    app.include_router(commercial_pilot.router)
    return TestClient(app)


def test_feishu_pilot_status_ready_from_runtime_reports(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pilot_operational_ready"
    assert payload["pilot_channel"] == "feishu"
    assert payload["pilot_tag_name"] == PILOT_TAG
    assert payload["full_codex_parity_claimed"] is False
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert {check["status"] for check in payload["checks"]} == {"passed"}
    inbound = next(check for check in payload["checks"] if check["name"] == "feishu_inbound_event_audit")
    assert inbound["details"]["event_id"] == "200a6a4679c9192722309edf45478364"


def test_feishu_pilot_reports_list_includes_digests(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/reports")

    assert response.status_code == 200
    payload = response.json()
    acceptance = next(report for report in payload["reports"] if report["name"] == "acceptance_gate")
    assert acceptance["status"] == "passed"
    assert acceptance["sha256"]
    assert acceptance["size_bytes"] > 0


def test_feishu_pilot_single_report_returns_payload(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/reports/acceptance_gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "report_available"
    assert payload["report"]["name"] == "acceptance_gate"
    assert payload["payload"]["status"] == "pilot_acceptance_ready"


def test_feishu_pilot_status_action_required_when_handoff_index_missing(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)
    (tmp_path / "commercial-pilot-handoff-index.json").unlink()

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pilot_operational_action_required"
    handoff = next(report for report in payload["reports"] if report["name"] == "handoff_index")
    assert handoff["status"] == "missing"


def test_feishu_pilot_status_blocks_full_codex_parity_claim(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)
    _write_json(
        tmp_path / "commercial-pilot-delivery-receipt.json",
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt", parity=True),
    )

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pilot_operational_blocked"
    parity = next(check for check in payload["checks"] if check["name"] == "no_full_codex_parity_claim")
    assert parity["status"] == "failed"
    assert "delivery_receipt" in parity["details"]["claiming_reports"]


def test_feishu_pilot_unknown_report_returns_404(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _write_all_reports(tmp_path)

    response = _client(tmp_path, monkeypatch).get("/api/v1/commercial-pilot/feishu/reports/unknown")

    assert response.status_code == 404
