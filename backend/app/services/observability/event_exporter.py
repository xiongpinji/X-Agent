from __future__ import annotations

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
