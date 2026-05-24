from backend.app.services.memory.qdrant_client import vector_client


def test_qdrant_facade_can_ensure_collection_and_search() -> None:
    ensured = vector_client.ensure_collection("memory")
    record = vector_client.upsert(
        "memory",
        tenant_id="tenant-real",
        text="qdrant collection initialization",
        embedding=[0.1, 0.2, 0.3],
        payload={"source": "test"},
    )
    results = vector_client.search("memory", tenant_id="tenant-real", query="collection initialization", top_k=3)

    assert ensured in {True, False}
    assert record.tenant_id == "tenant-real"
    assert any(item.id == record.id for item in results)
