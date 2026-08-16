from datetime import UTC, datetime

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.tracing_postgres import TRACE_SCHEMA_SQL, PostgresTraceStore
from backend.app.dependencies import build_trace_store


class FakeResult:
    def __init__(self, rows) -> None:
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, rows=None) -> None:
        self.executed = []
        self.autocommit = False
        self.rows = rows or []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT trace_id" in sql:
            return FakeResult(self.rows)


def test_trace_schema_contains_table_and_indexes() -> None:
    assert "CREATE TABLE IF NOT EXISTS trace_events" in TRACE_SCHEMA_SQL
    assert "trace_id TEXT NOT NULL" in TRACE_SCHEMA_SQL
    assert "tenant_id TEXT" in TRACE_SCHEMA_SQL
    assert "user_id TEXT" in TRACE_SCHEMA_SQL
    assert "request_id TEXT" in TRACE_SCHEMA_SQL
    assert "agent_id TEXT" in TRACE_SCHEMA_SQL
    assert "idx_trace_events_trace_time" in TRACE_SCHEMA_SQL


def test_postgres_trace_store_restores_principal_correlation_fields() -> None:
    timestamp = datetime.now(UTC)
    conn = FakeConnection(
        rows=[
            (
                "trace-restored",
                "agent.started",
                {"task": "restore me"},
                timestamp,
                "request-restored",
                "agent-restored",
                "tenant-restored",
                "user-restored",
            )
        ]
    )

    store = PostgresTraceStore(
        database_url="postgresql://example",
        connection=conn,
        ensure_schema=False,
    )

    event = store.list_events("trace-restored")[0]
    summary = store.get_summary("trace-restored")
    assert event.request_id == "request-restored"
    assert event.agent_id == "agent-restored"
    assert event.tenant_id == "tenant-restored"
    assert event.user_id == "user-restored"
    assert summary.snapshot["tenant_id"] == "tenant-restored"


def test_postgres_trace_store_writes_event_to_connection() -> None:
    conn = FakeConnection()
    store = PostgresTraceStore(
        database_url="postgresql://example",
        connection=conn,
        ensure_schema=False,
    )
    context = RunContext(trace_id="trace-1")

    event = store.record(context, "agent.started", task="hello")

    assert event.event == "agent.started"
    insert = next((sql, params) for sql, params in conn.executed if "INSERT INTO trace_events" in sql)
    assert "::uuid" not in insert[0]
    assert insert[1][0] == "trace-1"


def test_trace_factory_selects_backend(tmp_path) -> None:
    jsonl = build_trace_store(
        trace_backend="jsonl",
        database_url="postgresql://example",
        trace_store_path=tmp_path / "trace.jsonl",
    )
    memory = build_trace_store(
        trace_backend="memory",
        database_url="postgresql://example",
        trace_store_path=tmp_path / "trace.jsonl",
    )
    postgres = build_trace_store(
        trace_backend="postgres",
        database_url="postgresql://example",
        trace_store_path=tmp_path / "trace.jsonl",
    )

    assert jsonl is not None
    assert memory is not None
    assert isinstance(postgres, PostgresTraceStore)


def test_postgres_trace_store_has_no_async_loss_window(monkeypatch) -> None:
    monkeypatch.setattr(PostgresTraceStore, "_load_existing_events", lambda self: None)
    store = PostgresTraceStore(database_url="postgresql://example", ensure_schema=False)

    assert store._worker is None
    monkeypatch.setattr(
        store,
        "_write_event",
        lambda event: (_ for _ in ()).throw(OSError("database unavailable")),
    )

    with pytest.raises(OSError, match="database unavailable"):
        store.record(RunContext(trace_id="trace-fail"), "agent.failed")
    assert store.list_events("trace-fail") == []


def test_postgres_trace_store_normalizes_asyncpg_dsn(monkeypatch) -> None:
    import psycopg

    captured = []
    connection = FakeConnection()
    monkeypatch.setattr(psycopg, "connect", lambda dsn: captured.append(dsn) or connection)
    monkeypatch.setattr(PostgresTraceStore, "_load_existing_events", lambda self: None)
    store = PostgresTraceStore(
        database_url="postgresql+asyncpg://user:pass@db.internal:5432/xagent",
        ensure_schema=False,
    )

    assert store._get_connection() is connection
    assert captured == ["postgresql://user:pass@db.internal:5432/xagent"]
