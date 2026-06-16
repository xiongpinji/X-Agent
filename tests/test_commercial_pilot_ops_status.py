from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_ops_status import build_pilot_ops_status_report, write_report

PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
RC_TAG = "x-agent-commercial-rc-20260608-6"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _handoff_payload(*, status: str = "pilot_handoff_ready", parity: bool = False) -> dict[str, object]:
    return {
        "status": status,
        "pilot_tag_name": PILOT_TAG,
        "expected_pilot_commit_sha": PILOT_SHA,
        "rc_tag_name": RC_TAG,
        "expected_rc_commit_sha": RC_SHA,
        "full_codex_parity_claimed": parity,
    }


def _rc_payload(*, status: str = "commercial_rc_ready", rc_tag: str = RC_TAG, rc_sha: str = RC_SHA) -> dict[str, object]:
    return {
        "status": status,
        "tag_name": rc_tag,
        "expected_commit_sha": rc_sha,
    }


def _channel_payload(*, feishu_status: str = "ready", parity: bool = False) -> dict[str, object]:
    return {
        "status": "ready_with_owner_gates",
        "pilot_channel": "feishu",
        "full_codex_parity_claimed": parity,
        "channels": [
            {
                "channel": "telegram",
                "status": "preview",
                "capabilities": [],
            },
            {
                "channel": "feishu",
                "status": feishu_status,
                "capabilities": [
                    {"name": "live_owner_evidence", "status": "passed"},
                    {"name": "outbound_owner_gate", "status": "preview"},
                ],
            },
        ],
    }


def _inbound_payload(*, outbound_message_sent: bool = False) -> dict[str, object]:
    return {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_id": "200a6a4679c9192722309edf45478364",
        "event_type": "im.message.receive_v1",
        "signature_mode": "lark_sha256",
        "encrypted_callback": True,
        "mutation_performed": False,
        "outbound_message_sent": outbound_message_sent,
    }


def _outbound_payload(
    *,
    status: str = "owner_action_required",
    execute_requested: bool = False,
    owner_approved: bool = False,
    mutation_performed: bool = False,
    outbound_message_sent: bool = False,
    parity: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_outbound_live",
        "execute_requested": execute_requested,
        "owner_approved": owner_approved,
        "mutation_performed": mutation_performed,
        "outbound_message_sent": outbound_message_sent,
        "attempted_outbound_message_send": mutation_performed,
        "full_codex_parity_claimed": parity,
    }


def _write_all_reports(tmp_path: Path, *, include_outbound: bool = True) -> tuple[Path, Path, Path, Path, Path]:
    handoff = tmp_path / "commercial-pilot-handoff-status.json"
    channel = tmp_path / "commercial-pilot-channel-readiness.json"
    inbound = tmp_path / "commercial-pilot-feishu-live.json"
    outbound = tmp_path / "commercial-pilot-feishu-outbound-live.json"
    rc = tmp_path / "rc-delivery-status.json"
    _write_json(handoff, _handoff_payload())
    _write_json(channel, _channel_payload())
    _write_json(inbound, _inbound_payload())
    _write_json(rc, _rc_payload())
    if include_outbound:
        _write_json(outbound, _outbound_payload())
    return handoff, channel, inbound, outbound, rc


def test_ops_status_ready_with_optional_outbound_owner_gate_preview(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_ready"
    assert report.outbound_owner_gate_status == "preview"
    assert report.full_codex_parity_claimed is False
    required = [check for check in report.checks if check.name != "feishu_outbound_owner_gate"]
    assert {check.status for check in required} == {"passed"}


def test_ops_status_ready_when_optional_outbound_report_is_missing(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path, include_outbound=False)

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_ready"
    outbound_check = next(check for check in report.checks if check.name == "feishu_outbound_owner_gate")
    assert outbound_check.status == "preview"
    assert outbound_check.details["optional"] is True


def test_ops_status_records_passed_owner_approved_outbound_send(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    _write_json(
        outbound,
        _outbound_payload(
            status="passed",
            execute_requested=True,
            owner_approved=True,
            mutation_performed=True,
            outbound_message_sent=True,
        ),
    )

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_ready"
    outbound_check = next(check for check in report.checks if check.name == "feishu_outbound_owner_gate")
    assert outbound_check.status == "passed"
    assert outbound_check.details["outbound_message_sent"] is True


def test_ops_status_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    _write_json(channel, _channel_payload(parity=True))

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "channel_readiness" in parity.details["claiming_reports"]


def test_ops_status_blocks_outbound_mutation_without_owner_approval(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    _write_json(outbound, _outbound_payload(mutation_performed=True, outbound_message_sent=False))

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_blocked"
    outbound_check = next(check for check in report.checks if check.name == "feishu_outbound_owner_gate")
    assert outbound_check.status == "failed"
    assert "without explicit execute and owner approval" in str(outbound_check.error)


def test_ops_status_requires_ready_channel_matrix(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    _write_json(channel, _channel_payload(feishu_status="owner_action_required"))

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_action_required"
    readiness = next(check for check in report.checks if check.name == "channel_readiness")
    assert readiness.status == "action_required"


def test_ops_status_rejects_inbound_report_with_outbound_send(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    _write_json(inbound, _inbound_payload(outbound_message_sent=True))

    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    assert report.status == "pilot_ops_blocked"
    inbound_check = next(check for check in report.checks if check.name == "feishu_inbound_live")
    assert inbound_check.status == "failed"
    assert "outbound_message_sent" in inbound_check.details["mismatches"]


def test_write_report_serializes_ops_status(tmp_path: Path) -> None:
    handoff, channel, inbound, outbound, rc = _write_all_reports(tmp_path)
    output = tmp_path / "commercial-pilot-ops-status.json"
    report = build_pilot_ops_status_report(
        handoff_report_path=handoff,
        channel_readiness_report_path=channel,
        feishu_live_report_path=inbound,
        outbound_report_path=outbound,
        rc_delivery_report_path=rc,
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pilot_ops_ready"
    assert payload["pilot_channel"] == "feishu"
    assert payload["pilot_tag_name"] == PILOT_TAG
    assert payload["reports"]["feishu_inbound_live"] == str(inbound)
