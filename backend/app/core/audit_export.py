"""Scheduled audit log exports and external system integration (SIEM, log platforms)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ExportFrequency(StrEnum):
    """Export frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    HOURLY = "hourly"


class ExportFormat(StrEnum):
    """Export format options."""
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    SYSLOG = "syslog"


class ExternalSystemType(StrEnum):
    """External system types for integration."""
    SPLUNK = "splunk"
    ELASTICSEARCH = "elasticsearch"
    DATADOG = "datadog"
    CLOUDWATCH = "cloudwatch"
    SYSLOG = "syslog"
    WEBHOOK = "webhook"


class ScheduledExport(BaseModel):
    """Configuration for scheduled audit log exports."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    enabled: bool = True

    # Schedule
    frequency: ExportFrequency
    time_of_day: str = "00:00"  # HH:MM format
    day_of_week: int | None = None  # 0-6 for weekly, None for daily
    day_of_month: int | None = None  # 1-31 for monthly, None for daily

    # Export settings
    format: ExportFormat
    include_details: bool = True
    include_snapshots: bool = False
    include_signatures: bool = True

    # Filters
    tenant_id: str | None = None
    actor_id: str | None = None
    action: str | None = None
    resource_type: str | None = None
    outcome: str | None = None

    # Destination
    destination_path: str | None = None  # Local file path
    destination_url: str | None = None  # Remote URL
    destination_bucket: str | None = None  # S3 bucket
    destination_credentials: dict[str, str] = Field(default_factory=dict)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_export_at: datetime | None = None
    next_export_at: datetime | None = None
    export_count: int = 0


class ExternalSystemIntegration(BaseModel):
    """Configuration for external system integration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    system_type: ExternalSystemType
    enabled: bool = True

    # Connection settings
    endpoint: str
    api_key: str | None = None
    api_secret: str | None = None
    credentials: dict[str, str] = Field(default_factory=dict)

    # Integration settings
    batch_size: int = 100
    flush_interval_seconds: int = 60
    retry_attempts: int = 3
    retry_delay_seconds: int = 5

    # Filters
    min_severity: str = "info"  # info, warning, error, critical
    include_actions: list[str] = Field(default_factory=list)
    exclude_actions: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_sync_at: datetime | None = None
    sync_count: int = 0
    error_count: int = 0


