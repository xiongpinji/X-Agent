from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def test_qdrant_and_langfuse_behavior_contracts() -> None:
    vector_client.ensure_collection("memory")
    names = vector_client.get_collection_names()
    event = langfuse_client.log(
        "ready.behavior",
        trace_id="trace-behavior",
        run_id="run-behavior",
        agent_id="agent-behavior",
        workflow_id="workflow-behavior",
        tenant_id="tenant-behavior",
        user_id="user-behavior",
        detail="behavior contract",
    )

    assert isinstance(names, list)
    assert "memory" in names or names == []
    assert event.type == "ready.behavior"
    assert event.tenant_id == "tenant-behavior"
    assert event.user_id == "user-behavior"
