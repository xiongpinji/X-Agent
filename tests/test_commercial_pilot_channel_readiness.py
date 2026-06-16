from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import commercial_pilot_channel_readiness as channel_readiness
from scripts.commercial_pilot_channel_readiness import build_channel_readiness_matrix, write_report


def test_channel_readiness_matrix_marks_feishu_owner_gated_for_domestic_pilot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(channel_readiness, "_read_json", lambda path: None)

    report = build_channel_readiness_matrix(pilot_channel="feishu")

    assert report.status == "ready_with_owner_gates"
    assert report.full_codex_parity_claimed is False
    feishu = next(channel for channel in report.channels if channel.channel == "feishu")
    assert feishu.status == "owner_action_required"
    assert feishu.owner_gated is True
    assert feishu.recommended_for_first_pilot is True
    assert any(capability.name == "live_owner_evidence" for capability in feishu.capabilities)
    outbound = next(capability for capability in feishu.capabilities if capability.name == "outbound_owner_gate")
    assert outbound.status == "preview"
    assert outbound.details["optional"] is True


def test_channel_readiness_matrix_keeps_telegram_as_preview() -> None:
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    telegram = next(channel for channel in report.channels if channel.channel == "telegram")
    assert telegram.status == "preview"
    assert telegram.recommended_for_first_pilot is False


def test_channel_readiness_matrix_marks_feishu_ready_when_live_evidence_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "commercial-pilot-feishu-live.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_live",
                "event_id": "live-feishu-event",
                "event_type": "im.message.receive_v1",
                "signature_mode": "lark_sha256",
                "mutation_performed": False,
                "outbound_message_sent": False,
            }
        ),
        encoding="utf-8",
    )

    original_read_json = channel_readiness._read_json

    def fake_read_json(path: str):
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-live.json":
            return json.loads(report_path.read_text(encoding="utf-8"))
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json":
            return None
        return original_read_json(path)

    monkeypatch.setattr(channel_readiness, "_read_json", fake_read_json)
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    feishu = next(channel for channel in report.channels if channel.channel == "feishu")
    live = next(capability for capability in feishu.capabilities if capability.name == "live_owner_evidence")
    assert live.status == "passed"
    assert live.details["event_id"] == "live-feishu-event"
    assert feishu.status == "ready"
    outbound = next(capability for capability in feishu.capabilities if capability.name == "outbound_owner_gate")
    assert outbound.status == "preview"


def test_channel_readiness_matrix_marks_optional_feishu_outbound_ready_to_execute_as_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read_json(path: str):
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-live.json":
            return {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_live",
                "event_id": "live-feishu-event",
                "event_type": "im.message.receive_v1",
                "signature_mode": "lark_sha256",
                "mutation_performed": False,
                "outbound_message_sent": False,
            }
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json":
            return {
                "status": "ready_to_execute",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_outbound_live",
                "execute_requested": False,
                "owner_approved": False,
                "mutation_performed": False,
                "outbound_message_sent": False,
                "attempted_outbound_message_send": False,
                "full_codex_parity_claimed": False,
            }
        return None

    monkeypatch.setattr(channel_readiness, "_read_json", fake_read_json)
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    feishu = next(channel for channel in report.channels if channel.channel == "feishu")
    outbound = next(capability for capability in feishu.capabilities if capability.name == "outbound_owner_gate")
    assert feishu.status == "ready"
    assert outbound.status == "preview"
    assert outbound.details["source_status"] == "ready_to_execute"
    assert outbound.details["mutation_performed"] is False
    assert outbound.details["outbound_message_sent"] is False


def test_channel_readiness_matrix_marks_optional_feishu_outbound_passed_after_owner_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read_json(path: str):
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-live.json":
            return {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_live",
                "event_id": "live-feishu-event",
                "event_type": "im.message.receive_v1",
                "signature_mode": "lark_sha256",
                "mutation_performed": False,
                "outbound_message_sent": False,
            }
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json":
            return {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_outbound_live",
                "execute_requested": True,
                "owner_approved": True,
                "mutation_performed": True,
                "outbound_message_sent": True,
                "attempted_outbound_message_send": True,
                "full_codex_parity_claimed": False,
            }
        return None

    monkeypatch.setattr(channel_readiness, "_read_json", fake_read_json)
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    feishu = next(channel for channel in report.channels if channel.channel == "feishu")
    outbound = next(capability for capability in feishu.capabilities if capability.name == "outbound_owner_gate")
    assert feishu.status == "ready"
    assert outbound.status == "passed"
    assert outbound.details["execute_requested"] is True
    assert outbound.details["owner_approved"] is True


def test_channel_readiness_matrix_rejects_unsafe_feishu_outbound_report_as_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read_json(path: str):
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-live.json":
            return {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_live",
                "event_id": "live-feishu-event",
                "event_type": "im.message.receive_v1",
                "signature_mode": "lark_sha256",
                "mutation_performed": False,
                "outbound_message_sent": False,
            }
        if path == ".xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json":
            return {
                "status": "passed",
                "channel": "feishu",
                "evidence_type": "commercial_pilot_feishu_outbound_live",
                "execute_requested": True,
                "owner_approved": True,
                "mutation_performed": True,
                "outbound_message_sent": True,
                "attempted_outbound_message_send": True,
                "full_codex_parity_claimed": True,
            }
        return None

    monkeypatch.setattr(channel_readiness, "_read_json", fake_read_json)
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    feishu = next(channel for channel in report.channels if channel.channel == "feishu")
    outbound = next(capability for capability in feishu.capabilities if capability.name == "outbound_owner_gate")
    assert feishu.status == "ready"
    assert outbound.status == "preview"
    assert "not accepted" in str(outbound.error)


def test_channel_readiness_matrix_marks_preview_channels() -> None:
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    discord = next(channel for channel in report.channels if channel.channel == "discord")
    dingtalk = next(channel for channel in report.channels if channel.channel == "dingtalk")
    assert discord.status == "preview"
    assert dingtalk.status == "preview"


def test_channel_readiness_matrix_rejects_unknown_pilot_channel() -> None:
    report = build_channel_readiness_matrix(pilot_channel="unknown")

    assert report.status == "action_required"
    selected = next(check for check in report.checks if check.name == "selected_pilot_channel")
    assert selected.status == "action_required"


def test_write_report_serializes_channel_readiness_matrix(tmp_path: Path) -> None:
    output = tmp_path / "commercial-pilot-channel-readiness.json"
    report = build_channel_readiness_matrix(pilot_channel="feishu")

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "ready_with_owner_gates"
    assert payload["pilot_channel"] == "feishu"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["channels"][1]["channel"] == "feishu"