class ExportJob(BaseModel):
    """Represents an export job execution."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    export_config_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"  # running, completed, failed
    record_count: int = 0
    file_path: str | None = None
    file_size: int = 0
    error_message: str | None = None


class SIEMEventAdapter:
    """Adapts audit logs to SIEM event format."""

    @staticmethod
    def to_splunk_event(record: dict[str, Any]) -> dict[str, Any]:
        """Convert audit record to Splunk event format."""
        return {
            "time": record.get("created_at"),
            "source": "xagent-audit",
            "sourcetype": "audit:log",
            "event": {
                "id": record.get("id"),
                "tenant_id": record.get("tenant_id"),
                "actor_id": record.get("actor_id"),
                "action": record.get("action"),
                "resource_type": record.get("resource_type"),
                "resource_id": record.get("resource_id"),
                "outcome": record.get("outcome"),
                "details": record.get("details"),
            },
        }

    @staticmethod
    def to_elasticsearch_doc(record: dict[str, Any]) -> dict[str, Any]:
        """Convert audit record to Elasticsearch document format."""
        return {
            "@timestamp": record.get("created_at"),
            "source": "xagent-audit",
            "log.level": "info",
            "message": f"{record.get('action')} on {record.get('resource_type')}",
            "audit": {
                "id": record.get("id"),
                "tenant_id": record.get("tenant_id"),
                "actor_id": record.get("actor_id"),
                "action": record.get("action"),
                "resource_type": record.get("resource_type"),
                "resource_id": record.get("resource_id"),
                "outcome": record.get("outcome"),
                "duration_ms": record.get("duration_ms"),
                "ip_address": record.get("ip_address"),
            },
        }

    @staticmethod
    def to_datadog_event(record: dict[str, Any]) -> dict[str, Any]:
        """Convert audit record to Datadog event format."""
        return {
            "timestamp": int(datetime.fromisoformat(record.get("created_at")).timestamp()),
            "host": "xagent",
            "service": "audit",
            "ddsource": "xagent-audit",
            "ddtags": f"tenant:{record.get('tenant_id')},action:{record.get('action')}",
            "message": json.dumps(record),
        }

    @staticmethod
    def to_syslog_message(record: dict[str, Any]) -> str:
        """Convert audit record to syslog format (RFC 3164)."""
        timestamp = datetime.fromisoformat(record.get("created_at")).strftime("%b %d %H:%M:%S")
        hostname = "xagent"
        tag = "audit"
        priority = 134  # 16 * 8 + 6 (local0.info)

        message = (
            f"<{priority}>{timestamp} {hostname} {tag}[{record.get('id')[:8]}]: "
            f"action={record.get('action')} "
            f"resource_type={record.get('resource_type')} "
            f"outcome={record.get('outcome')} "
            f"actor_id={record.get('actor_id')} "
            f"tenant_id={record.get('tenant_id')}"
        )

        return message


class ScheduledExportManager:
    """Manages scheduled audit log exports."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._exports: dict[str, ScheduledExport] = {}
        self._jobs: list[ExportJob] = []
        self._storage_path = Path(storage_path) if storage_path else None
        self._export_callbacks: dict[str, Callable] = {}

        if self._storage_path:
            self._load_exports()

    def create_export(self, export: ScheduledExport) -> ScheduledExport:
        """Create a new scheduled export."""
        self._exports[export.id] = export
        self._calculate_next_export(export)
        self._save_exports()
        return export

    def update_export(self, export_id: str, updates: dict[str, Any]) -> ScheduledExport | None:
        """Update a scheduled export."""
        if export_id not in self._exports:
            return None

        export = self._exports[export_id]
        for key, value in updates.items():
            if hasattr(export, key):
                setattr(export, key, value)

        self._calculate_next_export(export)
        self._save_exports()
        return export

    def delete_export(self, export_id: str) -> bool:
        """Delete a scheduled export."""
        if export_id in self._exports:
            del self._exports[export_id]
            self._save_exports()
            return True
        return False

    def list_exports(self) -> list[ScheduledExport]:
        """List all scheduled exports."""
        return list(self._exports.values())

    def get_export(self, export_id: str) -> ScheduledExport | None:
        """Get a specific scheduled export."""
        return self._exports.get(export_id)

    def get_due_exports(self) -> list[ScheduledExport]:
        """Get exports that are due to run."""
        now = datetime.now(UTC)
        due = []

        for export in self._exports.values():
            if not export.enabled or export.next_export_at is None:
                continue

            if export.next_export_at <= now:
                due.append(export)

        return due

    def record_export(self, export_id: str, job: ExportJob) -> None:
        """Record an export job execution."""
        if export_id in self._exports:
            export = self._exports[export_id]
            export.last_export_at = job.completed_at or datetime.now(UTC)
            export.export_count += 1
            self._calculate_next_export(export)
            self._save_exports()

        self._jobs.append(job)

    def get_export_jobs(self, export_id: str | None = None, limit: int = 100) -> list[ExportJob]:
        """Get export job history."""
        jobs = self._jobs

        if export_id:
            jobs = [j for j in jobs if j.export_config_id == export_id]

        return jobs[-limit:]

    def _calculate_next_export(self, export: ScheduledExport) -> None:
        """Calculate next export time."""
        now = datetime.now(UTC)

        if export.frequency == ExportFrequency.HOURLY:
            export.next_export_at = now + timedelta(hours=1)
        elif export.frequency == ExportFrequency.DAILY:
            hour, minute = map(int, export.time_of_day.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            export.next_export_at = next_run
        elif export.frequency == ExportFrequency.WEEKLY:
            hour, minute = map(int, export.time_of_day.split(":"))
            day_of_week = export.day_of_week or 0
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = (day_of_week - next_run.weekday()) % 7
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            next_run += timedelta(days=days_ahead)
            export.next_export_at = next_run
        elif export.frequency == ExportFrequency.MONTHLY:
            hour, minute = map(int, export.time_of_day.split(":"))
            day_of_month = export.day_of_month or 1
            next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)
            export.next_export_at = next_run

    def _load_exports(self) -> None:
        """Load exports from disk."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                export = ScheduledExport.model_validate(json.loads(line))
                self._exports[export.id] = export

    def _save_exports(self) -> None:
        """Save exports to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as handle:
            for export in self._exports.values():
                handle.write(json.dumps(export.model_dump(mode="json"), ensure_ascii=False) + "\n")


