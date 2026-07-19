"""Tests for the Qdrant memory backend (P1-13).

Covers: happy-path store/search/count against a fake Qdrant client, tenant
filtering, explicit degradation when the server/package is unavailable
(inspectable status + working fallback), strict fail-fast, and the neo4j
graph store's explicit dependency handling.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import DeterministicEmbeddingModel
from backend.app.core.memory_qdrant import QdrantMemorySystem, build_qdrant_memory_system


class FakeQdrantClient:
    """In-memory fake of the qdrant_client.QdrantClient surface we use."""

    def __init__(self) -> None:
        self.vectors_config: dict[str, object] = {}
        self.points: dict[str, dict[str, object]] = {}

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in self.vectors_config]
        )

    def create_collection(self, collection_name, vectors_config):
        self.vectors_config[collection_name] = vectors_config

    def get_collection(self, name):
        vectors = self.vectors_config[name]
        return SimpleNamespace(
            config=SimpleNamespace(params=SimpleNamespace(vectors=vectors))
        )

    def upsert(self, collection_name, points):
        for point in points:
            self.points[point.id] = {"vector": point.vector, "payload": point.payload}

    def query_points(self, collection_name, query, query_filter, limit, with_payload):
        tenant_id = None
        layers = None
        for condition in getattr(query_filter, "must", []) or []:
            if condition.key == "tenant_id":
                tenant_id = condition.match.value
            if condition.key == "layer":
                layers = set(condition.match.any)
        scored = []
        for point_id, data in self.points.items():
            payload = data["payload"]
            if tenant_id is not None and payload.get("tenant_id") != tenant_id:
                continue
            if layers is not None and payload.get("layer") not in layers:
                continue
            score = DeterministicEmbeddingModel.similarity(query, data["vector"])
            scored.append(SimpleNamespace(id=point_id, payload=payload, score=score))
        scored.sort(key=lambda point: point.score, reverse=True)
        return SimpleNamespace(points=scored[:limit])

    def count(self, collection_name, count_filter=None, exact=False):
        return SimpleNamespace(count=len(self.points))

    def scroll(self, collection_name, scroll_filter, limit, with_payload):
        records = [
            SimpleNamespace(id=pid, payload=data["payload"])
            for pid, data in list(self.points.items())[:limit]
        ]
        return records, None


@pytest.fixture
def fake_client() -> FakeQdrantClient:
    return FakeQdrantClient()


class TestQdrantHappyPath:
    async def test_store_search_count(self, fake_client) -> None:
        system = QdrantMemorySystem(
            client=fake_client,
            embedding_model=DeterministicEmbeddingModel(dimensions=32),
        )
        assert system.available
        assert system.backend_status == "ok"
        context = RunContext(tenant_id="t1")
        item_id = await system.store(
            context, "qdrant stores semantic memory", layer=3, importance=0.8
        )
        assert item_id
        assert await system.count() == 1

        hits = await system.search_with_scores(context, "semantic memory", layers=[3])
        assert hits
        assert hits[0].item.id == item_id
        assert hits[0].item.content == "qdrant stores semantic memory"
        assert hits[0].vector_score > 0
        assert hits[0].item.importance == 0.8

    async def test_tenant_isolation(self, fake_client) -> None:
        system = QdrantMemorySystem(
            client=fake_client,
            embedding_model=DeterministicEmbeddingModel(dimensions=32),
        )
        await system.store(RunContext(tenant_id="t1"), "tenant one fact")
        await system.store(RunContext(tenant_id="t2"), "tenant two fact")
        hits_t1 = await system.search(RunContext(tenant_id="t1"), "tenant")
        assert len(hits_t1) == 1
        assert hits_t1[0].tenant_id == "t1"
        assert await system.count() == 2

    async def test_layer_filter(self, fake_client) -> None:
        system = QdrantMemorySystem(
            client=fake_client,
            embedding_model=DeterministicEmbeddingModel(dimensions=32),
        )
        context = RunContext(tenant_id="t1")
        await system.store(context, "layer three fact", layer=3)
        await system.store(context, "layer eight fact", layer=8)
        hits = await system.search(context, "fact", layers=[8])
        assert len(hits) == 1
        assert hits[0].layer == 8

    async def test_consolidate(self, fake_client) -> None:
        system = QdrantMemorySystem(
            client=fake_client,
            embedding_model=DeterministicEmbeddingModel(dimensions=32),
        )
        context = RunContext(tenant_id="t1")
        await system.store(context, "source memory one", layer=3, importance=0.6)
        await system.store(context, "source memory two", layer=3, importance=0.7)
        result = await system.consolidate(context, source_layers=[3], target_layer=4)
        assert result.source_count == 2
        assert result.target_memory_id
        assert await system.count() == 3

    async def test_revisions_raise_explicitly(self, fake_client) -> None:
        system = QdrantMemorySystem(client=fake_client)
        with pytest.raises(NotImplementedError, match="revisions"):
            system.add_revision("some-id", None, "summary")


class TestQdrantDegradation:
    async def test_unreachable_server_degrades_explicitly(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            system = build_qdrant_memory_system(
                url="http://127.0.0.1:1",  # 连接即拒
                embedding_model=DeterministicEmbeddingModel(dimensions=16),
                strict=False,
                connect_timeout_seconds=1.0,
            )
        assert not system.available
        assert system.backend_status == "degraded"
        assert system.degraded_reason
        assert any("DEGRADED" in record.message for record in caplog.records)
        # 降级后功能经内嵌 JSONL/内存库可用, 且状态可检查 —— 非静默
        context = RunContext(tenant_id="t1")
        item_id = await system.store(context, "fallback write")
        assert item_id
        hits = await system.search(context, "fallback")
        assert hits and hits[0].content == "fallback write"
        assert system.status()["status"] == "degraded"

    def test_unreachable_server_strict_raises(self) -> None:
        with pytest.raises(RuntimeError, match="qdrant"):
            build_qdrant_memory_system(
                url="http://127.0.0.1:1",
                strict=True,
                connect_timeout_seconds=1.0,
            )

    def test_missing_package_strict_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("backend.app.core.memory_qdrant.QdrantClient", None)
        with pytest.raises(RuntimeError, match="qdrant-client"):
            QdrantMemorySystem(url="http://whatever:6333", strict=True)

    def test_missing_package_degrades(self, monkeypatch, caplog) -> None:
        monkeypatch.setattr("backend.app.core.memory_qdrant.QdrantClient", None)
        with caplog.at_level(logging.WARNING):
            system = QdrantMemorySystem(url="http://whatever:6333")
        assert system.backend_status == "degraded"
        assert "qdrant-client" in (system.degraded_reason or "")


class TestNeo4jGraphDependency:
    def test_create_driver_without_package_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("backend.app.core.graph_memory_store.NEO4J_AVAILABLE", False)
        from backend.app.core.graph_memory_store import GraphMemoryStore

        with pytest.raises(RuntimeError, match="neo4j"):
            GraphMemoryStore.create_driver("bolt://localhost:7687")

    def test_no_driver_is_explicit_noop(self, caplog) -> None:
        from backend.app.core.graph_memory_store import GraphMemoryStore

        with caplog.at_level(logging.INFO):
            store = GraphMemoryStore(neo4j_driver=None)
        assert not store.available
        assert any("no-op degraded" in record.message for record in caplog.records)

    def test_create_driver_constructs_when_package_present(self) -> None:
        from backend.app.core.graph_memory_store import GraphMemoryStore, NEO4J_AVAILABLE

        if not NEO4J_AVAILABLE:
            pytest.skip("neo4j package not installed")
        # 驱动为惰性连接: 构造即成功, 不触发网络
        store = GraphMemoryStore.create_driver("bolt://127.0.0.1:1")
        assert store.available
