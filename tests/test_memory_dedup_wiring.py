"""Tests for write-path dedup wiring in the main memory store (P1-13).

Covers: exact-hash merge, vector-threshold merge via the repo's dedup engine,
tenant isolation, opt-out, the sync add() primitive staying raw, batch
maintenance dedup with JSONL rewrite, and the canonical model adapters that
unify the three legacy memory models.
"""

from __future__ import annotations

from backend.app.core.contracts import RunContext
from backend.app.core.memory import MemorySystem
from backend.app.core.memory_dedup_adapter import (
    WritePathDeduper,
    canonical_from_dedup_memory,
    canonical_from_hybrid_memory,
    canonical_from_store_item,
    dedup_memory_from_canonical,
    hybrid_memory_from_canonical,
)
from backend.app.core.memory_deduplication_enhanced import (
    Memory as DedupMemory,
    MemoryDeduplicatorEnhanced,
)


class MapEmbedding:
    """Deterministic mock embedding: exact vectors per text for threshold tests."""

    def __init__(self, mapping: dict[str, list[float]], default: list[float]) -> None:
        self.mapping = mapping
        self.default = default

    def embed(self, text: str) -> list[float]:
        return list(self.mapping.get(text, self.default))


class TestWritePathDedup:
    async def test_exact_duplicate_merges_into_existing(self) -> None:
        context = RunContext(tenant_id="t1")
        memory = MemorySystem()
        first_id = await memory.store(context, "用户喜欢深色模式", layer=3, importance=0.4)
        second_id = await memory.store(
            context, "用户喜欢深色模式", layer=5, importance=0.9, tags=["偏好"]
        )
        assert second_id == first_id
        assert memory.count() == 1
        kept = memory.get_item(first_id)
        assert kept.importance == 0.9  # max wins
        assert kept.tags == ["偏好"]  # union
        assert kept.metadata["merge_count"] == 1
        assert kept.metadata["merged_writes"][0]["layer"] == 5
        assert memory.dedup_stats()["merged_writes"] == 1

    async def test_whitespace_and_case_variants_merge(self) -> None:
        context = RunContext(tenant_id="t1")
        memory = MemorySystem()
        first_id = await memory.store(context, "Hello   World")
        second_id = await memory.store(context, "hello world")
        assert second_id == first_id
        assert memory.count() == 1

    async def test_vector_near_duplicate_merges_via_engine(self) -> None:
        embedding = MapEmbedding(
            {
                "alpha fact": [1.0, 0.0, 0.0],
                "alpha fact restated": [0.9995, 0.01, 0.0],
                "unrelated thing": [0.0, 1.0, 0.0],
            },
            default=[0.0, 0.0, 1.0],
        )
        context = RunContext(tenant_id="t1")
        memory = MemorySystem(embedding_model=embedding, dedup_vector_threshold=0.95)
        first_id = await memory.store(context, "alpha fact")
        second_id = await memory.store(context, "alpha fact restated")
        third_id = await memory.store(context, "unrelated thing")
        assert second_id == first_id  # cosine ~= 0.9999 >= 0.95
        assert third_id != first_id
        assert memory.count() == 2

    async def test_tenant_isolation_no_cross_tenant_merge(self) -> None:
        memory = MemorySystem()
        first_id = await memory.store(RunContext(tenant_id="t1"), "same content")
        second_id = await memory.store(RunContext(tenant_id="t2"), "same content")
        assert second_id != first_id
        assert memory.count() == 2

    async def test_dedup_opt_out(self) -> None:
        context = RunContext(tenant_id="t1")
        memory = MemorySystem(enable_dedup=False)
        first_id = await memory.store(context, "dup")
        second_id = await memory.store(context, "dup")
        assert second_id != first_id
        assert memory.count() == 2
        assert memory.dedup_stats()["enabled"] is False

    async def test_sync_add_stays_raw_append(self) -> None:
        memory = MemorySystem()
        a = memory.add("repeat", tenant_id="t1")
        b = memory.add("repeat", tenant_id="t1")
        assert a != b
        assert memory.count() == 2

    async def test_merge_still_attaches_session(self) -> None:
        context = RunContext(tenant_id="t1", user_id="u1")
        memory = MemorySystem()
        memory.start_session(context)
        session_id = next(iter(memory._sessions))
        first_id = await memory.store(context, "session fact", session_id=session_id)
        second_id = await memory.store(context, "session fact", session_id=session_id)
        assert second_id == first_id
        session = memory.get_session(session_id)
        assert session.last_memory_id == first_id


