"""P1-04: 审计日志轮转与留存单元测试。

覆盖:
- 按大小轮转(rotator 直测 + AuditStore 集成)
- 按日期轮转(注入时间)
- 留存清理: 默认 30 天 / 合规档 7 年 / 0=永久保留
- 轮转后进程内链验证 + 跨段文件链验证
- 简化 API: should_rotate / rotate / cleanup_old / get_stats
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.core.audit import AuditStore
from backend.app.core.audit_rotation import (
    COMPLIANCE_RETENTION_DAYS,
    AuditLogRotator,
    AuditRotationConfig,
)


def _write_lines(path: Path, n: int, payload: str = "x" * 64) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for i in range(n):
            handle.write(json.dumps({"i": i, "payload": payload}) + "\n")


def _make_segment(archive_dir: Path, stem: str, day: str, seq: int = 1) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    segment = archive_dir / f"{stem}-{day}-000000-{seq:04d}.jsonl"
    segment.write_text(json.dumps({"segment": day}) + "\n", encoding="utf-8")
    return segment


# ---------------------------------------------------------------------------
# 按大小轮转
# ---------------------------------------------------------------------------


def test_size_based_rotation(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    rotator = AuditLogRotator(AuditRotationConfig(max_bytes=1024, rotate_daily=False))

    _write_lines(live, 100)  # ~7KB > 1KB 上限
    segment = rotator.maybe_rotate(live)

    assert segment is not None
    assert segment.exists()
    assert not live.exists()  # 活动文件已被轮转走
    assert segment.parent == tmp_path / "audit_segments"
    assert segment.name.startswith("audit-")
    assert segment.name.endswith(".jsonl")

    # 标记文件已更新为当天
    marker = tmp_path / "audit.jsonl.segment_date"
    assert marker.exists()


def test_no_rotation_below_size_limit(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    rotator = AuditLogRotator(AuditRotationConfig(max_bytes=10 * 1024 * 1024, rotate_daily=False))

    _write_lines(live, 2)
    assert rotator.maybe_rotate(live) is None
    assert live.exists()


def test_size_rotation_disabled_when_zero(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    rotator = AuditLogRotator(AuditRotationConfig(max_bytes=0, rotate_daily=False))

    _write_lines(live, 500)
    assert rotator.maybe_rotate(live) is None


# ---------------------------------------------------------------------------
# 按日期轮转
# ---------------------------------------------------------------------------


def test_date_based_rotation(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    marker = tmp_path / "audit.jsonl.segment_date"
    rotator = AuditLogRotator(AuditRotationConfig(max_bytes=0, rotate_daily=True))

    day1 = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
    day2 = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    # 显式预置日期标记为 day1(避免依赖真实文件 mtime 时钟)
    _write_lines(live, 3)
    marker.write_text(day1.date().isoformat(), encoding="utf-8")

    # 同一天不轮转
    assert rotator.maybe_rotate(live, now=day1) is None

    # 跨天 → 轮转
    segment = rotator.maybe_rotate(live, now=day2)
    assert segment is not None
    assert segment.exists()
    assert marker.read_text(encoding="utf-8").strip() == day2.date().isoformat()

    # 同一天内不再轮转
    _write_lines(live, 3)
    assert rotator.maybe_rotate(live, now=day2) is None


# ---------------------------------------------------------------------------
# 留存清理
# ---------------------------------------------------------------------------


def test_retention_cleanup_default_30_days(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    live.write_text("", encoding="utf-8")
    archive = tmp_path / "audit_segments"

    now = datetime(2026, 7, 20, tzinfo=UTC)
    old_day = (now - timedelta(days=120)).strftime("%Y%m%d")
    edge_day = (now - timedelta(days=91)).strftime("%Y%m%d")
    kept_day = (now - timedelta(days=10)).strftime("%Y%m%d")

    old_seg = _make_segment(archive, "audit", old_day)
    edge_seg = _make_segment(archive, "audit", edge_day)
    kept_seg = _make_segment(archive, "audit", kept_day)

    rotator = AuditLogRotator(AuditRotationConfig())  # 默认 30 天
    deleted = rotator.cleanup_expired(live, now=now)

    assert set(deleted) == {old_seg, edge_seg}
    assert not old_seg.exists()
    assert not edge_seg.exists()
    assert kept_seg.exists()


def test_retention_compliance_profile_keeps_7_years(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    live.write_text("", encoding="utf-8")
    archive = tmp_path / "audit_segments"

    now = datetime(2026, 7, 20, tzinfo=UTC)
    six_years = (now - timedelta(days=365 * 6)).strftime("%Y%m%d")
    eight_years = (now - timedelta(days=365 * 8)).strftime("%Y%m%d")

    kept_seg = _make_segment(archive, "audit", six_years)
    expired_seg = _make_segment(archive, "audit", eight_years)

    rotator = AuditLogRotator(AuditRotationConfig.compliance())
    assert rotator.config.retention_days == COMPLIANCE_RETENTION_DAYS == 365 * 7

    deleted = rotator.cleanup_expired(live, now=now)
    assert set(deleted) == {expired_seg}
    assert kept_seg.exists()


def test_retention_zero_keeps_everything(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    live.write_text("", encoding="utf-8")
    archive = tmp_path / "audit_segments"

    ancient = _make_segment(archive, "audit", "20100101")
    rotator = AuditLogRotator(AuditRotationConfig(retention_days=0))
    assert rotator.cleanup_expired(live) == []
    assert ancient.exists()


# ---------------------------------------------------------------------------
# AuditStore 集成: 轮转 + 链验证
# ---------------------------------------------------------------------------


def test_store_rotation_and_chain_integrity(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    store = AuditStore(
        storage_path=live,
        hmac_secret="rotation-secret",
        rotation=AuditRotationConfig(max_bytes=2048, rotate_daily=False),
    )

    for i in range(60):
        store.record(action=f"action-{i}", resource_type="test", tenant_id="t1")

    segments = store.rotated_segments()
    assert len(segments) >= 1, "按大小轮转应产生至少一个段"
    assert live.exists()

    # 进程内完整链验证
    assert store.verify_chain().valid is True

    # 跨段文件链验证(模拟重启后: 段 + 活动文件)
    across = store.verify_chain_across_files()
    assert across.valid is True
    assert across.checked == 60
    assert across.signed == 60


def test_store_verify_chain_detects_tamper_after_rotation(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    store = AuditStore(
        storage_path=live,
        hmac_secret="rotation-secret",
        rotation=AuditRotationConfig(max_bytes=1024, rotate_daily=False),
    )
    for _ in range(40):
        store.record(action=f"action-{_}", resource_type="test")

    segment = store.rotated_segments()[0]
    lines = segment.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["outcome"] = "tampered"
    lines[0] = json.dumps(payload)
    segment.write_text("\n".join(lines) + "\n", encoding="utf-8")

    across = store.verify_chain_across_files()
    assert across.valid is False
    # 篡改 outcome 后 hash 不再匹配 → 在 hash 校验处即被检出
    assert across.reason == "Record hash mismatch."
    assert across.broken_at == payload["id"]


def test_store_cleanup_expired_segments(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    store = AuditStore(
        storage_path=live,
        rotation=AuditRotationConfig(retention_days=90),
    )
    archive = tmp_path / "audit_segments"
    old_seg = _make_segment(archive, "audit", "20200101")

    deleted = store.cleanup_expired_segments()
    assert deleted == [old_seg]
    assert not old_seg.exists()


def test_store_without_rotation_unchanged(tmp_path: Path) -> None:
    """未配置轮转时行为与原来完全一致(回归保护)。"""
    live = tmp_path / "audit.jsonl"
    store = AuditStore(storage_path=live, hmac_secret="s")
    for _ in range(5):
        store.record(action="a", resource_type="t")

    assert store.rotated_segments() == []
    assert store.cleanup_expired_segments() == []
    assert store.verify_chain().valid is True
    assert store.verify_chain_across_files().valid is True

    reloaded = AuditStore(storage_path=live, hmac_secret="s")
    assert reloaded.count() == 5
    assert reloaded.verify_chain().valid is True


# ---------------------------------------------------------------------------
# 简化 API: should_rotate / rotate / cleanup_old / get_stats
# ---------------------------------------------------------------------------


def test_simplified_should_rotate(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    rotator = AuditLogRotator(log_path=live, max_size_mb=1, retention_days=30)
    # 覆盖 max_bytes 为小值以便测试
    rotator.config.max_bytes = 512
    rotator.config.rotate_daily = False

    # 空文件 / 不存在 → 不需轮转
    assert rotator.should_rotate() is False

    _write_lines(live, 50)  # 超过 512 bytes
    assert rotator.should_rotate() is True


def test_simplified_rotate(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    rotator = AuditLogRotator(log_path=live, max_size_mb=50, retention_days=30)

    # 空文件 → 返回空字符串
    assert rotator.rotate() == ""

    _write_lines(live, 10)
    archive_path = rotator.rotate()
    assert archive_path != ""
    assert Path(archive_path).exists()
    assert not live.exists()  # 活动文件已被轮转走


def test_simplified_cleanup_old(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    live.write_text("", encoding="utf-8")
    archive = tmp_path / "audit_segments"

    now = datetime.now(UTC)
    old_day = (now - timedelta(days=60)).strftime("%Y%m%d")
    _make_segment(archive, "audit", old_day)

    rotator = AuditLogRotator(log_path=live, max_size_mb=50, retention_days=30)
    deleted_count = rotator.cleanup_old()
    assert deleted_count == 1


def test_simplified_get_stats(tmp_path: Path) -> None:
    live = tmp_path / "audit.jsonl"
    _write_lines(live, 10)

    rotator = AuditLogRotator(log_path=live, max_size_mb=50, retention_days=30)
    stats = rotator.get_stats()

    assert stats["active_file"] == str(live)
    assert stats["active_size_bytes"] > 0
    assert stats["total_size_bytes"] > 0
    assert stats["segment_count"] == 0
    assert stats["max_size_mb"] == 50.0
    assert stats["retention_days"] == 30
    assert stats["rotation_enabled"] is True
    assert stats["oldest_segment"] is None
    assert stats["newest_segment"] is None
