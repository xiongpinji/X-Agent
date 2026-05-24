from backend.app.services.observability.langfuse_client import langfuse_client


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
