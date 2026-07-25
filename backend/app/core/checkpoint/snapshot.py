"""执行状态快照。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ExecutionSnapshot:
    """一次检查点的完整执行状态快照。"""

    run_id: str
    checkpoint_id: str
    step_index: int = 0
    trajectory: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    partial_results: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "active"  # active / completed / expired

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "checkpoint_id": self.checkpoint_id,
            "step_index": self.step_index,
            "trajectory": self.trajectory,
            "plan": self.plan,
            "tool_calls": self.tool_calls,
            "partial_results": self.partial_results,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionSnapshot:
        return cls(
            run_id=data["run_id"],
            checkpoint_id=data["checkpoint_id"],
            step_index=data.get("step_index", 0),
            trajectory=data.get("trajectory", []),
            plan=data.get("plan", []),
            tool_calls=data.get("tool_calls", []),
            partial_results=data.get("partial_results", {}),
            context=data.get("context", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
            status=data.get("status", "active"),
        )

    @classmethod
    def from_json(cls, raw: str) -> ExecutionSnapshot:
        return cls.from_dict(json.loads(raw))
