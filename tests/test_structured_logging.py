from __future__ import annotations

import io
import json
import logging
import sys

from backend.app.core.structured_logging import (
    JsonLogFormatter,
    configure_json_logging,
    log_event,
)


def test_json_log_formatter_emits_json_with_structured_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="xagent.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="task.started",
        args=(),
        exc_info=None,
    )
    record.structured = {"trace_id": "trace-1", "count": 2}

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "info"
    assert payload["logger"] == "xagent.test"
    assert payload["event"] == "task.started"
    assert payload["trace_id"] == "trace-1"
    assert payload["count"] == 2
    assert payload["timestamp"].endswith("+00:00")


def test_json_log_formatter_includes_exception_text() -> None:
    formatter = JsonLogFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.getLogger("xagent.test").makeRecord(
            "xagent.test",
            logging.ERROR,
            __file__,
            20,
            "task.failed",
            args=(),
            exc_info=sys.exc_info(),
            func=None,
            extra={"structured": {"task_id": "task-1"}},
        )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "error"
    assert payload["event"] == "task.failed"
    assert payload["task_id"] == "task-1"
    assert "RuntimeError: boom" in payload["exception"]


def test_log_event_writes_structured_json_to_configured_handler() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("xagent.structured-test")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)

    log_event(logger, "validation.completed", trace_id="trace-1", ok=True)

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "validation.completed"
    assert payload["trace_id"] == "trace-1"
    assert payload["ok"] is True


def test_configure_json_logging_replaces_root_handlers(monkeypatch) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        root.handlers = [logging.NullHandler()]
        configure_json_logging(level="DEBUG")

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
        assert root.level == logging.DEBUG
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
