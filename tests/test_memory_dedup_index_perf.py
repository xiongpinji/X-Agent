"""Performance + correctness verification for the indexed write-path dedup.

Before indexing, ``store()`` re-hashed every candidate, awaited embeddings
one by one, and ran sklearn cosine per pair on every write (O(n^2) total;
2000 writes exceeded 300s on a Windows dev box). The indexed path keeps a
per-tenant hash index (O(1) exact dedup) and per-dimension L2-normalized
vector matrices (one numpy dot product per write).

These tests assert both semantics (exact/near duplicates merge, distinct
content survives, tenants stay isolated) and wall-clock budget (2000 writes
with an 8-dim mock embedding finish far below the legacy path).
"""

from __future__ import annotations

import hashlib
import time

from backend.app.core.contracts import RunContext
from backend.app.core.memory import MemorySystem


class HashEmbedding:
    """Deterministic 32-dim mock embedding derived from content bytes.

    Components are centered (mean ~0), so cosine between distinct contents is
    ~N(0, 1/32) and collisions above the 0.95 threshold are negligible; the
    legacy engine path and the indexed path compute the same cosine math.
    """

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [digest[i] / 127.5 - 1.0 for i in range(32)]


class TestIndexedWriteDedupPerf:
    async def test_2000_writes_under_budget_and_correct(self) -> None:
        memory = MemorySystem(embedding_model=HashEmbedding(), dedup_vector_threshold=0.95)
        assert memory.dedup_stats()["indexed"] is True
        context = RunContext(tenant_id="perf-tenant")

        start = time.perf_counter()
        for i in range(2000):
            await memory.store(context, f"unique memory content number {i}")
        elapsed = time.perf_counter() - start
        assert elapsed < 30, f"2000 indexed writes took {elapsed:.2f}s (budget 30s)"
        assert memory.count() == 2000, "distinct contents must all be kept"

        # Exact duplicate merges into the first write (kept id returned).
        first_id = await memory.store(context, "exact dup probe", importance=0.3)
        again_id = await memory.store(context, "  EXACT dup   probe ", importance=0.9, tags=["t"])
        assert again_id == first_id
        kept = memory.get_item(first_id)
        assert kept.importance == 0.9  # max wins
        assert kept.tags == ["t"]  # union
        assert kept.metadata["merged_writes"]  # 留痕

        # Vector near-duplicate (cosine >= 0.95) merges via the numpy matrix path.
        class MapEmbedding:
            def embed(self, text: str) -> list[float]:
                return {
                    "vector base": [1.0, 0.0, 0.0],
                    "vector near": [0.9995, 0.01, 0.0],
                    "vector far": [0.0, 1.0, 0.0],
                }.get(text, [0.0, 0.0, 1.0])

        memory2 = MemorySystem(embedding_model=MapEmbedding(), dedup_vector_threshold=0.95)
        base_id = await memory2.store(context, "vector base")
        near_id = await memory2.store(context, "vector near")
        far_id = await memory2.store(context, "vector far")
        assert near_id == base_id
        assert far_id != base_id
        assert memory2.count() == 2

        # Tenant isolation: same content under another tenant is NOT merged.
        other_tenant_id = await memory.store(
            RunContext(tenant_id="other-tenant"), "exact dup probe"
        )
        assert other_tenant_id != first_id

    async def test_index_survives_disk_reload(self, tmp_path) -> None:
        path = tmp_path / "memory.jsonl"
        context = RunContext(tenant_id="reload-tenant")
        memory = MemorySystem(storage_path=path, embedding_model=HashEmbedding())
        original_id = await memory.store(context, "persisted fact")

        reloaded = MemorySystem(storage_path=path, embedding_model=HashEmbedding())
        dup_id = await reloaded.store(context, "persisted fact")
        assert dup_id == original_id  # index rebuilt from _load_from_disk
        assert reloaded.count() == 1

    async def test_index_consistent_after_batch_dedup_removal(self) -> None:
        context = RunContext(tenant_id="batch-tenant")
        memory = MemorySystem(embedding_model=HashEmbedding())
        memory.add("raw dup", tenant_id="batch-tenant")  # raw append, no write dedup
        memory.add("raw dup", tenant_id="batch-tenant")
        result = await memory.deduplicate(context)
        assert result["removed"] == 1
        # After removal + index rebuild, write-path dedup still finds the survivor.
        survivor = next(i for i in memory._items if i.content == "raw dup")
        write_id = await memory.store(context, "raw dup")
        assert write_id == survivor.id
        assert memory.count() == 1
