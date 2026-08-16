from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from backend.app.core.contracts import RunContext, TraceEvent
from backend.app.core.tracing import TraceStore

TRACE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trace_events (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    request_id TEXT NULL,
    agent_id TEXT NULL,
    tenant_id TEXT NULL,
    user_id TEXT NULL,
    event TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE trace_events ADD COLUMN IF NOT EXISTS request_id TEXT NULL;
ALTER TABLE trace_events ADD COLUMN IF NOT EXISTS agent_id TEXT NULL;
ALTER TABLE trace_events ADD COLUMN IF NOT EXISTS tenant_id TEXT NULL;
ALTER TABLE trace_events ADD COLUMN IF NOT EXISTS user_id TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_trace_events_trace_time
    ON trace_events (trace_id, timestamp ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_trace_events_event_time
    ON trace_events (event, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trace_events_tenant_time
    ON trace_events (tenant_id, timestamp DESC);
"""


class PostgresTraceStore(TraceStore):
    """Trace store that keeps in-memory reads and durably writes to Postgres.

    ``record()`` does not acknowledge an event until PostgreSQL accepts it. This
    intentionally favors audit correctness over hiding database latency.
    """

    def __init__(
        self,
        database_url: str,
        *,
        connection: Any | None = None,
        ensure_schema: bool = True,
    ) -> None:
        super().__init__(storage_path=None)
        self.database_url = database_url
        self._connection = connection
        self._ensure_schema = ensure_schema
        self._initialized = False
        self._worker = None
        self._load_existing_events()

    def record(self, context: RunContext, event: str, **data: Any) -> TraceEvent:
        trace_event = TraceEvent(
            trace_id=context.trace_id,
            event=event,
            data=data,
            request_id=context.request_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
        )
        self._write_event(trace_event)
        with self._lock:
            self._events.setdefault(context.trace_id, []).append(trace_event)
        return trace_event

    def flush(self) -> None:
        return None

    def close(self) -> None:
        if self._connection is not None and hasattr(self._connection, "close"):
            self._connection.close()
        self._connection = None

    def _get_connection(self) -> Any:
        if self._connection is None:
            import psycopg

            dsn = self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
            self._connection = psycopg.connect(dsn)
            self._connection.autocommit = True
        if self._ensure_schema and not self._initialized:
            self._connection.execute(TRACE_SCHEMA_SQL)
            self._initialized = True
        return self._connection

    def _write_event(self, event: TraceEvent) -> None:
        connection = self._get_connection()
        connection.execute(
            """
            INSERT INTO trace_events (
                trace_id, event, data, timestamp,
                request_id, agent_id, tenant_id, user_id
            )
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            """,
            (
                event.trace_id,
                event.event,
                json.dumps(event.data),
                event.timestamp,
                event.request_id,
                event.agent_id,
                event.tenant_id,
                event.user_id,
            ),
        )

    def _load_existing_events(self) -> None:
        try:
            connection = self._get_connection()
        except Exception:
            return

        try:
            rows = connection.execute(
                """
                SELECT trace_id::text, event, data, timestamp,
                       request_id, agent_id, tenant_id, user_id
                FROM trace_events
                ORDER BY timestamp ASC, id ASC
                """
            )
        except Exception:
            return

        if rows is None:
            return

        if hasattr(rows, "fetchall"):
            rows = rows.fetchall()
        for row in rows:
            event = self.row_to_event(row)
            self._events.setdefault(event.trace_id, []).append(event)

    @staticmethod
    def row_to_event(row: Any) -> TraceEvent:
        data = row["data"] if isinstance(row, dict) else row[2]
        timestamp = row["timestamp"] if isinstance(row, dict) else row[3]
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return TraceEvent(
            trace_id=row["trace_id"] if isinstance(row, dict) else row[0],
            event=row["event"] if isinstance(row, dict) else row[1],
            data=data,
            timestamp=timestamp,
            request_id=row.get("request_id") if isinstance(row, dict) else row[4],
            agent_id=row.get("agent_id") if isinstance(row, dict) else row[5],
            tenant_id=row.get("tenant_id") if isinstance(row, dict) else row[6],
            user_id=row.get("user_id") if isinstance(row, dict) else row[7],
        )
