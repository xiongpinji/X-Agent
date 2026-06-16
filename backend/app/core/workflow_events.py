from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Protocol

from backend.app.core.storage import dumps_json, to_jsonable


class WorkflowEventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a workflow event to an external or local event stream."""

    def check_health(self) -> dict[str, Any]:
        """Validate that the publisher can be used without emitting an event."""


class LocalWorkflowEventPublisher:
    def __init__(self) -> None:
        self._lock = RLock()
        self._events: list[dict[str, Any]] = []

    @property
    def events(self) -> list[dict[str, Any]]:
        return [self._json_safe_event(event) for event in self._snapshot()]

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "event_type": event_type,
            "payload": payload,
            "published_at": datetime.now(UTC),
        }
        with self._lock:
            self._events.append(event)

    def check_health(self) -> dict[str, Any]:
        return {"event_count": len(self._snapshot())}

    def _snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [deepcopy(event) for event in self._events]

    @staticmethod
    def _json_safe_event(event: dict[str, Any]) -> dict[str, Any]:
        json_safe_event = to_jsonable(event)
        if not isinstance(json_safe_event, dict):
            return {}
        return json_safe_event


class RabbitMQWorkflowEventPublisher:
    """RabbitMQ publisher for workflow lifecycle fan-out events."""

    def __init__(
        self,
        amqp_url: str,
        *,
        exchange: str = "xagent.workflow",
        routing_key_prefix: str = "",
        connection: Any | None = None,
        channel: Any | None = None,
    ) -> None:
        self.amqp_url = amqp_url
        self.exchange = exchange
        self.routing_key_prefix = routing_key_prefix.strip(".")
        self._connection = connection
        self._channel = channel
        self._initialized = False

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        channel = self._get_channel()
        routing_key = self._routing_key(event_type)
        body = dumps_json(
            {
                "event_type": event_type,
                "published_at": datetime.now(UTC).isoformat(),
                "payload": payload,
            },
        )
        channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=body,
            properties=self._message_properties(),
        )

    def check_health(self) -> dict[str, Any]:
        self._get_channel()
        return {
            "exchange": self.exchange,
            "routing_key_prefix": self.routing_key_prefix,
        }

    def _get_channel(self) -> Any:
        if self._channel is not None:
            self._ensure_exchange(self._channel)
            return self._channel
        if self._connection is None:
            import pika

            self._connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self._channel = self._connection.channel()
        self._ensure_exchange(self._channel)
        return self._channel

    def _ensure_exchange(self, channel: Any) -> None:
        if self._initialized:
            return
        channel.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)
        self._initialized = True

    def _message_properties(self) -> Any | None:
        try:
            import pika
        except Exception:  # pragma: no cover - fake-channel tests do not require pika
            return None
        return pika.BasicProperties(content_type="application/json", delivery_mode=2)

    def _routing_key(self, event_type: str) -> str:
        if not self.routing_key_prefix:
            return event_type
        return f"{self.routing_key_prefix}.{event_type}"


def build_workflow_event_publisher(
    *,
    workflow_event_broker_backend: str,
    workflow_event_rabbitmq_url: str,
    workflow_event_exchange: str,
) -> WorkflowEventPublisher | None:
    if workflow_event_broker_backend in {"", "none", "disabled"}:
        return None
    if workflow_event_broker_backend == "local":
        return LocalWorkflowEventPublisher()
    if workflow_event_broker_backend == "rabbitmq":
        return RabbitMQWorkflowEventPublisher(
            amqp_url=workflow_event_rabbitmq_url,
            exchange=workflow_event_exchange,
        )
    raise ValueError(f"Unsupported workflow event broker: {workflow_event_broker_backend}")
