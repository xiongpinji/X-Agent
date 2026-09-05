"""自进化存储（reflections/learnings/capabilities）。

P2-12 起反思记录增加 JSONL 持久化（``data/evolution_reflections.jsonl``），
写法对齐 ``core/checkpoint/store.py``：逐行容错加载、append+fsync、容量上限。
此前纯内存实现意味着进程重启后所有反思记录丢失，
loop.py 的 ``add_reflection`` 一直在写入空壳记录（字段错配，见 loop.py 修复）。
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_REFLECTIONS_FILE = "data/evolution_reflections.jsonl"
# 环境变量可覆盖存储文件（主要用于测试隔离）
_EVOLUTION_STORE_PATH_ENV = "XAGENT_EVOLUTION_STORE_PATH"
# 容量上限：防止无界增长（超出后保留最新记录并压缩磁盘文件）
_MAX_REFLECTIONS = 1000


class ReflectionRecord(BaseModel):
    reflection_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    agent_id: str = "anonymous"
    task_id: str = ""
    trace_id: str = ""
    task_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningRecord(BaseModel):
    learning_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    agent_id: str = "anonymous"
    domain: str = "general"
    pattern: str = ""
    outcome: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    promoted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CapabilityVersion(BaseModel):
    capability_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str = "anonymous"
    name: str = ""
    version: str = "v1"
    description: str = ""
    promoted_from: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvolutionStore:
    """自进化记录存储。

    线程安全；反思记录（ReflectionRecord）持久化到 JSONL 文件，
    学习记录与能力版本暂为进程内存（按需再扩展）。
    """

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._lock = RLock()
        self._reflections: list[ReflectionRecord] = []
        self._learnings: list[LearningRecord] = []
        self._capabilities: list[CapabilityVersion] = []
        self._loaded = False
        if storage_path is None:
            storage_path = os.environ.get(_EVOLUTION_STORE_PATH_ENV) or _DEFAULT_REFLECTIONS_FILE
        self._storage_path = Path(storage_path)

    def add_reflection(self, record: ReflectionRecord) -> ReflectionRecord:
        with self._lock:
            self._ensure_loaded()
            self._reflections.append(record)
            self._append_to_disk(record)
            # 容量上限：超出后保留最新 N 条并压缩磁盘文件（JSONL 只增不减会无限膨胀）
            if len(self._reflections) > _MAX_REFLECTIONS:
                self._reflections = self._reflections[-_MAX_REFLECTIONS:]
                self._rewrite_disk()
        return record

    def add_learning(self, record: LearningRecord) -> LearningRecord:
        with self._lock:
            self._learnings.append(record)
        return record

    def promote_capability(self, record: CapabilityVersion) -> CapabilityVersion:
        with self._lock:
            self._capabilities.append(record)
        return record

    def list_reflections(self, agent_id: str | None = None) -> list[ReflectionRecord]:
        with self._lock:
            self._ensure_loaded()
            items = self._reflections
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))

    def list_learnings(self, agent_id: str | None = None) -> list[LearningRecord]:
        items = self._learnings
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))

    def list_capabilities(self, agent_id: str | None = None) -> list[CapabilityVersion]:
        items = self._capabilities
        if agent_id is not None:
            items = [item for item in items if item.agent_id == agent_id]
        return list(reversed(items))

    # ─── JSONL 持久化（对齐 core/checkpoint/store.py 的写法） ──────────────

    def _ensure_loaded(self) -> None:
        """惰性加载磁盘记录（首次访问时执行；构造期不做 IO，避免 import 副作用）。"""
        if self._loaded:
            return
        self._loaded = True
        try:
            self._load_from_disk()
        except Exception as e:  # 加载失败不阻断写入路径
            logger.warning("Failed to load evolution reflections from %s: %s", self._storage_path, e)

    def _append_to_disk(self, record: ReflectionRecord) -> None:
        """追加写入一行 JSON（flush + fsync 防崩溃撕裂）。"""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            logger.warning("Failed to persist evolution reflection: %s", e)

    def _rewrite_disk(self) -> None:
        """用内存记录全量重写 JSONL（原子替换，用于容量裁剪）。"""
        tmp_path = self._storage_path.with_suffix(".jsonl.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                for record in self._reflections:
                    f.write(record.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._storage_path)
        except OSError as e:
            logger.warning("Failed to compact evolution reflections file %s: %s", self._storage_path, e)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_from_disk(self) -> None:
        """逐行容错加载：单行损坏只跳过该行并告警，不丢弃其余有效记录。"""
        if not self._storage_path.exists():
            return
        loaded: list[ReflectionRecord] = []
        try:
            with open(self._storage_path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        loaded.append(ReflectionRecord.model_validate_json(line))
                    except ValueError as e:
                        logger.warning(
                            "Skipping corrupt evolution reflection line %s:%d: %s",
                            self._storage_path, line_no, e,
                        )
        except OSError as e:
            logger.warning("Failed to read evolution reflections file %s: %s", self._storage_path, e)
            return
        if loaded:
            self._reflections = loaded[-_MAX_REFLECTIONS:]


evolution_store = EvolutionStore()
