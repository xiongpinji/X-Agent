"""Full-coverage unit tests for backend.app.core.workflows.

Covers:
- Enums and Pydantic models
- _MinimalCron parser (fields, matching, next_after)
- next_cron_run / validate_cron_expression
- WorkflowRepository (CRUD, validation, topological order, persistence)
- WorkflowScheduleStore (create, list, due, acquire, mark, reschedule, persist)
- WorkflowExecutor (node types, conditions, compensation, approval, recovery)
- WorkflowRuntimeManager (start, pause, resume, cancel, recovery)
- WorkflowScheduler (schedule, run_due, cancel)
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.workflows import (
    WorkflowApprovalRequired,
    WorkflowControlResponse,
    WorkflowCreateRequest,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowExecutionError,
    WorkflowExecutor,
    WorkflowNode,
    WorkflowNodeExecutionError,
    WorkflowNodeResult,
    WorkflowNodeType,
    WorkflowRepository,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowRuntimeManager,
    WorkflowScheduleRecord,
    WorkflowScheduleRequest,
    WorkflowScheduleStatus,
    WorkflowScheduleStore,
    WorkflowScheduler,
    WorkflowSummary,
    WorkflowUpdateRequest,
    _MinimalCron,
    _SafeFormatDict,
    next_cron_run,
    validate_cron_expression,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_definition(**kw) -> WorkflowDefinition:
    defaults = dict(
        name="test-wf",
        nodes=[
            WorkflowNode(id="start", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="end", type=WorkflowNodeType.OUTPUT),
        ],
        edges=[WorkflowEdge(source="start", target="end")],
    )
    defaults.update(kw)
    return WorkflowDefinition(**defaults)


def _make_executor(repository: WorkflowRepository | None = None, **kw) -> WorkflowExecutor:
    from backend.app.core.agent.loop import AgentLoop
    from backend.app.core.llm.backends import LLMRouter, MockLLMBackend
    from backend.app.core.memory.store import MemorySystem
    from backend.app.core.tools import ToolRegistry

    agent = AgentLoop(
        llm_router=LLMRouter(backend=MockLLMBackend()),
        memory=MemorySystem(),
        tools=ToolRegistry(),
    )
    repo = repository or WorkflowRepository()
    return WorkflowExecutor(agent=agent, repository=repo, **kw)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_node_types(self):
        assert WorkflowNodeType.INPUT == "input"
        assert WorkflowNodeType.TRANSFORM == "transform"
        assert WorkflowNodeType.TOOL == "tool"
        assert WorkflowNodeType.AGENT == "agent"
        assert WorkflowNodeType.CONDITION == "condition"
        assert WorkflowNodeType.WAIT == "wait"
        assert WorkflowNodeType.APPROVAL == "approval"
        assert WorkflowNodeType.OUTPUT == "output"

    def test_run_status(self):
        assert WorkflowRunStatus.DRAFT == "draft"
        assert WorkflowRunStatus.RUNNING == "running"
        assert WorkflowRunStatus.COMPLETED == "completed"
        assert WorkflowRunStatus.FAILED == "failed"
        assert WorkflowRunStatus.CANCELED == "canceled"
        assert WorkflowRunStatus.PAUSED == "paused"
        assert WorkflowRunStatus.NEEDS_APPROVAL == "needs_approval"

    def test_schedule_status(self):
        assert WorkflowScheduleStatus.PENDING == "pending"
        assert WorkflowScheduleStatus.TRIGGERED == "triggered"
        assert WorkflowScheduleStatus.CANCELED == "canceled"
        assert WorkflowScheduleStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_workflow_node(self):
        node = WorkflowNode(id="n1", type=WorkflowNodeType.INPUT, config={"key": "x"})
        assert node.id == "n1"
        assert node.config == {"key": "x"}

    def test_workflow_edge(self):
        edge = WorkflowEdge(source="a", target="b", condition="true")
        assert edge.condition == "true"

    def test_workflow_definition_defaults(self):
        wf = _simple_definition()
        assert wf.id  # uuid generated
        assert wf.description == ""
        assert len(wf.nodes) == 2

    def test_workflow_run_record(self):
        rec = WorkflowRunRecord(
            workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        assert rec.run_id
        assert rec.tenant_id == "default"
        assert rec.resume_cursor == 0

    def test_workflow_schedule_record(self):
        rec = WorkflowScheduleRecord(
            workflow_id="w1", run_at=datetime.now(UTC)
        )
        assert rec.status == WorkflowScheduleStatus.PENDING
        assert rec.cron is None

    def test_workflow_summary(self):
        s = WorkflowSummary(
            workflow_id="w1", name="wf", node_count=2, edge_count=1,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        )
        assert s.latest_run_id is None

    def test_exceptions(self):
        err = WorkflowNodeExecutionError("fail", 3)
        assert err.attempts == 3
        assert str(err) == "fail"

        approval_err = WorkflowApprovalRequired("appr-123")
        assert approval_err.approval_id == "appr-123"
        assert "appr-123" in str(approval_err)


# ---------------------------------------------------------------------------
# _MinimalCron
# ---------------------------------------------------------------------------

class TestMinimalCron:
    def test_every_minute(self):
        cron = _MinimalCron("* * * * *")
        now = datetime(2024, 6, 15, 10, 30, tzinfo=UTC)
        assert cron.matches(now)

    def test_specific_minute_hour(self):
        cron = _MinimalCron("30 10 * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 10, 31, tzinfo=UTC))

    def test_range(self):
        cron = _MinimalCron("0-5 * * * *")
        assert cron.matches(datetime(2024, 1, 1, 0, 3, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 1, 1, 0, 6, tzinfo=UTC))

    def test_step(self):
        cron = _MinimalCron("*/15 * * * *")
        assert cron.matches(datetime(2024, 1, 1, 0, 0, tzinfo=UTC))
        assert cron.matches(datetime(2024, 1, 1, 0, 15, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 1, 1, 0, 7, tzinfo=UTC))

    def test_comma_list(self):
        cron = _MinimalCron("0,30 * * * *")
        assert cron.matches(datetime(2024, 1, 1, 0, 0, tzinfo=UTC))
        assert cron.matches(datetime(2024, 1, 1, 0, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 1, 1, 0, 15, tzinfo=UTC))

    def test_day_of_week_sunday_normalization(self):
        # 7 means Sunday, should be normalized to 0
        cron = _MinimalCron("0 0 * * 7")
        # 2024-06-16 is a Sunday
        assert cron.matches(datetime(2024, 6, 16, 0, 0, tzinfo=UTC))

    def test_dom_dow_or_semantics(self):
        # Both dom and dow restricted: OR semantics
        cron = _MinimalCron("0 0 15 * 1")  # 15th OR Monday
        # 2024-06-15 is Saturday (15th matches)
        assert cron.matches(datetime(2024, 6, 15, 0, 0, tzinfo=UTC))
        # 2024-06-17 is Monday (dow matches)
        assert cron.matches(datetime(2024, 6, 17, 0, 0, tzinfo=UTC))

    def test_next_after(self):
        cron = _MinimalCron("0 12 * * *")
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2024, 6, 15, 12, 0, tzinfo=UTC)

    def test_next_after_wraps_day(self):
        cron = _MinimalCron("0 8 * * *")
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2024, 6, 16, 8, 0, tzinfo=UTC)

    def test_invalid_field_count(self):
        with pytest.raises(WorkflowExecutionError, match="5 fields"):
            _MinimalCron("* * *")

    def test_invalid_step(self):
        with pytest.raises(WorkflowExecutionError, match="step"):
            _MinimalCron("*/abc * * * *")

    def test_negative_step(self):
        with pytest.raises(WorkflowExecutionError, match="positive"):
            _MinimalCron("*/0 * * * *")

    def test_out_of_range(self):
        with pytest.raises(WorkflowExecutionError, match="out of range"):
            _MinimalCron("60 * * * *")

    def test_invalid_value(self):
        with pytest.raises(WorkflowExecutionError, match="Invalid cron value"):
            _MinimalCron("abc * * * *")

    def test_invalid_range(self):
        with pytest.raises(WorkflowExecutionError, match="Invalid cron range"):
            _MinimalCron("a-b * * * *")

    def test_empty_item(self):
        with pytest.raises(WorkflowExecutionError, match="empty item"):
            _MinimalCron("0, * * * *")

    def test_vixie_shorthand(self):
        # "5/10" means "5-high/10"
        cron = _MinimalCron("5/10 * * * *")
        assert cron.matches(datetime(2024, 1, 1, 0, 5, tzinfo=UTC))
        assert cron.matches(datetime(2024, 1, 1, 0, 15, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 1, 1, 0, 4, tzinfo=UTC))


# ---------------------------------------------------------------------------
# next_cron_run / validate_cron_expression
# ---------------------------------------------------------------------------

class TestCronUtils:
    def test_next_cron_run_basic(self):
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = next_cron_run("30 10 * * *", now=now)
        assert result.minute == 30
        assert result.hour == 10

    def test_next_cron_run_empty(self):
        with pytest.raises(WorkflowExecutionError, match="must not be empty"):
            next_cron_run("")

    def test_next_cron_run_naive_datetime(self):
        now = datetime(2024, 6, 15, 10, 0)  # naive
        result = next_cron_run("0 12 * * *", now=now)
        assert result.tzinfo is not None

    def test_validate_cron_expression_valid(self):
        assert validate_cron_expression("*/5 * * * *") == "*/5 * * * *"

    def test_validate_cron_expression_invalid(self):
        with pytest.raises(WorkflowExecutionError):
            validate_cron_expression("invalid")


# ---------------------------------------------------------------------------
# WorkflowRepository
# ---------------------------------------------------------------------------

class TestWorkflowRepository:
    def test_upsert_and_get(self):
        repo = WorkflowRepository()
        req = WorkflowCreateRequest(
            name="wf1",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        )
        wf = repo.upsert_definition(req)
        assert wf.name == "wf1"
        assert repo.get_definition(wf.id) is not None

    def test_upsert_update(self):
        repo = WorkflowRepository()
        req = WorkflowCreateRequest(
            name="wf1",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        )
        wf = repo.upsert_definition(req)
        update = WorkflowUpdateRequest(name="wf1-updated")
        wf2 = repo.upsert_definition(update, workflow_id=wf.id)
        assert wf2.name == "wf1-updated"

    def test_upsert_nonexistent_raises(self):
        repo = WorkflowRepository()
        update = WorkflowUpdateRequest(name="x")
        with pytest.raises(KeyError):
            repo.upsert_definition(update, workflow_id="nonexistent")

    def test_upsert_definition_object(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        result = repo.upsert_definition(defn)
        assert result.id == defn.id

    def test_list_definitions_sorted(self):
        repo = WorkflowRepository()
        req1 = WorkflowCreateRequest(name="a", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        req2 = WorkflowCreateRequest(name="b", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        repo.upsert_definition(req1)
        repo.upsert_definition(req2)
        defs = repo.list_definitions()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}

    def test_delete_definition(self):
        repo = WorkflowRepository()
        req = WorkflowCreateRequest(name="wf", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        wf = repo.upsert_definition(req)
        assert repo.delete_definition(wf.id) is True
        assert repo.delete_definition(wf.id) is False
        assert repo.get_definition(wf.id) is None

    def test_validate_duplicate_node_ids(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="bad",
            nodes=[
                WorkflowNode(id="n1", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="n1", type=WorkflowNodeType.OUTPUT),
            ],
        )
        with pytest.raises(WorkflowExecutionError, match="unique"):
            repo.upsert_definition(defn)

    def test_validate_unknown_edge_node(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="bad",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
            edges=[WorkflowEdge(source="n1", target="n2")],
        )
        with pytest.raises(WorkflowExecutionError, match="unknown node"):
            repo.upsert_definition(defn)

    def test_validate_cycle(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="cycle",
            nodes=[
                WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="b", type=WorkflowNodeType.OUTPUT),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="b", target="a"),
            ],
        )
        with pytest.raises(WorkflowExecutionError, match="cycle"):
            repo.upsert_definition(defn)

    def test_topological_order(self):
        defn = _simple_definition()
        order = WorkflowRepository._topological_order(defn)
        assert order == ["start", "end"]

    def test_record_and_get_run(self):
        repo = WorkflowRepository()
        run = WorkflowRunRecord(
            workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        repo.record_run(run)
        assert repo.get_run(run.run_id) is not None

    def test_update_run_status(self):
        repo = WorkflowRepository()
        run = WorkflowRunRecord(
            workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        repo.record_run(run)
        updated = repo.update_run_status(run.run_id, WorkflowRunStatus.COMPLETED)
        assert updated.status == WorkflowRunStatus.COMPLETED
        assert repo.update_run_status("nonexistent", WorkflowRunStatus.FAILED) is None

    def test_update_run_status_with_cursor(self):
        repo = WorkflowRepository()
        run = WorkflowRunRecord(
            workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        repo.record_run(run)
        updated = repo.update_run_status(run.run_id, WorkflowRunStatus.PAUSED, resume_cursor=3)
        assert updated.resume_cursor == 3

    def test_list_runs_filter(self):
        repo = WorkflowRepository()
        r1 = WorkflowRunRecord(workflow_id="w1", workflow_name="wf1", status=WorkflowRunStatus.COMPLETED)
        r2 = WorkflowRunRecord(workflow_id="w2", workflow_name="wf2", status=WorkflowRunStatus.RUNNING)
        repo.record_run(r1)
        repo.record_run(r2)
        assert len(repo.list_runs(workflow_id="w1")) == 1
        assert len(repo.list_runs()) == 2

    def test_update_run_progress(self):
        repo = WorkflowRepository()
        run = WorkflowRunRecord(
            workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        repo.record_run(run)
        nr = WorkflowNodeResult(node_id="n1", node_type=WorkflowNodeType.INPUT, status=WorkflowRunStatus.COMPLETED)
        updated = repo.update_run_progress(run.run_id, node_results=[nr], resume_cursor=1, worker_id="w-1")
        assert updated.resume_cursor == 1
        assert updated.worker_id == "w-1"
        assert repo.update_run_progress("nonexistent", node_results=[], resume_cursor=0) is None

    def test_counts(self):
        repo = WorkflowRepository()
        req = WorkflowCreateRequest(name="wf", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        repo.upsert_definition(req)
        assert repo.definition_count() == 1
        assert repo.run_count() == 0

    def test_count_runs(self):
        repo = WorkflowRepository()
        r1 = WorkflowRunRecord(workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.COMPLETED)
        r2 = WorkflowRunRecord(workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.FAILED)
        repo.record_run(r1)
        repo.record_run(r2)
        assert repo.count_runs("w1") == 2
        assert repo.count_runs() == 2
        assert repo.count_runs("w2") == 0

    def test_latest_run_for(self):
        repo = WorkflowRepository()
        assert repo.latest_run_for("w1") is None
        r = WorkflowRunRecord(workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.COMPLETED)
        repo.record_run(r)
        assert repo.latest_run_for("w1").run_id == r.run_id

    def test_summary_for(self):
        repo = WorkflowRepository()
        req = WorkflowCreateRequest(name="wf", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        wf = repo.upsert_definition(req)
        summary = repo.summary_for(wf.id)
        assert summary.name == "wf"
        assert summary.node_count == 1

    def test_run_snapshot(self):
        repo = WorkflowRepository()
        snap = repo.run_snapshot("w1")
        assert snap["run_count"] == 0
        assert snap["latest_run_id"] is None

    def test_persistence_definitions(self, tmp_path):
        def_path = tmp_path / "defs.json"
        repo = WorkflowRepository(definition_path=def_path)
        req = WorkflowCreateRequest(name="persist-wf", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        wf = repo.upsert_definition(req)
        assert def_path.exists()
        # Reload
        repo2 = WorkflowRepository(definition_path=def_path)
        assert repo2.get_definition(wf.id) is not None

    def test_persistence_runs(self, tmp_path):
        run_path = tmp_path / "runs.jsonl"
        repo = WorkflowRepository(run_path=run_path)
        r = WorkflowRunRecord(workflow_id="w1", workflow_name="wf", status=WorkflowRunStatus.COMPLETED)
        repo.record_run(r)
        assert run_path.exists()
        # Reload
        repo2 = WorkflowRepository(run_path=run_path)
        assert repo2.get_run(r.run_id) is not None

    def test_load_corrupt_definitions(self, tmp_path):
        def_path = tmp_path / "defs.json"
        def_path.write_text("not json{{{")
        repo = WorkflowRepository(definition_path=def_path)
        assert repo.definition_count() == 0

    def test_persist_snapshot_stale_skip(self, tmp_path):
        def_path = tmp_path / "defs.json"
        repo = WorkflowRepository(definition_path=def_path)
        req = WorkflowCreateRequest(name="wf", nodes=[WorkflowNode(id="n", type=WorkflowNodeType.INPUT)])
        repo.upsert_definition(req)
        # Manually set persisted version higher
        repo._def_version_persisted = 999
        repo._persist_snapshot(1, [])  # Should be skipped (stale)


# ---------------------------------------------------------------------------
# WorkflowScheduleStore
# ---------------------------------------------------------------------------

class TestWorkflowScheduleStore:
    def test_create_and_get(self):
        store = WorkflowScheduleStore()
        rec = store.create(
            workflow_id="w1", inputs={"x": 1}, tenant_id="t1",
            user_id="u1", permission_scope=["read"],
            run_at=datetime(2024, 6, 15, 12, 0, tzinfo=UTC),
        )
        assert store.get(rec.schedule_id) is not None
        assert rec.status == WorkflowScheduleStatus.PENDING

    def test_create_naive_datetime(self):
        store = WorkflowScheduleStore()
        rec = store.create(
            workflow_id="w1", inputs={}, tenant_id="t1",
            user_id="u1", permission_scope=[],
            run_at=datetime(2024, 6, 15, 12, 0),  # naive
        )
        assert rec.run_at.tzinfo is not None

    def test_list_filter(self):
        store = WorkflowScheduleStore()
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        store.create(workflow_id="w2", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=datetime(2024, 6, 16, tzinfo=UTC))
        assert len(store.list(workflow_id="w1")) == 1
        assert len(store.list(status=WorkflowScheduleStatus.PENDING)) == 2

    def test_due(self):
        store = WorkflowScheduleStore()
        past = datetime(2024, 1, 1, tzinfo=UTC)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=past)
        store.create(workflow_id="w2", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=future)
        due = store.due(now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(due) == 1
        assert due[0].workflow_id == "w1"

    def test_acquire_due(self):
        store = WorkflowScheduleStore()
        past = datetime(2024, 1, 1, tzinfo=UTC)
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=past)
        acquired = store.acquire_due(worker_id="worker-1", now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(acquired) == 1
        assert acquired[0].locked_by == "worker-1"
        # Second acquire should not get it again (locked)
        acquired2 = store.acquire_due(worker_id="worker-2", now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(acquired2) == 0

    def test_acquire_expired_lease(self):
        store = WorkflowScheduleStore()
        past = datetime(2024, 1, 1, tzinfo=UTC)
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=past)
        store.acquire_due(worker_id="w1", lease_seconds=1, now=datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC))
        # After lease expires
        acquired = store.acquire_due(worker_id="w2", now=datetime(2024, 6, 15, 0, 1, 0, tzinfo=UTC))
        assert len(acquired) == 1
        assert acquired[0].locked_by == "w2"

    def test_mark(self):
        store = WorkflowScheduleStore()
        rec = store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        updated = store.mark(rec.schedule_id, WorkflowScheduleStatus.TRIGGERED, run_id="r1")
        assert updated.status == WorkflowScheduleStatus.TRIGGERED
        assert updated.run_id == "r1"
        assert store.mark("nonexistent", WorkflowScheduleStatus.FAILED) is None

    def test_count(self):
        store = WorkflowScheduleStore()
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        assert store.count() == 1
        assert store.count(WorkflowScheduleStatus.PENDING) == 1
        assert store.count(WorkflowScheduleStatus.FAILED) == 0

    def test_reschedule(self):
        store = WorkflowScheduleStore()
        rec = store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC), cron="0 * * * *")
        new_time = datetime(2024, 6, 15, 13, 0, tzinfo=UTC)
        updated = store.reschedule(rec.schedule_id, run_at=new_time, run_id="r1")
        assert updated.status == WorkflowScheduleStatus.PENDING
        assert updated.run_at == new_time
        assert "last_run_at" in updated.snapshot
        assert store.reschedule("nonexistent", run_at=new_time) is None

    def test_reschedule_with_error(self):
        store = WorkflowScheduleStore()
        rec = store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        updated = store.reschedule(rec.schedule_id, run_at=datetime(2024, 7, 1, tzinfo=UTC), error="oops")
        assert updated.error == "oops"
        assert updated.snapshot.get("last_error") == "oops"

    def test_persistence(self, tmp_path):
        path = tmp_path / "schedules.json"
        store = WorkflowScheduleStore(storage_path=path)
        store.create(workflow_id="w1", inputs={}, tenant_id="t", user_id="u",
                     permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        assert path.exists()
        store2 = WorkflowScheduleStore(storage_path=path)
        assert store2.count() == 1


# ---------------------------------------------------------------------------
# WorkflowExecutor - node execution
# ---------------------------------------------------------------------------

class TestWorkflowExecutor:
    async def test_execute_simple_workflow(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {"key": "value"})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_not_found(self):
        repo = WorkflowRepository()
        executor = _make_executor(repo)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await executor.execute("nonexistent")

    async def test_execute_input_node_with_key(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="input-wf",
            nodes=[
                WorkflowNode(id="inp", type=WorkflowNodeType.INPUT, config={"key": "name", "default": "world"}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "inp"}),
            ],
            edges=[WorkflowEdge(source="inp", target="out")],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {"name": "Alice"})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_input_node_default(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="input-default",
            nodes=[
                WorkflowNode(id="inp", type=WorkflowNodeType.INPUT, config={"key": "missing", "default": "fallback"}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "inp"}),
            ],
            edges=[WorkflowEdge(source="inp", target="out")],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_transform_node(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="transform-wf",
            nodes=[
                WorkflowNode(id="inp", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="tr", type=WorkflowNodeType.TRANSFORM, config={"template": "Hello {input_name}"}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "tr"}),
            ],
            edges=[
                WorkflowEdge(source="inp", target="tr"),
                WorkflowEdge(source="tr", target="out"),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {"name": "Bob"})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_condition_node(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="cond-wf",
            nodes=[
                WorkflowNode(id="inp", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="cond", type=WorkflowNodeType.CONDITION, config={"left": "yes", "right": "yes", "operator": "equals"}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "cond"}),
            ],
            edges=[
                WorkflowEdge(source="inp", target="cond"),
                WorkflowEdge(source="cond", target="out"),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_wait_node(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="wait-wf",
            nodes=[
                WorkflowNode(id="w", type=WorkflowNodeType.WAIT, config={"delay_ms": 10}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "w"}),
            ],
            edges=[WorkflowEdge(source="w", target="out")],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_output_node_with_value(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="out-val",
            nodes=[
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"value": {"result": "done"}}),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_execute_edge_condition_skip(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="skip-wf",
            nodes=[
                WorkflowNode(id="inp", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="skipped", type=WorkflowNodeType.TRANSFORM, config={"template": "never"}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT),
            ],
            edges=[
                WorkflowEdge(source="inp", target="skipped", condition="false"),
                WorkflowEdge(source="inp", target="out"),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.COMPLETED
        # skipped node should not be in results
        node_ids = [nr.node_id for nr in record.node_results]
        assert "skipped" not in node_ids

    async def test_execute_failing_node(self):
        repo = WorkflowRepository()
        # CONDITION with unsupported operator raises WorkflowExecutionError
        defn = WorkflowDefinition(
            name="fail-wf",
            nodes=[
                WorkflowNode(id="cond", type=WorkflowNodeType.CONDITION,
                             config={"left": 1, "right": 2, "operator": "invalid_op"}),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.FAILED

    async def test_execute_with_retry(self):
        repo = WorkflowRepository()
        # CONDITION with invalid operator raises, testing retry logic
        defn = WorkflowDefinition(
            name="retry-wf",
            nodes=[
                WorkflowNode(id="cond", type=WorkflowNodeType.CONDITION,
                             config={"left": 1, "right": 2, "operator": "bad_op",
                                     "max_retries": 2, "retry_delay_ms": 1}),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.FAILED
        assert record.node_results[0].attempts == 3  # 1 + 2 retries

    async def test_execute_with_timeout(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="timeout-wf",
            nodes=[
                WorkflowNode(id="w", type=WorkflowNodeType.WAIT, config={"delay_ms": 5000, "timeout_ms": 10}),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.FAILED

    async def test_execute_approval_node_no_store(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="approval-wf",
            nodes=[
                WorkflowNode(id="appr", type=WorkflowNodeType.APPROVAL, config={}),
            ],
        )
        repo.upsert_definition(defn)
        executor = _make_executor(repo)  # no approval_store
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.FAILED

    async def test_execute_approval_node_creates_approval(self):
        from backend.app.core.approvals import ApprovalStore
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="approval-wf",
            nodes=[
                WorkflowNode(id="appr", type=WorkflowNodeType.APPROVAL, config={"risk_level": "high"}),
            ],
        )
        repo.upsert_definition(defn)
        approval_store = ApprovalStore()
        executor = _make_executor(repo, approval_store=approval_store)
        record = await executor.execute(defn.id, {})
        assert record.status == WorkflowRunStatus.NEEDS_APPROVAL
        assert record.pending_approval_id is not None

    async def test_execute_approval_pre_approved(self):
        from backend.app.core.approvals import ApprovalStore
        from backend.app.core.contracts import RunContext
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="pre-approved",
            nodes=[
                WorkflowNode(id="appr", type=WorkflowNodeType.APPROVAL, config={}),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT, config={"from": "appr"}),
            ],
            edges=[WorkflowEdge(source="appr", target="out")],
        )
        repo.upsert_definition(defn)
        approval_store = ApprovalStore()
        ctx = RunContext(trace_id="t", tenant_id="default", user_id="u")
        approval = approval_store.create_approval(
            context=ctx, resource_type="workflow", resource_id="appr",
            action="approve", risk_level="high", reason="test",
        )
        approval_store.approve(approval.id, MagicMock(decided_by="admin"))
        executor = _make_executor(repo, approval_store=approval_store)
        record = await executor.execute(defn.id, {}, approved_approvals={"appr": approval.id})
        assert record.status == WorkflowRunStatus.COMPLETED

    async def test_resume_not_found(self):
        repo = WorkflowRepository()
        executor = _make_executor(repo)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await executor.resume("nonexistent")

    async def test_resume_not_resumable(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        run = WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="wf", status=WorkflowRunStatus.COMPLETED
        )
        repo.record_run(run)
        executor = _make_executor(repo)
        with pytest.raises(WorkflowExecutionError, match="not resumable"):
            await executor.resume(run.run_id)

    async def test_resume_failed_run(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        run = WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="wf", status=WorkflowRunStatus.FAILED,
            resume_cursor=0,
        )
        repo.record_run(run)
        executor = _make_executor(repo)
        record = await executor.resume(run.run_id)
        assert record.status == WorkflowRunStatus.COMPLETED


# ---------------------------------------------------------------------------
# WorkflowExecutor - compare / edge conditions / rendering
# ---------------------------------------------------------------------------

class TestExecutorHelpers:
    def test_compare_operators(self):
        assert WorkflowExecutor._compare(1, 1, "equals") is True
        assert WorkflowExecutor._compare(1, 2, "equals") is False
        assert WorkflowExecutor._compare(1, 2, "not_equals") is True
        assert WorkflowExecutor._compare(2, 1, "gt") is True
        assert WorkflowExecutor._compare(1, 1, "gte") is True
        assert WorkflowExecutor._compare(1, 2, "lt") is True
        assert WorkflowExecutor._compare(2, 2, "lte") is True
        assert WorkflowExecutor._compare("hello", "ell", "contains") is True
        assert WorkflowExecutor._compare(1, None, "truthy") is True
        assert WorkflowExecutor._compare(0, None, "falsy") is True

    def test_compare_unsupported(self):
        with pytest.raises(WorkflowExecutionError, match="Unsupported"):
            WorkflowExecutor._compare(1, 1, "invalid_op")

    def test_evaluate_edge_condition_none(self):
        executor = _make_executor()
        edge = WorkflowEdge(source="a", target="b")
        assert executor._evaluate_edge_condition(edge, {}, {}) is True

    def test_evaluate_edge_condition_bool(self):
        executor = _make_executor()
        edge = WorkflowEdge(source="a", target="b", condition="true")
        assert executor._evaluate_edge_condition(edge, {}, {}) is True
        edge2 = WorkflowEdge(source="a", target="b", condition="false")
        assert executor._evaluate_edge_condition(edge2, {}, {}) is False

    def test_evaluate_edge_condition_numeric(self):
        executor = _make_executor()
        edge = WorkflowEdge(source="a", target="b", condition="{val}")
        assert executor._evaluate_edge_condition(edge, {"val": 1}, {}) is True
        assert executor._evaluate_edge_condition(edge, {"val": 0}, {}) is False

    def test_render_value_string(self):
        executor = _make_executor()
        result = executor._render_value("Hello {name}", {}, {"name": "World"})
        assert result == "Hello World"

    def test_render_value_dict(self):
        executor = _make_executor()
        result = executor._render_value({"greeting": "Hi {name}"}, {}, {"name": "X"})
        assert result == {"greeting": "Hi X"}

    def test_render_value_list(self):
        executor = _make_executor()
        result = executor._render_value(["{a}", "{b}"], {"a": "1", "b": "2"}, {})
        assert result == ["1", "2"]

    def test_render_value_tuple(self):
        executor = _make_executor()
        result = executor._render_value(("{a}",), {"a": "x"}, {})
        assert result == ("x",)

    def test_render_value_primitive(self):
        executor = _make_executor()
        assert executor._render_value(42, {}, {}) == 42
        assert executor._render_value(None, {}, {}) is None

    def test_safe_format_dict(self):
        d = _SafeFormatDict({"a": "1"})
        assert d["a"] == "1"
        assert d["missing"] == "{missing}"

    def test_stringify(self):
        assert WorkflowExecutor._stringify("hello") == "hello"
        assert WorkflowExecutor._stringify(42) == 42
        assert WorkflowExecutor._stringify(None) is None
        result = WorkflowExecutor._stringify({"key": "val"})
        assert isinstance(result, str)

    def test_workflow_recovery_hint(self):
        hint = WorkflowExecutor._workflow_recovery_hint({}, error=None)
        assert hint["branch"] == "continue"

    def test_workflow_recovery_hint_with_error(self):
        hint = WorkflowExecutor._workflow_recovery_hint({}, error="something failed")
        assert hint["branch"] == "compensation"

    def test_workflow_recovery_hint_approval(self):
        state = {"pending_approval_id": "appr-1"}
        hint = WorkflowExecutor._workflow_recovery_hint(state, error=None)
        assert hint["branch"] == "approval_wait"

    def test_workflow_branch_from_state(self):
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=True, recent_failures=0,
            status="", subtask_status="", tool_count=None, iterations=None
        ) == "approval_wait"
        assert WorkflowExecutor._workflow_branch_from_state(
            error="err", approval_pending=False, recent_failures=0,
            status="", subtask_status="", tool_count=None, iterations=None
        ) == "compensation"
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=False, recent_failures=1,
            status="", subtask_status="", tool_count=None, iterations=None
        ) == "compensation"
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=False, recent_failures=0,
            status="failed", subtask_status="", tool_count=None, iterations=None
        ) == "compensation"
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=False, recent_failures=0,
            status="", subtask_status="", tool_count=None, iterations=5
        ) == "reobserve"
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=False, recent_failures=0,
            status="", subtask_status="", tool_count=0, iterations=None
        ) == "observe"
        assert WorkflowExecutor._workflow_branch_from_state(
            error=None, approval_pending=False, recent_failures=0,
            status="", subtask_status="", tool_count=3, iterations=1
        ) == "continue"

    def test_default_compensation_type(self):
        node = WorkflowNode(id="n", type=WorkflowNodeType.AGENT)
        assert WorkflowExecutor._default_compensation_type(node, {"branch": "approval_wait"}) == "wait"
        assert WorkflowExecutor._default_compensation_type(node, {"branch": "compensation"}) == "tool"
        assert WorkflowExecutor._default_compensation_type(node, {"branch": "reobserve"}) == "wait"

    def test_default_compensation_delay(self):
        node = WorkflowNode(id="n", type=WorkflowNodeType.AGENT)
        assert WorkflowExecutor._default_compensation_delay(node, {"branch": "approval_wait"}) == 1000
        assert WorkflowExecutor._default_compensation_delay(node, {"branch": "reobserve"}) == 250
        assert WorkflowExecutor._default_compensation_delay(node, {"branch": "compensation"}) == 500
        other = WorkflowNode(id="n", type=WorkflowNodeType.INPUT)
        assert WorkflowExecutor._default_compensation_delay(other, {"branch": "compensation"}) == 0

    def test_default_compensation_tool(self):
        agent_node = WorkflowNode(id="n", type=WorkflowNodeType.AGENT)
        tool_node = WorkflowNode(id="n", type=WorkflowNodeType.TOOL)
        assert WorkflowExecutor._default_compensation_tool(agent_node, {"branch": "compensation"}) == "workflow_compensate_agent"
        assert WorkflowExecutor._default_compensation_tool(tool_node, {"branch": "compensation"}) == "workflow_compensate_tool"
        assert WorkflowExecutor._default_compensation_tool(agent_node, {"branch": "continue"}) is None

    def test_default_compensation_template(self):
        node = WorkflowNode(id="n", type=WorkflowNodeType.AGENT)
        assert "Approval" in WorkflowExecutor._default_compensation_template(node, {"branch": "approval_wait"})
        assert "Re-observe" in WorkflowExecutor._default_compensation_template(node, {"branch": "reobserve"})
        assert "Observe" in WorkflowExecutor._default_compensation_template(node, {"branch": "observe"})
        assert "compensated" in WorkflowExecutor._default_compensation_template(node, {"branch": "continue"})

    def test_permission_scope_for_node(self):
        node = WorkflowNode(id="n", type=WorkflowNodeType.AGENT, config={"permission_scope": ["read", "write"]})
        assert WorkflowExecutor._permission_scope_for_node(node) == ["read", "write"]
        node2 = WorkflowNode(id="n", type=WorkflowNodeType.AGENT)
        assert WorkflowExecutor._permission_scope_for_node(node2) == []

    def test_topological_levels(self):
        repo = WorkflowRepository()
        defn = WorkflowDefinition(
            name="levels",
            nodes=[
                WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="b", type=WorkflowNodeType.TRANSFORM),
                WorkflowNode(id="c", type=WorkflowNodeType.TRANSFORM),
                WorkflowNode(id="d", type=WorkflowNodeType.OUTPUT),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="a", target="c"),
                WorkflowEdge(source="b", target="d"),
                WorkflowEdge(source="c", target="d"),
            ],
        )
        executor = _make_executor(repo)
        levels = executor._topological_levels(defn)
        assert len(levels) == 3
        assert [n.id for n in levels[0]] == ["a"]
        assert sorted(n.id for n in levels[1]) == ["b", "c"]
        assert [n.id for n in levels[2]] == ["d"]

    def test_build_snapshot(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        executor = _make_executor(repo)
        snap = executor._build_snapshot(defn, {"x": 1}, {"y": 2}, status=WorkflowRunStatus.COMPLETED)
        assert snap["workflow_id"] == defn.id
        assert snap["status"] == "completed"
        assert snap["input_keys"] == ["x"]

    def test_collect_outputs(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        executor = _make_executor(repo)
        state = {"end": {"result": "done"}, "start": "input"}
        outputs = executor._collect_outputs(state, defn)
        assert "end" in outputs
        assert "start" not in outputs

    def test_derive_node_context(self):
        from backend.app.core.contracts import RunContext
        executor = _make_executor()
        ctx = RunContext(trace_id="t1", tenant_id="ten", user_id="u1")
        node = WorkflowNode(id="n1", type=WorkflowNodeType.AGENT)
        node_ctx = executor._derive_node_context(ctx, node)
        assert node_ctx.trace_id == "t1:n1"
        assert node_ctx.tenant_id == "ten"


# ---------------------------------------------------------------------------
# WorkflowExecutor - compensation
# ---------------------------------------------------------------------------

class TestCompensation:
    async def test_compensation_transform(self):
        from backend.app.core.contracts import RunContext
        executor = _make_executor()
        node = WorkflowNode(id="n", type=WorkflowNodeType.TRANSFORM,
                            config={"on_failure": {"type": "transform", "template": "compensated {node_id}"}})
        ctx = RunContext(trace_id="t", tenant_id="ten", user_id="u")
        output, error = await executor._execute_compensation(ctx, node, {"node_id": "n"}, {})
        assert error is None
        assert "compensated" in str(output)

    async def test_compensation_wait(self):
        from backend.app.core.contracts import RunContext
        executor = _make_executor()
        node = WorkflowNode(id="n", type=WorkflowNodeType.WAIT,
                            config={"on_failure": {"type": "wait", "delay_ms": 1}})
        ctx = RunContext(trace_id="t", tenant_id="ten", user_id="u")
        output, error = await executor._execute_compensation(ctx, node, {}, {})
        assert error is None
        assert output["waited_ms"] == 1

    async def test_compensation_unsupported_type(self):
        from backend.app.core.contracts import RunContext
        executor = _make_executor()
        node = WorkflowNode(id="n", type=WorkflowNodeType.INPUT,
                            config={"on_failure": {"type": "invalid_type"}})
        ctx = RunContext(trace_id="t", tenant_id="ten", user_id="u")
        output, error = await executor._execute_compensation(ctx, node, {}, {})
        assert output is None
        assert "Unsupported" in error

    async def test_compensation_no_config(self):
        from backend.app.core.contracts import RunContext
        executor = _make_executor()
        node = WorkflowNode(id="n", type=WorkflowNodeType.INPUT)
        ctx = RunContext(trace_id="t", tenant_id="ten", user_id="u")
        output, error = await executor._execute_compensation(ctx, node, {}, {})
        # Default compensation type is transform
        assert error is None


# ---------------------------------------------------------------------------
# WorkflowRuntimeManager
# ---------------------------------------------------------------------------

class TestWorkflowRuntimeManager:
    async def test_start_and_complete(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        record = await runtime.start(defn.id, {"x": 1})
        assert record.status == WorkflowRunStatus.RUNNING
        # Wait for task to complete
        task = runtime._tasks.get(record.run_id)
        if task:
            await task
        final = repo.get_run(record.run_id)
        assert final.status == WorkflowRunStatus.COMPLETED

    async def test_start_not_found(self):
        repo = WorkflowRepository()
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await runtime.start("nonexistent")

    async def test_pause_no_active_run(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        with pytest.raises(WorkflowExecutionError, match="No active"):
            await runtime.pause_latest(defn.id)

    async def test_resume_no_paused_run(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        with pytest.raises(WorkflowExecutionError, match="No paused"):
            await runtime.resume_latest(defn.id)

    async def test_cancel_no_active_run(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        with pytest.raises(WorkflowExecutionError, match="No active"):
            await runtime.cancel_latest(defn.id)

    async def test_list_interrupted_runs(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        # Simulate an interrupted run
        run = WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="wf", status=WorkflowRunStatus.RUNNING
        )
        repo.record_run(run)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        interrupted = runtime.list_interrupted_runs()
        assert len(interrupted) == 1
        assert interrupted[0].run_id == run.run_id

    async def test_recover_interrupted_runs_resume(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        run = WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="wf", status=WorkflowRunStatus.RUNNING,
            resume_cursor=0,
        )
        repo.record_run(run)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        recovered = await runtime.recover_interrupted_runs(resume=True)
        assert len(recovered) == 1
        # Wait for recovery task
        task = runtime._tasks.get(run.run_id)
        if task:
            await task

    async def test_recover_interrupted_runs_mark_failed(self):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        run = WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="wf", status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        recovered = await runtime.recover_interrupted_runs(resume=False)
        assert len(recovered) == 1
        assert recovered[0].status == WorkflowRunStatus.FAILED

    def test_cleanup_run(self):
        repo = WorkflowRepository()
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        runtime._tasks["r1"] = MagicMock()
        runtime._paused.add("r1")
        runtime._approved["r1"] = {}
        runtime._cleanup_run("r1")
        assert "r1" not in runtime._tasks
        assert "r1" not in runtime._paused
        assert "r1" not in runtime._approved


# ---------------------------------------------------------------------------
# WorkflowScheduler
# ---------------------------------------------------------------------------

class TestWorkflowScheduler:
    def _make_scheduler(self, tmp_path=None):
        repo = WorkflowRepository()
        defn = _simple_definition()
        repo.upsert_definition(defn)
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        schedule_store = WorkflowScheduleStore(
            storage_path=tmp_path / "sched.json" if tmp_path else None
        )
        scheduler = WorkflowScheduler(
            repository=repo, runtime=runtime, schedule_store=schedule_store
        )
        return scheduler, defn, repo, runtime

    def test_schedule_with_delay(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={"x": 1}, delay_seconds=60)
        record = scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])
        assert record.status == WorkflowScheduleStatus.PENDING
        assert record.workflow_id == defn.id

    def test_schedule_with_cron(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={}, cron="*/5 * * * *")
        record = scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])
        assert record.cron == "*/5 * * * *"

    def test_schedule_with_run_at(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        run_at = datetime(2099, 1, 1, tzinfo=UTC)
        req = WorkflowScheduleRequest(inputs={}, run_at=run_at)
        record = scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])
        assert record.run_at == run_at

    def test_schedule_invalid_cron(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={}, cron="invalid cron")
        with pytest.raises(WorkflowExecutionError):
            scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])

    def test_schedule_workflow_not_found(self, tmp_path):
        scheduler, _, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={})
        with pytest.raises(WorkflowExecutionError, match="not found"):
            scheduler.schedule("nonexistent", req, tenant_id="t", user_id="u", permission_scope=[])

    async def test_run_due(self, tmp_path):
        scheduler, defn, repo, runtime = self._make_scheduler(tmp_path)
        # Create a due schedule
        past = datetime(2024, 1, 1, tzinfo=UTC)
        scheduler.schedule_store.create(
            workflow_id=defn.id, inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=past,
        )
        triggered = await scheduler.run_due()
        assert len(triggered) == 1
        assert triggered[0].status == WorkflowScheduleStatus.TRIGGERED
        # Wait for the started task
        for task in list(runtime._tasks.values()):
            if not task.done():
                await task

    async def test_run_due_cron_reschedule(self, tmp_path):
        scheduler, defn, repo, runtime = self._make_scheduler(tmp_path)
        past = datetime(2024, 1, 1, tzinfo=UTC)
        scheduler.schedule_store.create(
            workflow_id=defn.id, inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=past, cron="*/5 * * * *",
        )
        triggered = await scheduler.run_due()
        assert len(triggered) == 1
        # Cron schedule should be re-armed (still PENDING)
        assert triggered[0].status == WorkflowScheduleStatus.PENDING
        for task in list(runtime._tasks.values()):
            if not task.done():
                await task

    async def test_run_due_failure(self, tmp_path):
        repo = WorkflowRepository()
        # Don't add definition so start() fails
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        schedule_store = WorkflowScheduleStore()
        scheduler = WorkflowScheduler(repository=repo, runtime=runtime, schedule_store=schedule_store)
        past = datetime(2024, 1, 1, tzinfo=UTC)
        schedule_store.create(
            workflow_id="missing-wf", inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=past,
        )
        triggered = await scheduler.run_due()
        assert len(triggered) == 1
        assert triggered[0].status == WorkflowScheduleStatus.FAILED

    async def test_run_due_cron_failure_reschedule(self, tmp_path):
        repo = WorkflowRepository()
        executor = _make_executor(repo)
        runtime = WorkflowRuntimeManager(executor=executor, repository=repo)
        schedule_store = WorkflowScheduleStore()
        scheduler = WorkflowScheduler(repository=repo, runtime=runtime, schedule_store=schedule_store)
        past = datetime(2024, 1, 1, tzinfo=UTC)
        schedule_store.create(
            workflow_id="missing-wf", inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=past, cron="*/5 * * * *",
        )
        triggered = await scheduler.run_due()
        assert len(triggered) == 1
        # Cron failure should reschedule (still PENDING)
        assert triggered[0].status == WorkflowScheduleStatus.PENDING
        assert triggered[0].error is not None

    def test_cancel_schedule(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={}, delay_seconds=3600)
        record = scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])
        canceled = scheduler.cancel(record.schedule_id)
        assert canceled is not None
        assert canceled.status == WorkflowScheduleStatus.CANCELED

    def test_cancel_nonexistent(self, tmp_path):
        scheduler, _, _, _ = self._make_scheduler(tmp_path)
        assert scheduler.cancel("nonexistent") is None

    def test_cancel_already_triggered(self, tmp_path):
        scheduler, defn, _, _ = self._make_scheduler(tmp_path)
        req = WorkflowScheduleRequest(inputs={}, delay_seconds=3600)
        record = scheduler.schedule(defn.id, req, tenant_id="t", user_id="u", permission_scope=[])
        scheduler.schedule_store.mark(record.schedule_id, WorkflowScheduleStatus.TRIGGERED)
        assert scheduler.cancel(record.schedule_id) is None
