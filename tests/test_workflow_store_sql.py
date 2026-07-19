"""P1-07: SQL 工作流存储（SQLite 验证 SQLAlchemy 模型与 CRUD 对等性）。"""
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.core.workflow_store import (
    SQLWorkflowRepository,
    SQLWorkflowScheduleStore,
    WorkflowDefinitionRow,
    WorkflowRunRow,
    WorkflowScheduleRow,
    WorkflowStoreBase,
    build_workflow_repository,
    build_workflow_schedule_store,
    create_workflow_engine,
)
from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeResult,
    WorkflowNodeType,
    WorkflowRepository,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowScheduleStatus,
    WorkflowScheduleStore,
    WorkflowUpdateRequest,
)


@pytest.fixture()
def engine(tmp_path):
    return create_workflow_engine(f"sqlite:///{tmp_path / 'workflow.db'}")


def _workflow_request(name: str = "sql-wf") -> WorkflowCreateRequest:
    return WorkflowCreateRequest(
        name=name,
        description="demo",
        nodes=[
            WorkflowNode(id="a", type=WorkflowNodeType.INPUT),
            WorkflowNode(id="b", type=WorkflowNodeType.TRANSFORM, config={"template": "{a}-b"}),
            WorkflowNode(id="c", type=WorkflowNodeType.OUTPUT, config={"from": "b"}),
        ],
        edges=[WorkflowEdge(source="a", target="b"), WorkflowEdge(source="b", target="c")],
    )


class TestSchemaCreation:
    def test_tables_created(self, engine) -> None:
        from sqlalchemy import inspect

        from backend.app.core.workflow_store import init_workflow_store_schema

        init_workflow_store_schema(engine)
        tables = set(inspect(engine).get_table_names())
        assert {"workflow_definitions", "workflow_runs", "workflow_schedules"} <= tables

    def test_models_registered_on_dedicated_base(self) -> None:
        tables = set(WorkflowStoreBase.metadata.tables)
        assert {"workflow_definitions", "workflow_runs", "workflow_schedules"} <= tables
        assert WorkflowDefinitionRow.__tablename__ == "workflow_definitions"
        assert WorkflowRunRow.__tablename__ == "workflow_runs"
        assert WorkflowScheduleRow.__tablename__ == "workflow_schedules"


