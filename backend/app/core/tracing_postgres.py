from __future__ import annotations

import json
import queue
import threading
from datetime import UTC, datetime
from typing import Any

from backend.app.core.contracts import RunContext, TraceEvent
from backend.app.core.tracing import TraceStore

TRACE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trace_events (
    id BIGSERIAL PRIMARY KEY,
    trace_id UUID NOT NULL,
    event TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trace_events_trace_time
    ON trace_events (trace_id, timestamp ASC, id ASC);

CREATE INDEX IF NOT EXISTS idx_trace_events_event_time
    ON trace_events (event, timestamp DESC);
"""


class PostgresTraceStore(TraceStore):
    """Trace store that keeps in-memory reads and writes events to Postgres.

    The public `record()` method remains synchronous to avoid changing AgentLoop. Database
    writes are handled by a small background worker using psycopg so request latency does
    not depend on the audit sink.
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
        self._queue: queue.Queue[TraceEvent | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        if connection is None:
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()
        self._load_existing_events()

    def record(self, context: RunContext, event: str, **data: Any) -> TraceEvent:
        trace_event = super().record(context, event, **data)
        if self._connection is not None:
            self._write_event(trace_event)
        else:
            self._queue.put(trace_event)
        return trace_event

    def flush(self) -> None:
        self._queue.join()

    def close(self) -> None:
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=2)

    def _worker_loop(self) -> None:
        while True:
            event = self._queue.get()
            try:
                if event is None:
                    return
                self._write_event(event)
            finally:
                self._queue.task_done()

    def _get_connection(self) -> Any:
        if self._connection is None:
            import psycopg

            self._connection = psycopg.connect(self.database_url)
            self._connection.autocommit = True
        if self._ensure_schema and not self._initialized:
            self._connection.execute(TRACE_SCHEMA_SQL)
            self._initialized = True
        return self._connection

    def _write_event(self, event: TraceEvent) -> None:
        connection = self._get_connection()
        connection.execute(
            """
            INSERT INTO trace_events (trace_id, event, data, timestamp)
            VALUES (%s::uuid, %s, %s::jsonb, %s)
            """,
            (
                event.trace_id,
                event.event,
                json.dumps(event.data),
                event.timestamp,
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
                SELECT trace_id::text, event, data, timestamp
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
        )
