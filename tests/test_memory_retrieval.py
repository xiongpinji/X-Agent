import pytest

from backend.app.services.memory.indexer import memory_indexer
from backend.app.services.memory.retriever import memory_retriever
from backend.app.services.memory.qdrant_client import vector_client
from backend.app.services.observability.langfuse_client import langfuse_client


def _qdrant_reachable() -> bool:
    """跳过判定：仅当配置了真实 qdrant 客户端但服务器不可达时跳过。

    memory_indexer/memory_retriever 共用同一 vector_client 单例。生产
    QdrantVectorClient 有确定性内存回退；未配置 url 时无真实客户端，内存路径
    可正常工作，无需跳过。配了 url 但服务器拒连（WinError 10061）才跳过。
    """
    try:
        if not vector_client.has_real_client:
            return True
        vector_client.get_collection_names()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_reachable(),
    reason="requires a reachable qdrant server (configured url refused connection)",
)


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
