from types import SimpleNamespace

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import DeterministicEmbeddingModel, OpenAIEmbeddingModel
from backend.app.core.memory import MemorySystem


async def test_memory_persists_local_embeddings(tmp_path) -> None:
    path = tmp_path / "memory.jsonl"
    context = RunContext(tenant_id="tenant-a")
    memory = MemorySystem(storage_path=path)

    await memory.store(context, "vector search remembers semantic context", layer=3)

    reloaded = MemorySystem(storage_path=path)
    hits = await reloaded.search(context, "vector", layers=[3], top_k=1)

    assert hits
    assert hits[0].embedding
    assert hits[0].content == "vector search remembers semantic context"


async def test_memory_vector_search_recalls_token_related_content() -> None:
    context = RunContext(tenant_id="tenant-a")
    memory = MemorySystem()
    await memory.store(
        context,
        "浏览器 自动化 任务 可以 操作 页面 表单",
        layer=3,
        importance=0.3,
    )
    await memory.store(
        context,
        "数据库 备份 任务 使用 jsonl 持久化",
        layer=3,
        importance=1.0,
    )

    hits = await memory.search(context, "浏览器 页面", layers=[3], top_k=1)

    assert hits[0].content.startswith("浏览器")


async def test_memory_search_with_scores_explains_hybrid_ranking() -> None:
    context = RunContext(tenant_id="tenant-a")
    memory = MemorySystem()
    await memory.store(context, "agent workflow planning", layer=3, importance=0.2)
    await memory.store(context, "agent workflow planning critical", layer=3, importance=1.0)

    hits = await memory.search_with_scores(context, "agent workflow", layers=[3], top_k=2)

    assert hits[0].item.content == "agent workflow planning critical"
    assert hits[0].score >= hits[1].score
    assert hits[0].keyword_score == 2
    assert hits[0].vector_score > 0
    assert hits[0].importance_score == 1.0
    assert hits[0].freshness_score > 0


async def test_memory_graph_expands_related_recall() -> None:
    context = RunContext(tenant_id="tenant-a")
    memory = MemorySystem()
    await memory.store(context, "openclaw browser automation", layer=3)
    await memory.store(context, "browser automation controls pages", layer=3)

    hits = await memory.search_with_scores(context, "openclaw", layers=[3], top_k=2)

    assert any(hit.item.content == "browser automation controls pages" for hit in hits)
    related_hit = next(
        hit for hit in hits if hit.item.content == "browser automation controls pages"
    )
    assert related_hit.keyword_score == 0
    assert related_hit.graph_score > 0


def test_deterministic_embedding_similarity_is_stable() -> None:
    model = DeterministicEmbeddingModel(dimensions=32)
    first = model.embed("agent workflow memory")
    second = model.embed("agent workflow memory")
    unrelated = model.embed("database backup")

    assert first == second
    assert model.similarity(first, second) > model.similarity(first, unrelated)


async def test_openai_embedding_model_uses_configured_model_and_dimensions() -> None:
    calls = []

    class FakeEmbeddings:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])])

    client = SimpleNamespace(embeddings=FakeEmbeddings())
    model = OpenAIEmbeddingModel(
        api_key="test-key",
        model="text-embedding-3-small",
        dimensions=3,
        client=client,
    )

    embedding = await model.embed("memory text")

    assert embedding == [0.1, 0.2, 0.3]
    assert calls == [
        {
            "model": "text-embedding-3-small",
            "input": "memory text",
            "dimensions": 3,
        }
    ]
