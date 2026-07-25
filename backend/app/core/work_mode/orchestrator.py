"""Work Mode 长时任务编排器 — 跨应用、数小时持续工作。

对标 ChatGPT Work：目标分解 → 里程碑顺序执行 → 工件产出 → 断点恢复。
利用 CheckpointStore 实现跨迭代持久化，里程碑间传递上下文。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.app.core.work_mode.connectors import AppConnector, FileConnector
from backend.app.core.work_mode.goal_decomposer import GoalDecomposer

logger = logging.getLogger(__name__)

_SESSION_DIR = Path("data/work_sessions")


class WorkSessionStatus(StrEnum):
    """Work Session 状态."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Milestone:
    """里程碑实例."""

    index: int = 0
    title: str = ""
    description: str = ""
    status: str = "pending"  # pending | running | completed | failed | skipped
    output: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float = 0.0
    deliverable: str = ""


@dataclass
class Artifact:
    """工件（任务产出）."""

    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    content: str = ""
    artifact_type: str = "text"  # text | file | report | code
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    milestone_index: int = -1


@dataclass
class WorkSession:
    """Work Mode 会话."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    milestones: list[Milestone] = field(default_factory=list)
    status: WorkSessionStatus = WorkSessionStatus.ACTIVE
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    max_duration_hours: float = 8.0
    artifacts: list[Artifact] = field(default_factory=list)
    connected_apps: list[str] = field(default_factory=list)
    current_milestone_index: int = 0
    context_accumulator: dict[str, Any] = field(default_factory=dict)
    total_tokens_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "max_duration_hours": self.max_duration_hours,
            "current_milestone_index": self.current_milestone_index,
            "milestones": [
                {
                    "index": m.index,
                    "title": m.title,
                    "status": m.status,
                    "output": m.output[:500],
                    "duration_seconds": m.duration_seconds,
                }
                for m in self.milestones
            ],
            "artifacts": [
                {"artifact_id": a.artifact_id, "name": a.name, "type": a.artifact_type}
                for a in self.artifacts
            ],
            "connected_apps": self.connected_apps,
            "total_tokens_used": self.total_tokens_used,
        }


class WorkOrchestrator:
    """Work Mode 编排器 — 管理长时任务生命周期.

    Args:
        agent_factory: 创建 Agent 执行的工厂 (async callable(task, context) -> response)
        llm_router: LLMRouter 实例（用于目标分解）
        connectors: 应用连接器列表
    """

    def __init__(
        self,
        agent_factory: Callable | None = None,
        llm_router: Any | None = None,
        connectors: list[AppConnector] | None = None,
    ) -> None:
        self._factory = agent_factory
        self._router = llm_router
        self._decomposer = GoalDecomposer(llm_router=llm_router)
        self._connectors: dict[str, AppConnector] = {}
        for c in (connectors or []):
            self._connectors[c.name] = c
        # 默认文件连接器
        if "file" not in self._connectors:
            self._connectors["file"] = FileConnector()

        self._sessions: dict[str, WorkSession] = {}
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def sessions(self) -> dict[str, WorkSession]:
        return dict(self._sessions)

    async def start_session(
        self,
        goal: str,
        max_hours: float = 8.0,
        max_milestones: int = 6,
        context: dict[str, Any] | None = None,
    ) -> WorkSession:
        """启动新的 Work Session.

        1. 目标分解为里程碑
        2. 创建会话并持久化
        3. 开始执行第一个里程碑
        """
        session = WorkSession(
            goal=goal,
            max_duration_hours=max_hours,
            connected_apps=list(self._connectors.keys()),
        )

        # 目标分解
        specs = await self._decomposer.decompose(goal, max_milestones, context)
        session.milestones = [
            Milestone(
                index=i,
                title=spec.title,
                description=spec.description,
                deliverable=spec.deliverable,
            )
            for i, spec in enumerate(specs)
        ]

        self._sessions[session.session_id] = session
        self._persist_session(session)

        logger.info(
            "Work session %s started: goal='%s', %d milestones",
            session.session_id, goal[:60], len(session.milestones),
        )
        return session

    async def tick(self, session_id: str) -> WorkSession:
        """推进会话 — 执行当前里程碑（由调度器定时调用）.

        Returns:
            更新后的 WorkSession
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        if session.status != WorkSessionStatus.ACTIVE:
            return session

        # 超时检查
        started = datetime.fromisoformat(session.started_at)
        elapsed_hours = (datetime.now(UTC) - started).total_seconds() / 3600
        if elapsed_hours > session.max_duration_hours:
            session.status = WorkSessionStatus.TIMEOUT
            session.completed_at = datetime.now(UTC).isoformat()
            self._persist_session(session)
            return session

        # 找到当前待执行里程碑
        idx = session.current_milestone_index
        if idx >= len(session.milestones):
            session.status = WorkSessionStatus.COMPLETED
            session.completed_at = datetime.now(UTC).isoformat()
            self._persist_session(session)
            return session

        milestone = session.milestones[idx]
        milestone.status = "running"
        milestone.started_at = datetime.now(UTC).isoformat()

        # 执行里程碑
        start_time = time.time()
        try:
            output = await self._execute_milestone(session, milestone)
            milestone.output = output
            milestone.status = "completed"

            # 产出工件
            if output:
                session.artifacts.append(Artifact(
                    name=f"{milestone.title} 产出",
                    content=output[:5000],
                    artifact_type="text",
                    milestone_index=idx,
                ))

            # 累积上下文
            session.context_accumulator[f"milestone_{idx}"] = output[:1000]

        except Exception as exc:
            milestone.output = f"ERROR: {exc}"
            milestone.status = "failed"
            logger.warning("Milestone %d failed in session %s: %s", idx, session_id, exc)

        milestone.completed_at = datetime.now(UTC).isoformat()
        milestone.duration_seconds = time.time() - start_time

        # 推进到下一个里程碑
        session.current_milestone_index = idx + 1
        if session.current_milestone_index >= len(session.milestones):
            session.status = WorkSessionStatus.COMPLETED
            session.completed_at = datetime.now(UTC).isoformat()

        self._persist_session(session)
        return session

    async def resume_session(self, session_id: str) -> WorkSession:
        """恢复暂停/中断的会话."""
        session = self._sessions.get(session_id)
        if session is None:
            # 尝试从磁盘恢复
            session = self._load_session(session_id)
            if session is None:
                raise ValueError(f"Session not found: {session_id}")
            self._sessions[session_id] = session

        if session.status in (WorkSessionStatus.PAUSED, WorkSessionStatus.TIMEOUT):
            session.status = WorkSessionStatus.ACTIVE
            self._persist_session(session)

        return session

    async def pause_session(self, session_id: str) -> WorkSession:
        """暂停会话."""
        session = self._sessions.get(session_id)
        if session and session.status == WorkSessionStatus.ACTIVE:
            session.status = WorkSessionStatus.PAUSED
            self._persist_session(session)
        return session

    def get_session(self, session_id: str) -> WorkSession | None:
        """获取会话."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话摘要."""
        return [s.to_dict() for s in self._sessions.values()]

    async def _execute_milestone(self, session: WorkSession, milestone: Milestone) -> str:
        """执行单个里程碑."""
        if self._factory is None:
            # 无 agent_factory 时返回模拟结果
            return f"[模拟执行] {milestone.description}"

        # 构建任务上下文（包含前序里程碑产出）
        task_context = {
            "goal": session.goal,
            "milestone_title": milestone.title,
            "milestone_description": milestone.description,
            "previous_outputs": session.context_accumulator,
        }

        response = await self._factory(milestone.description, task_context)

        if hasattr(response, "answer"):
            return response.answer or ""
        if isinstance(response, dict):
            return str(response.get("answer", response.get("output", "")))
        return str(response)

    def _persist_session(self, session: WorkSession) -> None:
        """持久化会话到磁盘."""
        try:
            path = _SESSION_DIR / f"{session.session_id}.json"
            path.write_text(
                json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.debug("Session persist failed: %s", exc)

    def _load_session(self, session_id: str) -> WorkSession | None:
        """从磁盘加载会话."""
        path = _SESSION_DIR / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            session = WorkSession(
                session_id=data["session_id"],
                goal=data["goal"],
                status=WorkSessionStatus(data["status"]),
                started_at=data["started_at"],
                completed_at=data.get("completed_at"),
                max_duration_hours=data.get("max_duration_hours", 8.0),
                current_milestone_index=data.get("current_milestone_index", 0),
                connected_apps=data.get("connected_apps", []),
                total_tokens_used=data.get("total_tokens_used", 0),
            )
            for m in data.get("milestones", []):
                session.milestones.append(Milestone(
                    index=m["index"],
                    title=m["title"],
                    status=m["status"],
                    output=m.get("output", ""),
                    duration_seconds=m.get("duration_seconds", 0),
                ))
            return session
        except Exception as exc:
            logger.warning("Session load failed: %s", exc)
            return None


# ─── 全局单例 ─────────────────────────────────────────────────────────────────

_work_orchestrator: WorkOrchestrator | None = None


def get_work_orchestrator() -> WorkOrchestrator:
    """获取全局 Work 编排器单例."""
    global _work_orchestrator
    if _work_orchestrator is None:
        _work_orchestrator = WorkOrchestrator()
    return _work_orchestrator
