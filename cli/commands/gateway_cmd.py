from __future__ import annotations

import asyncio

import typer

from backend.app.core.channels.gateway import GatewayService
from backend.app.dependencies import get_workflow_scheduler
from cli.console import print_error, print_json, print_success
from cli.main import get_current_config

gateway_app = typer.Typer(
    name="gateway",
    help="Always-available gateway and scheduler commands",
    no_args_is_help=True,
)


def _service() -> GatewayService:
    return GatewayService(scheduler=get_workflow_scheduler())


@gateway_app.command("status")
def status() -> None:
    config = get_current_config()
    print_json(_service().status().__dict__, config)


@gateway_app.command("start")
def start(
    once: bool = typer.Option(False, "--once", help="Run one scheduler tick and exit"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Plan without triggering by default"),
    limit: int = typer.Option(20, "--limit", min=1, max=1000),
    lease_seconds: int = typer.Option(60, "--lease-seconds", min=1),
) -> None:
    config = get_current_config()
    if not once:
        print_error("Only --once mode is available in this MVP.", config)
        raise typer.Exit(code=1)
    result = asyncio.run(
        _service().run_once(
            dry_run=dry_run,
            limit=limit,
            lease_seconds=lease_seconds,
        )
    )
    print_json(result, config)
    print_success("Gateway once-run completed", config)