class TestSQLWorkflowRepository:
    def test_definition_crud_roundtrip(self, engine) -> None:
        repo = SQLWorkflowRepository(engine)
        created = repo.upsert_definition(_workflow_request())
        assert repo.definition_count() == 1

        fetched = repo.get_definition(created.id)
        assert fetched is not None
        assert fetched.name == "sql-wf"
        assert len(fetched.nodes) == 3
        # SQLite 读取后时区必须被归一化为 UTC（否则调度比较会 TypeError）
        assert fetched.created_at.tzinfo is not None
        assert fetched.updated_at.tzinfo is not None

        updated = repo.upsert_definition(
            WorkflowUpdateRequest(name="renamed"), workflow_id=created.id
        )
        assert updated.name == "renamed"
        assert repo.list_definitions()[0].name == "renamed"

        assert repo.delete_definition(created.id) is True
        assert repo.delete_definition(created.id) is False
        assert repo.definition_count() == 0

    def test_upsert_missing_definition_raises_key_error(self, engine) -> None:
        repo = SQLWorkflowRepository(engine)
        with pytest.raises(KeyError):
            repo.upsert_definition(WorkflowUpdateRequest(name="x"), workflow_id="missing")

    def test_definition_validation_rejects_cycle(self, engine) -> None:
        repo = SQLWorkflowRepository(engine)
        from backend.app.core.workflows import WorkflowExecutionError

        with pytest.raises(WorkflowExecutionError):
            repo.upsert_definition(
                WorkflowCreateRequest(
                    name="cyclic",
                    nodes=[
                        WorkflowNode(id="a", type=WorkflowNodeType.TRANSFORM),
                        WorkflowNode(id="b", type=WorkflowNodeType.TRANSFORM),
                    ],
                    edges=[WorkflowEdge(source="a", target="b"), WorkflowEdge(source="b", target="a")],
                )
            )

    def test_run_lifecycle_and_progress(self, engine) -> None:
        repo = SQLWorkflowRepository(engine)
        definition = repo.upsert_definition(_workflow_request())
        run = WorkflowRunRecord(
            workflow_id=definition.id,
            workflow_name=definition.name,
            status=WorkflowRunStatus.RUNNING,
            tenant_id="tenant-a",
        )
        repo.record_run(run)
        assert repo.count_runs() == 1
        assert repo.get_run(run.run_id).status == WorkflowRunStatus.RUNNING

        node_result = WorkflowNodeResult(
            node_id="a",
            node_type=WorkflowNodeType.INPUT,
            status=WorkflowRunStatus.COMPLETED,
            output={"k": 1},
        )
        progressed = repo.update_run_progress(
            run.run_id, node_results=[node_result], resume_cursor=1, worker_id="worker-1"
        )
        assert progressed.resume_cursor == 1
        assert progressed.worker_id == "worker-1"
        assert progressed.heartbeat_at is not None and progressed.heartbeat_at.tzinfo is not None
        assert len(progressed.node_results) == 1

        completed = repo.update_run_status(run.run_id, WorkflowRunStatus.COMPLETED)
        assert completed.status == WorkflowRunStatus.COMPLETED

        # 换实例（模拟重启）后仍能从 DB 读回 —— 运行态已外置
        repo2 = SQLWorkflowRepository(engine)
        reloaded = repo2.get_run(run.run_id)
        assert reloaded is not None
        assert reloaded.status == WorkflowRunStatus.COMPLETED
        assert reloaded.resume_cursor == 1
        assert reloaded.node_results[0].node_id == "a"

    def test_list_runs_orders_and_filters(self, engine) -> None:
        repo = SQLWorkflowRepository(engine)
        definition = repo.upsert_definition(_workflow_request())
        other = repo.upsert_definition(_workflow_request("other"))
        for idx in range(3):
            repo.record_run(
                WorkflowRunRecord(
                    workflow_id=definition.id,
                    workflow_name=definition.name,
                    status=WorkflowRunStatus.COMPLETED,
                    started_at=datetime(2026, 7, 20, 10, idx, tzinfo=UTC),
                )
            )
        repo.record_run(
            WorkflowRunRecord(
                workflow_id=other.id, workflow_name=other.name, status=WorkflowRunStatus.FAILED
            )
        )
        runs = repo.list_runs(workflow_id=definition.id, limit=10)
        assert len(runs) == 3
        assert runs[0].started_at > runs[-1].started_at
        assert repo.count_runs() == 4
        assert repo.count_runs(definition.id) == 3
        assert repo.latest_run_for(definition.id).run_id == runs[0].run_id

    def test_summary_matches_file_store_semantics(self, engine, tmp_path) -> None:
        sql_repo = SQLWorkflowRepository(engine)
        file_repo = WorkflowRepository(
            definition_path=tmp_path / "defs.json", run_path=tmp_path / "runs.jsonl"
        )
        for repo in (sql_repo, file_repo):
            definition = repo.upsert_definition(_workflow_request())
            repo.record_run(
                WorkflowRunRecord(
                    workflow_id=definition.id,
                    workflow_name=definition.name,
                    status=WorkflowRunStatus.COMPLETED,
                )
            )
            summary = repo.summary_for(definition.id)
            assert summary.node_count == 3
            assert summary.latest_run_status == WorkflowRunStatus.COMPLETED
            assert summary.snapshot["run_count"] == 1


