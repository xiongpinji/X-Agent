from backend.app.core.contracts import RunContext
from backend.app.core.tracing_postgres import TRACE_SCHEMA_SQL, PostgresTraceStore
from backend.app.dependencies import build_trace_store


class FakeConnection:
    def __init__(self) -> None:
        self.executed = []
        self.autocommit = False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))


def test_trace_schema_contains_table_and_indexes() -> None:
    assert "CREATE TABLE IF NOT EXISTS trace_events" in TRACE_SCHEMA_SQL
    assert "idx_trace_events_trace_time" in TRACE_SCHEMA_SQL


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
    assert any("INSERT INTO trace_events" in sql for sql, _ in conn.executed)


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
