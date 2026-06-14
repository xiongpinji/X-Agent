from backend.app.services.observability.langfuse_client import langfuse_client
from backend.app.services.observability.langfuse_client import LangfuseClient


def test_observability_client_records_custom_events() -> None:
    event = langfuse_client.log(
        "custom.event",
        trace_id="trace-1",
        request_id="request-1",
        agent_id="agent-1",
        tenant_id="tenant-a",
        user_id="user-a",
        payload_key="payload-value",
    )

    assert event.type == "custom.event"
    assert event.trace_id == "trace-1"
    assert event.payload["payload_key"] == "payload-value"
    assert any(item.type == "custom.event" for item in langfuse_client.events())


def test_observability_client_supports_langfuse_create_event_api() -> None:
    class CreateEventClient:
        def __init__(self) -> None:
            self.calls = []

        def create_event(self, **kwargs):
            self.calls.append(kwargs)

    client = CreateEventClient()
    observability_client = LangfuseClient()
    observability_client._client = client

    event = observability_client.log(
        "agent.run.completed",
        trace_id="trace-create-event",
        tenant_id="tenant-a",
        user_id="user-a",
        run_id="run-a",
        agent_id="agent-a",
        payload_key="payload-value",
    )

    assert event.trace_id == "trace-create-event"
    assert client.calls == [
        {
            "trace_context": {"trace_id": "trace-create-event"},
            "name": "agent.run.completed",
            "metadata": {
                "payload_key": "payload-value",
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "run_id": "run-a",
                "workflow_id": None,
                "agent_id": "agent-a",
            },
        }
    ]


def test_observability_client_keeps_local_event_when_langfuse_export_fails() -> None:
    class FailingCreateEventClient:
        def create_event(self, **kwargs):
            raise RuntimeError("network unavailable")

    observability_client = LangfuseClient()
    observability_client._client = FailingCreateEventClient()

    event = observability_client.log(
        "agent.run.failed",
        trace_id="trace-fallback",
        payload_key="payload-value",
    )

    assert event.type == "agent.run.failed"
    assert event.trace_id == "trace-fallback"
    assert event.payload["payload_key"] == "payload-value"
