"""FTS5 引擎接入 MemorySystem 主路径的集成测试。

覆盖（任务要求）:
- 写路径接线: store()/add() 落盘同步 index_memory（中英文各一例可搜）
- BM25 排序合理性（词频高者分高）
- FTS 损坏/异常时回退全量线性扫描（降级安全）
- _load_from_disk 全量重建索引幂等（重复重建行数不变）
- FTS 路径可配置: 显式参数 / XAGENT_MEMORY_FTS_PATH env / storage 同级默认 / off 开关
- FTS 写失败仅告警不阻断
- 小数据集下线性扫 vs FTS 的耗时对比日志
"""

from __future__ import annotations

import logging
import sqlite3
import time

import pytest

from backend.app.core.contracts import RunContext
from backend.app.core.memory.store import MemorySystem
from backend.app.core.memory_fts import MemoryFTSEngine

LOGGER = logging.getLogger(__name__)


def _ctx(**kw) -> RunContext:
    defaults = dict(trace_id="t-fts", agent_id="agent-fts", tenant_id="ten-fts", user_id="u1")
    defaults.update(kw)
    return RunContext(**defaults)


def _system(tmp_path, **kw) -> MemorySystem:
    """Isolated MemorySystem: jsonl + fts 库都在 tmp_path，不污染生产 data/。"""
    kw.setdefault("storage_path", tmp_path / "memory.jsonl")
    kw.setdefault("fts_path", tmp_path / "memory_fts.sqlite3")
    kw.setdefault("enable_dedup", False)
    return MemorySystem(**kw)


# ---------------------------------------------------------------------------
# 1. 写路径接线：写入 -> FTS 可搜（中英文）
# ---------------------------------------------------------------------------


async def test_write_then_fts_searchable_english(tmp_path):
    system = _system(tmp_path)
    memory_id = await system.store(
        _ctx(), "deploy the payment service with blue green strategy", layer=3
    )
    engine = system._get_fts()
    assert engine is not None

    response = engine.search("payment", tenant_id="ten-fts", limit=10)
    assert [r.memory_id for r in response.results] == [memory_id]
    assert response.results[0].content.startswith("deploy the payment")

    # 主路径 search 也应命中（FTS 候选 + 重排）
    hits = await system.search_with_scores(_ctx(), "payment", top_k=5)
    assert memory_id in {h.item.id for h in hits}
    system.close_fts()


async def test_write_then_fts_searchable_chinese(tmp_path):
    system = _system(tmp_path)
    memory_id = await system.store(
        _ctx(), "用户偏好深色主题界面，夜间模式下护眼", layer=3
    )
    engine = system._get_fts()
    assert engine is not None

    response = engine.search("深色主题", tenant_id="ten-fts", limit=10)
    assert memory_id in {r.memory_id for r in response.results}

    hits = await system.search_with_scores(_ctx(), "深色主题", top_k=5)
    assert memory_id in {h.item.id for h in hits}
    system.close_fts()


async def test_raw_add_also_indexes_fts(tmp_path):
    """同步 add() 是 raw append 原语，同样经 _append_to_disk 接线进 FTS。"""
    system = _system(tmp_path)
    memory_id = system.add("raw append kafka consumer lag alert", tenant_id="ten-fts")
    engine = system._get_fts()
    response = engine.search("kafka", tenant_id="ten-fts")
    assert memory_id in {r.memory_id for r in response.results}
    system.close_fts()


# ---------------------------------------------------------------------------
# 2. BM25 排序合理性
# ---------------------------------------------------------------------------


