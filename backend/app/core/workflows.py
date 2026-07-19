from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.approvals import ApprovalStore
from backend.app.core.contracts import RiskLevel, RunContext, TraceEvent, TaskFrame, PlanFrame, ExecutionFrame, RecoveryFrame
from backend.app.core.audit import AuditStore
from backend.app.core.tracing import TraceStore
from backend.app.services.observability.langfuse_client import langfuse_client

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop

logger = logging.getLogger(__name__)


class WorkflowNodeType(StrEnum):
    INPUT = "input"
    TRANSFORM = "transform"
    TOOL = "tool"
    AGENT = "agent"
    CONDITION = "condition"
    WAIT = "wait"
    APPROVAL = "approval"
    OUTPUT = "output"


class WorkflowRunStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    PAUSED = "paused"
    NEEDS_APPROVAL = "needs_approval"


class WorkflowScheduleStatus(StrEnum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    CANCELED = "canceled"
    FAILED = "failed"


class WorkflowNode(BaseModel):
    id: str
    type: WorkflowNodeType
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: str | None = None


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkflowNodeResult(BaseModel):
    node_id: str
    node_type: WorkflowNodeType
    status: WorkflowRunStatus
    attempts: int = 1
    output: Any = None
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_trace_id: str | None = None
    compensated: bool = False
    compensation_output: Any = None
    compensation_error: str | None = None


class WorkflowRunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    workflow_name: str
    status: WorkflowRunStatus
    tenant_id: str = "default"
    user_id: str = "anonymous"
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    node_results: list[WorkflowNodeResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    pending_approval_id: str | None = None
    pending_node_id: str | None = None
    resume_cursor: int = 0
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowScheduleRecord(BaseModel):
    schedule_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    user_id: str = "anonymous"
    permission_scope: list[str] = Field(default_factory=list)
    run_at: datetime
    status: WorkflowScheduleStatus = WorkflowScheduleStatus.PENDING
    run_id: str | None = None
    locked_by: str | None = None
    locked_until: datetime | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowSummary(BaseModel):
    workflow_id: str
    name: str
    description: str = ""
    node_count: int
    edge_count: int
    latest_run_id: str | None = None
    latest_run_status: WorkflowRunStatus | None = None
    created_at: datetime
    updated_at: datetime
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge] = Field(default_factory=list)


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[WorkflowNode] | None = None
    edges: list[WorkflowEdge] | None = None


class WorkflowRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    user_id: str = "anonymous"
    async_run: bool = False


class WorkflowScheduleRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "default"
    user_id: str = "anonymous"
    run_at: datetime | None = None
    delay_seconds: int = Field(default=0, ge=0)


class WorkflowChatCreateRequest(BaseModel):
    request: str


class WorkflowRunStatusResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    status: WorkflowRunStatus
    latest_run_id: str | None = None
    latest_run_status: WorkflowRunStatus | None = None
    run_count: int = 0
    updated_at: datetime
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowControlResponse(BaseModel):
    run_id: str
    workflow_id: str
    status: WorkflowRunStatus
    changed: bool
    message: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunTimelineEvent(BaseModel):
    timestamp: datetime
    kind: str
    node_id: str | None = None
    node_type: WorkflowNodeType | None = None
    status: WorkflowRunStatus | None = None
    detail: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunDetailResponse(BaseModel):
    run: WorkflowRunRecord
    timeline: list[WorkflowRunTimelineEvent] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionError(RuntimeError):
    pass


class WorkflowNodeExecutionError(WorkflowExecutionError):
    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class WorkflowApprovalRequired(WorkflowExecutionError):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"Workflow approval required: {approval_id}")
        self.approval_id = approval_id


