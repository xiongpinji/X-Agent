from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ObservabilityEvent:
    type: str
    trace_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    workflow_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class TraceMapper:
    def map(self, event_type: str, **payload: Any) -> ObservabilityEvent:
        return ObservabilityEvent(
            type=event_type,
            trace_id=payload.pop("trace_id", None),
            run_id=payload.pop("run_id", None),
            agent_id=payload.pop("agent_id", None),
            workflow_id=payload.pop("workflow_id", None),
            tenant_id=payload.pop("tenant_id", None),
            user_id=payload.pop("user_id", None),
            payload=dict(payload),
        )


trace_mapper = TraceMapper()
