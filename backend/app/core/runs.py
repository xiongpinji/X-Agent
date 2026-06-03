from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from backend.app.core.contracts import AgentRunRecord, AgentRunResponse, RunContext


class RunStore:
    """JSONL-backed run registry for Phase 0."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._records: dict[str, AgentRunRecord] = {}
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def save(self, context: RunContext, task: str, response: AgentRunResponse, run_view: dict[str, Any] | None = None) -> AgentRunRecord:
        record = AgentRunRecord(
            trace_id=response.trace_id,
            agent_id=response.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            task=task,
            status=response.status,
            answer=response.answer[:4_000],
            iterations=response.iterations,
            memory_hits=response.memory_hits,
            tool_call_count=len(response.tool_calls),
            error=response.error[:2_000] if response.error else None,
            stage=response.snapshot.get("stage", "finalizing"),
            execution_summary={**response.execution_summary, "session_id": response.execution_summary.get("session_id")},
            plan=response.plan,
            tool_calls=response.tool_calls,
            run_view=run_view or response.snapshot.get("run_view", {}) if isinstance(response.snapshot, dict) else {},
            snapshot=response.snapshot,
        )
        with self._lock:
            self._records[record.trace_id] = record
            self._append_to_disk(record)
        return record

    def list(self, limit: int = 20) -> list[AgentRunRecord]:
        records = list(self._records.values())
        records.sort(key=lambda record: record.completed_at, reverse=True)
        return records[:limit]

    def get(self, trace_id: str) -> AgentRunRecord | None:
        return self._records.get(trace_id)

    def continue_from(self, trace_id: str, response: AgentRunResponse) -> AgentRunRecord | None:
        previous = self.get(trace_id)
        if previous is None:
            return None
        resumed = AgentRunRecord(
            trace_id=response.trace_id,
            agent_id=response.agent_id,
            tenant_id=previous.tenant_id,
            user_id=previous.user_id,
            task=previous.task,
            status=response.status,
            answer=response.answer[:4_000],
            iterations=response.iterations,
            memory_hits=response.memory_hits,
            tool_call_count=len(response.tool_calls),
            error=response.error[:2_000] if response.error else None,
            stage=response.snapshot.get("stage", previous.stage),
            execution_summary={**previous.execution_summary, **response.execution_summary, "resumed_from": trace_id, "previous_stage": previous.status, "previous_tool_call_count": previous.tool_call_count},
            plan=response.plan or previous.plan,
            tool_calls=response.tool_calls or previous.tool_calls,
            run_view=response.snapshot.get("run_view", previous.run_view) if isinstance(response.snapshot, dict) else previous.run_view,
            snapshot=response.snapshot,
        )
        with self._lock:
            self._records[resumed.trace_id] = resumed
            self._append_to_disk(resumed)
        return resumed

    def snapshot_for(self, trace_id: str) -> dict[str, object] | None:
        record = self.get(trace_id)
        if record is None:
            return None
        return {
            "trace_id": record.trace_id,
            "task": record.task,
            "stage": record.stage,
            "status": record.status.value if hasattr(record.status, "value") else str(record.status),
            "iterations": record.iterations,
            "memory_hits": record.memory_hits,
            "tool_call_count": record.tool_call_count,
            "execution_summary": record.execution_summary,
            "plan_count": len(record.plan),
            "tool_history_count": len(record.tool_calls),
            "run_view": record.run_view,
        }

    def count(self) -> int:
        return len(self._records)

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = AgentRunRecord.model_validate(json.loads(line))
                self._records[record.trace_id] = record

    def _append_to_disk(self, record: AgentRunRecord) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n")