class TestBatchDeduplicate:
    async def test_batch_dedup_removes_and_persists(self, tmp_path) -> None:
        path = tmp_path / "memory.jsonl"
        context = RunContext(tenant_id="t1")
        memory = MemorySystem(storage_path=path)
        # 经 sync add 写入原始重复(不触发写路径去重)
        memory.add("dup content", tenant_id="t1")
        memory.add("dup content", tenant_id="t1")
        memory.add("unique content", tenant_id="t1")
        assert memory.count() == 3

        result = await memory.deduplicate(context)
        assert result["removed"] == 1
        assert result["deduplicated_count"] == 2
        assert memory.count() == 2

        # JSONL 已重写: 重载后不复活已删除项
        reloaded = MemorySystem(storage_path=path)
        assert reloaded.count() == 2

    async def test_batch_dedup_disabled_when_opted_out(self) -> None:
        memory = MemorySystem(enable_dedup=False)
        result = await memory.deduplicate(RunContext(tenant_id="t1"))
        assert result["enabled"] is False
        assert result["removed"] == 0


class TestCanonicalAdapters:
    def _make_store_item(self):
        from backend.app.core.memory.store import MemoryItem, MemoryScope

        return MemoryItem(
            tenant_id="t1",
            agent_id="a1",
            content="canonical content",
            layer=7,
            importance=0.8,
            tags=["x"],
            metadata={"k": "v"},
            embedding=[0.1, 0.2, 0.3],
            scope=MemoryScope(share_scope="project", visibility="shared"),
        )

    def test_store_item_round_trip_through_dedup_model(self) -> None:
        canonical = canonical_from_store_item(self._make_store_item())
        assert canonical.tenant_id == "t1"
        assert canonical.layer == 7
        assert canonical.share_scope == "project"

        dedup_memory = dedup_memory_from_canonical(canonical)
        assert isinstance(dedup_memory, DedupMemory)
        assert dedup_memory.content == "canonical content"
        assert dedup_memory.metadata["tenant_id"] == "t1"
        assert list(dedup_memory.embedding) == [0.1, 0.2, 0.3]

        back = canonical_from_dedup_memory(dedup_memory)
        assert back.id == canonical.id
        assert back.tenant_id == "t1"
        assert back.embedding == [0.1, 0.2, 0.3]

    def test_hybrid_round_trip(self) -> None:
        hybrid = hybrid_memory_from_canonical(canonical_from_store_item(self._make_store_item()))
        assert hybrid.content == "canonical content"
        assert hybrid.metadata["tenant_id"] == "t1"
        back = canonical_from_hybrid_memory(hybrid)
        assert back.id is not None
        assert back.embedding == [0.1, 0.2, 0.3]
        assert back.extras["tier"] == "hot"

    def test_hybrid_model_interop_methods(self) -> None:
        from backend.app.core.hybrid_memory_system import Memory as HybridMemory

        hybrid = HybridMemory(id="m1", content="interop", embedding=[1.0, 0.0])
        canonical = hybrid.to_canonical()
        assert canonical.id == "m1"
        rebuilt = HybridMemory.from_canonical(canonical)
        assert rebuilt.id == "m1"
        assert rebuilt.content == "interop"


class TestEngineSingleWriteCheck:
    def test_check_new_against_existing_hash_and_vector(self) -> None:
        import numpy as np

        engine = MemoryDeduplicatorEnhanced(vector_similarity_threshold=0.95)
        existing = [
            DedupMemory(id="e1", content="exact same", embedding=np.asarray([1.0, 0.0])),
            DedupMemory(id="e2", content="other", embedding=np.asarray([0.99, 0.01])),
            DedupMemory(id="e3", content="far", embedding=np.asarray([0.0, 1.0])),
        ]
        # 哈希命中
        hit = engine.check_new_against_existing(
            DedupMemory(id="n1", content="exact same"), existing
        )
        assert hit is not None and hit.id == "e1"
        # 向量命中 (cos([1,0],[0.99,0.01]) ~= 0.9999)
        hit = engine.check_new_against_existing(
            DedupMemory(id="n2", content="paraphrase", embedding=np.asarray([1.0, 0.0])),
            [existing[1], existing[2]],
        )
        assert hit is not None and hit.id == "e2"
        # 未命中
        miss = engine.check_new_against_existing(
            DedupMemory(id="n3", content="novel", embedding=np.asarray([0.0, 1.0])),
            [],
        )
        assert miss is None

    def test_write_path_deduper_hash_first(self) -> None:
        from backend.app.core.memory_dedup_adapter import CanonicalMemory

        deduper = WritePathDeduper(vector_threshold=0.95)
        new = CanonicalMemory(id="n", tenant_id="t", content="dup", layer=3)
        hit = deduper.find_duplicate(
            new, [CanonicalMemory(id="x", tenant_id="t", content="dup", layer=3)]
        )
        assert hit is not None and hit.id == "x"
