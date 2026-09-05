"""统一异步任务实体存储（2026-09-06 统一任务层）.

对照 Codex "submit and come back" 模型：任务提交即返回 task_id，
调用方稍后回来查询状态/结果。本模块只负责持久化与状态机，
执行编排（后台 agent run）在 backend/app/api/tasks.py。

与现有机制的关系（不迁移、不破坏）：
- sandbox_tasks（shell 命令）/ run/stream（SSE 同步流）/ scheduler（定时投递）
  保持原样；本存储是它们之上的"统一视图"起点，TaskRecord.source 字段
  预留区分记录来源（当前只有 "unified"，未来可聚合 sandbox/stream 记录）。

持久化写法参考 checkpoint/store.py：
- 逐行 JSONL 容错加载（单行损坏只跳过该行并告警，不丢整文件）；
- append + flush + fsync（崩溃不留半行）；
- 每 kind 容量上限，超限触发 tmp 文件 + os.replace 的原子压缩重写。
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_STORE_DIR = "data/tasks"
# 环境变量可覆盖存储目录（测试隔离用，惯例同 XAGENT_CHECKPOINT_STORE_PATH）
_STORE_PATH_ENV = "XAGENT_TASKS_STORE_PATH"

TaskKind = Literal["agent_run", "shell", "issue_to_pr"]
TaskState = Literal[
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
]

# 状态机：允许的状态转移。终态（completed/failed/cancelled）无出边。
# queued → failed：提交后、启动前失败（如后台协程创建失败/启动即异常）。
VALID_TASK_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"awaiting_approval", "completed", "failed", "cancelled"},
    "awaiting_approval": {"running", "completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}

TERMINAL_TASK_STATES = frozenset({"completed", "failed", "cancelled"})


class TaskRecord(BaseModel):
    """统一任务实体.

    status 状态机: queued → running → awaiting_approval → completed|failed|cancelled
    （queued 也可直接 → cancelled；running/awaiting_approval 的取消是协作式的：
    先置 cancel_requested=True，执行体完成后落 cancelled——agent loop 无法硬杀）。
    """

    task_id: str = Field(default_factory=lambda: f"utask-{uuid4().hex[:12]}")
    kind: TaskKind = "agent_run"
    status: TaskState = "queued"
    payload: dict[str, Any] = Field(default_factory=dict)
    # 结果摘要（不是全量 answer；answer 截断后放这里）
    result: dict[str, Any] | None = None
    error: str | None = None
    trace_id: str | None = None
    created_by: str = "anonymous"
    tenant_id: str = "default"
    # 协作式取消标记：running 中收到 cancel 请求时置位，终态落 cancelled
    cancel_requested: bool = False
    # 记录来源（预留：unified=本层创建；未来可聚合 sandbox/stream）
    source: str = "unified"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InvalidTaskTransition(ValueError):
    """非法状态转移（如终态再变更）。"""


class TasksStore:
    """统一任务的 JSONL 持久化存储.

    线程安全（RLock；操作内无 await）。每个 kind 一个 JSONL 文件，
    同一 task_id 后写的行覆盖先写的行（重启发灌取最新）。
    """

    def __init__(self, storage_dir: str | Path | None = None, max_per_kind: int = 500):
        self._records: dict[str, TaskRecord] = {}
        self._lock = threading.RLock()
        self._max_per_kind = max_per_kind
        if storage_dir is None:
            storage_dir = os.environ.get(_STORE_PATH_ENV) or _DEFAULT_STORE_DIR
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    # ─── 写路径 ───────────────────────────────────────────────────

    def create(self, record: TaskRecord) -> TaskRecord:
        """新建任务记录（queued）。task_id 冲突直接覆盖（uuid 碰撞概率忽略）。"""
        with self._lock:
            self._records[record.task_id] = record
            self._append_to_disk(record)
        logger.info(
            "Unified task created: %s kind=%s by=%s",
            record.task_id, record.kind, record.created_by,
        )
        return record

    def update(self, task_id: str, **fields: Any) -> TaskRecord:
        """按状态机转移并持久化。

        可更新字段白名单外的字段忽略；status 变更会校验转移合法性，
        非法转移抛 InvalidTaskTransition（API 层映射 409）。
        """
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(task_id)

            new_status = fields.pop("status", None)
            if new_status is not None and new_status != record.status:
                allowed = VALID_TASK_TRANSITIONS.get(record.status, set())
                if new_status not in allowed:
                    raise InvalidTaskTransition(
                        f"cannot transition task {task_id} from "
                        f"{record.status!r} to {new_status!r}"
                    )
                record.status = new_status
                if new_status == "running" and record.started_at is None:
                    record.started_at = datetime.now(UTC)
                if new_status in TERMINAL_TASK_STATES:
                    record.completed_at = datetime.now(UTC)

            for key in ("result", "error", "trace_id", "cancel_requested"):
                if key in fields:
                    setattr(record, key, fields.pop(key))
            # 未知字段忽略（防御性，避免调用方误传 payload 覆盖）

            record.updated_at = datetime.now(UTC)
            self._append_to_disk(record)
            return record

    def request_cancel(self, task_id: str) -> TaskRecord:
        """取消请求（诚实语义）：

        - queued → 直接 cancelled（还没开始执行）；
        - running / awaiting_approval → 置 cancel_requested=True，状态不变，
          执行体完成后落 cancelled（无法硬杀正在运行的 agent loop）；
        - 终态 → InvalidTaskTransition。
        """
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(task_id)
            if record.status == "queued":
                return self.update(task_id, status="cancelled")
            if record.status in ("running", "awaiting_approval"):
                return self.update(task_id, cancel_requested=True)
            raise InvalidTaskTransition(
                f"task {task_id} already in terminal state {record.status!r}"
            )

    # ─── 读路径 ───────────────────────────────────────────────────

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            record = self._records.get(task_id)
            return record.model_copy() if record else None

    def list(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRecord]:
        with self._lock:
            records = [
                rec.model_copy()
                for rec in self._records.values()
                if (status is None or rec.status == status)
                and (kind is None or rec.kind == kind)
            ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[offset : offset + limit]

    def count(self, *, status: str | None = None, kind: str | None = None) -> int:
        with self._lock:
            return sum(
                1
                for rec in self._records.values()
                if (status is None or rec.status == status)
                and (kind is None or rec.kind == kind)
            )

    # ─── 持久化 ───────────────────────────────────────────────────

    def _file_for(self, kind: str) -> Path:
        return self._storage_dir / f"{kind}.jsonl"

    def _append_to_disk(self, record: TaskRecord) -> None:
        """追加写入（flush + fsync 防崩溃撕裂）；超容量则原子压缩重写。"""
        try:
            file_path = self._file_for(record.kind)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._maybe_compact(record.kind)
        except OSError as e:
            # best-effort：持久化失败不阻断内存状态机（同 checkpoint store 惯例）
            logger.warning("Failed to persist unified task %s: %s", record.task_id, e)

    def _maybe_compact(self, kind: str) -> None:
        """每 kind 容量上限：超限时保留最新 max_per_kind 条并原子重写。"""
        of_kind = [r for r in self._records.values() if r.kind == kind]
        if len(of_kind) <= self._max_per_kind:
            return
        of_kind.sort(key=lambda r: (r.updated_at, r.created_at))
        dropped = of_kind[: len(of_kind) - self._max_per_kind]
        for rec in dropped:
            self._records.pop(rec.task_id, None)
        self._rewrite_disk(kind)
        logger.info(
            "Compacted unified tasks file for kind=%s: dropped %d, kept %d",
            kind, len(dropped), self._max_per_kind,
        )

    def _rewrite_disk(self, kind: str) -> None:
        """用内存中的记录全量重写 kind 文件（tmp + fsync + os.replace 原子替换）。"""
        file_path = self._file_for(kind)
        tmp_path = file_path.with_suffix(".jsonl.tmp")
        try:
            records = sorted(
                (r for r in self._records.values() if r.kind == kind),
                key=lambda r: (r.updated_at, r.created_at),
            )
            with open(tmp_path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(rec.model_dump_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
        except OSError as e:
            logger.warning("Failed to compact unified tasks file %s: %s", file_path, e)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_from_disk(self) -> None:
        """启动回灌：逐行解析，损坏行跳过并告警；同一 task_id 取最新一行。"""
        if not self._storage_dir.exists():
            return
        for file_path in sorted(self._storage_dir.glob("*.jsonl")):
            kind = file_path.stem
            latest: dict[str, TaskRecord] = {}
            try:
                with open(file_path, encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = TaskRecord.model_validate_json(line)
                            # 防御：文件名与记录 kind 不一致时以记录为准归档
                            if record.kind != kind:
                                record = record.model_copy(update={"kind": kind})
                            latest[record.task_id] = record
                        except ValueError as e:
                            logger.warning(
                                "Skipping corrupt unified task line %s:%d: %s",
                                file_path, line_no, e,
                            )
            except OSError as e:
                logger.warning("Failed to load unified tasks file %s: %s", file_path, e)
                continue
            # 每 kind 容量上限同样作用于回灌（按 updated_at 取最新）
            if len(latest) > self._max_per_kind:
                ordered = sorted(
                    latest.values(), key=lambda r: (r.updated_at, r.created_at)
                )
                latest = {
                    r.task_id: r
                    for r in ordered[len(latest) - self._max_per_kind:]
                }
            for record in latest.values():
                self._records[record.task_id] = record


# ─── 全局单例（惯例同 checkpoint/store.py） ──────────────────────────────────

_tasks_store: TasksStore | None = None
_store_lock = threading.Lock()


def get_tasks_store() -> TasksStore:
    """获取全局 TasksStore 单例（测试通过重置 _tasks_store + env 覆盖隔离）。"""
    global _tasks_store
    if _tasks_store is None:
        with _store_lock:
            if _tasks_store is None:
                _tasks_store = TasksStore()
    return _tasks_store


def reset_tasks_store() -> None:
    """重置单例（测试隔离用；生产不要调用）。"""
    global _tasks_store
    with _store_lock:
        _tasks_store = None
