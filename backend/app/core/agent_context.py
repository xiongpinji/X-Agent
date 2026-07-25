"""
Agent引擎迁移准备 - 统一上下文容器、会话恢复、状态快照
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class AgentContextSnapshot:
    """Agent上下文快照"""
    id: str
    session_id: str
    timestamp: str
    task: str
    goal: str
    stage: str
    subtasks: list[str] = field(default_factory=list)
    subtask_status: dict[str, str] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    context_tokens: int = 0
    compressed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSessionState:
    """Agent会话状态"""
    session_id: str
    created_at: str
    last_activity: str
    status: str  # active, paused, completed, failed
    iterations: int = 0
    max_iterations: int = 4
    current_phase: str = "planning"
    snapshots: list[AgentContextSnapshot] = field(default_factory=list)
    recovery_data: dict[str, Any] = field(default_factory=dict)


class AgentContextManager:
    """
    Agent上下文管理器 - 统一的上下文容器
    """

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path("data/agent_contexts")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.contexts: dict[str, AgentContextSnapshot] = {}
        self.sessions: dict[str, AgentSessionState] = {}

    def create_session(
        self,
        task: str,
        goal: str,
        max_iterations: int = 4,
    ) -> AgentSessionState:
        """创建新会话"""
        session_id = str(uuid4())
        now = datetime.now(UTC).isoformat()

        session = AgentSessionState(
            session_id=session_id,
            created_at=now,
            last_activity=now,
            status="active",
            max_iterations=max_iterations,
        )

        self.sessions[session_id] = session
        self._persist_session(session)
        return session

    def create_snapshot(
        self,
        session_id: str,
        task: str,
        goal: str,
        stage: str,
        subtasks: list[str] | None = None,
        observations: list[str] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        reflections: list[str] | None = None,
        context_tokens: int = 0,
    ) -> AgentContextSnapshot:
        """创建上下文快照"""
        snapshot = AgentContextSnapshot(
            id=str(uuid4()),
            session_id=session_id,
            timestamp=datetime.now(UTC).isoformat(),
            task=task,
            goal=goal,
            stage=stage,
            subtasks=subtasks or [],
            observations=observations or [],
            tool_results=tool_results or [],
            reflections=reflections or [],
            context_tokens=context_tokens,
        )

        self.contexts[snapshot.id] = snapshot

        # 更新会话
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.snapshots.append(snapshot)
            session.last_activity = datetime.now(UTC).isoformat()
            self._persist_session(session)

        self._persist_snapshot(snapshot)
        return snapshot

    def get_session(self, session_id: str) -> AgentSessionState | None:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_snapshot(self, snapshot_id: str) -> AgentContextSnapshot | None:
        """获取快照"""
        return self.contexts.get(snapshot_id)

    def get_latest_snapshot(self, session_id: str) -> AgentContextSnapshot | None:
        """获取最新快照"""
        session = self.sessions.get(session_id)
        if not session or not session.snapshots:
            return None
        return session.snapshots[-1]

    def recover_session(self, session_id: str) -> AgentSessionState | None:
        """恢复会话"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        # 更新状态
        session.status = "active"
        session.last_activity = datetime.now(UTC).isoformat()
        self._persist_session(session)
        return session

    def compress_context(
        self,
        snapshot_id: str,
        compression_ratio: float = 0.5,
    ) -> bool:
        """压缩上下文"""
        snapshot = self.contexts.get(snapshot_id)
        if not snapshot:
            return False

        # 标记为已压缩
        snapshot.compressed = True
        snapshot.context_tokens = int(snapshot.context_tokens * compression_ratio)
        self._persist_snapshot(snapshot)
        return True

    def update_session_status(
        self,
        session_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """更新会话状态"""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.status = status
        session.last_activity = datetime.now(UTC).isoformat()
        if metadata:
            session.recovery_data.update(metadata)

        self._persist_session(session)
        return True

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        """获取会话摘要"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        latest_snapshot = self.get_latest_snapshot(session_id)

        return {
            "session_id": session_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "status": session.status,
            "iterations": session.iterations,
            "max_iterations": session.max_iterations,
            "current_phase": session.current_phase,
            "total_snapshots": len(session.snapshots),
            "latest_snapshot": asdict(latest_snapshot) if latest_snapshot else None,
        }

    def _persist_session(self, session: AgentSessionState) -> None:
        """持久化会话"""
        session_file = self.storage_path / f"session_{session.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(asdict(session), f, indent=2, default=str)

    def _persist_snapshot(self, snapshot: AgentContextSnapshot) -> None:
        """持久化快照"""
        snapshot_file = self.storage_path / f"snapshot_{snapshot.id}.json"
        with open(snapshot_file, "w") as f:
            json.dump(asdict(snapshot), f, indent=2, default=str)


class AgentSessionRecovery:
    """
    Agent会话恢复 - 支持会话恢复和故障转移
    """

    def __init__(self, context_manager: AgentContextManager):
        self.context_manager = context_manager
        self.recovery_points: dict[str, dict[str, Any]] = {}

    def create_recovery_point(
        self,
        session_id: str,
        checkpoint_name: str,
        data: dict[str, Any],
    ) -> str:
        """创建恢复点"""
        recovery_id = f"{session_id}_{checkpoint_name}_{datetime.now(UTC).timestamp()}"
        self.recovery_points[recovery_id] = {
            "session_id": session_id,
            "checkpoint_name": checkpoint_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }
        return recovery_id

    def recover_from_point(
        self,
        recovery_id: str,
    ) -> dict[str, Any] | None:
        """从恢复点恢复"""
        recovery_point = self.recovery_points.get(recovery_id)
        if not recovery_point:
            return None

        session_id = recovery_point["session_id"]
        session = self.context_manager.recover_session(session_id)
        if not session:
            return None

        return recovery_point["data"]

    def get_recovery_options(self, session_id: str) -> list[dict[str, Any]]:
        """获取恢复选项"""
        options = []
        for recovery_id, point in self.recovery_points.items():
            if point["session_id"] == session_id:
                options.append({
                    "recovery_id": recovery_id,
                    "checkpoint_name": point["checkpoint_name"],
                    "timestamp": point["timestamp"],
                })
        return sorted(options, key=lambda x: x["timestamp"], reverse=True)


class AgentSnapshot:
    """
    Agent状态快照 - 支持状态保存和恢复
    """

    def __init__(self, context_manager: AgentContextManager):
        self.context_manager = context_manager
        self.snapshots: dict[str, dict[str, Any]] = {}

    def take_snapshot(
        self,
        session_id: str,
        agent_state: dict[str, Any],
    ) -> str:
        """拍摄快照"""
        snapshot_id = str(uuid4())
        self.snapshots[snapshot_id] = {
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_state": agent_state,
        }
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """恢复快照"""
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            return None
        return snapshot["agent_state"]

    def get_snapshots_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话的所有快照"""
        snapshots = []
        for snapshot_id, snapshot in self.snapshots.items():
            if snapshot["session_id"] == session_id:
                snapshots.append({
                    "snapshot_id": snapshot_id,
                    "timestamp": snapshot["timestamp"],
                })
        return sorted(snapshots, key=lambda x: x["timestamp"], reverse=True)

    def compare_snapshots(
        self,
        snapshot_id_1: str,
        snapshot_id_2: str,
    ) -> dict[str, Any] | None:
        """比较两个快照"""
        snapshot1 = self.snapshots.get(snapshot_id_1)
        snapshot2 = self.snapshots.get(snapshot_id_2)

        if not snapshot1 or not snapshot2:
            return None

        return {
            "snapshot_1": snapshot_id_1,
            "snapshot_2": snapshot_id_2,
            "timestamp_1": snapshot1["timestamp"],
            "timestamp_2": snapshot2["timestamp"],
            "state_1": snapshot1["agent_state"],
            "state_2": snapshot2["agent_state"],
        }


class AgentCompatibilityAdapter:
    """
    Agent兼容性适配器 - 支持新旧Agent引擎的兼容性
    """

    def __init__(self, context_manager: AgentContextManager):
        self.context_manager = context_manager
        self.adapters: dict[str, Any] = {}

    def register_adapter(
        self,
        name: str,
        adapter: Any,
    ) -> None:
        """注册适配器"""
        self.adapters[name] = adapter

    def adapt_old_agent_state(
        self,
        old_state: dict[str, Any],
    ) -> dict[str, Any]:
        """适配旧Agent状态"""
        # 将旧状态转换为新格式
        return {
            "task": old_state.get("task", ""),
            "goal": old_state.get("goal", ""),
            "stage": old_state.get("stage", "planning"),
            "subtasks": old_state.get("subtasks", []),
            "observations": old_state.get("observations", []),
            "tool_results": old_state.get("tool_results", []),
            "reflections": old_state.get("reflections", []),
        }

    def adapt_new_agent_state(
        self,
        new_state: dict[str, Any],
    ) -> dict[str, Any]:
        """适配新Agent状态"""
        # 将新状态转换为兼容格式
        return {
            "task": new_state.get("task", ""),
            "goal": new_state.get("goal", ""),
            "stage": new_state.get("stage", "planning"),
            "subtasks": new_state.get("subtasks", []),
            "observations": new_state.get("observations", []),
            "tool_results": new_state.get("tool_results", []),
            "reflections": new_state.get("reflections", []),
        }