class WorkflowRepository:
    def __init__(
        self,
        definition_path: str | Path | None = None,
        run_path: str | Path | None = None,
    ) -> None:
        self._definition_path = Path(definition_path) if definition_path else None
        self._run_path = Path(run_path) if run_path else None
        self._definitions: dict[str, WorkflowDefinition] = {}
        self._runs: dict[str, WorkflowRunRecord] = {}
        self._lock = RLock()
        # Disk writes are serialized by a SEPARATE lock so the in-memory state
        # lock (self._lock) is never held across blocking file I/O. A monotonic
        # version lets a later write skip a stale snapshot it would clobber.
        self._io_lock = RLock()
        self._def_version = 0
        self._def_version_persisted = 0
        if self._definition_path:
            self._load_definitions()
        if self._run_path:
            self._load_runs()

    def upsert_definition(
        self,
        workflow: WorkflowCreateRequest | WorkflowUpdateRequest | WorkflowDefinition,
        workflow_id: str | None = None,
    ) -> WorkflowDefinition:
        if isinstance(workflow, WorkflowDefinition):
            definition = workflow.model_copy()
            definition.updated_at = datetime.now(UTC)
        else:
            existing = self._definitions.get(workflow_id or "")
            if existing is None and workflow_id is not None:
                raise KeyError(workflow_id)
            base = existing.model_copy() if existing else WorkflowDefinition(
                id=workflow_id or str(uuid4()),
                name=workflow.name or "workflow",
                description=workflow.description or "",
                nodes=workflow.nodes or [],
                edges=workflow.edges or [],
            )
            if workflow.name is not None:
                base.name = workflow.name
            if workflow.description is not None:
                base.description = workflow.description
            if workflow.nodes is not None:
                base.nodes = workflow.nodes
            if workflow.edges is not None:
                base.edges = workflow.edges
            base.updated_at = datetime.now(UTC)
            definition = base

        self._validate_definition(definition)
        with self._lock:
            self._definitions[definition.id] = definition
            self._def_version += 1
            version = self._def_version
            snapshot = self._snapshot_definitions_locked()
        # Disk write happens OUTSIDE self._lock: threads no longer queue on
        # file I/O while holding the in-memory state lock.
        self._persist_snapshot(version, snapshot)
        return definition

    def list_definitions(self) -> list[WorkflowDefinition]:
        definitions = list(self._definitions.values())
        definitions.sort(key=lambda item: item.updated_at, reverse=True)
        return definitions

    def get_definition(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._definitions.get(workflow_id)

    def delete_definition(self, workflow_id: str) -> bool:
        with self._lock:
            deleted = self._definitions.pop(workflow_id, None) is not None
            if not deleted:
                return False
            self._def_version += 1
            version = self._def_version
            snapshot = self._snapshot_definitions_locked()
        self._persist_snapshot(version, snapshot)
        return True

    def record_run(self, run: WorkflowRunRecord) -> WorkflowRunRecord:
        with self._lock:
            self._runs[run.run_id] = run
            self._append_run(run)
        return run

    def run_snapshot(self, workflow_id: str | None = None) -> dict[str, Any]:
        runs = self.list_runs(workflow_id=workflow_id, limit=1_000)
        return {
            "run_count": len(runs),
            "latest_run_id": runs[0].run_id if runs else None,
            "latest_run_status": runs[0].status if runs else None,
            "workflow_id": workflow_id,
        }

    def update_run_status(
        self,
        run_id: str,
        status: WorkflowRunStatus,
        *,
        error: str | None = None,
        resume_cursor: int | None = None,
    ) -> WorkflowRunRecord | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            update_payload = {
                "status": status,
                "completed_at": datetime.now(UTC),
                "error": error if error is not None else run.error,
            }
            if resume_cursor is not None:
                update_payload["resume_cursor"] = resume_cursor
            updated = run.model_copy(update=update_payload)
            self._runs[run_id] = updated
            self._append_run(updated)
            return updated

    def list_runs(self, workflow_id: str | None = None, limit: int = 20) -> list[WorkflowRunRecord]:
        runs = [
            record
            for record in self._runs.values()
            if workflow_id is None or record.workflow_id == workflow_id
        ]
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> WorkflowRunRecord | None:
        return self._runs.get(run_id)

    def definition_count(self) -> int:
        return len(self._definitions)

    def run_count(self) -> int:
        return len(self._runs)

    def count_runs(self, workflow_id: str | None = None) -> int:
        if workflow_id is None:
            return len(self._runs)
        return sum(1 for run in self._runs.values() if run.workflow_id == workflow_id)

    def latest_run_for(self, workflow_id: str) -> WorkflowRunRecord | None:
        runs = self.list_runs(workflow_id=workflow_id, limit=1)
        return runs[0] if runs else None

    def summary_for(self, workflow_id: str) -> WorkflowSummary:
        definition = self._definitions[workflow_id]
        latest_run = self.latest_run_for(workflow_id)
        return WorkflowSummary(
            workflow_id=definition.id,
            name=definition.name,
            description=definition.description,
            node_count=len(definition.nodes),
            edge_count=len(definition.edges),
            latest_run_id=latest_run.run_id if latest_run else None,
            latest_run_status=latest_run.status if latest_run else None,
            created_at=definition.created_at,
            updated_at=definition.updated_at,
            snapshot=self.run_snapshot(workflow_id),
        )

    def run_snapshot(self, workflow_id: str) -> dict[str, Any]:
        runs = self.list_runs(workflow_id=workflow_id, limit=1)
        latest_run = runs[0] if runs else None
        return {
            "workflow_id": workflow_id,
            "run_count": self.count_runs(workflow_id),
            "latest_run_id": latest_run.run_id if latest_run else None,
            "latest_run_status": latest_run.status if latest_run else None,
        }

    def _validate_definition(self, definition: WorkflowDefinition) -> None:
        node_ids = [node.id for node in definition.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise WorkflowExecutionError("Workflow node ids must be unique.")
        known_nodes = set(node_ids)
        for edge in definition.edges:
            if edge.source not in known_nodes or edge.target not in known_nodes:
                raise WorkflowExecutionError(
                    f"Workflow edge references unknown node: {edge.source} -> {edge.target}"
                )
        self._topological_order(definition)

    @staticmethod
    def _topological_order(definition: WorkflowDefinition) -> list[str]:
        order_hint = {node.id: index for index, node in enumerate(definition.nodes)}
        adjacency: dict[str, set[str]] = {node.id: set() for node in definition.nodes}
        indegree: dict[str, int] = {node.id: 0 for node in definition.nodes}
        for edge in definition.edges:
            if edge.target not in adjacency[edge.source]:
                adjacency[edge.source].add(edge.target)
                indegree[edge.target] += 1
        queue = [node_id for node_id, degree in indegree.items() if degree == 0]
        queue.sort(key=lambda node_id: order_hint[node_id])
        ordered: list[str] = []
        while queue:
            node_id = queue.pop(0)
            ordered.append(node_id)
            for target in sorted(adjacency[node_id], key=lambda item: order_hint[item]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
                    queue.sort(key=lambda item: order_hint[item])
        if len(ordered) != len(definition.nodes):
            raise WorkflowExecutionError("Workflow contains a cycle.")
        return ordered

    def _load_definitions(self) -> None:
        if self._definition_path is None or not self._definition_path.exists():
            return
        try:
            with self._definition_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, ValueError):
            # File is empty or corrupt — treat as no definitions.
            logger.warning(
                "Workflow definitions file is empty or corrupt: %s",
                self._definition_path,
            )
            return
        for item in raw:
            definition = WorkflowDefinition.model_validate(item)
            self._definitions[definition.id] = definition

    def _snapshot_definitions_locked(self) -> list[dict]:
        """Serialize all definitions to plain dicts. Call while holding self._lock."""
        definitions = sorted(
            self._definitions.values(),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        return [definition.model_dump(mode="json") for definition in definitions]

    def _persist_snapshot(self, version: int, payload: list[dict]) -> None:
        """Atomically write a definitions snapshot to disk.

        Serialized by self._io_lock (NOT self._lock), so concurrent writers do
        not starve on the in-memory state lock. A stale snapshot (older version
        than what was last persisted) is skipped so it cannot clobber newer data.
        Writes to a temp file + os.replace for atomicity (no half-written JSON).
        """
        if self._definition_path is None:
            return
        with self._io_lock:
            if version < self._def_version_persisted:
                return
            self._definition_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self._definition_path.parent),
                prefix=self._definition_path.name + ".",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                os.replace(tmp_name, self._definition_path)
                self._def_version_persisted = version
            except BaseException:
                # Clean up the temp file on any failure; don't leave litter.
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

    def _load_runs(self) -> None:
        if self._run_path is None or not self._run_path.exists():
            return
        with self._run_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                run = WorkflowRunRecord.model_validate(json.loads(line))
                self._runs[run.run_id] = run

    def _append_run(self, run: WorkflowRunRecord) -> None:
        if self._run_path is None:
            return
        self._run_path.parent.mkdir(parents=True, exist_ok=True)
        with self._run_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(run.model_dump(mode="json"), ensure_ascii=False) + "\n")


class WorkflowScheduleStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._records: dict[str, WorkflowScheduleRecord] = {}
        self._lock = RLock()
        if self._storage_path:
            self._load_from_disk()

    def create(
        self,
        *,
        workflow_id: str,
        inputs: dict[str, Any],
        tenant_id: str,
        user_id: str,
        permission_scope: list[str],
        run_at: datetime,
    ) -> WorkflowScheduleRecord:
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=UTC)
        record = WorkflowScheduleRecord(
            workflow_id=workflow_id,
            inputs=inputs,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=permission_scope,
            run_at=run_at,
            snapshot={
                "workflow_id": workflow_id,
                "input_keys": sorted(inputs.keys()),
                "run_at": run_at.isoformat(),
            },
        )
        with self._lock:
            self._records[record.schedule_id] = record
            self._persist()
        return record

    def list(
        self,
        *,
        status: WorkflowScheduleStatus | None = None,
        workflow_id: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowScheduleRecord]:
        records = [
            record
            for record in self._records.values()
            if (status is None or record.status == status)
            and (workflow_id is None or record.workflow_id == workflow_id)
        ]
        records.sort(key=lambda record: record.run_at, reverse=True)
        return records[:limit]

    def due(
        self,
        *,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[WorkflowScheduleRecord]:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return [
            record
            for record in self.list(status=WorkflowScheduleStatus.PENDING, limit=10_000)
            if record.run_at <= now
        ][:limit]

    def acquire_due(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[WorkflowScheduleRecord]:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        lease_until = now + timedelta(seconds=lease_seconds)
        acquired: list[WorkflowScheduleRecord] = []
        with self._lock:
            for record in self.due(now=now, limit=10_000):
                if len(acquired) >= limit:
                    break
                if record.locked_until is not None and record.locked_until > now:
                    continue
                updated = record.model_copy(
                    update={
                        "locked_by": worker_id,
                        "locked_until": lease_until,
                        "updated_at": now,
                    }
                )
                self._records[record.schedule_id] = updated
                acquired.append(updated)
            if acquired:
                self._persist()
        return acquired

    def get(self, schedule_id: str) -> WorkflowScheduleRecord | None:
        return self._records.get(schedule_id)

    def mark(
        self,
        schedule_id: str,
        status: WorkflowScheduleStatus,
        *,
        run_id: str | None = None,
        error: str | None = None,
    ) -> WorkflowScheduleRecord | None:
        with self._lock:
            record = self._records.get(schedule_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={
                    "status": status,
                    "run_id": run_id if run_id is not None else record.run_id,
                    "locked_by": None,
                    "locked_until": None,
                    "error": error,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._records[schedule_id] = updated
            self._persist()
            return updated

    def count(self, status: WorkflowScheduleStatus | None = None) -> int:
        if status is None:
            return len(self._records)
        return sum(1 for record in self._records.values() if record.status == status)

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload:
            record = WorkflowScheduleRecord.model_validate(item)
            self._records[record.schedule_id] = record

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self.list(limit=10_000)]
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class WorkflowExecutor:
    def __init__(
        self,
        *,
        agent: AgentLoop,
        repository: WorkflowRepository,
        tracer: TraceStore | None = None,
        approval_store: ApprovalStore | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self.agent = agent
        self.repository = repository
        self.tracer = tracer
        self.approval_store = approval_store
        self.audit_store = audit_store
        self._paused: set[str] = set()

    async def execute(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        permission_scope: list[str] | None = None,
        run_id: str | None = None,
        pause_checkpoint: Callable[[str], Awaitable[None]] | None = None,
        approved_approvals: dict[str, str] | None = None,
    ) -> WorkflowRunRecord:
        definition = self.repository.get_definition(workflow_id)
        if definition is None:
            raise WorkflowExecutionError(f"Workflow not found: {workflow_id}")

        run_id = run_id or str(uuid4())
        run_context = RunContext(
            trace_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=permission_scope or RunContext().permission_scope,
        )
        inputs = inputs or {}
        self.repository.record_run(
            WorkflowRunRecord(
                run_id=run_id,
                workflow_id=definition.id,
                workflow_name=definition.name,
                status=WorkflowRunStatus.RUNNING,
                tenant_id=tenant_id,
                user_id=user_id,
                inputs=inputs,
                started_at=run_context.created_at,
                completed_at=run_context.created_at,
                resume_cursor=0,
                snapshot=self._build_snapshot(definition, inputs, state={"inputs": inputs}, status=WorkflowRunStatus.RUNNING, resume_cursor=0),
            )
        )
        self._record_event(run_context, "workflow.started", workflow_id=workflow_id)

        state: dict[str, Any] = {"inputs": inputs, "node_results": []}
        ordered_nodes = self.repository._topological_order(definition)
        node_map = {node.id: node for node in definition.nodes}
        outgoing_edges: dict[str, list[WorkflowEdge]] = {node.id: [] for node in definition.nodes}
        for edge in definition.edges:
            outgoing_edges.setdefault(edge.source, []).append(edge)
        node_results: list[WorkflowNodeResult] = []
        outputs: dict[str, Any] = {}

        try:
            for index, node_id in enumerate(ordered_nodes):
                if run_id in self._paused:
                    self.repository.update_run_status(run_id, WorkflowRunStatus.PAUSED, resume_cursor=index)
                    await self.pause_checkpoint(run_id)
                    if run_id not in self._paused:
                        self.repository.update_run_status(run_id, WorkflowRunStatus.RUNNING, resume_cursor=index)
                    else:
                        continue
                record_state = self.repository.get_run(run_id)
                if record_state is not None and index < record_state.resume_cursor:
                    continue
                if pause_checkpoint is not None:
                    await pause_checkpoint(run_id)
                if run_id in self._paused:
                    continue
                node = node_map[node_id]
                incoming_edges = [edge for edge in definition.edges if edge.target == node.id]
                if incoming_edges and not any(
                    self._evaluate_edge_condition(edge, state, inputs) for edge in incoming_edges
                ):
                    continue
                matched_edges = [edge for edge in incoming_edges if self._evaluate_edge_condition(edge, state, inputs)]
                state["active_node_id"] = node.id
                state["active_edge_ids"] = [edge.source for edge in matched_edges]
                state["recovery_hint"] = self._workflow_recovery_hint(state, error=None)
                self._record_event(
                    run_context,
                    "workflow.node.started",
                    node_id=node.id,
                    node_type=node.type.value,
                )
                started_at = datetime.now(UTC)
                attempts = 1
                try:
                    output, attempts = await self._execute_node_with_policy(
                        run_context,
                        node,
                        definition,
                        state,
                        inputs,
                        approved_approvals or {},
                    )
                    state[node.id] = output
                    state["recovery_hint"] = self._workflow_recovery_hint(state, error=None)
                    if node.type == WorkflowNodeType.OUTPUT:
                        outputs[node.id] = output
                    node_result = WorkflowNodeResult(
                        node_id=node.id,
                        node_type=node.type,
                        status=WorkflowRunStatus.COMPLETED,
                        attempts=attempts,
                        output=output,
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        agent_trace_id=output.get("trace_id") if isinstance(output, dict) else None,
                    )
                    node_results.append(node_result)
                    state["node_results"] = node_results
                    self._record_event(
                        run_context,
                        "workflow.node.completed",
                        node_id=node.id,
                        node_type=node.type.value,
                    )
                except WorkflowApprovalRequired as exc:
                    node_result = WorkflowNodeResult(
                        node_id=node.id,
                        node_type=node.type,
                        status=WorkflowRunStatus.NEEDS_APPROVAL,
                        output={"approval_id": exc.approval_id},
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                    )
                    node_results.append(node_result)
                    state["node_results"] = node_results
                    state["pending_approval_id"] = exc.approval_id
                    state["pending_node_id"] = node.id
                    self._record_event(
                        run_context,
                        "workflow.node.needs_approval",
                        node_id=node.id,
                        node_type=node.type.value,
                        approval_id=exc.approval_id,
                    )
                    raise
                except Exception as exc:  # noqa: BLE001 - surfaced as workflow failure
                    if isinstance(exc, WorkflowNodeExecutionError):
                        attempts = exc.attempts
                    recovery_hint = self._workflow_recovery_hint(state, error=str(exc))
                    compensation_output, compensation_error = await self._execute_compensation(
                        run_context,
                        node,
                        state,
                        inputs,
                        recovery_hint=recovery_hint,
                    )
                    node_result = WorkflowNodeResult(
                        node_id=node.id,
                        node_type=node.type,
                        status=WorkflowRunStatus.FAILED,
                        attempts=attempts,
                        error=str(exc),
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        compensated=(
                            compensation_output is not None or compensation_error is not None
                        ),
                        compensation_output=compensation_output,
                        compensation_error=compensation_error,
                    )
                    node_results.append(node_result)
                    state["node_results"] = node_results
                    state["last_failure"] = {
                        "node_id": node.id,
                        "node_type": node.type.value,
                        "error": str(exc),
                        "recovery_hint": recovery_hint,
                    }
                    self._record_event(
                        run_context,
                        "workflow.node.failed",
                        node_id=node.id,
                        node_type=node.type.value,
                        error=str(exc),
                    )
                    await self._capture_node_failure(
                        run_context,
                        definition,
                        node,
                        input_state=inputs,
                        state=state,
                        error=str(exc),
                        compensation_output=compensation_output,
                        compensation_error=compensation_error,
                    )
                    raise
            record = WorkflowRunRecord(
                run_id=run_id,
                workflow_id=definition.id,
                workflow_name=definition.name,
                status=WorkflowRunStatus.COMPLETED,
                tenant_id=tenant_id,
                user_id=user_id,
                inputs=inputs,
                outputs=outputs or self._collect_outputs(state, definition),
                node_results=node_results,
                started_at=run_context.created_at,
                completed_at=datetime.now(UTC),
                resume_cursor=len(ordered_nodes),
                snapshot=self._build_snapshot(definition, inputs, state, node_results, status=WorkflowRunStatus.COMPLETED, resume_cursor=len(ordered_nodes)),
            )
            self.repository.record_run(record)
            self._record_event(
                run_context,
                "workflow.completed",
                workflow_id=workflow_id,
                run_id=record.run_id,
            )
            self._record_audit(
                action="workflow.run.completed",
                run=record,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                user_id=user_id,
                details={"status": record.status.value, "node_count": len(node_results)},
            )
            return record
        except asyncio.CancelledError:
            record = WorkflowRunRecord(
                run_id=run_id,
                workflow_id=definition.id,
                workflow_name=definition.name,
                status=WorkflowRunStatus.CANCELED,
                tenant_id=tenant_id,
                user_id=user_id,
                inputs=inputs,
                outputs=outputs or self._collect_outputs(state, definition),
                node_results=node_results,
                started_at=run_context.created_at,
                completed_at=datetime.now(UTC),
                error="Workflow run canceled.",
                resume_cursor=len(node_results),
                snapshot=self._build_snapshot(definition, inputs, state, node_results, status=WorkflowRunStatus.CANCELED, resume_cursor=len(node_results), error="Workflow run canceled."),
            )
            self.repository.record_run(record)
            self._record_event(
                run_context,
                "workflow.canceled",
                workflow_id=workflow_id,
                run_id=record.run_id,
            )
            self._record_audit(
                action="workflow.run.canceled",
                run=record,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                user_id=user_id,
                details={"status": record.status.value},
            )
            raise
        except WorkflowApprovalRequired as exc:
            record = WorkflowRunRecord(
                run_id=run_id,
                workflow_id=definition.id,
                workflow_name=definition.name,
                status=WorkflowRunStatus.NEEDS_APPROVAL,
                tenant_id=tenant_id,
                user_id=user_id,
                inputs=inputs,
                outputs={"approval_id": exc.approval_id},
                node_results=node_results,
                started_at=run_context.created_at,
                completed_at=datetime.now(UTC),
                error=str(exc),
                pending_approval_id=exc.approval_id,
                pending_node_id=node_results[-1].node_id if node_results else None,
                resume_cursor=len(node_results),
                snapshot=self._build_snapshot(definition, inputs, state, node_results),
            )
            self.repository.record_run(record)
            self._record_event(
                run_context,
                "workflow.needs_approval",
                workflow_id=workflow_id,
                run_id=record.run_id,
                approval_id=exc.approval_id,
            )
            self._record_audit(
                action="workflow.run.needs_approval",
                run=record,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                user_id=user_id,
                details={"status": record.status.value, "approval_id": exc.approval_id},
            )
            return record
        except Exception as exc:  # noqa: BLE001 - normalized workflow error contract
            record = WorkflowRunRecord(
                run_id=run_id,
                workflow_id=definition.id,
                workflow_name=definition.name,
                status=WorkflowRunStatus.FAILED,
                tenant_id=tenant_id,
                user_id=user_id,
                inputs=inputs,
                outputs=outputs or self._collect_outputs(state, definition),
                node_results=node_results,
                started_at=run_context.created_at,
                completed_at=datetime.now(UTC),
                error=str(exc),
                resume_cursor=len(node_results),
                snapshot=self._build_snapshot(definition, inputs, state, node_results),
            )
            self.repository.record_run(record)
            self._record_event(
                run_context,
                "workflow.failed",
                workflow_id=workflow_id,
                run_id=record.run_id,
                error=str(exc),
            )
            self._record_audit(
                action="workflow.run.failed",
                run=record,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                user_id=user_id,
                details={"status": record.status.value, "error": str(exc)},
            )
            return record

    async def _execute_node_with_policy(
        self,
        run_context: RunContext,
        node: WorkflowNode,
        definition: WorkflowDefinition,
        state: dict[str, Any],
        inputs: dict[str, Any],
        approved_approvals: dict[str, str],
    ) -> tuple[Any, int]:
        max_retries = int(node.config.get("max_retries", 0))
        retry_delay_ms = int(node.config.get("retry_delay_ms", 0))
        timeout_ms = int(node.config.get("timeout_ms", 0))
        max_attempts = max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                coroutine = self._execute_node(
                    run_context,
                    node,
                    definition,
                    state,
                    inputs,
                    approved_approvals,
                )
                if timeout_ms > 0:
                    return await asyncio.wait_for(coroutine, timeout_ms / 1000), attempt
                return await coroutine, attempt
            except asyncio.CancelledError:
                raise
            except WorkflowApprovalRequired:
                raise
            except asyncio.TimeoutError as exc:
                last_error = exc
                self._record_event(
                    run_context,
                    "workflow.node.timeout",
                    node_id=node.id,
                    node_type=node.type.value,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    timeout_ms=timeout_ms,
                    error=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 - retries normalize transient node failures
                last_error = exc
                self._record_event(
                    run_context,
                    "workflow.node.retry",
                    node_id=node.id,
                    node_type=node.type.value,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    error=str(exc),
                )
            if attempt >= max_attempts:
                break
            if retry_delay_ms > 0:
                await asyncio.sleep(retry_delay_ms / 1000)

        raise WorkflowNodeExecutionError(
            str(last_error) if last_error else "Node execution failed.",
            max_attempts,
        )

    async def _execute_node(
        self,
        run_context: RunContext,
        node: WorkflowNode,
        definition: WorkflowDefinition,
        state: dict[str, Any],
        inputs: dict[str, Any],
        approved_approvals: dict[str, str],
    ) -> Any:
        if node.type == WorkflowNodeType.INPUT:
            key = node.config.get("key")
            if key:
                return inputs.get(key, node.config.get("default"))
            return inputs

        if node.type == WorkflowNodeType.TRANSFORM:
            template = str(node.config.get("template", ""))
            return self._render_value(template, state, inputs)

        if node.type == WorkflowNodeType.TOOL:
            tool_name = str(node.config.get("tool_name", ""))
            arguments = self._render_value(node.config.get("arguments", {}), state, inputs)
            node_context = self._derive_node_context(run_context, node)
            record = await self.agent.tools.execute(node_context, tool_name, arguments)
            return record.model_dump(mode="json")

        if node.type == WorkflowNodeType.AGENT:
            task = str(self._render_value(node.config.get("task", ""), state, inputs))
            extra_context = self._render_value(node.config.get("context", {}), state, inputs)
            node_context = self._derive_node_context(run_context, node)
            node_scopes = self._permission_scope_for_node(node)
            allowed = {
                s for s in node_scopes
                if s in run_context.permission_scope
                or f"{str(s).split(':', 1)[0]}:*" in run_context.permission_scope
            }
            node_context.permission_scope = list({*node_context.permission_scope, *allowed})
            node_results = state.get("node_results", [])
            previous_node = node_results[-1].model_dump(mode="json") if node_results and hasattr(node_results[-1], "model_dump") else node_results[-1] if node_results else None
            enriched_context = self._enrich_agent_context(node_context, node, definition, state, inputs, extra_context)
            task_frame = TaskFrame(goal=task or node.id, description=str(node.config.get("description", task or node.id)), risk_level=node_context.risk_level, requires_approval=node.type == WorkflowNodeType.APPROVAL, metadata={"workflow_id": definition.id, "workflow_name": definition.name, "workflow_node_id": node.id, "workflow_node_type": node.type.value, "extra_context": extra_context})
            execution_frame = ExecutionFrame(trace_id=node_context.trace_id, agent_id=node_context.agent_id, tenant_id=node_context.tenant_id, user_id=node_context.user_id, request_id=node_context.request_id, task=task_frame, plan=PlanFrame(goal=task_frame.goal, status="draft"), recovery_hint=RecoveryFrame(branch="continue"))
            execution_frame.workflow_state = {"workflow_id": definition.id, "workflow_name": definition.name, "workflow_node_id": node.id, "workflow_node_type": node.type.value, "workflow_status": state.get("workflow_status", "running"), "resume_cursor": state.get("resume_cursor", 0)}
            execution_frame.approval_state = {"approved_approvals": approved_approvals, "pending_approval_id": node.config.get("approval_id") if node.type == WorkflowNodeType.APPROVAL else None}
            execution_frame.browser_state = {"browser_session_id": extra_context.get("browser_session_id"), "browser_url": extra_context.get("browser_url")}
            execution_frame.desktop_state = {"desktop_session_id": extra_context.get("desktop_session_id"), "desktop_provider": extra_context.get("desktop_provider")}
            enriched_context["execution_frame"] = execution_frame.model_dump(mode="json")
            enriched_context["workflow_node_id"] = node.id
            enriched_context["workflow_node_type"] = node.type.value
            enriched_context["workflow_status"] = state.get("workflow_status", "running")
            enriched_context["resume_cursor"] = state.get("resume_cursor", 0)
            enriched_context["node_results"] = [result.model_dump(mode="json") for result in node_results if hasattr(result, "model_dump")]
            enriched_context["previous_node"] = previous_node
            enriched_context["approved_approvals"] = approved_approvals
            response = await self.agent.run(node_context, task, enriched_context)
            agent_summary = {
                "trace_id": response.trace_id,
                "status": response.status,
                "iterations": response.iterations,
                "current_subtask_index": response.execution_summary.get("current_subtask_index", 0),
                "subtask_status": response.execution_summary.get("subtask_status", {}),
                "subtasks": response.execution_summary.get("subtasks", []),
                "tool_count": len(response.tool_calls),
                "plan_steps": len(response.plan),
                "execution_summary": response.execution_summary,
                "snapshot": response.snapshot,
                "recovery_hint": response.execution_summary.get("branch"),
            }
            state["last_agent_summary"] = agent_summary
            state["last_agent_trace_id"] = response.trace_id
            state["last_agent_execution_summary"] = response.execution_summary
            state["last_agent_snapshot"] = response.snapshot
            state["last_agent_recovery_branch"] = response.execution_summary.get("branch")
            recovery_plan = response.execution_summary.get("recovery_plan") if isinstance(response.execution_summary, dict) else None
            if isinstance(recovery_plan, dict):
                state["recovery_hint"] = recovery_plan
            return {
                **response.model_dump(mode="json"),
                "workflow_node_id": node.id,
                "workflow_node_type": node.type.value,
                "workflow_id": definition.id,
                "workflow_name": definition.name,
                "agent_summary": agent_summary,
                "execution_summary": response.execution_summary,
                "recovery_hint": response.execution_summary.get("branch"),
                "recovery_plan": recovery_plan,
                "next_actions": response.execution_summary.get("next_actions", []),
                "retryable_failures": response.execution_summary.get("retryable_failures", 0),
            }

        if node.type == WorkflowNodeType.CONDITION:
            left = self._render_value(node.config.get("left"), state, inputs)
            right = self._render_value(node.config.get("right"), state, inputs)
            operator = str(node.config.get("operator", "equals")).lower()
            agent_summary = state.get("last_agent_summary") if isinstance(state.get("last_agent_summary"), dict) else {}
            execution_summary = state.get("last_agent_execution_summary") if isinstance(state.get("last_agent_execution_summary"), dict) else {}
            recovery_hint = state.get("last_agent_recovery_branch") or (execution_summary.get("branch") if isinstance(execution_summary, dict) else None)
            if left is None and isinstance(agent_summary, dict):
                left = agent_summary.get(str(node.config.get("left_key", "")), left)
            if right is None and isinstance(agent_summary, dict):
                right = agent_summary.get(str(node.config.get("right_key", "")), right)
            if left is None and execution_summary:
                left = execution_summary.get("branch") or execution_summary.get("status") or execution_summary.get("tool_calls") or execution_summary.get("observations") or execution_summary.get("current_subtask_index")
            if right is None and execution_summary:
                right = execution_summary.get("branch") or execution_summary.get("status") or execution_summary.get("tool_calls") or execution_summary.get("observations") or execution_summary.get("current_subtask_index")
            if left is None and recovery_hint:
                left = recovery_hint
            if right is None and recovery_hint:
                right = recovery_hint
            return self._compare(left, right, operator)

        if node.type == WorkflowNodeType.WAIT:
            delay_ms = int(node.config.get("delay_ms", 0))
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)
            return {
                "waited_ms": delay_ms,
                "last_agent_summary": state.get("last_agent_summary"),
                "last_agent_trace_id": state.get("last_agent_trace_id"),
                "recovery_hint": self._workflow_recovery_hint(state, error=None),
            }

        if node.type == WorkflowNodeType.APPROVAL:
            if self.approval_store is None:
                raise WorkflowExecutionError("Approval store is not configured.")
            approved_id = approved_approvals.get(node.id)
            if approved_id:
                approval = self.approval_store.get(approved_id)
                if approval is not None and approval.status.value == "approved" and approval.tenant_id == run_context.tenant_id:
                    return {
                        "approved": True,
                        "approval_id": approved_id,
                        "approval_state": {"approved_approvals": approved_approvals, "approval_id": approved_id, "approval_status": "approved"},
                        "last_agent_summary": state.get("last_agent_summary"),
                        "last_agent_trace_id": state.get("last_agent_trace_id"),
                        "recovery_hint": self._workflow_recovery_hint(state, error=None),
                    }
            risk_level = RiskLevel(str(node.config.get("risk_level", RiskLevel.HIGH.value)))
            recovery_hint = self._workflow_recovery_hint(state, error=None)
            approval = self.approval_store.create_approval(
                context=run_context,
                resource_type="workflow",
                resource_id=str(node.config.get("resource_id", node.id)),
                action=str(node.config.get("action", "workflow.node.approve")),
                risk_level=risk_level,
                reason=str(node.config.get("reason", "Workflow node requires approval.")),
                arguments_preview={
                    "workflow_trace_id": run_context.trace_id,
                    "node_id": node.id,
                    "last_agent_trace_id": state.get("last_agent_trace_id"),
                    "recovery_hint": recovery_hint,
                },
                arguments={
                    "workflow_trace_id": run_context.trace_id,
                    "node_id": node.id,
                    "last_agent_trace_id": state.get("last_agent_trace_id"),
                    "recovery_hint": recovery_hint,
                },
            )
            raise WorkflowApprovalRequired(approval.id)

        if node.type == WorkflowNodeType.OUTPUT:
            source = node.config.get("from") or node.config.get("source")
            if source:
                result = state.get(str(source))
            else:
                result = self._render_value(node.config.get("value", state), state, inputs)
            if isinstance(result, dict):
                result.setdefault("last_agent_summary", state.get("last_agent_summary"))
                result.setdefault("last_agent_trace_id", state.get("last_agent_trace_id"))
                result.setdefault("recovery_hint", self._workflow_recovery_hint(state, error=None))
            return result

        return self._render_value(node.config, state, inputs)

    async def _execute_compensation(
        self,
        run_context: RunContext,
        node: WorkflowNode,
        state: dict[str, Any],
        inputs: dict[str, Any],
        *,
        recovery_hint: dict[str, Any] | None = None,
    ) -> tuple[Any, str | None]:
        config = node.config.get("on_failure")
        if not isinstance(config, dict):
            config = {}
        try:
            hint = recovery_hint or self._workflow_recovery_hint(state, error=None)
            compensation_type = str(config.get("type") or self._default_compensation_type(node, hint)).lower()
            if compensation_type == "transform":
                return self._render_value(config.get("template", self._default_compensation_template(node, hint)), state, inputs), None
            if compensation_type == "wait":
                delay_ms = int(config.get("delay_ms", self._default_compensation_delay(node, hint)))
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000)
                return {"waited_ms": delay_ms, "recovery_hint": hint}, None
            if compensation_type == "tool":
                tool_name = str(config.get("tool_name") or self._default_compensation_tool(node, hint) or "")
                if not tool_name:
                    raise WorkflowExecutionError("No compensation tool configured.")
                arguments = self._render_value(config.get("arguments", self._default_compensation_arguments(node, hint)), state, inputs)
                if isinstance(arguments, dict):
                    arguments.setdefault("recovery_hint", hint)
                    arguments.setdefault("workflow_node_id", node.id)
                record = await self.agent.tools.execute(run_context, tool_name, arguments)
                return record.model_dump(mode="json"), None
            raise WorkflowExecutionError(f"Unsupported compensation type: {compensation_type}")
        except Exception as exc:  # noqa: BLE001 - compensation failure is attached to node result
            return None, str(exc)

    def _evaluate_edge_condition(self, edge: WorkflowEdge, state: dict[str, Any], inputs: dict[str, Any]) -> bool:
        if edge.condition is None:
            return True
        rendered = self._render_value(edge.condition, state, inputs)
        if isinstance(rendered, bool):
            return rendered
        if isinstance(rendered, (int, float)):
            return rendered != 0
        if isinstance(rendered, str):
            normalized = rendered.strip().lower()
            recovery_hint = state.get("recovery_hint") if isinstance(state.get("recovery_hint"), dict) else {}
            if normalized in {
                self._branch_from_recovery_hint(recovery_hint).strip().lower(),
                str(recovery_hint.get("status", "")).strip().lower(),
                str(state.get("active_node_id", "")).strip().lower(),
            }:
                return True
            if normalized in {"true", "yes", "on", "1"}:
                return True
            if normalized in {"false", "no", "off", "0", ""}:
                return False
            return False
        return bool(rendered)

    @staticmethod
    def _compare(left: Any, right: Any, operator: str) -> bool:
        if operator in {"equals", "==", "eq"}:
            return left == right
        if operator in {"not_equals", "!=", "ne"}:
            return left != right
        if operator in {"gt", ">"}:
            return left > right
        if operator in {"gte", ">="}:
            return left >= right
        if operator in {"lt", "<"}:
            return left < right
        if operator in {"lte", "<="}:
            return left <= right
        if operator == "contains":
            return right in left
        if operator == "truthy":
            return bool(left)
        if operator == "falsy":
            return not bool(left)
        raise WorkflowExecutionError(f"Unsupported condition operator: {operator}")

    @staticmethod
    def _workflow_recovery_hint(state: dict[str, Any], error: str | None) -> dict[str, Any]:
        summary = state.get("last_agent_summary") if isinstance(state.get("last_agent_summary"), dict) else {}
        status = WorkflowExecutor._workflow_status_from_hint(summary)
        tool_count = summary.get("tool_count")
        iterations = summary.get("iterations")
        raw_subtask_status = summary.get("subtask_status", "")
        subtask_status = str(raw_subtask_status).lower()
        approval_pending = bool(state.get("pending_approval_id") or summary.get("approval_pending"))
        if isinstance(raw_subtask_status, dict):
            approval_pending = approval_pending or any(
                str(value).lower() in {"pending", "waiting", "blocked"}
                for value in raw_subtask_status.values()
            )
        node_results = state.get("node_results") if isinstance(state.get("node_results"), list) else []
        recent_failures = [
            item
            for item in node_results[-3:]
            if getattr(item, "status", None) and str(getattr(item.status, "value", item.status)).lower() == "failed"
        ]
        branch = WorkflowExecutor._workflow_branch_from_state(
            error=error,
            approval_pending=approval_pending,
            recent_failures=len(recent_failures),
            status=status,
            subtask_status=subtask_status,
            tool_count=tool_count,
            iterations=iterations,
        )
        recovery_plan = WorkflowExecutor._workflow_recovery_plan(
            branch=branch,
            status=status,
            error=error,
            approval_pending=approval_pending,
            recent_failures=len(recent_failures),
            tool_count=tool_count,
            iterations=iterations,
            last_failure=state.get("last_failure"),
            subtask_status=subtask_status or None,
        )
        return {
            "branch": branch,
            "status": status or None,
            "tool_count": tool_count,
            "iterations": iterations,
            "subtask_status": subtask_status or None,
            "approval_pending": approval_pending,
            "recent_failures": len(recent_failures),
            "last_failure": state.get("last_failure"),
            "error": error,
            "recovery_plan": recovery_plan,
        }

    @staticmethod
    def _workflow_branch_from_state(
        *,
        error: str | None,
        approval_pending: bool,
        recent_failures: int,
        status: str,
        subtask_status: str,
        tool_count: Any,
        iterations: Any,
    ) -> str:
        if approval_pending:
            return "approval_wait"
        if error:
            return "compensation"
        if recent_failures:
            return "compensation"
        if status in {"failed", "error", "blocked"} or subtask_status in {"blocked", "waiting", "stuck"}:
            return "compensation"
        if iterations is not None and isinstance(iterations, (int, float)) and iterations >= 3:
            return "reobserve"
        if tool_count is not None and isinstance(tool_count, (int, float)) and tool_count <= 0:
            return "observe"
        return "continue"

    @staticmethod
    def _workflow_recovery_plan(
        *,
        branch: str,
        status: str,
        error: str | None,
        approval_pending: bool,
        recent_failures: int,
        tool_count: Any,
        iterations: Any,
        last_failure: Any,
        subtask_status: str | None,
    ) -> dict[str, Any]:
        next_actions = ["continue"]
        if branch == "approval_wait":
            next_actions = ["await approval", "resume after approval"]
        elif branch == "compensation":
            next_actions = ["inspect failure", "run compensation", "retry with reduced scope"]
        elif branch == "reobserve":
            next_actions = ["re-observe workflow state", "reduce redundant retries"]
        elif branch == "observe":
            next_actions = ["observe current context", "collect missing evidence"]
        if approval_pending:
            next_actions.insert(0, "surface approval boundary")
        if recent_failures:
            next_actions.append(f"review {recent_failures} recent failures")
        if isinstance(tool_count, (int, float)) and tool_count <= 0:
            next_actions.append("select a tool before continuing")
        if isinstance(iterations, (int, float)) and iterations >= 3:
            next_actions.append("prefer a smaller follow-up step")
        return {
            "branch": branch,
            "status": status,
            "error": error,
            "approval_pending": approval_pending,
            "recent_failures": recent_failures,
            "tool_count": tool_count,
            "iterations": iterations,
            "subtask_status": subtask_status,
            "last_failure": last_failure,
            "next_actions": list(dict.fromkeys(next_actions)),
        }

    @staticmethod
    def _branch_from_recovery_hint(hint: dict[str, Any]) -> str:
        return str(hint.get("branch", "continue"))

    @staticmethod
    def _workflow_status_from_hint(hint: dict[str, Any]) -> str:
        return str(hint.get("status", ""))

    @staticmethod
    def _default_compensation_type(node: WorkflowNode, hint: dict[str, Any]) -> str:
        branch = str(hint.get("branch", "continue"))
        if branch in {"approval_wait"}:
            return "wait"
        if branch in {"compensation"}:
            return "tool" if node.type in {WorkflowNodeType.AGENT, WorkflowNodeType.TOOL} else "wait"
        if branch in {"reobserve", "observe"}:
            return "wait"
        return str(node.config.get("on_failure", {}).get("type", "transform"))

    @staticmethod
    def _default_compensation_delay(node: WorkflowNode, hint: dict[str, Any]) -> int:
        branch = str(hint.get("branch", "continue"))
        if branch == "approval_wait":
            return 1000
        if branch in {"reobserve", "observe"}:
            return 250
        if node.type in {WorkflowNodeType.AGENT, WorkflowNodeType.TOOL}:
            return 500
        return 0

    @staticmethod
    def _default_compensation_tool(node: WorkflowNode, hint: dict[str, Any]) -> str | None:
        branch = str(hint.get("branch", "continue"))
        if branch == "compensation" and node.type == WorkflowNodeType.AGENT:
            return "workflow_compensate_agent"
        if branch == "compensation" and node.type == WorkflowNodeType.TOOL:
            return "workflow_compensate_tool"
        return None

    @staticmethod
    def _default_compensation_template(node: WorkflowNode, hint: dict[str, Any]) -> str:
        branch = str(hint.get("branch", "continue"))
        if branch == "approval_wait":
            return "Approval pending for {node_id}; waiting for approval to resume."
        if branch == "reobserve":
            return "Re-observe workflow node {node_id} after multiple iterations."
        if branch == "observe":
            return "Observe workflow node {node_id} before continuing."
        return "Workflow node {node_id} compensated under branch {branch}."

    @staticmethod
    def _default_compensation_arguments(node: WorkflowNode, hint: dict[str, Any]) -> dict[str, Any]:
        return {
            "workflow_node_id": node.id,
            "branch": str(hint.get("branch", "continue")),
            "status": hint.get("status"),
            "tool_count": hint.get("tool_count"),
            "iterations": hint.get("iterations"),
            "subtask_status": hint.get("subtask_status"),
            "approval_pending": hint.get("approval_pending"),
        }

    def _record_event(self, context: RunContext, event: str, **data: Any) -> TraceEvent | None:
        if self.tracer is None:
            return None
        return self.tracer.record(context, event, **data)

    def _record_audit(
        self,
        *,
        action: str,
        run: WorkflowRunRecord,
        workflow_id: str,
        tenant_id: str,
        user_id: str,
        details: dict[str, Any],
    ) -> None:
        if self.audit_store is None:
            return
        self.audit_store.record(
            action=action,
            resource_type="workflow",
            resource_id=workflow_id,
            tenant_id=tenant_id,
            actor_id=user_id,
            trace_id=run.run_id,
            run_id=run.run_id,
            workflow_id=workflow_id,
            details=details,
        )

    def _collect_outputs(
        self,
        state: dict[str, Any],
        definition: WorkflowDefinition,
    ) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for node in definition.nodes:
            if node.type == WorkflowNodeType.OUTPUT and node.id in state:
                outputs[node.id] = state[node.id]
        return outputs

    def _enrich_agent_context(
        self,
        run_context: RunContext,
        node: WorkflowNode,
        definition: WorkflowDefinition,
        state: dict[str, Any],
        inputs: dict[str, Any],
        extra_context: dict[str, Any],
    ) -> dict[str, Any]:
        context = {
            "workflow_id": definition.id,
            "workflow_name": definition.name,
            "workflow_node_id": node.id,
            "workflow_node_type": node.type.value,
            "workflow_inputs": inputs,
            "workflow_state": state,
            "workflow_trace_id": run_context.trace_id,
            "extra_context": extra_context,
            "recovery_hint": self._workflow_recovery_hint(state, error=None),
        }
        if isinstance(extra_context, dict):
            context.update(extra_context)
        return context

    def _derive_node_context(self, run_context: RunContext, node: WorkflowNode) -> RunContext:
        return RunContext(
            trace_id=f"{run_context.trace_id}:{node.id}",
            tenant_id=run_context.tenant_id,
            user_id=run_context.user_id,
            request_id=run_context.request_id,
            agent_id=run_context.agent_id,
            permission_scope=list(run_context.permission_scope),
            budget_tokens=run_context.budget_tokens,
            budget_usd=run_context.budget_usd,
            risk_level=run_context.risk_level,
        )

    @staticmethod
    def _permission_scope_for_node(node: WorkflowNode) -> list[str]:
        required = node.config.get("permission_scope")
        if isinstance(required, list):
            return [str(item) for item in required if str(item).strip()]
        return []

    async def _capture_node_failure(
        self,
        run_context: RunContext,
        definition: WorkflowDefinition,
        node: WorkflowNode,
        *,
        input_state: dict[str, Any],
        state: dict[str, Any],
        error: str,
        compensation_output: Any,
        compensation_error: str | None,
    ) -> None:
        task_summary = f"Workflow {definition.name} node {node.id} failed: {error}"
        memory_payload = {
            "workflow_id": definition.id,
            "workflow_name": definition.name,
            "node_id": node.id,
            "node_type": node.type.value,
            "error": error,
            "compensation_output": compensation_output,
            "compensation_error": compensation_error,
            "input_keys": sorted(input_state.keys()),
            "state_keys": sorted(state.keys()),
        }
        await self.agent.memory.store(
            run_context,
            content=task_summary,
            layer=5,
            importance=0.75,
            tags=["workflow", "failure", node.type.value],
            metadata={
                **memory_payload,
                "trace_id": run_context.trace_id,
                "request_id": run_context.request_id,
                "agent_id": run_context.agent_id,
                "tenant_id": run_context.tenant_id,
                "user_id": run_context.user_id,
            },
        )
        evolution_store.add_learning(
            LearningRecord(
                tenant_id=run_context.tenant_id,
                agent_id=run_context.agent_id,
                domain="workflow_failure",
                pattern=f"{definition.id}:{node.id}",
                outcome=error[:500],
                confidence=0.54,
                promoted=False,
            )
        )
        if "capability" in error.lower() or node.type in {WorkflowNodeType.AGENT, WorkflowNodeType.TOOL}:
            report = open_source_discovery_store.build_report(error, limit=5)
            await self.agent.memory.store(
                run_context,
                content=f"Workflow failure open-source discovery: {definition.name} / {node.id}\n{report.model_dump(mode='json')}",
                layer=6,
                importance=0.65,
                tags=["open-source", "workflow", "failure"],
                metadata={
                    "workflow_id": definition.id,
                    "workflow_name": definition.name,
                    "node_id": node.id,
                    "query": error,
                    "report": report.model_dump(mode="json"),
                    "trace_id": run_context.trace_id,
                    "request_id": run_context.request_id,
                },
            )

    def _build_snapshot(
        self,
        definition: WorkflowDefinition,
        inputs: dict[str, Any],
        state: dict[str, Any],
        node_results: list[WorkflowNodeResult] | None = None,
        *,
        status: WorkflowRunStatus | None = None,
        resume_cursor: int | None = None,
        error: str | None = None,
        pending_approval_id: str | None = None,
        pending_node_id: str | None = None,
    ) -> dict[str, Any]:
        snapshot = {
            "workflow_id": definition.id,
            "workflow_name": definition.name,
            "input_keys": sorted(inputs.keys()),
            "state_keys": sorted(state.keys()),
            "node_count": len(definition.nodes),
            "edge_count": len(definition.edges),
            "node_result_count": len(node_results or []),
        }
        if status is not None:
            snapshot["status"] = status.value
        if resume_cursor is not None:
            snapshot["resume_cursor"] = resume_cursor
        if error is not None:
            snapshot["error"] = error
        if pending_approval_id is not None:
            snapshot["pending_approval_id"] = pending_approval_id
        if pending_node_id is not None:
            snapshot["pending_node_id"] = pending_node_id
        if "last_agent_summary" in state:
            snapshot["last_agent_summary"] = state["last_agent_summary"]
        if "last_agent_trace_id" in state:
            snapshot["last_agent_trace_id"] = state["last_agent_trace_id"]
        if "last_agent_execution_summary" in state:
            snapshot["last_agent_execution_summary"] = state["last_agent_execution_summary"]
        if "last_agent_snapshot" in state:
            snapshot["last_agent_snapshot"] = state["last_agent_snapshot"]
        if "last_agent_recovery_branch" in state:
            snapshot["last_agent_recovery_branch"] = state["last_agent_recovery_branch"]
        if "node_results" in state:
            snapshot["node_results"] = [result.model_dump(mode="json") for result in state["node_results"] if hasattr(result, "model_dump")]
        if "recovery_hint" in state:
            snapshot["recovery_hint"] = state["recovery_hint"]
        return snapshot

    def _render_value(self, value: Any, state: dict[str, Any], inputs: dict[str, Any]) -> Any:
        if isinstance(value, str):
            return self._render_template(value, state, inputs)
        if isinstance(value, dict):
            return {
                key: self._render_value(item, state, inputs)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._render_value(item, state, inputs) for item in value]
        if isinstance(value, tuple):
            return tuple(self._render_value(item, state, inputs) for item in value)
        return value

    def _render_template(self, template: str, state: dict[str, Any], inputs: dict[str, Any]) -> str:
        context = self._template_context(state, inputs)
        return template.format_map(_SafeFormatDict(context))

    def _template_context(self, state: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for key, value in inputs.items():
            context[f"input_{key}"] = self._stringify(value)
            context[key] = self._stringify(value)
        for key, value in state.items():
            context[key] = self._stringify(value)
        context["inputs"] = self._stringify(inputs)
        context["state"] = self._stringify(state)
        return context

    @staticmethod
    def _stringify(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return json.dumps(value, ensure_ascii=False, default=str)


class _SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class WorkflowRuntimeManager:
    def __init__(self, *, executor: WorkflowExecutor, repository: WorkflowRepository) -> None:
        self.executor = executor
        self.repository = repository
        self._tasks: dict[str, asyncio.Task] = {}
        self._paused: set[str] = set()
        self._approved: dict[str, dict[str, str]] = {}

    async def start(
        self,
        workflow_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        permission_scope: list[str] | None = None,
    ) -> WorkflowRunRecord:
        definition = self.repository.get_definition(workflow_id)
        if definition is None:
            raise WorkflowExecutionError(f"Workflow not found: {workflow_id}")

        run_id = str(uuid4())
        record = WorkflowRunRecord(
            run_id=run_id,
            workflow_id=definition.id,
            workflow_name=definition.name,
            status=WorkflowRunStatus.RUNNING,
            tenant_id=tenant_id,
            user_id=user_id,
            inputs=inputs or {},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            snapshot={
                "workflow_id": definition.id,
                "workflow_name": definition.name,
                "input_keys": sorted((inputs or {}).keys()),
                "node_count": len(definition.nodes),
                "edge_count": len(definition.edges),
            },
        )
        self.repository.record_run(record)
        langfuse_client.log(
            "workflow.run.started",
            trace_id=record.snapshot.get("workflow_id", record.workflow_id),
            run_id=record.run_id,
            workflow_id=record.workflow_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        task = asyncio.create_task(
            self.executor.execute(
                workflow_id,
                inputs or {},
                tenant_id=tenant_id,
                user_id=user_id,
                permission_scope=permission_scope,
                run_id=run_id,
                pause_checkpoint=self.pause_checkpoint,
                approved_approvals=self._approved.get(run_id, {}),
            )
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._cleanup_run(run_id))
        return record

    async def pause_latest(self, workflow_id: str) -> WorkflowControlResponse:
        run = self._latest_active_run(workflow_id)
        if run is None:
            raise WorkflowExecutionError(f"No active workflow run for {workflow_id}.")
        task = self._tasks.get(run.run_id)
        if task is None or task.done():
            raise WorkflowExecutionError(f"No active workflow run for {workflow_id}.")
        self._paused.add(run.run_id)
        updated = self.repository.update_run_status(
            run.run_id,
            WorkflowRunStatus.PAUSED,
            resume_cursor=len(run.node_results),
        )
        if updated is None:
            raise WorkflowExecutionError(f"No active workflow run for {workflow_id}.")
        langfuse_client.log(
            "workflow.run.paused",
            trace_id=run.workflow_id,
            run_id=run.run_id,
            workflow_id=workflow_id,
        )
        return WorkflowControlResponse(
            run_id=run.run_id,
            workflow_id=workflow_id,
            status=updated.status,
            changed=True,
            message="Workflow run paused.",
            snapshot=self.repository.run_snapshot(workflow_id),
        )

    async def resume_latest(self, workflow_id: str) -> WorkflowControlResponse:
        run = self._latest_paused_run(workflow_id)
        if run is None:
            raise WorkflowExecutionError(f"No paused workflow run for {workflow_id}.")
        task = self._tasks.get(run.run_id)
        if task is None or task.done():
            raise WorkflowExecutionError(f"No paused workflow run for {workflow_id}.")
        self._paused.discard(run.run_id)
        updated = self.repository.update_run_status(
            run.run_id,
            WorkflowRunStatus.RUNNING,
            resume_cursor=run.resume_cursor,
        )
        if updated is None:
            raise WorkflowExecutionError(f"No paused workflow run for {workflow_id}.")
        langfuse_client.log(
            "workflow.run.resumed",
            trace_id=run.workflow_id,
            run_id=run.run_id,
            workflow_id=workflow_id,
        )
        return WorkflowControlResponse(
            run_id=run.run_id,
            workflow_id=workflow_id,
            status=updated.status,
            changed=True,
            message="Workflow run resumed.",
            snapshot=self.repository.run_snapshot(workflow_id),
        )

    async def cancel_latest(self, workflow_id: str) -> WorkflowControlResponse:
        run = self._latest_active_or_paused_run(workflow_id)
        if run is None:
            raise WorkflowExecutionError(f"No active workflow run for {workflow_id}.")
        task = self._tasks.get(run.run_id)
        self._paused.discard(run.run_id)
        if task is not None and not task.done():
            task.cancel()
        self._approved.pop(run.run_id, None)
        updated = self.repository.update_run_status(
            run.run_id,
            WorkflowRunStatus.CANCELED,
            error="Workflow run canceled.",
            resume_cursor=run.resume_cursor,
        )
        if updated is None:
            raise WorkflowExecutionError(f"No active workflow run for {workflow_id}.")
        langfuse_client.log(
            "workflow.run.canceled",
            trace_id=run.workflow_id,
            run_id=run.run_id,
            workflow_id=workflow_id,
        )
        return WorkflowControlResponse(
            run_id=run.run_id,
            workflow_id=workflow_id,
            status=updated.status,
            changed=True,
            message="Workflow run canceled.",
            snapshot=self.repository.run_snapshot(workflow_id),
        )

    async def pause_checkpoint(self, run_id: str) -> None:
        while run_id in self._paused:
            task = self._tasks.get(run_id)
            if task is None or task.done():
                self._paused.discard(run_id)
                break
            await asyncio.sleep(0.05)

    def _latest_active_run(self, workflow_id: str) -> WorkflowRunRecord | None:
        for run in self.repository.list_runs(workflow_id=workflow_id, limit=100):
            if run.run_id in self._tasks and run.status == WorkflowRunStatus.RUNNING:
                return run
        return None

    def _latest_paused_run(self, workflow_id: str) -> WorkflowRunRecord | None:
        for run in self.repository.list_runs(workflow_id=workflow_id, limit=100):
            if run.run_id in self._tasks and run.run_id in self._paused:
                return run
        return None

    def _latest_active_or_paused_run(self, workflow_id: str) -> WorkflowRunRecord | None:
        return self._latest_active_run(workflow_id) or self._latest_paused_run(workflow_id)

    def _cleanup_run(self, run_id: str) -> None:
        self._tasks.pop(run_id, None)
        self._paused.discard(run_id)
        self._approved.pop(run_id, None)


class WorkflowScheduler:
    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        runtime: WorkflowRuntimeManager,
        schedule_store: WorkflowScheduleStore,
    ) -> None:
        self.repository = repository
        self.runtime = runtime
        self.schedule_store = schedule_store

    def schedule(
        self,
        workflow_id: str,
        request: WorkflowScheduleRequest,
        *,
        tenant_id: str,
        user_id: str,
        permission_scope: list[str],
    ) -> WorkflowScheduleRecord:
        if self.repository.get_definition(workflow_id) is None:
            raise WorkflowExecutionError(f"Workflow not found: {workflow_id}")
        run_at = request.run_at or datetime.now(UTC) + timedelta(seconds=request.delay_seconds)
        record = self.schedule_store.create(
            workflow_id=workflow_id,
            inputs=request.inputs,
            tenant_id=tenant_id,
            user_id=user_id,
            permission_scope=permission_scope,
            run_at=run_at,
        )
        record.snapshot = {
            "workflow_id": workflow_id,
            "scheduled_for": run_at.isoformat(),
            "input_keys": sorted(request.inputs.keys()),
        }
        return record

    async def run_due(
        self,
        *,
        limit: int = 20,
        worker_id: str = "workflow-runtime",
        lease_seconds: int = 60,
    ) -> list[WorkflowScheduleRecord]:
        triggered: list[WorkflowScheduleRecord] = []
        for record in self.schedule_store.acquire_due(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            limit=limit,
        ):
            try:
                run = await self.runtime.start(
                    record.workflow_id,
                    record.inputs,
                    tenant_id=record.tenant_id,
                    user_id=record.user_id,
                    permission_scope=record.permission_scope,
                )
                updated = self.schedule_store.mark(
                    record.schedule_id,
                    WorkflowScheduleStatus.TRIGGERED,
                    run_id=run.run_id,
                )
            except Exception as exc:  # noqa: BLE001 - schedule failures are persisted
                updated = self.schedule_store.mark(
                    record.schedule_id,
                    WorkflowScheduleStatus.FAILED,
                    error=str(exc),
                )
            if updated is not None:
                triggered.append(updated)
        return triggered

    def cancel(self, schedule_id: str) -> WorkflowScheduleRecord | None:
        record = self.schedule_store.get(schedule_id)
        if record is None or record.status != WorkflowScheduleStatus.PENDING:
            return None
        return self.schedule_store.mark(schedule_id, WorkflowScheduleStatus.CANCELED)
