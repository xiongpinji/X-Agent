from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.core.channels.base import ChannelRegistry, get_channel_registry
from backend.app.core.workflows import WorkflowScheduler, WorkflowScheduleRecord


@dataclass
class GatewayStatus:
    status: str
    channels: list[str]
    scheduler: dict[str, Any]
    dry_run_supported: bool = True
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class GatewayService:
    """Thin gateway wrapper around channel registry and workflow scheduler."""

    def __init__(
        self,
        *,
        scheduler: WorkflowScheduler | None = None,
        registry: ChannelRegistry | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.registry = registry or get_channel_registry()

    def status(self) -> GatewayStatus:
        pending = 0
        if self.scheduler is not None and hasattr(self.scheduler, "schedule_store"):
            try:
                pending = len(self.scheduler.schedule_store.list(limit=1000))
            except Exception:
                pending = 0
        return GatewayStatus(
            status="ready",
            channels=self.registry.names(),
            scheduler={
                "configured": self.scheduler is not None,
                "pending_schedules": pending,
            },
        )

    async def run_once(
        self,
        *,
        dry_run: bool = True,
        limit: int = 20,
        lease_seconds: int = 60,
    ) -> dict[str, Any]:
        worker_id = f"gateway-{uuid4()}"
        if self.scheduler is None:
            return {
                "status": "degraded",
                "dry_run": dry_run,
                "worker_id": worker_id,
                "triggered": [],
                "reason": "scheduler is not configured",
            }
        if dry_run:
            return {
                "status": "planned",
                "dry_run": True,
                "worker_id": worker_id,
                "triggered": [],
                "limit": limit,
                "lease_seconds": lease_seconds,
            }

        records = await self.scheduler.run_due(
            limit=limit,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        return {
            "status": "executed",
            "dry_run": False,
            "worker_id": worker_id,
            "triggered": [_record_to_dict(record) for record in records],
            "limit": limit,
            "lease_seconds": lease_seconds,
        }


def _record_to_dict(record: WorkflowScheduleRecord) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    return dict(record)
