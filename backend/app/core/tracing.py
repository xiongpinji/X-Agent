from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from backend.app.core.contracts import RunContext, TraceEvent, TraceSummary


class TraceStore:
    """Small trace recorder with optional JSONL persistence."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._events: dict[str, list[TraceEvent]] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def record(self, context: RunContext, event: str, **data: Any) -> TraceEvent:
        trace_event = TraceEvent(
            trace_id=context.trace_id,
            event=event,
            data=data,
            request_id=context.request_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
        )
        with self._lock:
            self._events.setdefault(context.trace_id, []).append(trace_event)
            self._append_to_disk(trace_event)
        return trace_event

    def record_resume(self, context: RunContext, resumed_from: str, **data: Any) -> TraceEvent:
        payload = {"resumed_from": resumed_from, **data}
        return self.record(context, "agent.resumed", **payload)

    def list_events(self, trace_id: str) -> list[TraceEvent]:
        return list(self._events.get(trace_id, []))

    def list_trace_ids(self) -> list[str]:
        trace_ids = list(self._events)
        trace_ids.sort(key=self._trace_sort_key, reverse=True)
        return trace_ids

    def list_summaries(self, limit: int = 20) -> list[TraceSummary]:
        summaries = [self._summarize_trace_id(trace_id) for trace_id in self.list_trace_ids()]
        return summaries[:limit]

    def get_summary(self, trace_id: str) -> TraceSummary:
        return self._summarize_trace_id(trace_id)

    def event_count(self) -> int:
        return sum(len(events) for events in self._events.values())

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                event = TraceEvent.model_validate(json.loads(line))
                self._events.setdefault(event.trace_id, []).append(event)

    def _append_to_disk(self, event: TraceEvent) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def _summarize_trace_id(self, trace_id: str) -> TraceSummary:
        events = self._events.get(trace_id, [])
        if not events:
            return TraceSummary(trace_id=trace_id, event_count=0)
        first = events[0]
        last = events[-1]
        task = None
        resumed_from = None
        for event in events:
            if event.event == "agent.started":
                task = event.data.get("task")
            if event.event == "agent.resumed":
                resumed_from = event.data.get("resumed_from")
        return TraceSummary(
            trace_id=trace_id,
            event_count=len(events),
            started_at=first.timestamp,
            ended_at=last.timestamp,
            last_event=last.event,
            task=task,
            snapshot={
                "request_id": first.request_id,
                "agent_id": first.agent_id,
                "tenant_id": first.tenant_id,
                "user_id": first.user_id,
                "event_count": len(events),
                "last_event": last.event,
                "resumed_from": resumed_from,
                "resume_count": sum(1 for event in events if event.event == "agent.resumed"),
            },
        )

    def _trace_sort_key(self, trace_id: str) -> tuple:
        events = self._events.get(trace_id, [])
        if not events:
            return (0, trace_id)
        return (events[-1].timestamp, trace_id)


def build_tracer(storage_path: str | Path | None = None) -> TraceStore:
    return TraceStore(storage_path=storage_path)


tracer = TraceStore()