async def test_bm25_ranking_prefers_higher_term_frequency(tmp_path):
    system = _system(tmp_path)
    frequent_id = await system.store(
        _ctx(), "python python python recipes for data pipelines", layer=3
    )
    single_id = await system.store(_ctx(), "a note about python and testing", layer=3)
    unrelated_id = await system.store(_ctx(), "weather forecast for tomorrow", layer=3)

    engine = system._get_fts()
    response = engine.search("python", tenant_id="ten-fts", limit=10)
    ids = [r.memory_id for r in response.results]
    scores = {r.memory_id: r.score for r in response.results}

    assert unrelated_id not in ids  # 无关键词命中不进候选
    assert ids.index(frequent_id) < ids.index(single_id)  # 词频高者 BM25 靠前
    assert scores[frequent_id] > scores[single_id]
    system.close_fts()


async def test_fts_candidates_include_keyword_exact_hits(tmp_path, caplog):
    """质量底线：FTS 候选必须包含关键词精确命中的条目（含中文干扰项）。"""
    system = _system(tmp_path)
    target_id = await system.store(_ctx(), "kubernetes cluster autoscaling policy", layer=3)
    for i in range(10):
        await system.store(_ctx(), f"unrelated filler note number {i} about lunch plans", layer=3)
    await system.store(_ctx(), "深夜模式下阅读长文", layer=3)  # 中文干扰项

    with caplog.at_level(logging.DEBUG, logger="backend.app.core.memory.store"):
        hits = await system.search_with_scores(_ctx(), "kubernetes", top_k=3)

    assert hits, "keyword-exact hit must be found"
    assert hits[0].item.id == target_id
    assert hits[0].keyword_score > 0
    assert any("fts=True" in record.message for record in caplog.records)
    system.close_fts()


# ---------------------------------------------------------------------------
# 3. FTS 损坏 / 异常时回退全量扫描（降级安全）
# ---------------------------------------------------------------------------


async def _seed(system: MemorySystem) -> None:
    """写入固定语料（每个系统只 seed 一次）。"""
    await system.store(_ctx(), "postgresql vacuum full analysis", layer=3)
    await system.store(_ctx(), "redis eviction policy allkeys lru", layer=3)
    await system.store(_ctx(), "配置中心热更新开关说明", layer=3)


async def test_fts_runtime_error_falls_back_to_full_scan(tmp_path, monkeypatch, caplog):
    """engine.search 抛异常 -> 告警 + 全量线性扫描，结果不劣化。"""
    system = _system(tmp_path)
    baseline = _system(tmp_path / "baseline", enable_fts=False)
    await _seed(system)
    await _seed(baseline)

    query = "redis eviction"
    assert [h.item.content for h in await system.search_with_scores(_ctx(), query)] == [
        h.item.content for h in await baseline.search_with_scores(_ctx(), query)
    ]

    def _boom(*args, **kwargs):
        raise RuntimeError("fts index corrupted")

    monkeypatch.setattr(MemoryFTSEngine, "search", _boom)
    with caplog.at_level(logging.WARNING, logger="backend.app.core.memory.store"):
        fallback_hits = await system.search_with_scores(_ctx(), query, top_k=5)
    baseline_hits = await baseline.search_with_scores(_ctx(), query, top_k=5)

    assert [h.item.content for h in fallback_hits] == [h.item.content for h in baseline_hits]
    assert any("falling back to linear scan" in r.message for r in caplog.records)
    system.close_fts()
    baseline.close_fts()


async def test_corrupt_fts_file_degrades_to_linear_scan(tmp_path, caplog):
    """FTS 库文件物理损坏 -> 重建失败告警 + 停用 FTS，搜索回退全扫仍正确。"""
    system = _system(tmp_path)
    await system.store(_ctx(), "opentelemetry trace sampling head", layer=3)
    await system.store(_ctx(), "message queue backpressure handling", layer=3)
    system.close_fts()

    # 物理损坏 FTS 库（覆盖为垃圾字节，保留 jsonl）
    fts_file = tmp_path / "memory_fts.sqlite3"
    fts_file.write_bytes(b"this is not a sqlite database at all" * 64)

    with caplog.at_level(logging.WARNING, logger="backend.app.core.memory.store"):
        revived = MemorySystem(
            storage_path=tmp_path / "memory.jsonl",
            fts_path=fts_file,
            enable_dedup=False,
        )

    assert revived.count() == 2
    assert revived._get_fts() is None  # 引擎初始化失败已停用
    assert any("memory fts" in r.message.lower() for r in caplog.records)

    hits = await revived.search_with_scores(_ctx(), "backpressure", top_k=5)
    assert hits and "backpressure" in hits[0].item.content
    revived.close_fts()


