from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.app.core.workflow_events import (
    LocalWorkflowEventPublisher,
    RabbitMQWorkflowEventPublisher,
    build_workflow_event_publisher,
)


class FakeRabbitChannel:
    def __init__(self) -> None:
        self.exchanges: list[dict[str, object]] = []
        self.messages: list[dict[str, object]] = []

    def exchange_declare(self, **kwargs: object) -> None:
        self.exchanges.append(kwargs)

    def basic_publish(self, **kwargs: object) -> None:
        self.messages.append(kwargs)


def test_local_workflow_event_publisher_captures_events() -> None:
    publisher = LocalWorkflowEventPublisher()

    publisher.publish("workflow.schedule.triggered", {"schedule_id": "sch_1"})

    assert publisher.events[0]["event_type"] == "workflow.schedule.triggered"
    assert publisher.events[0]["payload"] == {"schedule_id": "sch_1"}
    assert publisher.check_health() == {"event_count": 1}


def test_local_workflow_event_publisher_returns_json_safe_event_snapshots() -> None:
    publisher = LocalWorkflowEventPublisher()

    publisher.publish(
        "workflow.schedule.triggered",
        {"run_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC)},
    )
    events = publisher.events
    run_at = events[0]["payload"]["run_at"]
    published_at = events[0]["published_at"]
    events[0]["payload"]["run_at"] = "mutated"

    assert published_at.endswith("+00:00")
    assert run_at == "2026-05-11T12:00:00+00:00"
    assert publisher.events[0]["payload"]["run_at"] == "2026-05-11T12:00:00+00:00"


def test_workflow_event_publishers_serialize_open_payload_values() -> None:
    local = LocalWorkflowEventPublisher()
    channel = FakeRabbitChannel()
    rabbit = RabbitMQWorkflowEventPublisher(
        amqp_url="amqp://example",
        exchange="xagent.test",
        channel=channel,
    )
    payload = {
        "run_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
        "path": Path("runtime/workflow-event.json"),
    }

    local.publish("workflow.schedule.triggered", payload)
    rabbit.publish("workflow.schedule.triggered", payload)
    local_payload = local.events[0]["payload"]
    rabbit_payload = json.loads(str(channel.messages[0]["body"]))["payload"]

    assert local_payload["run_at"] == "2026-05-11T12:00:00+00:00"
    assert local_payload["path"] in {
        "runtime/workflow-event.json",
        "runtime\\workflow-event.json",
    }
    assert rabbit_payload == local_payload


def test_local_workflow_event_publisher_uses_stable_snapshot() -> None:
    class AppendingSnapshotPublisher(LocalWorkflowEventPublisher):
        def __init__(self) -> None:
            super().__init__()
            self.appended_after_snapshot = False

        def _snapshot(self) -> list[dict[str, object]]:
            snapshot = super()._snapshot()
            if not self.appended_after_snapshot:
                self.appended_after_snapshot = True
                self.publish("workflow.schedule.after_snapshot", {"schedule_id": "after"})
            return snapshot

    publisher = AppendingSnapshotPublisher()
    publisher.publish("workflow.schedule.before_snapshot", {"schedule_id": "before"})

    events = publisher.events

    assert [event["event_type"] for event in events] == ["workflow.schedule.before_snapshot"]
    assert publisher.check_health() == {"event_count": 2}


def test_rabbitmq_workflow_event_publisher_uses_topic_exchange() -> None:
    channel = FakeRabbitChannel()
    publisher = RabbitMQWorkflowEventPublisher(
        amqp_url="amqp://example",
        exchange="xagent.test",
        routing_key_prefix="tenant-a",
        channel=channel,
    )

    publisher.publish("workflow.schedule.triggered", {"schedule_id": "sch_1"})

    assert channel.exchanges == [
        {"exchange": "xagent.test", "exchange_type": "topic", "durable": True}
    ]
    assert channel.messages[0]["exchange"] == "xagent.test"
    assert channel.messages[0]["routing_key"] == "tenant-a.workflow.schedule.triggered"
    body = json.loads(str(channel.messages[0]["body"]))
    assert body["event_type"] == "workflow.schedule.triggered"
    assert body["payload"]["schedule_id"] == "sch_1"


def test_rabbitmq_workflow_event_publisher_serializes_datetimes_as_iso8601() -> None:
    channel = FakeRabbitChannel()
    publisher = RabbitMQWorkflowEventPublisher(
        amqp_url="amqp://example",
        exchange="xagent.test",
        channel=channel,
    )

    publisher.publish(
        "workflow.schedule.triggered",
        {"run_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC)},
    )
    body = json.loads(str(channel.messages[0]["body"]))

    assert body["published_at"].endswith("+00:00")
    assert body["payload"]["run_at"] == "2026-05-11T12:00:00+00:00"


def test_rabbitmq_workflow_event_health_does_not_publish_message() -> None:
    channel = FakeRabbitChannel()
    publisher = RabbitMQWorkflowEventPublisher(
        amqp_url="amqp://example",
        exchange="xagent.test",
        routing_key_prefix="tenant-a",
        channel=channel,
    )

    health = publisher.check_health()

    assert health == {"exchange": "xagent.test", "routing_key_prefix": "tenant-a"}
    assert channel.exchanges == [
        {"exchange": "xagent.test", "exchange_type": "topic", "durable": True}
    ]
    assert channel.messages == []


def test_workflow_event_publisher_builder_selects_backends() -> None:
    assert (
        build_workflow_event_publisher(
            workflow_event_broker_backend="disabled",
            workflow_event_rabbitmq_url="amqp://example",
            workflow_event_exchange="xagent.workflow",
        )
        is None
    )
    assert isinstance(
        build_workflow_event_publisher(
            workflow_event_broker_backend="local",
            workflow_event_rabbitmq_url="amqp://example",
            workflow_event_exchange="xagent.workflow",
        ),
        LocalWorkflowEventPublisher,
    )
    assert isinstance(
        build_workflow_event_publisher(
            workflow_event_broker_backend="rabbitmq",
            workflow_event_rabbitmq_url="amqp://example",
            workflow_event_exchange="xagent.workflow",
        ),
        RabbitMQWorkflowEventPublisher,
    )
