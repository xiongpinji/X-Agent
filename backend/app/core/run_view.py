from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunView:
    trace_id: str
    status: str
    answer: str | None = None
    recovery: dict[str, Any] = field(default_factory=dict)
    snapshot: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "answer": self.answer,
            "recovery": self.recovery,
            "snapshot": self.snapshot,
            "summary": self.summary,
            "metadata": self.metadata,
        }
