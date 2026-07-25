"""Deep coverage tests for backend/app/core/workflow_store.py — SQL stores + factories."""
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine

from backend.app.core.workflow_store import (
    SQLWorkflowRepository,
    SQLWorkflowScheduleStore,
    WorkflowDefinitionRow,
    WorkflowRunRow,
    WorkflowScheduleRow,
    WorkflowStoreBase,
    _as_utc,
    _normalize_record_datetimes,
    _resolve_backend,
    build_workflow_repository,
    build_workflow_schedule_store,
    create_workflow_engine,
    init_workflow_store_schema,
)
from backend.app.core.workflows import (
    WorkflowCreateRequest,
    WorkflowDefinition,
    WorkflowNodeResult,
    WorkflowRunRecord,
    WorkflowRunStatus,
    WorkflowScheduleRecord,
    WorkflowScheduleStatus,
    WorkflowUpdateRequest,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    def test_as_utc_none(self):
        assert _as_utc(None) is None

    def test_as_utc_naive(self):
        naive = datetime(2024, 1, 1, 12, 0, 0)
        result = _as_utc(naive)
        assert result.tzinfo == UTC

    def test_as_utc_aware(self):
        aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = _as_utc(aware)
        assert result is aware

    def test_normalize_record_datetimes_datetime_field(self):
        naive = datetime(2024, 6, 15, 10, 0, 0)
        payload = {"created_at": naive, "name": "test"}
        result = _normalize_record_datetimes(payload, ("created_at",))
        assert result["created_at"].tzinfo == UTC
        assert result["name"] == "test"

    def test_normalize_record_datetimes_string_field(self):
        payload = {"started_at": "2024-06-15T10:00:00"}
        result = _normalize_record_datetimes(payload, ("started_at",))
        assert isinstance(result["started_at"], datetime)
        assert result["started_at"].tzinfo == UTC

    def test_normalize_record_datetimes_missing_field(self):
        payload = {"name": "x"}
        result = _normalize_record_datetimes(payload, ("created_at",))
        assert "created_at" not in result

    def test_normalize_record_datetimes_non_datetime(self):
        payload = {"created_at": 12345}
        result = _normalize_record_datetimes(payload, ("created_at",))
        assert result["created_at"] == 12345  # unchanged


class TestCreateWorkflowEngine:
    def test_sqlite_url(self):
        engine = create_workflow_engine("sqlite:///:memory:")
        assert "sqlite" in str(engine.url)

    def test_asyncpg_conversion(self):
        # Just test URL normalization logic (won't actually connect)
        with patch("backend.app.core.workflow_store.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            create_workflow_engine("postgresql+asyncpg://user:pass@host/db")
            call_url = mock_ce.call_args[0][0]
            assert "+psycopg" in call_url
            assert "+asyncpg" not in call_url

    def test_plain_postgresql_conversion(self):
        with patch("backend.app.core.workflow_store.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            create_workflow_engine("postgresql://user:pass@host/db")
            call_url = mock_ce.call_args[0][0]
            assert "postgresql+psycopg://" in call_url

    def test_aiosqlite_conversion(self):
        with patch("backend.app.core.workflow_store.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            create_workflow_engine("sqlite+aiosqlite:///test.db")
            call_url = mock_ce.call_args[0][0]
            assert "+aiosqlite" not in call_url
            assert "sqlite" in call_url

    def test_sqlite_connect_args(self):
        with patch("backend.app.core.workflow_store.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            create_workflow_engine("sqlite:///test.db")
            kwargs = mock_ce.call_args[1]
            assert kwargs["connect_args"]["timeout"] == 30

    def test_non_sqlite_pool_pre_ping(self):
        with patch("backend.app.core.workflow_store.create_engine") as mock_ce:
            mock_ce.return_value = MagicMock()
            create_workflow_engine("postgresql+psycopg://u:p@h/d")
            kwargs = mock_ce.call_args[1]
            assert kwargs["pool_pre_ping"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# SQLWorkflowRepository
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sql_repo():
    engine = create_engine("sqlite:///:memory:", echo=False, future=True,
                           connect_args={"timeout": 30})
    repo = SQLWorkflowRepository(engine)
    return repo


class TestSQLWorkflowRepository:
    def test_init_with_string_url(self):
        repo = SQLWorkflowRepository("sqlite:///:memory:")
        assert repo._engine is not None

    def test_upsert_definition_create(self, sql_repo):
        req = WorkflowCreateRequest(name="test_wf", description="desc", nodes=[], edges=[])
        result = sql_repo.upsert_definition(req)
        assert result.name == "test_wf"
        assert result.id is not None

    def test_upsert_definition_update(self, sql_repo):
        req = WorkflowCreateRequest(name="wf1", description="d1", nodes=[], edges=[])
        created = sql_repo.upsert_definition(req)
        update = WorkflowUpdateRequest(name="wf1_updated")
        result = sql_repo.upsert_definition(update, workflow_id=created.id)
        assert result.name == "wf1_updated"
        assert result.id == created.id

    def test_upsert_definition_with_definition_object(self, sql_repo):
        defn = WorkflowDefinition(id="def1", name="direct", description="", nodes=[], edges=[])
        result = sql_repo.upsert_definition(defn)
        assert result.id == "def1"
        assert result.name == "direct"

    def test_upsert_definition_update_nonexistent_raises(self, sql_repo):
        update = WorkflowUpdateRequest(name="x")
        with pytest.raises(KeyError):
            sql_repo.upsert_definition(update, workflow_id="nonexist")

    def test_list_definitions(self, sql_repo):
        sql_repo.upsert_definition(WorkflowCreateRequest(name="a", nodes=[], edges=[]))
        sql_repo.upsert_definition(WorkflowCreateRequest(name="b", nodes=[], edges=[]))
        defs = sql_repo.list_definitions()
        assert len(defs) == 2

    def test_get_definition(self, sql_repo):
        created = sql_repo.upsert_definition(WorkflowCreateRequest(name="x", nodes=[], edges=[]))
        fetched = sql_repo.get_definition(created.id)
        assert fetched is not None
        assert fetched.name == "x"

    def test_get_definition_not_found(self, sql_repo):
        assert sql_repo.get_definition("nope") is None

    def test_delete_definition(self, sql_repo):
        created = sql_repo.upsert_definition(WorkflowCreateRequest(name="del", nodes=[], edges=[]))
        assert sql_repo.delete_definition(created.id) is True
        assert sql_repo.get_definition(created.id) is None

    def test_delete_definition_not_found(self, sql_repo):
        assert sql_repo.delete_definition("nope") is False

    def test_definition_count(self, sql_repo):
        assert sql_repo.definition_count() == 0
        sql_repo.upsert_definition(WorkflowCreateRequest(name="c1", nodes=[], edges=[]))
        assert sql_repo.definition_count() == 1

    def test_record_run_and_get(self, sql_repo):
        run = WorkflowRunRecord(
            workflow_id="wf1",
            workflow_name="test_wf",
            status=WorkflowRunStatus.RUNNING,
            tenant_id="t1",
            user_id="u1",
        )
        sql_repo.record_run(run)
        fetched = sql_repo.get_run(run.run_id)
        assert fetched is not None
        assert fetched.workflow_id == "wf1"
        assert fetched.status == WorkflowRunStatus.RUNNING

    def test_get_run_not_found(self, sql_repo):
        assert sql_repo.get_run("nope") is None

    def test_update_run_status(self, sql_repo):
        run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.RUNNING, tenant_id="t1")
        sql_repo.record_run(run)
        updated = sql_repo.update_run_status(run.run_id, WorkflowRunStatus.COMPLETED, error="err1")
        assert updated is not None
        assert updated.status == WorkflowRunStatus.COMPLETED
        assert updated.error == "err1"

    def test_update_run_status_with_cursor(self, sql_repo):
        run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.RUNNING, tenant_id="t1")
        sql_repo.record_run(run)
        updated = sql_repo.update_run_status(run.run_id, WorkflowRunStatus.FAILED, resume_cursor=5)
        assert updated.resume_cursor == 5

    def test_update_run_status_not_found(self, sql_repo):
        assert sql_repo.update_run_status("nope", WorkflowRunStatus.COMPLETED) is None

    def test_update_run_progress(self, sql_repo):
        run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.RUNNING, tenant_id="t1")
        sql_repo.record_run(run)
        node_result = WorkflowNodeResult(node_id="n1", node_type="agent", status=WorkflowRunStatus.COMPLETED)
        updated = sql_repo.update_run_progress(
            run.run_id, node_results=[node_result], resume_cursor=2, worker_id="w1"
        )
        assert updated is not None
        assert updated.resume_cursor == 2
        assert updated.worker_id == "w1"

    def test_update_run_progress_not_found(self, sql_repo):
        assert sql_repo.update_run_progress("nope", node_results=[], resume_cursor=0) is None

    def test_list_runs(self, sql_repo):
        for i in range(3):
            run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1")
            sql_repo.record_run(run)
        runs = sql_repo.list_runs(workflow_id="wf1")
        assert len(runs) == 3

    def test_list_runs_with_limit(self, sql_repo):
        for i in range(5):
            run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1")
            sql_repo.record_run(run)
        runs = sql_repo.list_runs(workflow_id="wf1", limit=2)
        assert len(runs) == 2

    def test_list_runs_no_filter(self, sql_repo):
        run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1")
        sql_repo.record_run(run)
        runs = sql_repo.list_runs()
        assert len(runs) == 1

    def test_run_count(self, sql_repo):
        assert sql_repo.run_count() == 0
        run = WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1")
        sql_repo.record_run(run)
        assert sql_repo.run_count() == 1

    def test_count_runs_with_filter(self, sql_repo):
        sql_repo.record_run(WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1"))
        sql_repo.record_run(WorkflowRunRecord(workflow_id="wf2", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1"))
        assert sql_repo.count_runs(workflow_id="wf1") == 1
        assert sql_repo.count_runs() == 2

    def test_latest_run_for(self, sql_repo):
        sql_repo.record_run(WorkflowRunRecord(workflow_id="wf1", workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1"))
        latest = sql_repo.latest_run_for("wf1")
        assert latest is not None
        assert latest.workflow_id == "wf1"

    def test_latest_run_for_empty(self, sql_repo):
        assert sql_repo.latest_run_for("nope") is None

    def test_summary_for(self, sql_repo):
        defn = sql_repo.upsert_definition(WorkflowCreateRequest(name="sum_wf", nodes=[], edges=[]))
        sql_repo.record_run(WorkflowRunRecord(workflow_id=defn.id, workflow_name="w", status=WorkflowRunStatus.COMPLETED, tenant_id="t1"))
        summary = sql_repo.summary_for(defn.id)
        assert summary.name == "sum_wf"
        assert summary.latest_run_status == WorkflowRunStatus.COMPLETED

    def test_summary_for_not_found(self, sql_repo):
        with pytest.raises(KeyError):
            sql_repo.summary_for("nope")

    def test_run_snapshot(self, sql_repo):
        defn = sql_repo.upsert_definition(WorkflowCreateRequest(name="snap_wf", nodes=[], edges=[]))
        sql_repo.record_run(WorkflowRunRecord(workflow_id=defn.id, workflow_name="w", status=WorkflowRunStatus.RUNNING, tenant_id="t1"))
        snap = sql_repo.run_snapshot(defn.id)
        assert snap["workflow_id"] == defn.id
        assert snap["run_count"] == 1
        assert snap["latest_run_status"] == WorkflowRunStatus.RUNNING

    def test_run_snapshot_empty(self, sql_repo):
        snap = sql_repo.run_snapshot("nope")
        assert snap["run_count"] == 0
        assert snap["latest_run_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# SQLWorkflowScheduleStore
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def schedule_store():
    engine = create_engine("sqlite:///:memory:", echo=False, future=True,
                           connect_args={"timeout": 30})
    store = SQLWorkflowScheduleStore(engine)
    return store


class TestSQLWorkflowScheduleStore:
    def test_init_with_string(self):
        store = SQLWorkflowScheduleStore("sqlite:///:memory:")
        assert store._engine is not None

    def test_create_schedule(self, schedule_store):
        record = schedule_store.create(
            workflow_id="wf1",
            inputs={"key": "val"},
            tenant_id="t1",
            user_id="u1",
            permission_scope=["read"],
            run_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert record.workflow_id == "wf1"
        assert record.status == WorkflowScheduleStatus.PENDING
        assert record.schedule_id is not None

    def test_create_schedule_naive_run_at(self, schedule_store):
        naive_time = datetime(2025, 6, 1, 12, 0, 0)
        record = schedule_store.create(
            workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
            permission_scope=[], run_at=naive_time,
        )
        assert record.run_at.tzinfo == UTC

    def test_create_schedule_with_cron(self, schedule_store):
        record = schedule_store.create(
            workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
            permission_scope=[], run_at=datetime.now(UTC), cron="0 * * * *",
        )
        assert record.cron == "0 * * * *"

    def test_list_schedules(self, schedule_store):
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        schedule_store.create(workflow_id="wf2", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        records = schedule_store.list()
        assert len(records) == 2

    def test_list_schedules_filter_status(self, schedule_store):
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        records = schedule_store.list(status=WorkflowScheduleStatus.PENDING)
        assert len(records) == 1
        records = schedule_store.list(status=WorkflowScheduleStatus.CANCELED)
        assert len(records) == 0

    def test_list_schedules_filter_workflow(self, schedule_store):
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        schedule_store.create(workflow_id="wf2", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        records = schedule_store.list(workflow_id="wf1")
        assert len(records) == 1

    def test_due_schedules(self, schedule_store):
        past = datetime.now(UTC) - timedelta(minutes=5)
        future = datetime.now(UTC) + timedelta(hours=1)
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=past)
        schedule_store.create(workflow_id="wf2", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=future)
        due = schedule_store.due()
        assert len(due) == 1
        assert due[0].workflow_id == "wf1"

    def test_due_with_custom_now(self, schedule_store):
        run_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=run_at)
        due = schedule_store.due(now=datetime(2025, 6, 1, 13, 0, 0, tzinfo=UTC))
        assert len(due) == 1

    def test_acquire_due(self, schedule_store):
        past = datetime.now(UTC) - timedelta(minutes=5)
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=past)
        acquired = schedule_store.acquire_due(worker_id="worker1", lease_seconds=60)
        assert len(acquired) == 1
        assert acquired[0].locked_by == "worker1"
        assert acquired[0].locked_until is not None

    def test_acquire_due_skips_locked(self, schedule_store):
        past = datetime.now(UTC) - timedelta(minutes=5)
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=past)
        # First acquire
        schedule_store.acquire_due(worker_id="w1", lease_seconds=3600)
        # Second acquire should skip (still locked)
        acquired = schedule_store.acquire_due(worker_id="w2", lease_seconds=60)
        assert len(acquired) == 0

    def test_acquire_due_expired_lock(self, schedule_store):
        past = datetime.now(UTC) - timedelta(minutes=10)
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=past)
        # Acquire with very short lease
        schedule_store.acquire_due(worker_id="w1", lease_seconds=-600)  # already expired
        # Should be acquirable again
        acquired = schedule_store.acquire_due(worker_id="w2", lease_seconds=60)
        assert len(acquired) == 1

    def test_get_schedule(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        fetched = schedule_store.get(record.schedule_id)
        assert fetched is not None
        assert fetched.workflow_id == "wf1"

    def test_get_schedule_not_found(self, schedule_store):
        assert schedule_store.get("nope") is None

    def test_mark_schedule(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        marked = schedule_store.mark(record.schedule_id, WorkflowScheduleStatus.TRIGGERED, run_id="run1")
        assert marked is not None
        assert marked.status == WorkflowScheduleStatus.TRIGGERED
        assert marked.run_id == "run1"
        assert marked.locked_by is None

    def test_mark_schedule_not_found(self, schedule_store):
        assert schedule_store.mark("nope", WorkflowScheduleStatus.TRIGGERED) is None

    def test_mark_schedule_with_error(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        marked = schedule_store.mark(record.schedule_id, WorkflowScheduleStatus.FAILED, error="boom")
        assert marked.error == "boom"

    def test_reschedule(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        new_time = datetime.now(UTC) + timedelta(hours=2)
        rescheduled = schedule_store.reschedule(record.schedule_id, run_at=new_time, run_id="r1")
        assert rescheduled is not None
        assert rescheduled.status == WorkflowScheduleStatus.PENDING
        assert rescheduled.run_id == "r1"
        assert "last_run_at" in rescheduled.snapshot

    def test_reschedule_naive_time(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        naive = datetime(2025, 12, 1, 0, 0, 0)
        rescheduled = schedule_store.reschedule(record.schedule_id, run_at=naive)
        assert rescheduled.run_at.tzinfo == UTC

    def test_reschedule_with_error(self, schedule_store):
        record = schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                                       permission_scope=[], run_at=datetime.now(UTC))
        rescheduled = schedule_store.reschedule(record.schedule_id,
                                                run_at=datetime.now(UTC) + timedelta(hours=1),
                                                error="retry")
        assert rescheduled.snapshot.get("last_error") == "retry"

    def test_reschedule_not_found(self, schedule_store):
        assert schedule_store.reschedule("nope", run_at=datetime.now(UTC)) is None

    def test_count(self, schedule_store):
        assert schedule_store.count() == 0
        schedule_store.create(workflow_id="wf1", inputs={}, tenant_id="t1", user_id="u1",
                             permission_scope=[], run_at=datetime.now(UTC))
        assert schedule_store.count() == 1
        assert schedule_store.count(status=WorkflowScheduleStatus.PENDING) == 1
        assert schedule_store.count(status=WorkflowScheduleStatus.CANCELED) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Backend factories
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveBackend:
    def test_default_auto(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("XAGENT_WORKFLOW_STORE_BACKEND", None)
            assert _resolve_backend(None) == "auto"

    def test_explicit_db(self):
        assert _resolve_backend("db") == "db"

    def test_explicit_file(self):
        assert _resolve_backend("file") == "file"

    def test_from_env(self):
        with patch.dict(os.environ, {"XAGENT_WORKFLOW_STORE_BACKEND": "file"}):
            assert _resolve_backend(None) == "file"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Unknown workflow store backend"):
            _resolve_backend("invalid")

    def test_case_insensitive(self):
        assert _resolve_backend("  DB  ") == "db"


class TestBuildWorkflowRepository:
    def test_file_backend(self, tmp_path):
        repo = build_workflow_repository(backend="file", definition_path=tmp_path / "d.json",
                                         run_path=tmp_path / "r.json")
        from backend.app.core.workflows import WorkflowRepository
        assert isinstance(repo, WorkflowRepository)
        assert not isinstance(repo, SQLWorkflowRepository)

    def test_db_backend_no_url_raises(self):
        with pytest.raises(RuntimeError, match="requires a database_url"):
            build_workflow_repository(backend="db", database_url=None)

    def test_db_backend_with_url(self):
        repo = build_workflow_repository(backend="db", database_url="sqlite:///:memory:")
        assert isinstance(repo, SQLWorkflowRepository)

    def test_auto_backend_no_url_falls_to_file(self, tmp_path):
        repo = build_workflow_repository(backend="auto", database_url=None,
                                         definition_path=tmp_path / "d.json")
        from backend.app.core.workflows import WorkflowRepository
        assert not isinstance(repo, SQLWorkflowRepository)

    def test_auto_backend_with_url(self):
        repo = build_workflow_repository(backend="auto", database_url="sqlite:///:memory:")
        assert isinstance(repo, SQLWorkflowRepository)

    def test_auto_backend_sql_fails_fallback(self, tmp_path):
        with patch("backend.app.core.workflow_store.SQLWorkflowRepository", side_effect=Exception("no db")):
            repo = build_workflow_repository(backend="auto", database_url="sqlite:///:memory:",
                                             definition_path=tmp_path / "d.json")
            from backend.app.core.workflows import WorkflowRepository
            assert not isinstance(repo, SQLWorkflowRepository)


class TestBuildWorkflowScheduleStore:
    def test_file_backend(self, tmp_path):
        store = build_workflow_schedule_store(backend="file", storage_path=tmp_path / "s.json")
        from backend.app.core.workflows import WorkflowScheduleStore
        assert isinstance(store, WorkflowScheduleStore)
        assert not isinstance(store, SQLWorkflowScheduleStore)

    def test_db_backend_no_url_raises(self):
        with pytest.raises(RuntimeError, match="requires a database_url"):
            build_workflow_schedule_store(backend="db", database_url=None)

    def test_db_backend_with_url(self):
        store = build_workflow_schedule_store(backend="db", database_url="sqlite:///:memory:")
        assert isinstance(store, SQLWorkflowScheduleStore)

    def test_auto_backend_no_url(self, tmp_path):
        store = build_workflow_schedule_store(backend="auto", database_url=None,
                                              storage_path=tmp_path / "s.json")
        assert not isinstance(store, SQLWorkflowScheduleStore)

    def test_auto_backend_sql_fails_fallback(self, tmp_path):
        with patch("backend.app.core.workflow_store.SQLWorkflowScheduleStore", side_effect=Exception("no db")):
            store = build_workflow_schedule_store(backend="auto", database_url="sqlite:///:memory:",
                                                  storage_path=tmp_path / "s.json")
            assert not isinstance(store, SQLWorkflowScheduleStore)