async def test_empty_fts_index_falls_back_to_full_scan(tmp_path):
    """FTS 库为空（如索引丢失）时同样回退全扫，不丢召回。"""
    system = _system(tmp_path)
    await system.store(_ctx(), "oslo norway fjord cruise itinerary", layer=3)
    # 清空 FTS 索引但保留 jsonl/内存
    engine = system._get_fts()
    engine.remove_memories([item.id for item in system._items])
    assert engine.search("fjord", tenant_id="ten-fts").results == []

    hits = await system.search_with_scores(_ctx(), "fjord", top_k=5)
    assert hits and "fjord" in hits[0].item.content
    system.close_fts()


# ---------------------------------------------------------------------------
# 4. 重建索引幂等
# ---------------------------------------------------------------------------


async def test_rebuild_index_idempotent(tmp_path):
    system = _system(tmp_path)
    ids = [
        await system.store(_ctx(), f"memory fragment {i} about networking", layer=3)
        for i in range(5)
    ]

    engine = system._get_fts()
    system._rebuild_fts_index()
    system._rebuild_fts_index()  # 重复重建
    conn = engine._get_conn()
    meta_rows = conn.execute("SELECT COUNT(*) FROM memory_meta").fetchone()[0]
    fts_rows = conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
    assert meta_rows == 5
    assert fts_rows == 5

    # 重启加载路径: jsonl 重建索引仍然幂等（不重复、不丢失）
    system.close_fts()
    revived = MemorySystem(
        storage_path=tmp_path / "memory.jsonl",
        fts_path=tmp_path / "memory_fts.sqlite3",
        enable_dedup=False,
    )
    engine2 = revived._get_fts()
    conn2 = engine2._get_conn()
    assert conn2.execute("SELECT COUNT(*) FROM memory_meta").fetchone()[0] == 5
    assert conn2.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0] == 5

    response = engine2.search("networking", tenant_id="ten-fts")
    assert set(ids) == {r.memory_id for r in response.results}
    revived.close_fts()


# ---------------------------------------------------------------------------
# 5. 路径配置: env 覆盖 / 同级默认 / off 开关
# ---------------------------------------------------------------------------


async def test_fts_path_env_override(tmp_path, monkeypatch):
    env_path = tmp_path / "env_dir" / "override_fts.sqlite3"
    monkeypatch.setenv("XAGENT_MEMORY_FTS_PATH", str(env_path))
    system = MemorySystem(
        storage_path=tmp_path / "memory.jsonl", enable_dedup=False
    )
    assert system._fts_path == env_path
    await system.store(_ctx(), "env override path indexing check", layer=3)
    assert env_path.exists()
    system.close_fts()


async def test_fts_default_is_sibling_of_storage(tmp_path, monkeypatch):
    monkeypatch.delenv("XAGENT_MEMORY_FTS_PATH", raising=False)
    nested = tmp_path / "nested"
    system = MemorySystem(storage_path=nested / "memory.jsonl", enable_dedup=False)
    assert system._fts_path == nested / "memory_fts.sqlite3"
    system.add("sibling default path", tenant_id="ten-fts")
    assert (nested / "memory_fts.sqlite3").exists()
    system.close_fts()


async def test_fts_disabled_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("XAGENT_MEMORY_FTS", "off")
    fts_path = tmp_path / "disabled.sqlite3"
    system = MemorySystem(
        storage_path=tmp_path / "memory.jsonl",
        fts_path=fts_path,
        enable_dedup=False,
    )
    assert system._fts_path is None
    memory_id = await system.store(_ctx(), "linear scan only mode content", layer=3)
    assert not fts_path.exists()

    hits = await system.search_with_scores(_ctx(), "linear scan", top_k=5)
    assert memory_id in {h.item.id for h in hits}


