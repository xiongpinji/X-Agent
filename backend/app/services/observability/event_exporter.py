from __future__ import annotations

from typing import Any

from backend.app.services.observability.trace_mapper import ObservabilityEvent, trace_mapper


class ObservabilityExporter:
    def __init__(self) -> None:
        self._events: list[ObservabilityEvent] = []

    def export(self, event_type: str, **payload) -> ObservabilityEvent:
        event = trace_mapper.map(event_type, **payload)
        self._events.append(event)
        return event

    def list_events(self) -> list[ObservabilityEvent]:
        return list(self._events)


observability_exporter = ObservabilityExporter()


class EventExporter:
    """Async event exporter for batch event sending."""

    def __init__(self) -> None:
        self._buffer: list[dict[str, Any]] = []

    async def _send_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Send events to backend (stub for mocking)."""
        return {"status": "success", "count": len(events)}

    async def export(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """Export a batch of events."""
        return await self._send_events(events)
