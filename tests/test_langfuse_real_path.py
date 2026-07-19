from backend.app.services.observability.langfuse_client import langfuse_client


def test_langfuse_facade_records_trace_with_extended_metadata() -> None:
    event = langfuse_client.log(
        "agent.started",
        trace_id="trace-real",
        run_id="run-real",
        agent_id="agent-real",
        workflow_id="workflow-real",
        tenant_id="tenant-real",
        user_id="user-real",
        task="real path",
    )

    assert event.trace_id == "trace-real"
    assert event.workflow_id == "workflow-real"
    assert event.tenant_id == "tenant-real"
    assert event.user_id == "user-real"
    assert event.payload["task"] == "real path"
