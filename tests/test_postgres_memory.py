from datetime import UTC, datetime

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import DeterministicEmbeddingModel
from backend.app.core.memory import MemorySystem
from backend.app.core.memory_postgres import PostgresMemorySystem
from backend.app.dependencies import build_memory_system


class FakePool:
    def __init__(self) -> None:
        self.executed = []
        self.fetched = []
        self.rows = [
            {
                "id": "3aa8db29-7b74-472a-a153-1cbe6b92f636",
                "tenant_id": "tenant-a",
                "agent_id": "f8b8165c-d156-4399-bc9d-e1fb59d3715c",
                "content": "persistent postgres note",
                "layer": 3,
                "importance": 0.7,
                "tags": ["agent-run"],
                "metadata": {"trace_id": "trace-1"},
                "created_at": datetime.now(UTC),
            }
        ]

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return "OK"

    async def fetch(self, sql, *args):
        self.fetched.append((sql, args))
        return self.rows


async def test_postgres_memory_store_and_search_use_pool() -> None:
    pool = FakePool()
    memory = PostgresMemorySystem(
        database_url="postgresql://example",
        pool=pool,
        ensure_schema=False,
    )
    context = RunContext(
        tenant_id="tenant-a",
        agent_id="f8b8165c-d156-4399-bc9d-e1fb59d3715c",
    )

    item_id = await memory.store(
        context,
        content="persistent postgres note",
        layer=3,
        importance=0.7,
        tags=["agent-run"],
        metadata={"trace_id": "trace-1"},
    )
    hits = await memory.search(context, "postgres", layers=[3], top_k=2)

    assert item_id
    assert len(pool.executed) == 1
    assert pool.executed[0][1][1] == "tenant-a"
    assert pool.fetched[0][1] == ("tenant-a", [3], "postgres", 2)
    assert hits[0].content == "persistent postgres note"
    assert hits[0].metadata["trace_id"] == "trace-1"


async def test_postgres_memory_vector_store_and_search_use_pgvector() -> None:
    pool = FakePool()
    memory = PostgresMemorySystem(
        database_url="postgresql://example",
        pool=pool,
        ensure_schema=False,
        embedding_model=DeterministicEmbeddingModel(dimensions=8),
        enable_vector_search=True,
        vector_dimensions=8,
    )
    context = RunContext(
        tenant_id="tenant-a",
        agent_id="f8b8165c-d156-4399-bc9d-e1fb59d3715c",
    )

    await memory.store(context, content="vector postgres note", layer=3)
    await memory.search(context, "vector", layers=[3], top_k=2)

    assert "embedding" in pool.executed[0][0]
    assert "::vector" in pool.executed[0][0]
    assert "::vector" in pool.fetched[0][0]
    assert pool.fetched[0][1][0] == "tenant-a"
    assert pool.fetched[0][1][1] == [3]
    assert pool.fetched[0][1][3] == 2


def test_memory_factory_selects_backend(tmp_path) -> None:
    # embedding_backend="local": 工厂选型测试只需离线 hash 嵌入；
    # 默认 "auto" 会在本机加载 sentence-transformers（首次 ~90s+），导致 30s 测试超时挂死。
    jsonl = build_memory_system(
        memory_backend="jsonl",
        database_url="postgresql://example",
        memory_store_path=tmp_path / "memory.jsonl",
        embedding_backend="local",
    )
    memory_only = build_memory_system(
        memory_backend="memory",
        database_url="postgresql://example",
        memory_store_path=tmp_path / "memory.jsonl",
        embedding_backend="local",
    )
    postgres = build_memory_system(
        memory_backend="postgres",
        database_url="postgresql://example",
        memory_store_path=tmp_path / "memory.jsonl",
    )
    postgres_vector = build_memory_system(
        memory_backend="postgres",
        database_url="postgresql://example",
        memory_store_path=tmp_path / "memory.jsonl",
        postgres_enable_vector_search=True,
        postgres_vector_dimensions=8,
        embedding_backend="local",
    )

    assert isinstance(jsonl, MemorySystem)
    assert isinstance(memory_only, MemorySystem)
    assert isinstance(postgres, PostgresMemorySystem)
    assert isinstance(postgres_vector, PostgresMemorySystem)
