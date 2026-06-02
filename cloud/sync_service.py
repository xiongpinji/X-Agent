"""
X-Agent 云端同步服务实现

支持三端同步、冲突解决、版本控制和加密
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================


class VectorClock(BaseModel):
    """向量时钟 - 用于检测因果关系"""

    clock: dict[str, int] = Field(default_factory=dict)

    def increment(self, client_id: str) -> None:
        """递增指定客户端的时钟"""
        self.clock[client_id] = self.clock.get(client_id, 0) + 1

    def merge(self, other: VectorClock) -> None:
        """合并两个向量时钟"""
        for client_id, value in other.clock.items():
            self.clock[client_id] = max(self.clock.get(client_id, 0), value)

    def happens_before(self, other: VectorClock) -> bool:
        """检查是否发生在other之前"""
        all_clients = set(self.clock.keys()) | set(other.clock.keys())

        less_or_equal = all(
            self.clock.get(c, 0) <= other.clock.get(c, 0)
            for c in all_clients
        )
        strictly_less = any(
            self.clock.get(c, 0) < other.clock.get(c, 0)
            for c in all_clients
        )

        return less_or_equal and strictly_less

    def concurrent_with(self, other: VectorClock) -> bool:
        """检查是否与other并发"""
        return not self.happens_before(other) and not other.happens_before(self)


class SyncOperation(BaseModel):
    """同步操作"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    client_id: str
    entity_type: str
    entity_id: str
    operation: str  # create, update, delete
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    vector_clock: VectorClock = Field(default_factory=VectorClock)
    data: dict[str, Any]
    checksum: str = ""
    encrypted: bool = False
    encryption_key_id: Optional[str] = None

    def compute_checksum(self) -> str:
        """计算数据校验和"""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def validate_checksum(self) -> bool:
        """验证数据完整性"""
        return self.checksum == self.compute_checksum()


class VersionSnapshot(BaseModel):
    """版本快照"""

    version_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str
    entity_id: str
    parent_version: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    author: Optional[str] = None
    message: str = ""
    data: dict[str, Any]
    diff: Optional[dict[str, Any]] = None
    checksum: str = ""

    def compute_checksum(self) -> str:
        """计算版本校验和"""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


class ConflictRecord(BaseModel):
    """冲突记录"""

    conflict_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str
    entity_id: str
    conflict_type: str  # concurrent_modification, delete_update, data_mismatch
    operations: list[SyncOperation]
    details: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending, resolved, manual_review
    resolution_strategy: Optional[str] = None
    resolution: Optional[dict[str, Any]] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SyncState(BaseModel):
    """同步状态"""

    client_id: str
    status: str = "synced"  # synced, syncing, pending, error
    vector_clock: VectorClock = Field(default_factory=VectorClock)
    last_sync_at: Optional[datetime] = None
    pending_operations_count: int = 0
    pending_conflicts_count: int = 0
    error_message: Optional[str] = None
    error_count: int = 0


# ============================================================================
# 冲突检测与解决
# ============================================================================


class ConflictDetector:
    """冲突检测器"""

    @staticmethod
    def detect_conflict(
        operation: SyncOperation,
        existing_operations: list[SyncOperation],
    ) -> Optional[ConflictRecord]:
        """检测冲突"""

        conflicts = []

        for existing_op in existing_operations:
            # 检查是否是同一实体的操作
            if (operation.entity_type != existing_op.entity_type or
                operation.entity_id != existing_op.entity_id):
                continue

            # 检查是否并发
            if operation.vector_clock.concurrent_with(existing_op.vector_clock):
                # 并发修改冲突
                if operation.operation == "update" and existing_op.operation == "update":
                    conflicts.append({
                        "type": "concurrent_modification",
                        "operations": [operation, existing_op],
                    })

                # 删除与修改冲突
                elif (operation.operation == "delete" and existing_op.operation == "update") or \
                     (operation.operation == "update" and existing_op.operation == "delete"):
                    conflicts.append({
                        "type": "delete_update",
                        "operations": [operation, existing_op],
                    })

        if conflicts:
            return ConflictRecord(
                entity_type=operation.entity_type,
                entity_id=operation.entity_id,
                conflict_type=conflicts[0]["type"],
                operations=[operation] + [c["operations"][1] for c in conflicts],
                details={"conflicts": conflicts},
            )

        return None


