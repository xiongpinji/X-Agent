"""Full-coverage unit tests for backend.app.core.memory.store (MemorySystem).

Covers:
- Models: MemoryScope, MemoryRevision, MemoryItem, SessionRecord, MemorySearchHit, etc.
- MemorySystem: add, store, store_layer, sessions, revisions, rollback
- Pollution detection, shared memory routing
- Search with scoring (keyword, graph, vector, importance, freshness)
- Layer profiles, counts, summaries
- Consolidation, dedup, export/import
- Persistence (JSONL load/append/rewrite)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.memory.store import (
    MemoryConsolidationResult,
    MemoryExportBundle,
    MemoryItem,
    MemoryPollutionReport,
    MemoryRevision,
    MemoryRollbackResult,
    MemoryScope,
    MemorySearchHit,
    MemorySystem,
    MemoryUpdateResult,
    SessionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**kw) -> RunContext:
    defaults = dict(trace_id="t1", agent_id="agent1", tenant_id="ten1", user_id="u1")
    defaults.update(kw)
    return RunContext(**defaults)


def _memory(**kw) -> MemorySystem:
    return MemorySystem(enable_dedup=False, **kw)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_memory_scope_defaults(self):
        scope = MemoryScope()
        assert scope.share_scope == "private"
        assert scope.visibility == "private"
        assert scope.shared_with == []

    def test_memory_revision(self):
        rev = MemoryRevision(memory_id="m1", actor_agent_id="a1", summary="test")
        assert rev.revision_id
        assert rev.memory_id == "m1"

    def test_memory_item(self):
        item = MemoryItem(tenant_id="t1", content="hello", layer=3)
        assert item.id
        assert item.importance == 0.5
        assert item.tags == []

    def test_session_record(self):
        session = SessionRecord(tenant_id="t1", user_id="u1")
        assert session.session_id
        assert session.shared is False

    def test_memory_search_hit(self):
        item = MemoryItem(tenant_id="t1", content="x", layer=1)
        hit = MemorySearchHit(item=item, score=1.5)
        assert hit.keyword_score == 0.0

    def test_memory_export_bundle(self):
        bundle = MemoryExportBundle()
        assert bundle.memories == []
        assert bundle.sessions == []


# ---------------------------------------------------------------------------
# MemorySystem - basic operations
# ---------------------------------------------------------------------------

class TestMemorySystemBasic:
    def test_add_requires_tenant(self):
        mem = _memory()
        with pytest.raises(ValueError, match="tenant_id"):
            mem.add("content")

    def test_add(self):
        mem = _memory()
        mid = mem.add("test content", tenant_id="t1")
        assert mid
        assert mem.count() == 1
        item = mem.get_item(mid)
        assert item.content == "test content"
        assert item.layer == 3

    def test_add_with_summary(self):
        mem = _memory()
        mid = mem.add("content", summary="my summary", tenant_id="t1")
        item = mem.get_item(mid)
        assert item.metadata["summary"] == "my summary"

    def test_get_item_not_found(self):
        mem = _memory()
        assert mem.get_item("nonexistent") is None

    async def test_store(self):
        mem = _memory()
        ctx = _ctx()
        mid = await mem.store(ctx, "stored content", layer=5, importance=0.8, tags=["test"])
        assert mid
        item = mem.get_item(mid)
        assert item.content == "stored content"
        assert item.layer == 5
        assert item.importance == 0.8
        assert "test" in item.tags

    async def test_store_layer_normalization(self):
        mem = _memory()
        ctx = _ctx()
        mid = await mem.store_layer(ctx, layer=99, content="high layer")
        item = mem.get_item(mid)
        assert item.layer == 10

    async def test_store_with_session(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx, title="test session")
        mid = await mem.store(ctx, "session memory", session_id=session.session_id)
        item = mem.get_item(mid)
        assert item.session_id == session.session_id
        # Session should be updated
        assert mem.get_session(session.session_id).last_memory_id == mid

    async def test_store_with_scope(self):
        mem = _memory()
        ctx = _ctx()
        scope = MemoryScope(share_scope="team", visibility="shared")
        mid = await mem.store(ctx, "shared memory", scope=scope)
        item = mem.get_item(mid)
        assert item.scope.share_scope == "team"

    def test_count(self):
        mem = _memory()
        assert mem.count() == 0
        mem.add("x", tenant_id="t1")
        assert mem.count() == 1


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TestSessions:
    def test_start_session(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx, title="My Session", tags=["tag1"])
        assert session.session_id
        assert session.title == "My Session"
        assert "tag1" in session.tags

    def test_get_session(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx)
        assert mem.get_session(session.session_id) is session
        assert mem.get_session("nonexistent") is None

    def test_list_sessions(self):
        mem = _memory()
        ctx = _ctx()
        mem.start_session(ctx, title="s1")
        mem.start_session(_ctx(tenant_id="t2"), title="s2")
        assert len(mem.list_sessions()) == 2
        assert len(mem.list_sessions(tenant_id="ten1")) == 1

    def test_append_session_summary(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx)
        mem.append_session_summary(session.session_id, "first summary")
        assert "first summary" in mem.get_session(session.session_id).summary
        mem.append_session_summary(session.session_id, "second")
        assert "second" in mem.get_session(session.session_id).summary
        # Non-existent session - no error
        mem.append_session_summary("nonexistent", "noop")

    def test_session_snapshot(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx, title="snap")
        snap = mem.session_snapshot(session.session_id)
        assert snap["title"] == "snap"
        assert mem.session_snapshot("nonexistent") is None

    def test_session_count(self):
        mem = _memory()
        assert mem.session_count() == 0
        mem.start_session(_ctx())
        assert mem.session_count() == 1

    def test_session_items(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx)
        mem.add("item1", tenant_id="ten1")
        # Manually set session_id
        mem._items[0].session_id = session.session_id
        items = mem.session_items(session.session_id)
        assert len(items) == 1

    def test_session_summary(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx)
        mem.add("item1", tenant_id="ten1")
        mem._items[0].session_id = session.session_id
        summary = mem.session_summary(session.session_id)
        assert summary["count"] == 1
        assert mem.session_summary("nonexistent") is None

    def test_session_memory_layers(self):
        mem = _memory()
        ctx = _ctx()
        session = mem.start_session(ctx)
        mem.add("item1", tenant_id="ten1")
        mem._items[0].session_id = session.session_id
        layers = mem.session_memory_layers(session.session_id)
        assert len(layers) == 1
        assert layers[0]["layer"] == 3


# ---------------------------------------------------------------------------
# Revisions and Rollback
# ---------------------------------------------------------------------------

class TestRevisions:
    def test_add_revision(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        rev = mem.add_revision(mid, actor_agent_id="a1", summary="update")
        assert rev is not None
        assert rev.memory_id == mid
        item = mem.get_item(mid)
        assert len(item.revisions) == 1
        assert item.metadata["revision_count"] == 1

    def test_add_revision_not_found(self):
        mem = _memory()
        assert mem.add_revision("nonexistent", None, "") is None

    def test_list_revisions(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        mem.add_revision(mid, None, "rev1")
        mem.add_revision(mid, None, "rev2")
        revs = mem.list_revisions(mid)
        assert len(revs) == 2
        assert mem.list_revisions("nonexistent") == []

    def test_rollback_memory(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        rev = mem.add_revision(mid, None, "revision content")
        result = mem.rollback_memory(mid, rev.revision_id)
        assert result is not None
        assert result.revision_id == rev.revision_id

    def test_rollback_latest(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        mem.add_revision(mid, None, "rev1")
        result = mem.rollback_memory(mid)
        assert result is not None

    def test_rollback_no_revisions(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        result = mem.rollback_memory(mid)
        assert result is not None
        assert result.content == "original"

    def test_rollback_not_found(self):
        mem = _memory()
        assert mem.rollback_memory("nonexistent") is None

    def test_rollback_invalid_revision_id(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        mem.add_revision(mid, None, "rev1")
        assert mem.rollback_memory(mid, "bad-id") is None


# ---------------------------------------------------------------------------
# Pollution detection and shared memory
# ---------------------------------------------------------------------------

class TestPollutionAndSharing:
    def test_detect_pollution_low_risk(self):
        mem = _memory()
        mid = mem.add("safe content", tenant_id="t1")
        report = mem.detect_pollution(mid)
        assert report is not None
        assert report.risk_level == "low"
        assert report.blocked is False

    def test_detect_pollution_not_found(self):
        mem = _memory()
        assert mem.detect_pollution("nonexistent") is None

    def test_detect_pollution_high_risk(self):
        mem = _memory()
        mid = mem.add("shared content", tenant_id="t1")
        item = mem.get_item(mid)
        item.scope.visibility = "shared"
        item.session_id = None  # Not anchored to session
        report = mem.detect_pollution(mid)
        assert report.risk_level == "high"
        assert report.blocked is True

    def test_share_memory(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        item = mem.share_memory(mid, share_scope="team", shared_with=["agent2"])
        assert item is not None
        assert item.scope.visibility == "shared"
        assert item.scope.share_scope == "team"
        assert "agent2" in item.scope.shared_with

    def test_share_memory_not_found(self):
        mem = _memory()
        assert mem.share_memory("nonexistent", "team") is None

    def test_unshare_memory(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        mem.share_memory(mid, "team")
        item = mem.unshare_memory(mid)
        assert item.scope.visibility == "private"
        assert item.scope.shared_with == []

    def test_unshare_memory_not_found(self):
        mem = _memory()
        assert mem.unshare_memory("nonexistent") is None

    def test_route_shared_memory_accepted(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        item = mem.get_item(mid)
        item.scope.visibility = "shared"
        item.scope.share_scope = "project"
        item.session_id = "s1"
        routed = mem.route_shared_memory(mid)
        assert routed.metadata["shared_route"] == "accepted"

    def test_route_shared_memory_blocked(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        item = mem.get_item(mid)
        item.scope.visibility = "shared"
        item.session_id = None  # triggers high risk
        routed = mem.route_shared_memory(mid)
        assert routed.metadata["shared_route"] == "blocked"
        assert routed.scope.visibility == "private"

    def test_route_shared_memory_downgraded(self):
        mem = _memory()
        mid = mem.add("content", tenant_id="t1")
        item = mem.get_item(mid)
        item.scope.visibility = "shared"
        item.scope.share_scope = "team"
        item.scope.owner_agent_id = None  # triggers medium risk
        item.session_id = "s1"
        routed = mem.route_shared_memory(mid)
        assert routed.metadata["shared_route"] == "downgraded_to_project"

    def test_route_shared_memory_not_found(self):
        mem = _memory()
        assert mem.route_shared_memory("nonexistent") is None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    async def test_search_basic(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "python programming language")
        await mem.store(ctx, "javascript framework react")
        results = await mem.search(ctx, "python")
        assert len(results) >= 1
        assert "python" in results[0].content

    async def test_search_with_scores(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "machine learning algorithms")
        hits = await mem.search_with_scores(ctx, "machine learning")
        assert len(hits) >= 1
        assert hits[0].score > 0
        assert hits[0].keyword_score > 0

    async def test_search_layer_filter(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "layer 1 content", layer=1)
        await mem.store(ctx, "layer 5 content", layer=5)
        results = await mem.search(ctx, "content", layers=[5])
        for item in results:
            assert item.layer == 5

    async def test_search_no_results(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "completely unrelated xyz")
        results = await mem.search(ctx, "zzzznonexistentterm")
        assert len(results) == 0

    async def test_search_tenant_isolation(self):
        mem = _memory()
        ctx1 = _ctx(tenant_id="t1")
        ctx2 = _ctx(tenant_id="t2")
        await mem.store(ctx1, "tenant1 secret data")
        results = await mem.search(ctx2, "secret")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Layer operations
# ---------------------------------------------------------------------------

class TestLayers:
    def test_layer_profile(self):
        mem = _memory()
        profile = mem.layer_profile(1)
        assert profile["name"] == "instant_context"
        profile10 = mem.layer_profile(10)
        assert profile10["name"] == "long_term_evolution"

    def test_layer_counts(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")  # layer 3
        counts = mem.layer_counts()
        assert counts[3] == 1
        assert counts[1] == 0

    def test_layer_summary(self):
        mem = _memory()
        summary = mem.layer_summary()
        assert len(summary) == 10
        assert summary[0]["layer"] == 1

    def test_layer_roles(self):
        mem = _memory()
        roles = mem.layer_roles()
        assert roles[1] == "instant_context"
        assert roles[10] == "long_term_evolution"

    def test_layer_items(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")
        items = mem.layer_items(3)
        assert len(items) == 1
        assert mem.layer_items(1) == []

    def test_normalize_layer(self):
        assert MemorySystem._normalize_layer(0) == 1
        assert MemorySystem._normalize_layer(11) == 10
        assert MemorySystem._normalize_layer(5) == 5


# ---------------------------------------------------------------------------
# Agent operations
# ---------------------------------------------------------------------------

class TestAgentOps:
    async def test_agent_items(self):
        mem = _memory()
        ctx = _ctx(agent_id="agent1")
        await mem.store(ctx, "agent1 memory")
        items = mem.agent_items("agent1")
        assert len(items) == 1
        assert mem.agent_items("other") == []

    async def test_agent_summary(self):
        mem = _memory()
        ctx = _ctx(agent_id="agent1")
        await mem.store(ctx, "agent1 memory")
        summary = mem.agent_summary("agent1")
        assert summary["count"] == 1
        assert mem.agent_summary("nonexistent") is None

    async def test_agent_memory_layers(self):
        mem = _memory()
        ctx = _ctx(agent_id="agent1")
        await mem.store(ctx, "agent1 memory", layer=5)
        layers = mem.agent_memory_layers("agent1")
        assert len(layers) == 1
        assert layers[0]["layer"] == 5


# ---------------------------------------------------------------------------
# Consolidation
# ---------------------------------------------------------------------------

class TestConsolidation:
    async def test_consolidate(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "memory one", layer=3, importance=0.6)
        await mem.store(ctx, "memory two", layer=5, importance=0.7)
        # Use different request_id so items aren't filtered out
        ctx2 = _ctx(request_id="different-request")
        result = await mem.consolidate(ctx2, target_layer=4)
        assert result.source_count == 2
        assert result.target_memory_id is not None
        assert "consolidated" in result.tags

    async def test_consolidate_empty(self):
        mem = _memory()
        ctx = _ctx()
        result = await mem.consolidate(ctx)
        assert result.source_count == 0

    async def test_consolidate_min_importance(self):
        mem = _memory()
        ctx = _ctx()
        await mem.store(ctx, "low importance", layer=3, importance=0.1)
        result = await mem.consolidate(ctx, min_importance=0.5)
        assert result.source_count == 0


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

class TestExportImport:
    def test_export_bundle(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")
        mem.start_session(_ctx())
        bundle = mem.export_bundle()
        assert len(bundle.memories) == 1
        assert len(bundle.sessions) == 1

    def test_export_bundle_tenant_filter(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")
        mem.add("y", tenant_id="t2")
        bundle = mem.export_bundle(tenant_id="t1")
        assert len(bundle.memories) == 1

    def test_import_bundle(self):
        mem = _memory()
        item = MemoryItem(tenant_id="t1", content="imported", layer=3)
        session = SessionRecord(tenant_id="t1", user_id="u1")
        bundle = MemoryExportBundle(memories=[item], sessions=[session])
        result = mem.import_bundle(bundle)
        assert result["memories"] == 1
        assert result["sessions"] == 1
        assert mem.count() == 1

    def test_import_bundle_update_existing(self):
        mem = _memory()
        mid = mem.add("original", tenant_id="t1")
        item = MemoryItem(id=mid, tenant_id="t1", content="updated", layer=3)
        bundle = MemoryExportBundle(memories=[item])
        mem.import_bundle(bundle)
        assert mem.get_item(mid).content == "updated"


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

class TestDedup:
    def test_dedup_stats_disabled(self):
        mem = _memory()
        stats = mem.dedup_stats()
        assert stats["enabled"] is False

    def test_dedup_stats_enabled(self):
        mem = MemorySystem(enable_dedup=True)
        stats = mem.dedup_stats()
        assert stats["enabled"] is True
        assert stats["vector_threshold"] == 0.95

    async def test_store_dedup_exact_match(self):
        mem = MemorySystem(enable_dedup=True)
        ctx = _ctx()
        id1 = await mem.store(ctx, "duplicate content here")
        id2 = await mem.store(ctx, "duplicate content here")
        assert id1 == id2  # merged into same item
        assert mem.count() == 1

    async def test_store_no_dedup_different_content(self):
        mem = MemorySystem(enable_dedup=True)
        ctx = _ctx()
        id1 = await mem.store(ctx, "content alpha")
        id2 = await mem.store(ctx, "content beta totally different")
        assert id1 != id2
        assert mem.count() == 2

    async def test_deduplicate_batch(self):
        mem = MemorySystem(enable_dedup=True)
        ctx = _ctx()
        await mem.store(ctx, "same content xyz")
        # Manually add a duplicate bypassing write-path dedup
        item = MemoryItem(tenant_id="ten1", content="same content xyz", layer=3,
                          embedding=mem._embedding_model.embed("same content xyz"))
        mem._items.append(item)
        assert mem.count() == 2
        result = await mem.deduplicate(ctx)
        assert result["enabled"] is True

    async def test_deduplicate_disabled(self):
        mem = _memory()
        ctx = _ctx()
        result = await mem.deduplicate(ctx)
        assert result["enabled"] is False

    async def test_deduplicate_too_few(self):
        mem = MemorySystem(enable_dedup=True)
        ctx = _ctx()
        await mem.store(ctx, "only one item")
        result = await mem.deduplicate(ctx)
        assert result["removed"] == 0


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------

class TestStaticHelpers:
    def test_normalize_tags(self):
        assert MemorySystem._normalize_tags(None) == []
        assert MemorySystem._normalize_tags(["a", "b", "a"]) == ["a", "b"]
        assert MemorySystem._normalize_tags(["  ", "x"]) == ["x"]

    def test_normalize_metadata(self):
        assert MemorySystem._normalize_metadata(None) == {}
        assert MemorySystem._normalize_metadata({"k": "v"}) == {"k": "v"}

    def test_normalize_scope(self):
        ctx = _ctx()
        scope = MemorySystem._normalize_scope(None, ctx, "s1", {})
        assert scope.owner_agent_id == "agent1"
        assert scope.task_id == "s1"

    def test_normalize_scope_explicit(self):
        ctx = _ctx()
        explicit = MemoryScope(share_scope="team")
        scope = MemorySystem._normalize_scope(explicit, ctx, None, {})
        assert scope.share_scope == "team"

    def test_merge_session_summary(self):
        assert MemorySystem._merge_session_summary("", "new") == "new"
        result = MemorySystem._merge_session_summary("existing", "new")
        assert "existing" in result
        assert "new" in result

    def test_merge_tags(self):
        assert MemorySystem._merge_tags(["a"], ["b", "a"]) == ["a", "b"]
        # Max 20 tags
        result = MemorySystem._merge_tags([], [f"t{i}" for i in range(30)])
        assert len(result) == 20

    def test_freshness_score(self):
        now = datetime.now(UTC)
        score = MemorySystem._freshness_score(now)
        assert score > 0.9
        old = now - timedelta(days=30)
        old_score = MemorySystem._freshness_score(old)
        assert old_score < score

    def test_freshness_score_naive(self):
        naive = datetime(2024, 1, 1)
        score = MemorySystem._freshness_score(naive)
        assert 0 < score < 1

    def test_consolidation_summary(self):
        items = [
            MemoryItem(tenant_id="t", content="first item", layer=3, importance=0.5),
            MemoryItem(tenant_id="t", content="second item", layer=5, importance=0.8),
        ]
        summary = MemorySystem._consolidation_summary(items)
        assert "Consolidated memory:" in summary
        assert "first item" in summary

    def test_consolidation_tags(self):
        items = [
            MemoryItem(tenant_id="t", content="x", layer=3, tags=["python", "code"]),
            MemoryItem(tenant_id="t", content="y", layer=5, tags=["python"]),
        ]
        tags = MemorySystem._consolidation_tags(items)
        assert "consolidated" in tags
        assert "python" in tags

    def test_layer_role(self):
        assert MemorySystem._layer_role(1) == "instant_context"
        assert MemorySystem._layer_role(99) == "long_term_evolution"

    def test_scope_bonus(self):
        item = MemoryItem(tenant_id="t", content="x", layer=3,
                          scope=MemoryScope(room_id="r1", project_id="p1", task_id="task1", visibility="shared"))
        scope = MemoryScope(room_id="r1", project_id="p1", task_id="task1")
        bonus = MemorySystem._scope_bonus(item, scope)
        assert bonus > 1.0  # room(0.4) + project(0.3) + task(0.5) + shared(0.2)


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")
        snap = mem.snapshot()
        assert snap["count"] == 1
        assert snap["session_count"] == 0
        assert len(snap["layers"]) == 10


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persistence_roundtrip(self, tmp_path):
        path = tmp_path / "memory.jsonl"
        mem = MemorySystem(storage_path=path, enable_dedup=False)
        mid = mem.add("persisted content", tenant_id="t1")
        session = mem.start_session(_ctx(), title="persisted session")
        assert path.exists()
        # Reload
        mem2 = MemorySystem(storage_path=path, enable_dedup=False)
        assert mem2.count() == 1
        assert mem2.get_item(mid).content == "persisted content"
        assert mem2.get_session(session.session_id) is not None

    def test_persistence_upsert_by_id(self, tmp_path):
        path = tmp_path / "memory.jsonl"
        mem = MemorySystem(storage_path=path, enable_dedup=False)
        mid = mem.add("original", tenant_id="t1")
        # Mutate and re-append (simulates revision/share path)
        item = mem.get_item(mid)
        item.content = "updated"
        mem._append_to_disk(item)
        # Reload - should have 1 item with updated content
        mem2 = MemorySystem(storage_path=path, enable_dedup=False)
        assert mem2.count() == 1
        assert mem2.get_item(mid).content == "updated"

    def test_rewrite_disk(self, tmp_path):
        path = tmp_path / "memory.jsonl"
        mem = MemorySystem(storage_path=path, enable_dedup=False)
        mem.add("item1", tenant_id="t1")
        mem.add("item2", tenant_id="t1")
        mem.start_session(_ctx())
        mem._rewrite_disk()
        # Reload
        mem2 = MemorySystem(storage_path=path, enable_dedup=False)
        assert mem2.count() == 2
        assert mem2.session_count() == 1

    def test_no_storage_path(self):
        mem = _memory()
        mem.add("x", tenant_id="t1")
        # Should not raise
        mem._rewrite_disk()


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

class TestEmbedding:
    async def test_embed(self):
        mem = _memory()
        embedding = await mem._embed("test text")
        assert isinstance(embedding, list)
        assert len(embedding) > 0

    async def test_embedding_for_item_cached(self):
        mem = _memory()
        item = MemoryItem(tenant_id="t", content="x", layer=3, embedding=[1.0, 2.0])
        result = await mem._embedding_for_item(item)
        assert result == [1.0, 2.0]

    async def test_embedding_for_item_computed(self):
        mem = _memory()
        item = MemoryItem(tenant_id="t", content="hello world", layer=3)
        result = await mem._embedding_for_item(item)
        assert len(result) > 0
        assert item.embedding == result  # cached on item
