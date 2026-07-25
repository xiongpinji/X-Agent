"""Deep coverage tests for workflows.py — all branches and code paths."""
import asyncio
import json
import pytest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.workflows import (
    WorkflowNodeType,
    WorkflowRunStatus,
    WorkflowScheduleStatus,
    WorkflowNode,
    WorkflowEdge,
    WorkflowDefinition,
    WorkflowNodeResult,
    WorkflowRunRecord,
    WorkflowScheduleRecord,
    WorkflowSummary,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    WorkflowRunRequest,
    WorkflowScheduleRequest,
    WorkflowChatCreateRequest,
    WorkflowRunStatusResponse,
    WorkflowControlResponse,
    WorkflowRunTimelineEvent,
    WorkflowRunDetailResponse,
    WorkflowExecutionError,
    WorkflowNodeExecutionError,
    WorkflowApprovalRequired,
    WorkflowRepository,
    WorkflowScheduleStore,
    WorkflowExecutor,
    _MinimalCron,
    next_cron_run,
    validate_cron_expression,
)
from backend.app.core.contracts import RunContext, RiskLevel


# ═══════════════════════════════════════════════════════════════════════════════
# _MinimalCron TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMinimalCron:
    def test_valid_every_minute(self):
        cron = _MinimalCron("* * * * *")
        now = datetime(2024, 6, 15, 10, 30, tzinfo=UTC)
        assert cron.matches(now)

    def test_specific_minute(self):
        cron = _MinimalCron("30 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 10, 31, tzinfo=UTC))

    def test_range_field(self):
        cron = _MinimalCron("0 9-17 * * *")
        assert cron.matches(datetime(2024, 6, 15, 9, 0, tzinfo=UTC))
        assert cron.matches(datetime(2024, 6, 15, 17, 0, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 18, 0, tzinfo=UTC))

    def test_step_field(self):
        cron = _MinimalCron("*/15 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 0, tzinfo=UTC))
        assert cron.matches(datetime(2024, 6, 15, 10, 15, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 10, 7, tzinfo=UTC))

    def test_comma_list(self):
        cron = _MinimalCron("0,30 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 0, tzinfo=UTC))
        assert cron.matches(datetime(2024, 6, 15, 10, 30, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 10, 15, tzinfo=UTC))

    def test_day_of_week_sunday_normalization(self):
        # 7 means Sunday, should be normalized to 0
        cron = _MinimalCron("0 0 * * 7")
        # 2024-06-16 is a Sunday
        assert cron.matches(datetime(2024, 6, 16, 0, 0, tzinfo=UTC))

    def test_dom_and_dow_or_semantics(self):
        # Both dom and dow restricted -> OR semantics
        cron = _MinimalCron("0 0 1 * 1")  # 1st of month OR Monday
        # 2024-06-17 is Monday
        assert cron.matches(datetime(2024, 6, 17, 0, 0, tzinfo=UTC))
        # 2024-07-01 is 1st of month (Monday)
        assert cron.matches(datetime(2024, 7, 1, 0, 0, tzinfo=UTC))

    def test_invalid_field_count(self):
        with pytest.raises(WorkflowExecutionError, match="expected 5 fields"):
            _MinimalCron("* * *")

    def test_invalid_step_value(self):
        with pytest.raises(WorkflowExecutionError, match="Invalid cron step"):
            _MinimalCron("*/abc * * * *")

    def test_step_must_be_positive(self):
        with pytest.raises(WorkflowExecutionError, match="step must be positive"):
            _MinimalCron("*/0 * * * *")

    def test_invalid_range(self):
        with pytest.raises(WorkflowExecutionError, match="Invalid cron range"):
            _MinimalCron("a-b * * * *")

    def test_invalid_value(self):
        with pytest.raises(WorkflowExecutionError, match="Invalid cron value"):
            _MinimalCron("xyz * * * *")

    def test_out_of_range(self):
        with pytest.raises(WorkflowExecutionError, match="out of range"):
            _MinimalCron("60 * * * *")

    def test_empty_item_in_comma_list(self):
        with pytest.raises(WorkflowExecutionError, match="empty item"):
            _MinimalCron("0, * * * *")

    def test_next_after(self):
        cron = _MinimalCron("30 10 * * *")
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2024, 6, 15, 10, 30, tzinfo=UTC)

    def test_next_after_wraps_day(self):
        cron = _MinimalCron("0 9 * * *")
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        nxt = cron.next_after(now)
        assert nxt == datetime(2024, 6, 16, 9, 0, tzinfo=UTC)

    def test_vixie_shorthand(self):
        # "5/10" means "5-high/10"
        cron = _MinimalCron("5/10 * * * *")
        assert cron.matches(datetime(2024, 6, 15, 10, 5, tzinfo=UTC))
        assert cron.matches(datetime(2024, 6, 15, 10, 15, tzinfo=UTC))
        assert not cron.matches(datetime(2024, 6, 15, 10, 6, tzinfo=UTC))


class TestNextCronRun:
    def test_empty_expression(self):
        with pytest.raises(WorkflowExecutionError, match="must not be empty"):
            next_cron_run("")

    def test_whitespace_expression(self):
        with pytest.raises(WorkflowExecutionError, match="must not be empty"):
            next_cron_run("   ")

    def test_valid_expression(self):
        now = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
        result = next_cron_run("30 10 * * *", now=now)
        assert result.minute == 30
        assert result.hour == 10

    def test_naive_datetime_gets_utc(self):
        now = datetime(2024, 6, 15, 10, 0)  # naive
        result = next_cron_run("30 10 * * *", now=now)
        assert result.tzinfo is not None


class TestValidateCronExpression:
    def test_valid(self):
        assert validate_cron_expression("*/5 * * * *") == "*/5 * * * *"

    def test_invalid(self):
        with pytest.raises(WorkflowExecutionError):
            validate_cron_expression("invalid")


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowRepository TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkflowRepository:
    def _make_repo(self, tmp_path):
        return WorkflowRepository(
            definition_path=tmp_path / "defs.json",
            run_path=tmp_path / "runs.jsonl",
        )

    def test_upsert_create_request(self, tmp_path):
        repo = self._make_repo(tmp_path)
        req = WorkflowCreateRequest(
            name="Test WF",
            description="A test",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        )
        defn = repo.upsert_definition(req)
        assert defn.name == "Test WF"
        assert defn.id is not None
        assert repo.definition_count() == 1

    def test_upsert_update_request(self, tmp_path):
        repo = self._make_repo(tmp_path)
        req = WorkflowCreateRequest(
            name="WF1",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        )
        defn = repo.upsert_definition(req)
        update = WorkflowUpdateRequest(name="WF1 Updated")
        updated = repo.upsert_definition(update, workflow_id=defn.id)
        assert updated.name == "WF1 Updated"

    def test_upsert_update_nonexistent_raises(self, tmp_path):
        repo = self._make_repo(tmp_path)
        update = WorkflowUpdateRequest(name="X")
        with pytest.raises(KeyError):
            repo.upsert_definition(update, workflow_id="nonexistent")

    def test_upsert_definition_object(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = WorkflowDefinition(
            name="Direct",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.OUTPUT)],
        )
        result = repo.upsert_definition(defn)
        assert result.name == "Direct"

    def test_list_definitions_sorted(self, tmp_path):
        repo = self._make_repo(tmp_path)
        for i in range(3):
            repo.upsert_definition(WorkflowCreateRequest(
                name=f"WF{i}",
                nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
            ))
        defs = repo.list_definitions()
        assert len(defs) == 3

    def test_get_definition(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="WF",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        ))
        assert repo.get_definition(defn.id) is not None
        assert repo.get_definition("nope") is None

    def test_delete_definition(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="WF",
            nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        ))
        assert repo.delete_definition(defn.id) is True
        assert repo.delete_definition(defn.id) is False

    def test_validate_duplicate_node_ids(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="unique"):
            repo.upsert_definition(WorkflowCreateRequest(
                name="Bad",
                nodes=[
                    WorkflowNode(id="n1", type=WorkflowNodeType.INPUT),
                    WorkflowNode(id="n1", type=WorkflowNodeType.OUTPUT),
                ],
            ))

    def test_validate_unknown_edge_node(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="unknown node"):
            repo.upsert_definition(WorkflowCreateRequest(
                name="Bad",
                nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
                edges=[WorkflowEdge(source="n1", target="n99")],
            ))

    def test_validate_cycle(self, tmp_path):
        repo = self._make_repo(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="cycle"):
            repo.upsert_definition(WorkflowCreateRequest(
                name="Cycle",
                nodes=[
                    WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
                    WorkflowNode(id="b", type=WorkflowNodeType.OUTPUT),
                ],
                edges=[
                    WorkflowEdge(source="a", target="b"),
                    WorkflowEdge(source="b", target="a"),
                ],
            ))

    def test_record_and_get_run(self, tmp_path):
        repo = self._make_repo(tmp_path)
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="Test",
            status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        assert repo.get_run(run.run_id) is not None
        assert repo.run_count() == 1

    def test_update_run_status(self, tmp_path):
        repo = self._make_repo(tmp_path)
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="Test",
            status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        updated = repo.update_run_status(run.run_id, WorkflowRunStatus.COMPLETED)
        assert updated.status == WorkflowRunStatus.COMPLETED
        assert repo.update_run_status("nope", WorkflowRunStatus.FAILED) is None

    def test_update_run_status_with_error_and_cursor(self, tmp_path):
        repo = self._make_repo(tmp_path)
        run = WorkflowRunRecord(
            workflow_id="wf1", workflow_name="T", status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        updated = repo.update_run_status(
            run.run_id, WorkflowRunStatus.FAILED, error="boom", resume_cursor=3
        )
        assert updated.error == "boom"
        assert updated.resume_cursor == 3

    def test_list_runs_with_filter(self, tmp_path):
        repo = self._make_repo(tmp_path)
        for i in range(3):
            repo.record_run(WorkflowRunRecord(
                workflow_id=f"wf{i % 2}", workflow_name="T",
                status=WorkflowRunStatus.COMPLETED,
            ))
        assert len(repo.list_runs(workflow_id="wf0")) == 2
        assert len(repo.list_runs()) == 3

    def test_update_run_progress(self, tmp_path):
        repo = self._make_repo(tmp_path)
        run = WorkflowRunRecord(
            workflow_id="wf1", workflow_name="T", status=WorkflowRunStatus.RUNNING,
        )
        repo.record_run(run)
        results = [WorkflowNodeResult(
            node_id="n1", node_type=WorkflowNodeType.INPUT,
            status=WorkflowRunStatus.COMPLETED,
        )]
        updated = repo.update_run_progress(
            run.run_id, node_results=results, resume_cursor=1, worker_id="w1"
        )
        assert updated.resume_cursor == 1
        assert updated.worker_id == "w1"
        assert repo.update_run_progress("nope", node_results=[], resume_cursor=0) is None

    def test_count_runs(self, tmp_path):
        repo = self._make_repo(tmp_path)
        repo.record_run(WorkflowRunRecord(workflow_id="a", workflow_name="T", status=WorkflowRunStatus.COMPLETED))
        repo.record_run(WorkflowRunRecord(workflow_id="b", workflow_name="T", status=WorkflowRunStatus.COMPLETED))
        assert repo.count_runs() == 2
        assert repo.count_runs("a") == 1

    def test_latest_run_for(self, tmp_path):
        repo = self._make_repo(tmp_path)
        repo.record_run(WorkflowRunRecord(workflow_id="a", workflow_name="T", status=WorkflowRunStatus.COMPLETED))
        assert repo.latest_run_for("a") is not None
        assert repo.latest_run_for("z") is None

    def test_summary_for(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="WF", nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        ))
        summary = repo.summary_for(defn.id)
        assert summary.name == "WF"
        assert summary.node_count == 1

    def test_run_snapshot(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="WF", nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        ))
        snap = repo.run_snapshot(defn.id)
        assert snap["run_count"] == 0

    def test_persistence_reload(self, tmp_path):
        def_path = tmp_path / "defs.json"
        run_path = tmp_path / "runs.jsonl"
        repo1 = WorkflowRepository(definition_path=def_path, run_path=run_path)
        defn = repo1.upsert_definition(WorkflowCreateRequest(
            name="Persist", nodes=[WorkflowNode(id="n1", type=WorkflowNodeType.INPUT)],
        ))
        repo1.record_run(WorkflowRunRecord(
            workflow_id=defn.id, workflow_name="Persist", status=WorkflowRunStatus.COMPLETED,
        ))
        # Reload
        repo2 = WorkflowRepository(definition_path=def_path, run_path=run_path)
        assert repo2.get_definition(defn.id) is not None
        assert repo2.run_count() == 1

    def test_load_corrupt_definitions(self, tmp_path):
        def_path = tmp_path / "defs.json"
        def_path.write_text("not json{{{", encoding="utf-8")
        repo = WorkflowRepository(definition_path=def_path)
        assert repo.definition_count() == 0

    def test_topological_order(self, tmp_path):
        repo = self._make_repo(tmp_path)
        defn = WorkflowDefinition(
            name="Topo",
            nodes=[
                WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
                WorkflowNode(id="b", type=WorkflowNodeType.TRANSFORM),
                WorkflowNode(id="c", type=WorkflowNodeType.OUTPUT),
            ],
            edges=[
                WorkflowEdge(source="a", target="b"),
                WorkflowEdge(source="b", target="c"),
            ],
        )
        order = repo._topological_order(defn)
        assert order == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowScheduleStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkflowScheduleStore:
    def test_create_and_get(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        rec = store.create(
            workflow_id="wf1", inputs={"x": 1}, tenant_id="t1",
            user_id="u1", permission_scope=["tools:read"],
            run_at=datetime(2024, 6, 15, 10, 0, tzinfo=UTC),
        )
        assert store.get(rec.schedule_id) is not None
        assert rec.status == WorkflowScheduleStatus.PENDING

    def test_create_naive_datetime(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        rec = store.create(
            workflow_id="wf1", inputs={}, tenant_id="t1",
            user_id="u1", permission_scope=[],
            run_at=datetime(2024, 6, 15, 10, 0),  # naive
        )
        assert rec.run_at.tzinfo is not None

    def test_list_with_filters(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        store.create(workflow_id="wf2", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=datetime(2024, 6, 16, tzinfo=UTC))
        assert len(store.list(workflow_id="wf1")) == 1
        assert len(store.list()) == 2

    def test_due(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        past = datetime(2024, 1, 1, tzinfo=UTC)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=past)
        store.create(workflow_id="wf2", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=future)
        due = store.due(now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(due) == 1

    def test_acquire_due(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        past = datetime(2024, 1, 1, tzinfo=UTC)
        store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=past)
        acquired = store.acquire_due(worker_id="w1", now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(acquired) == 1
        assert acquired[0].locked_by == "w1"
        # Second acquire should not get it again (locked)
        acquired2 = store.acquire_due(worker_id="w2", now=datetime(2024, 6, 15, tzinfo=UTC))
        assert len(acquired2) == 0

    def test_mark(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        rec = store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        marked = store.mark(rec.schedule_id, WorkflowScheduleStatus.TRIGGERED, run_id="r1")
        assert marked.status == WorkflowScheduleStatus.TRIGGERED
        assert marked.run_id == "r1"
        assert store.mark("nope", WorkflowScheduleStatus.FAILED) is None

    def test_count(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                     permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        assert store.count() == 1
        assert store.count(WorkflowScheduleStatus.PENDING) == 1
        assert store.count(WorkflowScheduleStatus.FAILED) == 0

    def test_reschedule(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        rec = store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC),
                           cron="0 10 * * *")
        new_time = datetime(2024, 6, 16, 10, 0, tzinfo=UTC)
        rescheduled = store.reschedule(rec.schedule_id, run_at=new_time, run_id="r1")
        assert rescheduled.status == WorkflowScheduleStatus.PENDING
        assert rescheduled.run_at == new_time
        assert store.reschedule("nope", run_at=new_time) is None

    def test_reschedule_naive_datetime(self, tmp_path):
        store = WorkflowScheduleStore(storage_path=tmp_path / "sched.json")
        rec = store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                           permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        rescheduled = store.reschedule(rec.schedule_id, run_at=datetime(2024, 6, 16, 10, 0))
        assert rescheduled.run_at.tzinfo is not None

    def test_persistence(self, tmp_path):
        path = tmp_path / "sched.json"
        store1 = WorkflowScheduleStore(storage_path=path)
        store1.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                      permission_scope=[], run_at=datetime(2024, 6, 15, tzinfo=UTC))
        store2 = WorkflowScheduleStore(storage_path=path)
        assert store2.count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# WorkflowExecutor TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _make_executor(tmp_path, approval_store=None):
    agent = MagicMock()
    agent.tools = MagicMock()
    agent.tools.execute = AsyncMock()
    agent.run = AsyncMock()
    repo = WorkflowRepository(
        definition_path=tmp_path / "defs.json",
        run_path=tmp_path / "runs.jsonl",
    )
    return WorkflowExecutor(
        agent=agent,
        repository=repo,
        approval_store=approval_store,
    ), repo, agent


class TestWorkflowExecutor:
    async def test_execute_not_found(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await executor.execute("nonexistent")

    async def test_execute_simple_input_output(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Simple",
            nodes=[
                WorkflowNode(id="in1", type=WorkflowNodeType.INPUT, config={"key": "name"}),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"from": "in1"}),
            ],
            edges=[WorkflowEdge(source="in1", target="out1")],
        ))
        result = await executor.execute(defn.id, inputs={"name": "hello"})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_transform_node(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Transform",
            nodes=[
                WorkflowNode(id="in1", type=WorkflowNodeType.INPUT, config={"key": "x"}),
                WorkflowNode(id="t1", type=WorkflowNodeType.TRANSFORM, config={"template": "{{in1}}"}),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"from": "t1"}),
            ],
            edges=[
                WorkflowEdge(source="in1", target="t1"),
                WorkflowEdge(source="t1", target="out1"),
            ],
        ))
        result = await executor.execute(defn.id, inputs={"x": "world"})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_tool_node(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        agent.tools.execute.return_value = MagicMock(
            model_dump=lambda mode="json": {"tool_name": "echo", "success": True}
        )
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="ToolWF",
            nodes=[
                WorkflowNode(id="t1", type=WorkflowNodeType.TOOL, config={
                    "tool_name": "echo", "arguments": {"text": "hi"}
                }),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"from": "t1"}),
            ],
            edges=[WorkflowEdge(source="t1", target="out1")],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_condition_node_true(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Cond",
            nodes=[
                WorkflowNode(id="in1", type=WorkflowNodeType.INPUT, config={"key": "val"}),
                WorkflowNode(id="c1", type=WorkflowNodeType.CONDITION, config={
                    "left": "{{in1}}", "right": "yes", "operator": "equals"
                }),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"value": "done"}),
            ],
            edges=[
                WorkflowEdge(source="in1", target="c1"),
                WorkflowEdge(source="c1", target="out1"),
            ],
        ))
        result = await executor.execute(defn.id, inputs={"val": "yes"})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_wait_node(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Wait",
            nodes=[
                WorkflowNode(id="w1", type=WorkflowNodeType.WAIT, config={"delay_ms": 1}),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"from": "w1"}),
            ],
            edges=[WorkflowEdge(source="w1", target="out1")],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_node_failure_with_compensation(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        agent.tools.execute.side_effect = RuntimeError("tool broke")
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Fail",
            nodes=[
                WorkflowNode(id="t1", type=WorkflowNodeType.TOOL, config={
                    "tool_name": "echo", "arguments": {},
                    "on_failure": {"type": "transform", "template": "compensated"},
                }),
            ],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.FAILED

    async def test_execute_with_retry(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        call_count = {"n": 0}
        async def flaky_tool(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("transient")
            return MagicMock(model_dump=lambda mode="json": {"success": True})
        agent.tools.execute = flaky_tool
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Retry",
            nodes=[
                WorkflowNode(id="t1", type=WorkflowNodeType.TOOL, config={
                    "tool_name": "echo", "arguments": {},
                    "max_retries": 3, "retry_delay_ms": 1,
                }),
            ],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_execute_approval_node_no_store(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path, approval_store=None)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="Approval",
            nodes=[
                WorkflowNode(id="a1", type=WorkflowNodeType.APPROVAL, config={}),
            ],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.FAILED

    async def test_execute_approval_node_requires_approval(self, tmp_path):
        from backend.app.core.approvals import ApprovalStore
        approval_store = ApprovalStore()
        executor, repo, agent = _make_executor(tmp_path, approval_store=approval_store)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="ApprovalWF",
            nodes=[
                WorkflowNode(id="a1", type=WorkflowNodeType.APPROVAL, config={
                    "risk_level": "high", "reason": "Need approval"
                }),
            ],
        ))
        result = await executor.execute(defn.id, inputs={})
        assert result.status == WorkflowRunStatus.NEEDS_APPROVAL
        assert result.pending_approval_id is not None

    async def test_execute_edge_condition_skips_node(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = repo.upsert_definition(WorkflowCreateRequest(
            name="SkipNode",
            nodes=[
                WorkflowNode(id="in1", type=WorkflowNodeType.INPUT, config={"key": "x"}),
                WorkflowNode(id="out1", type=WorkflowNodeType.OUTPUT, config={"value": "skipped"}),
            ],
            edges=[WorkflowEdge(source="in1", target="out1", condition="false")],
        ))
        result = await executor.execute(defn.id, inputs={"x": "val"})
        assert result.status == WorkflowRunStatus.COMPLETED

    async def test_resume_not_found(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        with pytest.raises(WorkflowExecutionError, match="not found"):
            await executor.resume("nonexistent")

    async def test_resume_non_resumable_status(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        run = WorkflowRunRecord(
            workflow_id="wf1", workflow_name="T", status=WorkflowRunStatus.COMPLETED,
        )
        repo.record_run(run)
        with pytest.raises(WorkflowExecutionError, match="not resumable"):
            await executor.resume(run.run_id)

    async def test_topological_levels(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        defn = WorkflowDefinition(
            name="Levels",
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
        levels = executor._topological_levels(defn)
        assert len(levels) >= 2

    async def test_compare_operators(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        assert executor._compare(1, 1, "equals") is True
        assert executor._compare(1, 2, "not_equals") is True
        assert executor._compare(2, 1, "gt") is True
        assert executor._compare(2, 2, "gte") is True
        assert executor._compare(1, 2, "lt") is True
        assert executor._compare(2, 2, "lte") is True
        assert executor._compare("hello world", "world", "contains") is True
        assert executor._compare(1, None, "truthy") is True
        assert executor._compare(0, None, "falsy") is True
        with pytest.raises(WorkflowExecutionError, match="Unsupported"):
            executor._compare(1, 1, "invalid_op")

    async def test_evaluate_edge_condition_bool(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        edge = WorkflowEdge(source="a", target="b", condition=None)
        assert executor._evaluate_edge_condition(edge, {}, {}) is True

    async def test_evaluate_edge_condition_string_true(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        edge = WorkflowEdge(source="a", target="b", condition="true")
        assert executor._evaluate_edge_condition(edge, {}, {}) is True
        edge2 = WorkflowEdge(source="a", target="b", condition="false")
        assert executor._evaluate_edge_condition(edge2, {}, {}) is False

    async def test_workflow_recovery_hint(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        hint = executor._workflow_recovery_hint({}, error=None)
        assert "branch" in hint

    async def test_workflow_recovery_hint_with_error(self, tmp_path):
        executor, repo, agent = _make_executor(tmp_path)
        hint = executor._workflow_recovery_hint({}, error="something failed")
        assert "branch" in hint


# ═══════════════════════════════════════════════════════════════════════════════
# Model / Error class tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkflowModels:
    def test_node_execution_error(self):
        err = WorkflowNodeExecutionError("fail", attempts=3)
        assert err.attempts == 3
        assert str(err) == "fail"

    def test_approval_required(self):
        err = WorkflowApprovalRequired("appr-123")
        assert err.approval_id == "appr-123"
        assert "appr-123" in str(err)

    def test_workflow_run_request(self):
        req = WorkflowRunRequest(inputs={"x": 1}, async_run=True)
        assert req.async_run is True

    def test_workflow_schedule_request(self):
        req = WorkflowScheduleRequest(delay_seconds=60, cron="*/5 * * * *")
        assert req.cron == "*/5 * * * *"

    def test_workflow_chat_create_request(self):
        req = WorkflowChatCreateRequest(request="Build a workflow")
        assert req.request == "Build a workflow"

    def test_workflow_run_status_response(self):
        resp = WorkflowRunStatusResponse(
            workflow_id="wf1", workflow_name="T",
            status=WorkflowRunStatus.COMPLETED,
            updated_at=datetime.now(UTC),
        )
        assert resp.run_count == 0

    def test_workflow_control_response(self):
        resp = WorkflowControlResponse(
            run_id="r1", workflow_id="wf1",
            status=WorkflowRunStatus.CANCELED, changed=True, message="canceled",
        )
        assert resp.changed is True

    def test_workflow_run_timeline_event(self):
        evt = WorkflowRunTimelineEvent(
            timestamp=datetime.now(UTC), kind="node.started",
            node_id="n1", node_type=WorkflowNodeType.TOOL,
        )
        assert evt.kind == "node.started"

    def test_workflow_run_detail_response(self):
        run = WorkflowRunRecord(
            workflow_id="wf1", workflow_name="T", status=WorkflowRunStatus.COMPLETED,
        )
        resp = WorkflowRunDetailResponse(run=run)
        assert resp.timeline == []
