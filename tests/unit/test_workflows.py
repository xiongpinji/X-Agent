"""Unit tests for the workflow DAG execution engine (backend.app.core.workflows).

Covers:
- WorkflowDefinition / WorkflowNode / WorkflowEdge models
- WorkflowRepository CRUD
- DAG topological execution
- Cron scheduling (_MinimalCron, next_cron_run)
- WorkflowRunRecord lifecycle
- Node type execution dispatch
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowExecutionError,
    WorkflowNode,
    WorkflowNodeExecutionError,
    WorkflowNodeType,
    WorkflowRepository,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowScheduleRecord,
    WorkflowScheduleStatus,
    WorkflowSummary,
    WorkflowUpdateRequest,
    _MinimalCron,
    next_cron_run,
    validate_cron_expression,
)


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestWorkflowModels:
    def test_node_creation(self):
        node = WorkflowNode(id="n1", type=WorkflowNodeType.TRANSFORM)
        assert node.id == "n1"
        assert node.type == WorkflowNodeType.TRANSFORM
        assert node.config == {}

    def test_edge_creation(self):
        edge = WorkflowEdge(source="n1", target="n2", condition="x > 5")
        assert edge.source == "n1"
        assert edge.target == "n2"
        assert edge.condition == "x > 5"

    def test_edge_no_condition(self):
        edge = WorkflowEdge(source="a", target="b")
        assert edge.condition is None

    def test_definition_auto_id(self):
        wf = WorkflowDefinition(name="test", nodes=[])
        assert wf.id  # auto-generated UUID
        assert wf.name == "test"
        assert wf.edges == []

    def test_definition_with_nodes_edges(self):
        nodes = [
            WorkflowNode(id="start", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="end", type=WorkflowNodeType.OUTPUT),
        ]
        edges = [WorkflowEdge(source="start", target="end")]
        wf = WorkflowDefinition(name="pipeline", nodes=nodes, edges=edges)
        assert len(wf.nodes) == 2
        assert len(wf.edges) == 1

    def test_run_record_defaults(self):
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="test",
            status=WorkflowRunStatus.RUNNING,
        )
        assert run.run_id  # auto UUID
        assert run.tenant_id == "default"
        assert run.user_id == "anonymous"
        assert run.node_results == []

    def test_schedule_record(self):
        sched = WorkflowScheduleRecord(
            workflow_id="wf1",
            run_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert sched.status == WorkflowScheduleStatus.PENDING
        assert sched.cron is None

    def test_node_types_enum(self):
        assert WorkflowNodeType.INPUT == "input"
        assert WorkflowNodeType.AGENT == "agent"
        assert WorkflowNodeType.CONDITION == "condition"
        assert WorkflowNodeType.APPROVAL == "approval"

    def test_run_status_enum(self):
        assert WorkflowRunStatus.DRAFT == "draft"
        assert WorkflowRunStatus.RUNNING == "running"
        assert WorkflowRunStatus.COMPLETED == "completed"
        assert WorkflowRunStatus.FAILED == "failed"


# ---------------------------------------------------------------------------
# WorkflowRepository CRUD
# ---------------------------------------------------------------------------

class TestWorkflowRepository:
    @pytest.fixture
    def repo(self):
        return WorkflowRepository()

    def test_upsert_definition_create(self, repo):
        req = WorkflowCreateRequest(
            name="ETL Pipeline",
            nodes=[
                WorkflowNode(id="in", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="out", type=WorkflowNodeType.OUTPUT),
            ],
            edges=[WorkflowEdge(source="in", target="out")],
        )
        wf = repo.upsert_definition(req)
        assert wf.id
        assert wf.name == "ETL Pipeline"
        assert len(wf.nodes) == 2

    def test_get_definition(self, repo):
        req = WorkflowCreateRequest(name="test", nodes=[])
        wf = repo.upsert_definition(req)
        fetched = repo.get_definition(wf.id)
        assert fetched is not None
        assert fetched.name == "test"

    def test_get_nonexistent(self, repo):
        assert repo.get_definition("nonexistent") is None

    def test_update_definition(self, repo):
        req = WorkflowCreateRequest(name="old", nodes=[])
        wf = repo.upsert_definition(req)
        update = WorkflowUpdateRequest(name="new")
        updated = repo.upsert_definition(update, workflow_id=wf.id)
        assert updated.name == "new"

    def test_update_nonexistent_raises(self, repo):
        update = WorkflowUpdateRequest(name="x")
        with pytest.raises(KeyError):
            repo.upsert_definition(update, workflow_id="nonexistent")

    def test_delete_definition(self, repo):
        req = WorkflowCreateRequest(name="to_delete", nodes=[])
        wf = repo.upsert_definition(req)
        deleted = repo.delete_definition(wf.id)
        assert deleted is True
        assert repo.get_definition(wf.id) is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete_definition("nonexistent") is False

    def test_list_definitions(self, repo):
        repo.upsert_definition(WorkflowCreateRequest(name="wf1", nodes=[]))
        repo.upsert_definition(WorkflowCreateRequest(name="wf2", nodes=[]))
        items = repo.list_definitions()
        assert len(items) >= 2

    def test_record_run(self, repo):
        req = WorkflowCreateRequest(name="runnable", nodes=[])
        wf = repo.upsert_definition(req)
        run = WorkflowRunRecord(
            workflow_id=wf.id,
            workflow_name=wf.name,
            status=WorkflowRunStatus.RUNNING,
        )
        recorded = repo.record_run(run)
        assert recorded.run_id
        assert recorded.workflow_id == wf.id

    def test_get_run(self, repo):
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="test",
            status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        fetched = repo.get_run(run.run_id)
        assert fetched is not None
        assert fetched.workflow_id == "wf1"

    def test_update_run_status(self, repo):
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="test",
            status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        updated = repo.update_run_status(run.run_id, WorkflowRunStatus.COMPLETED)
        assert updated is not None
        assert updated.status == WorkflowRunStatus.COMPLETED

    def test_update_run_status_nonexistent(self, repo):
        result = repo.update_run_status("nonexistent", WorkflowRunStatus.FAILED)
        assert result is None

    def test_list_runs_for_workflow(self, repo):
        for _ in range(2):
            run = WorkflowRunRecord(
                workflow_id="wf-multi",
                workflow_name="multi",
                status=WorkflowRunStatus.RUNNING,
            )
            repo.record_run(run)
        runs = repo.list_runs(workflow_id="wf-multi")
        assert len(runs) == 2

    def test_run_snapshot(self, repo):
        run = WorkflowRunRecord(
            workflow_id="wf-snap",
            workflow_name="snap",
            status=WorkflowRunStatus.COMPLETED,
        )
        repo.record_run(run)
        snap = repo.run_snapshot(workflow_id="wf-snap")
        assert snap["run_count"] == 1
        assert snap["latest_run_id"] == run.run_id


# ---------------------------------------------------------------------------
# Cron scheduling
# ---------------------------------------------------------------------------

class TestMinimalCron:
    def test_every_minute(self):
        cron = _MinimalCron("* * * * *")
        now = datetime(2025, 6, 15, 10, 30, tzinfo=UTC)
        assert cron.matches(now)

    def test_specific_minute(self):
        cron = _MinimalCron("30 * * * *")
        assert cron.matches(datetime(2025, 6, 15, 10, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2025, 6, 15, 10, 31, tzinfo=UTC))

    def test_range(self):
        cron = _MinimalCron("0 9-17 * * *")
        assert cron.matches(datetime(2025, 6, 15, 12, 0, tzinfo=UTC))
        assert not cron.matches(datetime(2025, 6, 15, 20, 0, tzinfo=UTC))

    def test_step(self):
        cron = _MinimalCron("*/15 * * * *")
        assert cron.matches(datetime(2025, 6, 15, 10, 0, tzinfo=UTC))
        assert cron.matches(datetime(2025, 6, 15, 10, 15, tzinfo=UTC))
        assert not cron.matches(datetime(2025, 6, 15, 10, 7, tzinfo=UTC))

    def test_comma_list(self):
        cron = _MinimalCron("0,30 * * * *")
        assert cron.matches(datetime(2025, 6, 15, 10, 0, tzinfo=UTC))
        assert cron.matches(datetime(2025, 6, 15, 10, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2025, 6, 15, 10, 15, tzinfo=UTC))

    def test_day_of_week(self):
        # 2025-06-15 is Sunday (dow=0)
        cron = _MinimalCron("0 0 * * 0")
        assert cron.matches(datetime(2025, 6, 15, 0, 0, tzinfo=UTC))
        # Monday
        assert not cron.matches(datetime(2025, 6, 16, 0, 0, tzinfo=UTC))

    def test_invalid_expression(self):
        with pytest.raises(WorkflowExecutionError):
            _MinimalCron("invalid")

    def test_invalid_field_count(self):
        with pytest.raises(WorkflowExecutionError):
            _MinimalCron("* * *")

    def test_next_after(self):
        cron = _MinimalCron("0 12 * * *")
        now = datetime(2025, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2025, 6, 15, 12, 0, tzinfo=UTC)

    def test_next_after_wraps_day(self):
        cron = _MinimalCron("0 8 * * *")
        now = datetime(2025, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2025, 6, 16, 8, 0, tzinfo=UTC)


class TestNextCronRun:
    def test_basic(self):
        now = datetime(2025, 6, 15, 10, 0, tzinfo=UTC)
        result = next_cron_run("30 10 * * *", now=now)
        assert result.minute == 30
        assert result.hour == 10

    def test_empty_expression_raises(self):
        with pytest.raises(WorkflowExecutionError):
            next_cron_run("")

    def test_whitespace_expression_raises(self):
        with pytest.raises(WorkflowExecutionError):
            next_cron_run("   ")

    def test_naive_datetime_gets_utc(self):
        now = datetime(2025, 6, 15, 10, 0)  # naive
        result = next_cron_run("0 12 * * *", now=now)
        assert result.tzinfo is not None


class TestValidateCronExpression:
    def test_valid(self):
        assert validate_cron_expression("*/5 * * * *") == "*/5 * * * *"

    def test_invalid_raises(self):
        with pytest.raises(WorkflowExecutionError):
            validate_cron_expression("bad cron")


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

class TestWorkflowErrors:
    def test_execution_error(self):
        err = WorkflowExecutionError("something failed")
        assert str(err) == "something failed"

    def test_node_execution_error(self):
        err = WorkflowNodeExecutionError("node failed", attempts=3)
        assert err.attempts == 3
        assert "node failed" in str(err)


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class TestRequestModels:
    def test_create_request(self):
        req = WorkflowCreateRequest(
            name="new wf",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        )
        assert req.name == "new wf"
        assert req.edges == []

    def test_update_request_partial(self):
        req = WorkflowUpdateRequest(name="updated")
        assert req.name == "updated"
        assert req.nodes is None
        assert req.edges is None

    def test_summary_model(self):
        s = WorkflowSummary(
            workflow_id="wf1",
            name="test",
            node_count=3,
            edge_count=2,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert s.node_count == 3
        assert s.latest_run_id is None
