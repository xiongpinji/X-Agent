"""
迁移框架 - 提供版本管理、状态跟踪和回滚机制
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, TypeVar
from uuid import uuid4


class MigrationStatus(StrEnum):
    """迁移状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationPhase(StrEnum):
    """迁移阶段"""
    PREPARATION = "preparation"
    VALIDATION = "validation"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    ROLLBACK = "rollback"


@dataclass
class MigrationVersion:
    """迁移版本信息"""
    version: str
    timestamp: str
    description: str
    components: list[str]
    breaking_changes: list[str] = field(default_factory=list)
    migration_path: str = ""
    rollback_supported: bool = True


@dataclass
class MigrationCheckpoint:
    """迁移检查点"""
    id: str
    name: str
    phase: MigrationPhase
    status: MigrationStatus
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    rollback_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationState:
    """迁移状态"""
    id: str
    version: str
    status: MigrationStatus
    phase: MigrationPhase
    progress: float  # 0.0 - 1.0
    checkpoints: list[MigrationCheckpoint] = field(default_factory=list)
    start_time: str = ""
    end_time: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


T = TypeVar('T')


class MigrationFramework(Generic[T]):
    """
    迁移框架 - 管理迁移的生命周期
    """

    def __init__(
        self,
        version: str,
        storage_path: str | Path | None = None,
        max_checkpoints: int = 100,
    ):
        self.version = version
        self.storage_path = Path(storage_path) if storage_path else Path("data/migrations")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints

        self.state = MigrationState(
            id=str(uuid4()),
            version=version,
            status=MigrationStatus.PENDING,
            phase=MigrationPhase.PREPARATION,
            progress=0.0,
            start_time=datetime.now(UTC).isoformat(),
        )

        self._rollback_handlers: dict[str, Callable[[], Any]] = {}
        self._validators: dict[str, Callable[[T], bool]] = {}
        self._load_state()

    def register_rollback_handler(
        self,
        checkpoint_name: str,
        handler: Callable[[], Any],
    ) -> None:
        """注册回滚处理器"""
        self._rollback_handlers[checkpoint_name] = handler

    def register_validator(
        self,
        checkpoint_name: str,
        validator: Callable[[T], bool],
    ) -> None:
        """注册验证器"""
        self._validators[checkpoint_name] = validator

    def add_checkpoint(
        self,
        name: str,
        phase: MigrationPhase,
        details: dict[str, Any] | None = None,
        rollback_data: dict[str, Any] | None = None,
    ) -> MigrationCheckpoint:
        """添加检查点"""
        checkpoint = MigrationCheckpoint(
            id=str(uuid4()),
            name=name,
            phase=phase,
            status=MigrationStatus.IN_PROGRESS,
            timestamp=datetime.now(UTC).isoformat(),
            details=details or {},
            rollback_data=rollback_data or {},
        )

        self.state.checkpoints.append(checkpoint)
        self._cleanup_old_checkpoints()
        self._persist_state()

        return checkpoint

    def complete_checkpoint(
        self,
        checkpoint_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """完成检查点"""
        for checkpoint in self.state.checkpoints:
            if checkpoint.id == checkpoint_id:
                checkpoint.status = MigrationStatus.COMPLETED
                if details:
                    checkpoint.details.update(details)
                self._persist_state()
                return

        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    def fail_checkpoint(
        self,
        checkpoint_id: str,
        error: str,
    ) -> None:
        """标记检查点失败"""
        for checkpoint in self.state.checkpoints:
            if checkpoint.id == checkpoint_id:
                checkpoint.status = MigrationStatus.FAILED
                checkpoint.error = error
                self.state.status = MigrationStatus.FAILED
                self.state.error = error
                self._persist_state()
                return

        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    def update_progress(self, progress: float) -> None:
        """更新进度"""
        self.state.progress = max(0.0, min(1.0, progress))
        self._persist_state()

    def transition_phase(self, new_phase: MigrationPhase) -> None:
        """转换阶段"""
        self.state.phase = new_phase
        self._persist_state()

    def validate_checkpoint(
        self,
        checkpoint_id: str,
        data: T,
    ) -> bool:
        """验证检查点"""
        checkpoint = self._get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False

        validator = self._validators.get(checkpoint.name)
        if not validator:
            return True

        return validator(data)

    def rollback(self, to_checkpoint_id: str | None = None) -> bool:
        """回滚迁移"""
        try:
            self.state.status = MigrationStatus.ROLLED_BACK
            self.state.phase = MigrationPhase.ROLLBACK

            if to_checkpoint_id:
                # 回滚到特定检查点
                target_idx = None
                for i, cp in enumerate(self.state.checkpoints):
                    if cp.id == to_checkpoint_id:
                        target_idx = i
                        break

                if target_idx is None:
                    raise ValueError(f"Checkpoint {to_checkpoint_id} not found")

                # 反向执行回滚处理器
                for checkpoint in reversed(self.state.checkpoints[target_idx + 1 :]):
                    handler = self._rollback_handlers.get(checkpoint.name)
                    if handler:
                        handler()
                    checkpoint.status = MigrationStatus.ROLLED_BACK
            else:
                # 回滚所有检查点
                for checkpoint in reversed(self.state.checkpoints):
                    handler = self._rollback_handlers.get(checkpoint.name)
                    if handler:
                        handler()
                    checkpoint.status = MigrationStatus.ROLLED_BACK

            self._persist_state()
            return True
        except Exception as e:
            self.state.error = str(e)
            self._persist_state()
            return False

    def complete_migration(self) -> None:
        """完成迁移"""
        self.state.status = MigrationStatus.COMPLETED
        self.state.phase = MigrationPhase.VERIFICATION
        self.state.progress = 1.0
        self.state.end_time = datetime.now(UTC).isoformat()
        self._persist_state()

    def get_state(self) -> MigrationState:
        """获取迁移状态"""
        return self.state

    def get_checkpoint(self, checkpoint_id: str) -> MigrationCheckpoint | None:
        """获取检查点"""
        return self._get_checkpoint(checkpoint_id)

    def get_checkpoints_by_phase(self, phase: MigrationPhase) -> list[MigrationCheckpoint]:
        """获取特定阶段的检查点"""
        return [cp for cp in self.state.checkpoints if cp.phase == phase]

    def get_summary(self) -> dict[str, Any]:
        """获取迁移摘要"""
        completed = sum(1 for cp in self.state.checkpoints if cp.status == MigrationStatus.COMPLETED)
        failed = sum(1 for cp in self.state.checkpoints if cp.status == MigrationStatus.FAILED)

        duration = 0.0
        if self.state.end_time:
            start = datetime.fromisoformat(self.state.start_time)
            end = datetime.fromisoformat(self.state.end_time)
            duration = (end - start).total_seconds()

        return {
            "id": self.state.id,
            "version": self.state.version,
            "status": self.state.status.value,
            "phase": self.state.phase.value,
            "progress": self.state.progress,
            "total_checkpoints": len(self.state.checkpoints),
            "completed_checkpoints": completed,
            "failed_checkpoints": failed,
            "duration_seconds": duration,
            "error": self.state.error,
        }

    def _get_checkpoint(self, checkpoint_id: str) -> MigrationCheckpoint | None:
        """获取检查点（内部）"""
        for checkpoint in self.state.checkpoints:
            if checkpoint.id == checkpoint_id:
                return checkpoint
        return None

    def _cleanup_old_checkpoints(self) -> None:
        """清理旧检查点"""
        if len(self.state.checkpoints) > self.max_checkpoints:
            # 保留最新的检查点
            self.state.checkpoints = self.state.checkpoints[-self.max_checkpoints :]

    def _persist_state(self) -> None:
        """持久化状态"""
        state_file = self.storage_path / f"migration_{self.state.id}.json"
        with open(state_file, "w") as f:
            json.dump(asdict(self.state), f, indent=2, default=str)

    def _load_state(self) -> None:
        """加载状态"""
        state_file = self.storage_path / f"migration_{self.state.id}.json"
        if state_file.exists():
            with open(state_file) as f:
                data = json.load(f)
                # 重建状态对象
                self.state = MigrationState(**data)


class MigrationVersionManager:
    """迁移版本管理器"""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path("data/migrations")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.versions: dict[str, MigrationVersion] = {}
        self._load_versions()

    def register_version(self, version: MigrationVersion) -> None:
        """注册版本"""
        self.versions[version.version] = version
        self._persist_versions()

    def get_version(self, version: str) -> MigrationVersion | None:
        """获取版本"""
        return self.versions.get(version)

    def get_all_versions(self) -> list[MigrationVersion]:
        """获取所有版本"""
        return sorted(
            self.versions.values(),
            key=lambda v: v.timestamp,
            reverse=True,
        )

    def get_migration_path(
        self,
        from_version: str,
        to_version: str,
    ) -> list[MigrationVersion] | None:
        """获取迁移路径"""
        if from_version not in self.versions or to_version not in self.versions:
            return None

        from_v = self.versions[from_version]
        to_v = self.versions[to_version]

        # 简单的线性迁移路径
        path = []
        for v in self.get_all_versions():
            if v.timestamp >= from_v.timestamp and v.timestamp <= to_v.timestamp:
                path.append(v)

        return sorted(path, key=lambda v: v.timestamp) if path else None

    def _persist_versions(self) -> None:
        """持久化版本"""
        versions_file = self.storage_path / "versions.json"
        with open(versions_file, "w") as f:
            json.dump(
                {k: asdict(v) for k, v in self.versions.items()},
                f,
                indent=2,
                default=str,
            )

    def _load_versions(self) -> None:
        """加载版本"""
        versions_file = self.storage_path / "versions.json"
        if versions_file.exists():
            with open(versions_file) as f:
                data = json.load(f)
                for k, v in data.items():
                    self.versions[k] = MigrationVersion(**v)
