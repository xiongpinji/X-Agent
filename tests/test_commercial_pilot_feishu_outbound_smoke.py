from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import commercial_pilot_feishu_outbound_smoke
from scripts.commercial_pilot_feishu_outbound_smoke import (
    build_feishu_outbound_smoke_report,
    write_report,
)


class FakeBridge:
    def __init__(self, *, configured: bool = True, fail_send: bool = False) -> None:
        self.configured = configured
        self.fail_send = fail_send
        self.app_id = "cli_a_test" if configured else None
        self.app_secret = "secret" if configured else None
        self.encrypt_key = "encrypt" if configured else None
        self.sent: list[dict[str, str]] = []

    def configure_from_env(self) -> bool:
        return self.configured

    async def send_text_message(self, *, receive_id: str, text: str, receive_id_type: str = "chat_id") -> dict[str, object]:
        if self.fail_send:
            raise RuntimeError("provider rejected test send")
        self.sent.append(
            {
                "receive_id": receive_id,
                "text": text,
                "receive_id_type": receive_id_type,
            }
        )
        return {
            "code": 0,
            "msg": "ok",
            "data": {"message_id": "om_owner_smoke", "chat_id": receive_id},
        }


@pytest.mark.asyncio
async def test_default_mode_records_owner_action_required_without_mutation() -> None:
    bridge = FakeBridge(configured=False)

    report = await build_feishu_outbound_smoke_report(receive_id=None, bridge=bridge)

    assert report.status == "owner_action_required"
    assert report.execute_requested is False
    assert report.owner_approved is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.attempted_outbound_message_send is False
    assert report.full_codex_parity_claimed is False
    assert bridge.sent == []


@pytest.mark.asyncio
async def test_configured_dry_run_with_receive_id_is_ready_to_execute() -> None:
    bridge = FakeBridge(configured=True)

    report = await build_feishu_outbound_smoke_report(
        receive_id="oc_disposable",
        text="dry run only",
        bridge=bridge,
    )

    assert report.status == "ready_to_execute"
    assert report.receive_id_present is True
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert bridge.sent == []
    assert any("--execute --owner-approved" in command for command in report.next_commands)


@pytest.mark.asyncio
async def test_execute_without_owner_approval_does_not_send() -> None:
    bridge = FakeBridge(configured=True)

    report = await build_feishu_outbound_smoke_report(
        receive_id="oc_disposable",
        execute=True,
        owner_approved=False,
        bridge=bridge,
    )

    assert report.status == "owner_action_required"
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert bridge.sent == []
    owner_gate = next(check for check in report.checks if check.name == "owner_gate_mode")
    assert owner_gate.status == "action_required"


@pytest.mark.asyncio
async def test_execute_with_owner_approval_sends_once_and_summarizes_result() -> None:
    bridge = FakeBridge(configured=True)

    report = await build_feishu_outbound_smoke_report(
        receive_id="oc_disposable",
        receive_id_type="chat_id",
        text="owner approved smoke",
        execute=True,
        owner_approved=True,
        bridge=bridge,
    )

    assert report.status == "passed"
    assert report.mutation_performed is True
    assert report.outbound_message_sent is True
    assert report.attempted_outbound_message_send is True
    assert report.feishu_result_summary["code"] == 0
    assert report.feishu_result_summary["message_id_present"] is True
    assert bridge.sent == [
        {
            "receive_id": "oc_disposable",
            "text": "owner approved smoke",
            "receive_id_type": "chat_id",
        }
    ]


@pytest.mark.asyncio
async def test_execute_provider_failure_records_failed_report() -> None:
    bridge = FakeBridge(configured=True, fail_send=True)

    report = await build_feishu_outbound_smoke_report(
        receive_id="oc_disposable",
        execute=True,
        owner_approved=True,
        bridge=bridge,
    )

    assert report.status == "failed"
    assert report.mutation_performed is True
    assert report.outbound_message_sent is False
    send_check = next(check for check in report.checks if check.name == "outbound_send")
    assert send_check.status == "failed"
    assert "provider rejected test send" in str(send_check.error)


@pytest.mark.asyncio
async def test_write_report_serializes_without_receive_id_or_text(tmp_path: Path) -> None:
    bridge = FakeBridge(configured=True)
    output = tmp_path / "commercial-pilot-feishu-outbound-live.json"
    report = await build_feishu_outbound_smoke_report(
        receive_id="oc_disposable",
        text="do not store this text",
        execute=True,
        owner_approved=True,
        output_path=output,
        bridge=bridge,
    )

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "commercial_pilot_feishu_outbound_live"
    assert payload["full_codex_parity_claimed"] is False
    assert "oc_disposable" not in serialized
    assert "do not store this text" not in serialized


def test_cli_default_writes_owner_action_required_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    output = tmp_path / "commercial-pilot-feishu-outbound-live.json"
    monkeypatch.delenv("XAGENT_FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("XAGENT_FEISHU_APP_SECRET", raising=False)
    monkeypatch.delenv("XAGENT_FEISHU_ENCRYPT_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts/commercial_pilot_feishu_outbound_smoke.py",
            "--output",
            str(output),
        ],
    )

    exit_code = commercial_pilot_feishu_outbound_smoke.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Commercial pilot Feishu outbound smoke status: owner_action_required" in captured.out
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