async def test_in_memory_system_has_fts_off_by_default(tmp_path, monkeypatch):
    """纯内存模式(storage_path=None)默认不开 FTS，避免污染 data/。"""
    monkeypatch.delenv("XAGENT_MEMORY_FTS_PATH", raising=False)
    system = MemorySystem(enable_dedup=False)
    assert system._fts_path is None
    memory_id = await system.store(_ctx(), "pure in memory item", layer=3)
    hits = await system.search_with_scores(_ctx(), "pure in memory", top_k=5)
    assert memory_id in {h.item.id for h in hits}


# ---------------------------------------------------------------------------
# 6. 写失败仅告警不阻断
# ---------------------------------------------------------------------------


async def test_fts_write_failure_warns_without_blocking(tmp_path, monkeypatch, caplog):
    system = _system(tmp_path)

    def _fail(*args, **kwargs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(MemoryFTSEngine, "index_memory", _fail)
    with caplog.at_level(logging.WARNING, logger="backend.app.core.memory.store"):
        memory_id = await system.store(_ctx(), "must survive fts write failure", layer=3)

    assert memory_id  # 写路径未被阻断
    assert system.count() == 1
    assert (tmp_path / "memory.jsonl").exists()  # jsonl 落盘正常
    assert any("memory fts index write failed" in r.message for r in caplog.records)
    monkeypatch.undo()

    # 引擎恢复后可补写（幂等 upsert 兜底）
    system._index_fts(system._items[0])
    engine = system._get_fts()
    assert engine.search("survive", tenant_id="ten-fts").results
    system.close_fts()


# ---------------------------------------------------------------------------
# 7. 性能对比：小数据集下线性扫 vs FTS 耗时日志
# ---------------------------------------------------------------------------


async def test_fts_vs_linear_performance_log(tmp_path):
    """300 条记忆下对比两种检索耗时（输出日志，不做脆弱的时间断言）。"""
    total, keyword_docs = 300, 12
    contents = [
        f"quantum computing qubit entanglement notes {i}" if i < keyword_docs
        else f"filler memo {i} about meetings and coffee preferences"
        for i in range(total)
    ]

    async def _fill(system: MemorySystem) -> None:
        for i, content in enumerate(contents):
            await system.store(_ctx(), content, layer=3, importance=0.5)

    fts_system = _system(tmp_path / "fts")
    linear_system = _system(tmp_path / "linear", enable_fts=False)
    await _fill(fts_system)
    await _fill(linear_system)

    query = "quantum entanglement"

    started = time.perf_counter()
    fts_hits = await fts_system.search_with_scores(_ctx(), query, top_k=5)
    fts_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    linear_hits = await linear_system.search_with_scores(_ctx(), query, top_k=5)
    linear_ms = (time.perf_counter() - started) * 1000

    LOGGER.info(
        "memory search perf (n=%d, query=%r): fts=%.2fms linear=%.2fms speedup=%.1fx",
        total,
        query,
        fts_ms,
        linear_ms,
        linear_ms / max(fts_ms, 1e-9),
    )
    print(
        f"\n[perf] n={total} query={query!r}: fts={fts_ms:.2f}ms "
        f"linear={linear_ms:.2f}ms speedup={linear_ms / max(fts_ms, 1e-9):.1f}x"
    )

    # 质量不劣于现状: 两者 top-5 内容集合一致（id 因两套系统而不同，用内容对比）
    assert {h.item.content for h in fts_hits} == {h.item.content for h in linear_hits}
    assert len(fts_hits) == 5
    assert all("quantum" in h.item.content for h in fts_hits)
    fts_system.close_fts()
    linear_system.close_fts()