class TestSQLWorkflowScheduleStore:
    def test_create_and_reload_with_cron(self, engine) -> None:
        store = SQLWorkflowScheduleStore(engine)
        record = store.create(
            workflow_id="wf-1",
            inputs={"k": "v"},
            tenant_id="tenant-a",
            user_id="user-a",
            permission_scope=["workflow:run"],
            run_at=datetime.now(UTC) + timedelta(minutes=5),
            cron="*/5 * * * *",
        )
        reloaded = store.get(record.schedule_id)
        assert reloaded is not None
        assert reloaded.cron == "*/5 * * * *"
        assert reloaded.inputs == {"k": "v"}
        assert reloaded.run_at.tzinfo is not None
        assert store.count() == 1

    def test_due_and_acquire_with_lease(self, engine) -> None:
        store = SQLWorkflowScheduleStore(engine)
        now = datetime.now(UTC)
        overdue = store.create(
            workflow_id="wf-1", inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=now - timedelta(seconds=5),
        )
        store.create(
            workflow_id="wf-1", inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=now + timedelta(hours=1),
        )
        due = store.due(now=now, limit=10)
        assert [r.schedule_id for r in due] == [overdue.schedule_id]

        acquired = store.acquire_due(worker_id="w1", lease_seconds=60, now=now, limit=10)
        assert len(acquired) == 1
        assert acquired[0].locked_by == "w1"
        assert acquired[0].locked_until > now

        # 租约未到期，其他 worker 领不到
        assert store.acquire_due(worker_id="w2", now=now, limit=10) == []
        # 租约到期后可以被重新领取
        later = now + timedelta(seconds=61)
        reacquired = store.acquire_due(worker_id="w2", now=later, limit=10)
        assert len(reacquired) == 1 and reacquired[0].locked_by == "w2"

    def test_mark_and_reschedule(self, engine) -> None:
        store = SQLWorkflowScheduleStore(engine)
        now = datetime.now(UTC)
        record = store.create(
            workflow_id="wf-1", inputs={}, tenant_id="t", user_id="u",
            permission_scope=[], run_at=now - timedelta(seconds=1), cron="* * * * *",
        )
        store.acquire_due(worker_id="w1", now=now, limit=1)
        next_fire = now + timedelta(minutes=1)
        rescheduled = store.reschedule(record.schedule_id, run_at=next_fire, run_id="run-9")
        assert rescheduled.status == WorkflowScheduleStatus.PENDING
        assert rescheduled.run_id == "run-9"
        assert rescheduled.locked_by is None
        assert rescheduled.run_at == next_fire
        assert rescheduled.snapshot["last_run_at"] is not None

        marked = store.mark(record.schedule_id, WorkflowScheduleStatus.CANCELED)
        assert marked.status == WorkflowScheduleStatus.CANCELED
        assert store.count(WorkflowScheduleStatus.CANCELED) == 1
        assert store.due(now=now + timedelta(hours=1), limit=10) == []

    def test_mark_missing_returns_none(self, engine) -> None:
        store = SQLWorkflowScheduleStore(engine)
        assert store.mark("missing", WorkflowScheduleStatus.TRIGGERED) is None
        assert store.reschedule("missing", run_at=datetime.now(UTC)) is None


class TestFactories:
    def test_file_backend_returns_file_stores(self, tmp_path) -> None:
        repo = build_workflow_repository(
            backend="file",
            definition_path=tmp_path / "d.json",
            run_path=tmp_path / "r.jsonl",
        )
        assert type(repo) is WorkflowRepository
        store = build_workflow_schedule_store(
            backend="file", storage_path=tmp_path / "s.json"
        )
        assert type(store) is WorkflowScheduleStore

    def test_db_backend_returns_sql_stores(self, tmp_path) -> None:
        url = f"sqlite:///{tmp_path / 'wf.db'}"
        repo = build_workflow_repository(backend="db", database_url=url)
        assert isinstance(repo, SQLWorkflowRepository)
        store = build_workflow_schedule_store(backend="db", database_url=url)
        assert isinstance(store, SQLWorkflowScheduleStore)

    def test_db_backend_without_url_raises(self) -> None:
        with pytest.raises(RuntimeError):
            build_workflow_repository(backend="db", database_url=None)

    def test_auto_backend_falls_back_to_file_on_bad_url(self, tmp_path, caplog) -> None:
        repo = build_workflow_repository(
            backend="auto",
            database_url="postgresql+driver_does_not_exist://u:p@127.0.0.1/db",
            definition_path=tmp_path / "d.json",
            run_path=tmp_path / "r.jsonl",
        )
        # 初始化失败必须显式降级到文件存储（有 WARNING 日志，非静默）
        assert type(repo) is WorkflowRepository
        assert any("falling back" in record.message.lower() for record in caplog.records)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError):
            build_workflow_repository(backend="cassandra")
