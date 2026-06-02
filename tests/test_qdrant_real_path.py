import pytest

from backend.app.services.memory.qdrant_client import vector_client


def _qdrant_reachable() -> bool:
    """跳过判定：仅当配置了真实 qdrant 客户端但服务器不可达时跳过。

    生产 QdrantVectorClient 有确定性内存回退；未配置 url 时无真实客户端，
    内存路径可正常工作，无需跳过。配了 url 但服务器拒连（WinError 10061）
    才跳过本组需要真实 qdrant 的集成测试。
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