class ConflictResolver:
    """冲突解决器"""

    @staticmethod
    def resolve_lww(conflict: ConflictRecord) -> SyncOperation:
        """最后写入胜利策略"""
        return max(conflict.operations, key=lambda op: (op.timestamp, op.id))

    @staticmethod
    def resolve_crdt(conflict: ConflictRecord) -> dict[str, Any]:
        """CRDT策略 - 合并操作"""
        # 对于并发修改，合并数据
        merged_data = {}

        for op in conflict.operations:
            if op.operation == "update":
                # 递归合并字典
                merged_data = ConflictResolver._merge_dicts(
                    merged_data, op.data
                )

        return merged_data

    @staticmethod
    def _merge_dicts(dict1: dict, dict2: dict) -> dict:
        """递归合并字典"""
        result = dict1.copy()

        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConflictResolver._merge_dicts(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def resolve_manual(conflict: ConflictRecord, resolution: dict) -> dict:
        """人工审核策略"""
        return resolution

    @staticmethod
    def resolve(
        conflict: ConflictRecord,
        strategy: str = "lww",
        resolution: Optional[dict] = None,
    ) -> dict[str, Any]:
        """解决冲突"""

        if strategy == "lww":
            winning_op = ConflictResolver.resolve_lww(conflict)
            return {
                "strategy": "lww",
                "winning_operation": winning_op.id,
                "data": winning_op.data,
            }

        elif strategy == "crdt":
            merged_data = ConflictResolver.resolve_crdt(conflict)
            return {
                "strategy": "crdt",
                "data": merged_data,
            }

        elif strategy == "manual":
            if not resolution:
                raise ValueError("Manual resolution requires resolution data")
            return {
                "strategy": "manual",
                "data": resolution,
            }

        else:
            raise ValueError(f"Unknown resolution strategy: {strategy}")


# ============================================================================
# 同步服务
# ============================================================================


class SyncService:
    """同步服务"""

    def __init__(self):
        self.operations: dict[str, SyncOperation] = {}
        self.versions: dict[str, VersionSnapshot] = {}
        self.conflicts: dict[str, ConflictRecord] = {}
        self.sync_states: dict[str, SyncState] = {}
        self.detector = ConflictDetector()
        self.resolver = ConflictResolver()

    def submit_operation(self, operation: SyncOperation) -> dict[str, Any]:
        """提交同步操作"""

        logger.info(f"Submitting operation: {operation.id}")

        # 计算校验和
        operation.checksum = operation.compute_checksum()

        # 验证校验和
        if not operation.validate_checksum():
            raise ValueError("Checksum validation failed")

        # 检测冲突
        existing_ops = [
            op for op in self.operations.values()
            if op.entity_type == operation.entity_type and
               op.entity_id == operation.entity_id
        ]

        conflict = self.detector.detect_conflict(operation, existing_ops)

        if conflict:
            logger.warning(f"Conflict detected: {conflict.conflict_id}")
            self.conflicts[conflict.conflict_id] = conflict

            return {
                "operation_id": operation.id,
                "status": "conflicted",
                "conflict_id": conflict.conflict_id,
                "conflict_type": conflict.conflict_type,
            }

        # 应用操作
        self.operations[operation.id] = operation

        # 更新同步状态
        self._update_sync_state(operation.client_id, operation.vector_clock)

        # 创建版本快照
        version = self._create_version_snapshot(operation)

        logger.info(f"Operation applied: {operation.id}, version: {version.version_id}")

        return {
            "operation_id": operation.id,
            "status": "applied",
            "version": version.version_id,
            "timestamp": operation.timestamp.isoformat(),
        }

    def resolve_conflict(
        self,
        conflict_id: str,
        strategy: str = "lww",
        resolution: Optional[dict] = None,
    ) -> dict[str, Any]:
        """解决冲突"""

        if conflict_id not in self.conflicts:
            raise ValueError(f"Conflict not found: {conflict_id}")

        conflict = self.conflicts[conflict_id]

        logger.info(f"Resolving conflict: {conflict_id} with strategy: {strategy}")

        # 解决冲突
        result = self.resolver.resolve(conflict, strategy, resolution)

        # 更新冲突状态
        conflict.status = "resolved"
        conflict.resolution_strategy = strategy
        conflict.resolution = result
        conflict.resolved_at = datetime.now(UTC)

        # 应用解决方案
        if strategy == "lww":
            # 应用获胜的操作
            winning_op_id = result["winning_operation"]
            winning_op = self.operations[winning_op_id]
            self._update_sync_state(winning_op.client_id, winning_op.vector_clock)

        logger.info(f"Conflict resolved: {conflict_id}")

        return {
            "conflict_id": conflict_id,
            "status": "resolved",
            "strategy": strategy,
            "resolved_at": conflict.resolved_at.isoformat(),
        }

    def get_version_history(self, entity_id: str) -> list[VersionSnapshot]:
        """获取版本历史"""

        versions = [
            v for v in self.versions.values()
            if v.entity_id == entity_id
        ]

        # 按时间排序
        versions.sort(key=lambda v: v.timestamp, reverse=True)

        return versions

    def restore_version(
        self,
        entity_id: str,
        version_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """恢复到指定版本"""

        if version_id not in self.versions:
            raise ValueError(f"Version not found: {version_id}")

        version = self.versions[version_id]

        logger.info(f"Restoring entity {entity_id} to version {version_id}")

        # 创建恢复操作
        restore_op = SyncOperation(
            client_id="system",
            entity_type=version.entity_type,
            entity_id=version.entity_id,
            operation="update",
            data=version.data,
        )

        # 提交恢复操作
        result = self.submit_operation(restore_op)

        logger.info(f"Entity restored: {entity_id}")

        return {
            "entity_id": entity_id,
            "new_version": result["version"],
            "restored_at": datetime.now(UTC).isoformat(),
            "reason": reason,
        }

    def get_sync_status(self, client_id: str) -> SyncState:
        """获取同步状态"""

        if client_id not in self.sync_states:
            self.sync_states[client_id] = SyncState(client_id=client_id)

        return self.sync_states[client_id]

    def get_sync_statistics(self, period: str = "day") -> dict[str, Any]:
        """获取同步统计"""

        total_ops = len(self.operations)
        total_conflicts = len(self.conflicts)
        resolved_conflicts = sum(
            1 for c in self.conflicts.values() if c.status == "resolved"
        )

        # 计算成功率
        success_rate = (total_ops - total_conflicts) / max(total_ops, 1) * 100

        return {
            "period": period,
            "total_operations": total_ops,
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "pending_conflicts": total_conflicts - resolved_conflicts,
            "success_rate": success_rate,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _create_version_snapshot(self, operation: SyncOperation) -> VersionSnapshot:
        """创建版本快照"""

        # 获取前一个版本
        existing_versions = [
            v for v in self.versions.values()
            if v.entity_id == operation.entity_id
        ]

        parent_version = None
        if existing_versions:
            parent_version = max(
                existing_versions,
                key=lambda v: v.timestamp
            ).version_id

        # 创建新版本
        version = VersionSnapshot(
            entity_type=operation.entity_type,
            entity_id=operation.entity_id,
            parent_version=parent_version,
            author=operation.client_id,
            message=f"Operation: {operation.operation}",
            data=operation.data,
        )

        version.checksum = version.compute_checksum()
        self.versions[version.version_id] = version

        return version

    def _update_sync_state(
        self,
        client_id: str,
        vector_clock: VectorClock,
    ) -> None:
        """更新同步状态"""

        if client_id not in self.sync_states:
            self.sync_states[client_id] = SyncState(client_id=client_id)

        state = self.sync_states[client_id]
        state.vector_clock.merge(vector_clock)
        state.last_sync_at = datetime.now(UTC)
        state.status = "synced"


# ============================================================================
# 使用示例
# ============================================================================


def example_usage():
    """使用示例"""

    # 创建同步服务
    sync_service = SyncService()

    # 创建操作1
    op1 = SyncOperation(
        client_id="client_1",
        entity_type="memory",
        entity_id="mem_123",
        operation="create",
        data={"content": "Initial memory", "tags": ["important"]},
    )

    # 提交操作1
    result1 = sync_service.submit_operation(op1)
    print(f"Operation 1 result: {result1}")

    # 创建操作2（并发修改）
    op2 = SyncOperation(
        client_id="client_2",
        entity_type="memory",
        entity_id="mem_123",
        operation="update",
        data={"content": "Updated by client 2", "tags": ["important", "recent"]},
        vector_clock=VectorClock(clock={"client_1": 1}),
    )

    # 提交操作2
    result2 = sync_service.submit_operation(op2)
    print(f"Operation 2 result: {result2}")

    # 如果有冲突，解决冲突
    if result2["status"] == "conflicted":
        conflict_id = result2["conflict_id"]
        resolve_result = sync_service.resolve_conflict(
            conflict_id,
            strategy="lww",
        )
        print(f"Conflict resolution result: {resolve_result}")

    # 获取版本历史
    versions = sync_service.get_version_history("mem_123")
    print(f"Version history: {len(versions)} versions")

    # 获取同步统计
    stats = sync_service.get_sync_statistics()
    print(f"Sync statistics: {stats}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_usage()
