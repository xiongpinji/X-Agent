from __future__ import annotations

from typer.testing import CliRunner

from backend.app.core.channels import ChannelRegistry, TelegramAdapter, ChannelConfig
from backend.app.core.channels.gateway import GatewayService
from cli.config import CLIConfig
from cli.main import app, set_current_config


class _FakeScheduleStore:
    def list(self, limit: int = 1000):
        return ["schedule-1"]


class _FakeScheduler:
    def __init__(self) -> None:
        self.schedule_store = _FakeScheduleStore()
        self.calls = 0

    async def run_due(self, *, limit: int, worker_id: str, lease_seconds: int):
        self.calls += 1
        return []


def test_gateway_status_reports_channels_without_credentials() -> None:
    registry = ChannelRegistry()
    registry.register(TelegramAdapter(ChannelConfig()))
    service = GatewayService(scheduler=_FakeScheduler(), registry=registry)  # type: ignore[arg-type]

    status = service.status()

    assert status.status == "ready"
    assert status.channels == ["telegram"]
    assert status.scheduler["pending_schedules"] == 1


async def test_gateway_run_once_dry_run_does_not_trigger_scheduler() -> None:
    scheduler = _FakeScheduler()
    service = GatewayService(scheduler=scheduler, registry=ChannelRegistry())  # type: ignore[arg-type]

    result = await service.run_once(dry_run=True)

    assert result["status"] == "planned"
    assert scheduler.calls == 0


async def test_gateway_run_once_execute_triggers_scheduler() -> None:
    scheduler = _FakeScheduler()
    service = GatewayService(scheduler=scheduler, registry=ChannelRegistry())  # type: ignore[arg-type]

    result = await service.run_once(dry_run=False, limit=5, lease_seconds=10)

    assert result["status"] == "executed"
    assert result["dry_run"] is False
    assert scheduler.calls == 1


def test_cli_gateway_status_outputs_json() -> None:
    set_current_config(CLIConfig(output_format="plain"))
    runner = CliRunner()

    result = runner.invoke(app, ["--output", "plain", "gateway", "status"])

    assert result.exit_code == 0
    assert '"status": "ready"' in result.stdout


def test_cli_gateway_start_requires_once() -> None:
    set_current_config(CLIConfig(output_format="plain"))
    runner = CliRunner()

    result = runner.invoke(app, ["--output", "plain", "gateway", "start"])

    assert result.exit_code == 1
    assert "Only --once mode" in result.stdout