class ExternalSystemIntegrationManager:
    """Manages external system integrations."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._integrations: dict[str, ExternalSystemIntegration] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        self._event_queue: list[dict[str, Any]] = []

        if self._storage_path:
            self._load_integrations()

    def create_integration(self, integration: ExternalSystemIntegration) -> ExternalSystemIntegration:
        """Create a new external system integration."""
        self._integrations[integration.id] = integration
        self._save_integrations()
        return integration

    def update_integration(self, integration_id: str, updates: dict[str, Any]) -> ExternalSystemIntegration | None:
        """Update an external system integration."""
        if integration_id not in self._integrations:
            return None

        integration = self._integrations[integration_id]
        for key, value in updates.items():
            if hasattr(integration, key):
                setattr(integration, key, value)

        self._save_integrations()
        return integration

    def delete_integration(self, integration_id: str) -> bool:
        """Delete an external system integration."""
        if integration_id in self._integrations:
            del self._integrations[integration_id]
            self._save_integrations()
            return True
        return False

    def list_integrations(self) -> list[ExternalSystemIntegration]:
        """List all external system integrations."""
        return list(self._integrations.values())

    def get_integration(self, integration_id: str) -> ExternalSystemIntegration | None:
        """Get a specific external system integration."""
        return self._integrations.get(integration_id)

    async def send_event(self, record: dict[str, Any]) -> None:
        """Send audit event to all enabled integrations."""
        for integration in self._integrations.values():
            if not integration.enabled:
                continue

            # Check filters
            if integration.include_actions and record.get("action") not in integration.include_actions:
                continue
            if integration.exclude_actions and record.get("action") in integration.exclude_actions:
                continue

            # Queue event
            self._event_queue.append({
                "integration_id": integration.id,
                "record": record,
                "timestamp": datetime.now(UTC),
            })

    async def flush_events(self) -> None:
        """Flush queued events to external systems."""
        if not self._event_queue:
            return

        # Group events by integration
        by_integration: dict[str, list[dict[str, Any]]] = {}
        for event in self._event_queue:
            integration_id = event["integration_id"]
            if integration_id not in by_integration:
                by_integration[integration_id] = []
            by_integration[integration_id].append(event["record"])

        # Send to each integration
        for integration_id, records in by_integration.items():
            integration = self._integrations.get(integration_id)
            if integration:
                await self._send_to_integration(integration, records)

        self._event_queue.clear()

    async def _send_to_integration(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send records to a specific integration."""
        try:
            if integration.system_type == ExternalSystemType.SPLUNK:
                await self._send_to_splunk(integration, records)
            elif integration.system_type == ExternalSystemType.ELASTICSEARCH:
                await self._send_to_elasticsearch(integration, records)
            elif integration.system_type == ExternalSystemType.DATADOG:
                await self._send_to_datadog(integration, records)
            elif integration.system_type == ExternalSystemType.SYSLOG:
                await self._send_to_syslog(integration, records)
            elif integration.system_type == ExternalSystemType.WEBHOOK:
                await self._send_to_webhook(integration, records)

            integration.last_sync_at = datetime.now(UTC)
            integration.sync_count += 1
        except Exception:
            integration.error_count += 1

    async def _send_to_splunk(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send events to Splunk."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            for record in records:
                event = SIEMEventAdapter.to_splunk_event(record)
                headers = {
                    "Authorization": f"Splunk {integration.api_key}",
                    "Content-Type": "application/json",
                }
                async with session.post(
                    f"{integration.endpoint}/services/collector",
                    json=event,
                    headers=headers,
                ) as resp:
                    if resp.status not in [200, 201]:
                        raise Exception(f"Splunk error: {resp.status}")

    async def _send_to_elasticsearch(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send events to Elasticsearch."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            for record in records:
                doc = SIEMEventAdapter.to_elasticsearch_doc(record)
                headers = {"Content-Type": "application/json"}
                if integration.api_key:
                    headers["Authorization"] = f"Bearer {integration.api_key}"

                async with session.post(
                    f"{integration.endpoint}/xagent-audit/_doc",
                    json=doc,
                    headers=headers,
                ) as resp:
                    if resp.status not in [200, 201]:
                        raise Exception(f"Elasticsearch error: {resp.status}")

    async def _send_to_datadog(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send events to Datadog."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            for record in records:
                event = SIEMEventAdapter.to_datadog_event(record)
                headers = {
                    "DD-API-KEY": integration.api_key,
                    "Content-Type": "application/json",
                }
                async with session.post(
                    f"{integration.endpoint}/v1/input",
                    json=event,
                    headers=headers,
                ) as resp:
                    if resp.status not in [200, 202]:
                        raise Exception(f"Datadog error: {resp.status}")

    async def _send_to_syslog(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send events to syslog server."""
        import socket

        host, port = integration.endpoint.split(":")
        port = int(port)

        for record in records:
            message = SIEMEventAdapter.to_syslog_message(record)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(message.encode("utf-8"), (host, port))

    async def _send_to_webhook(
        self,
        integration: ExternalSystemIntegration,
        records: list[dict[str, Any]],
    ) -> None:
        """Send events to webhook endpoint."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            payload = {
                "events": records,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            headers = {"Content-Type": "application/json"}
            if integration.api_key:
                headers["Authorization"] = f"Bearer {integration.api_key}"

            async with session.post(
                integration.endpoint,
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status not in [200, 201, 202]:
                    raise Exception(f"Webhook error: {resp.status}")

    def _load_integrations(self) -> None:
        """Load integrations from disk."""
        if self._storage_path is None or not self._storage_path.exists():
            return

        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                integration = ExternalSystemIntegration.model_validate(json.loads(line))
                self._integrations[integration.id] = integration

    def _save_integrations(self) -> None:
        """Save integrations to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("w", encoding="utf-8") as handle:
            for integration in self._integrations.values():
                handle.write(json.dumps(integration.model_dump(mode="json"), ensure_ascii=False) + "\n")
