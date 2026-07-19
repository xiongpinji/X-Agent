"""审计日志轮转与留存管理(P1-04)。

能力:
- 按大小轮转(默认 64 MiB, 可配置/可关闭)
- 按日期轮转(默认开启, 跨 UTC 日自动切到新文件)
- 可配置留存期(默认 90 天; 合规档 7 年)与自动清理过期段

轮转段命名: ``{stem}-{YYYYMMDD}-{HHMMSS}-{seq:04d}{suffix}``,
例如 ``audit-20260720-153012-0001.jsonl``, 统一存放在
``<live_file 同目录>/<stem>_segments/`` (可用 ``archive_dir`` 覆盖)。

当前活动文件属于哪个 UTC 日期由伴随标记文件
``<live_file>.segment_date`` 记录(内容为 ``YYYY-MM-DD``)。
标记缺失时, 已存在文件回退到其 mtime 日期, 新文件取当天。

哈希链说明: 轮转只做文件级切分, 不改写任何已落盘记录, 因此
跨段的 ``prev_hash`` 连续性保持完整; 留存清理删除最旧的整段后,
剩余链的"首条记录"视为链锚点(见 ``AuditStore.verify_chain`` 的
锚点语义)。
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, Field

DEFAULT_RETENTION_DAYS = 90
"""默认留存期: 90 天。"""

COMPLIANCE_RETENTION_DAYS = 365 * 7
"""合规档留存期: 7 年(SOC2/ISO27001 常见要求)。"""

DEFAULT_MAX_BYTES = 64 * 1024 * 1024
"""默认单文件上限: 64 MiB。"""

_SEGMENT_NAME_RE = re.compile(
    r"^(?P<stem>.+)-(?P<day>\d{8})-(?P<time>\d{6})-(?P<seq>\d{4})(?P<suffix>\.[^.]+)$"
)


class AuditRotationConfig(BaseModel):
    """审计轮转配置。

    Attributes:
        max_bytes: 活动文件达到该字节数即轮转; ``0`` 表示关闭按大小轮转。
        rotate_daily: 跨 UTC 日期时自动轮转。
        retention_days: 轮转段留存天数; ``0`` 表示永久保留(不自动清理)。
            默认 90 天; 合规档见 :meth:`compliance` (7 年)。
        archive_dir: 轮转段存放目录; ``None`` 时用活动文件旁的
            ``<stem>_segments/``。
    """

    max_bytes: int = Field(default=DEFAULT_MAX_BYTES, ge=0)
    rotate_daily: bool = True
    retention_days: int = Field(default=DEFAULT_RETENTION_DAYS, ge=0)
    archive_dir: Path | None = None

    @classmethod
    def compliance(cls, **overrides: object) -> AuditRotationConfig:
        """合规档: 7 年留存(2555 天), 其余参数可被 overrides 覆盖。"""
        base: dict[str, object] = {"retention_days": COMPLIANCE_RETENTION_DAYS}
        base.update(overrides)
        return cls(**base)  # type: ignore[arg-type]


class AuditLogRotator:
    """审计日志轮转器(线程安全)。

    供 ``AuditStore`` 在每次追加前调用 :meth:`maybe_rotate`;
    留存清理由 :meth:`cleanup_expired` 显式触发(或经 store 的
    ``cleanup_expired_segments``)。
    """

    def __init__(self, config: AuditRotationConfig | None = None) -> None:
        self.config = config or AuditRotationConfig()
        self._lock = RLock()

    # ------------------------------------------------------------------ paths

    def archive_dir_for(self, live_path: Path) -> Path:
        """返回该活动文件对应的轮转段目录。"""
        if self.config.archive_dir is not None:
            return Path(self.config.archive_dir)
        return live_path.parent / f"{live_path.stem}_segments"

    @staticmethod
    def _marker_path(live_path: Path) -> Path:
        return live_path.with_name(live_path.name + ".segment_date")

    # --------------------------------------------------------------- rotation

    def maybe_rotate(self, live_path: Path, *, now: datetime | None = None) -> Path | None:
        """若活动文件达到大小上限或跨日期, 执行轮转。

        Args:
            live_path: 当前活动审计文件。
            now: 注入时间(测试用), 默认取当前 UTC 时间。

        Returns:
            轮转出的段文件路径; 未发生轮转返回 ``None``。
        """
        now = now or datetime.now(UTC)
        live_path = Path(live_path)
        with self._lock:
            if not live_path.exists() or live_path.stat().st_size == 0:
                # 空文件无需轮转, 但仍需保证日期标记存在
                self._ensure_marker(live_path, now)
                return None

            marker_day = self._ensure_marker(live_path, now)
            should_rotate = False

            if self.config.rotate_daily and now.date() > marker_day:
                should_rotate = True
            if (
                self.config.max_bytes > 0
                and live_path.stat().st_size >= self.config.max_bytes
            ):
                should_rotate = True

            if not should_rotate:
                return None

            return self._rotate(live_path, now)

    def _rotate(self, live_path: Path, now: datetime) -> Path:
        archive_dir = self.archive_dir_for(live_path)
        archive_dir.mkdir(parents=True, exist_ok=True)

        stamp = now.strftime("%Y%m%d-%H%M%S")
        seq = 1
        while True:
            segment = archive_dir / f"{live_path.stem}-{stamp}-{seq:04d}{live_path.suffix}"
            if not segment.exists():
                break
            seq += 1

        live_path.rename(segment)
        self._marker_path(live_path).write_text(now.date().isoformat(), encoding="utf-8")
        return segment

    def _ensure_marker(self, live_path: Path, now: datetime) -> date:
        """读取/初始化日期标记, 返回活动文件所属的 UTC 日期。"""
        marker = self._marker_path(live_path)
        if marker.exists():
            raw = marker.read_text(encoding="utf-8").strip()
            try:
                return date.fromisoformat(raw)
            except ValueError:
                # 标记损坏: 按 mtime 重建, 避免静默跳过轮转
                pass

        if live_path.exists():
            file_day = datetime.fromtimestamp(live_path.stat().st_mtime, UTC).date()
        else:
            file_day = now.date()
        marker.write_text(file_day.isoformat(), encoding="utf-8")
        return file_day

    # -------------------------------------------------------------- retention

    def list_segments(self, live_path: Path) -> list[Path]:
        """按时间升序列出全部轮转段(不含当前活动文件)。"""
        live_path = Path(live_path)
        archive_dir = self.archive_dir_for(live_path)
        if not archive_dir.exists():
            return []
        segments = [
            path
            for path in archive_dir.iterdir()
            if path.is_file() and _SEGMENT_NAME_RE.match(path.name)
            and path.name.startswith(f"{live_path.stem}-")
        ]
        return sorted(segments, key=lambda p: p.name)

    def cleanup_expired(self, live_path: Path, *, now: datetime | None = None) -> list[Path]:
        """删除超出留存期的轮转段, 返回被删除的路径列表。

        段日期优先取文件名中的 ``YYYYMMDD``, 解析失败回退到文件 mtime。
        ``retention_days == 0`` 表示永久保留, 直接返回空列表。
        """
        if self.config.retention_days <= 0:
            return []

        now = now or datetime.now(UTC)
        cutoff = now.date() - timedelta(days=self.config.retention_days)
        deleted: list[Path] = []

        with self._lock:
            for segment in self.list_segments(live_path):
                segment_day = self._segment_date(segment)
                if segment_day is not None and segment_day < cutoff:
                    segment.unlink(missing_ok=True)
                    deleted.append(segment)
        return deleted

    @staticmethod
    def _segment_date(segment: Path) -> date | None:
        match = _SEGMENT_NAME_RE.match(segment.name)
        if match:
            try:
                return datetime.strptime(match.group("day"), "%Y%m%d").date()
            except ValueError:
                pass
        if segment.exists():
            return datetime.fromtimestamp(segment.stat().st_mtime, UTC).date()
        return None

    # ----------------------------------------------------------------- chain

    def chain_files(self, live_path: Path) -> list[Path]:
        """按时间顺序返回完整链文件列表: [最旧段 ... 最新段, 当前活动文件]。"""
        live_path = Path(live_path)
        return [*self.list_segments(live_path), live_path]
