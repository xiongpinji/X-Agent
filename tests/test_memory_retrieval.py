from backend.app.services.memory.indexer import memory_indexer
from backend.app.services.memory.retriever import memory_retriever
from backend.app.services.observability.langfuse_client import langfuse_client


def test_memory_index_and_retrieve_records_observability() -> None:
    record = memory_indexer.index(
        tenant_id="tenant-a",
        text="playwright browser workflow memory",
        source="unit-test",
    )
    results = memory_retriever.search(tenant_id="tenant-a", query="browser workflow", top_k=3)

    assert record.tenant_id == "tenant-a"
    assert any(item.id == record.id for item in results)
    assert any(event.type == "memory.indexed" for event in langfuse_client.events())
    assert any(event.type == "memory.search" for event in langfuse_client.events())


def test_memory_retriever_filters_by_tenant() -> None:
    memory_indexer.index(tenant_id="tenant-b", text="tenant scoped note", source="tenant-b")
    results = memory_retriever.search(tenant_id="tenant-a", query="tenant scoped", top_k=10)

    assert all(item.tenant_id == "tenant-a" for item in results)
