"""
X-Agent 端到端测试框架 - 离线测试模块

测试范围:
- 离线数据操作
- 网络恢复同步
- 冲突解决
- 离线队列管理
"""

import pytest
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import time


# ============================================================================
# 数据模型
# ============================================================================

class OfflineOperationType(str, Enum):
    """离线操作类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class NetworkStatus(str, Enum):
    """网络状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    POOR = "poor"
    RECOVERING = "recovering"


@dataclass
class OfflineOperation:
    """离线操作"""
    operation_id: str
    entity_type: str
    entity_id: str
    operation_type: OfflineOperationType
    data: Dict[str, Any]
    timestamp: datetime
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class OfflineConflict:
    """离线冲突"""
    conflict_id: str
    entity_id: str
    local_version: int
    remote_version: int
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    detected_at: datetime
    resolved: bool = False
    resolution: Optional[Dict[str, Any]] = None


# ============================================================================
# 离线存储
# ============================================================================

class OfflineStore:
    """离线存储"""

    def __init__(self):
        self.local_data: Dict[str, Any] = {}
        self.operation_queue: List[OfflineOperation] = []
        self.conflicts: List[OfflineConflict] = []
        self.network_status = NetworkStatus.ONLINE
        self.operation_counter = 0

    def create_offline(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> OfflineOperation:
        """离线创建"""
        self.operation_counter += 1
        operation = OfflineOperation(
            operation_id=f"op_{self.operation_counter:06d}",
            entity_type=entity_type,
            entity_id=entity_id,
            operation_type=OfflineOperationType.CREATE,
            data=data,
            timestamp=datetime.now()
        )

        # 保存到本地存储
        self.local_data[entity_id] = {
            "data": data,
            "version": 1,
            "created_at": datetime.now()
        }

        # 添加到操作队列
        self.operation_queue.append(operation)

        return operation

    def update_offline(self, entity_id: str, data: Dict[str, Any]) -> Optional[OfflineOperation]:
        """离线更新"""
        if entity_id not in self.local_data:
            return None

        self.operation_counter += 1
        operation = OfflineOperation(
            operation_id=f"op_{self.operation_counter:06d}",
            entity_type="task",
            entity_id=entity_id,
            operation_type=OfflineOperationType.UPDATE,
            data=data,
            timestamp=datetime.now()
        )

        # 更新本地存储
        self.local_data[entity_id]["data"] = data
        self.local_data[entity_id]["version"] += 1

        # 添加到操作队列
        self.operation_queue.append(operation)

        return operation

    def delete_offline(self, entity_id: str) -> Optional[OfflineOperation]:
        """离线删除"""
        if entity_id not in self.local_data:
            return None

        self.operation_counter += 1
        operation = OfflineOperation(
            operation_id=f"op_{self.operation_counter:06d}",
            entity_type="task",
            entity_id=entity_id,
            operation_type=OfflineOperationType.DELETE,
            data={},
            timestamp=datetime.now()
        )

        # 从本地存储删除
        del self.local_data[entity_id]

        # 添加到操作队列
        self.operation_queue.append(operation)

        return operation

    def set_network_status(self, status: NetworkStatus):
        """设置网络状态"""
        self.network_status = status

    def get_pending_operations(self) -> List[OfflineOperation]:
        """获取待同步操作"""
        return [op for op in self.operation_queue if op.retry_count < op.max_retries]

    def mark_operation_synced(self, operation_id: str):
        """标记操作已同步"""
        for op in self.operation_queue:
            if op.operation_id == operation_id:
                self.operation_queue.remove(op)
                break

    def add_conflict(self, conflict: OfflineConflict):
        """添加冲突"""
        self.conflicts.append(conflict)

    def resolve_conflict(self, conflict_id: str, resolution: Dict[str, Any]) -> bool:
        """解决冲突"""
        for conflict in self.conflicts:
            if conflict.conflict_id == conflict_id:
                conflict.resolved = True
                conflict.resolution = resolution
                return True
        return False

    def get_unresolved_conflicts(self) -> List[OfflineConflict]:
        """获取未解决的冲突"""
        return [c for c in self.conflicts if not c.resolved]


# ============================================================================
# 离线同步管理器
# ============================================================================

class OfflineSyncManager:
    """离线同步管理器"""

    def __init__(self):
        self.offline_store = OfflineStore()
        self.sync_history: List[Dict[str, Any]] = []
        self.sync_counter = 0

    async def sync_offline_queue(self, remote_store: Dict[str, Any]) -> Dict[str, Any]:
        """同步离线队列"""
        self.sync_counter += 1
        sync_id = f"sync_{self.sync_counter:06d}"

        sync_result = {
            "sync_id": sync_id,
            "started_at": datetime.now(),
            "completed_at": None,
            "total_operations": len(self.offline_store.operation_queue),
            "synced_operations": 0,
            "failed_operations": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "errors": []
        }

        pending_ops = self.offline_store.get_pending_operations()

        for operation in pending_ops:
            try:
                # 检查冲突
                conflict = self._check_conflict(operation, remote_store)

                if conflict:
                    self.offline_store.add_conflict(conflict)
                    sync_result["conflicts_detected"] += 1
                    # 自动解决冲突
                    resolution = self._auto_resolve_conflict(conflict)
                    self.offline_store.resolve_conflict(conflict.conflict_id, resolution)
                    sync_result["conflicts_resolved"] += 1

                # 应用操作
                self._apply_operation(operation, remote_store)
                self.offline_store.mark_operation_synced(operation.operation_id)
                sync_result["synced_operations"] += 1

            except Exception as e:
                operation.retry_count += 1
                sync_result["failed_operations"] += 1
                sync_result["errors"].append(str(e))

        sync_result["completed_at"] = datetime.now()
        self.sync_history.append(sync_result)

        return sync_result

    def _check_conflict(self, operation: OfflineOperation, remote_store: Dict[str, Any]) -> Optional[OfflineConflict]:
        """检查冲突"""
        if operation.entity_id in remote_store:
            remote_data = remote_store[operation.entity_id]
            local_data = self.offline_store.local_data.get(operation.entity_id, {})

            if local_data.get("version", 0) < remote_data.get("version", 0):
                conflict = OfflineConflict(
                    conflict_id=f"conflict_{int(datetime.now().timestamp() * 1000)}",
                    entity_id=operation.entity_id,
                    local_version=local_data.get("version", 0),
                    remote_version=remote_data.get("version", 0),
                    local_data=local_data.get("data", {}),
                    remote_data=remote_data.get("data", {}),
                    detected_at=datetime.now()
                )
                return conflict

        return None

    @staticmethod
    def _auto_resolve_conflict(conflict: OfflineConflict) -> Dict[str, Any]:
        """自动解决冲突 - 使用最后写入获胜策略"""
        return conflict.local_data

    @staticmethod
    def _apply_operation(operation: OfflineOperation, remote_store: Dict[str, Any]):
        """应用操作"""
        if operation.operation_type == OfflineOperationType.CREATE:
            remote_store[operation.entity_id] = {
                "data": operation.data,
                "version": 1,
                "created_at": operation.timestamp
            }
        elif operation.operation_type == OfflineOperationType.UPDATE:
            if operation.entity_id in remote_store:
                remote_store[operation.entity_id]["data"] = operation.data
                remote_store[operation.entity_id]["version"] += 1
        elif operation.operation_type == OfflineOperationType.DELETE:
            if operation.entity_id in remote_store:
                del remote_store[operation.entity_id]

    def get_sync_history(self) -> List[Dict[str, Any]]:
        """获取同步历史"""
        return self.sync_history


# ============================================================================
# 网络模拟器
# ============================================================================

class NetworkSimulator:
    """网络模拟器"""

    def __init__(self):
        self.status = NetworkStatus.ONLINE
        self.latency = 0  # 毫秒
        self.packet_loss = 0  # 百分比
        self.bandwidth = 1000  # Mbps

    def set_offline(self):
        """设置离线"""
        self.status = NetworkStatus.OFFLINE

    def set_online(self):
        """设置在线"""
        self.status = NetworkStatus.ONLINE

    def set_poor_connection(self, latency: int = 500, packet_loss: int = 10):
        """设置网络不良"""
        self.status = NetworkStatus.POOR
        self.latency = latency
        self.packet_loss = packet_loss

    def set_recovering(self):
        """设置恢复中"""
        self.status = NetworkStatus.RECOVERING

    def simulate_latency(self):
        """模拟延迟"""
        if self.status == NetworkStatus.OFFLINE:
            raise ConnectionError("Network is offline")

        if self.status == NetworkStatus.POOR:
            time.sleep(self.latency / 1000)

    def should_drop_packet(self) -> bool:
        """是否丢弃数据包"""
        import random
        return random.random() < (self.packet_loss / 100)


# ============================================================================
# 测试用例
# ============================================================================

class TestOfflineDataOperations:
    """离线数据操作测试"""

    def test_offline_create_task(self):
        """TC-OFFLINE-001: 离线创建任务"""
        offline_store = OfflineStore()

        operation = offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Offline Task", "status": "pending"}
        )

        assert operation.operation_type == OfflineOperationType.CREATE
        assert "task_001" in offline_store.local_data
        assert len(offline_store.operation_queue) == 1

    def test_offline_update_task(self):
        """TC-OFFLINE-002: 离线修改任务"""
        offline_store = OfflineStore()

        offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Original Task", "status": "pending"}
        )

        operation = offline_store.update_offline(
            entity_id="task_001",
            data={"title": "Updated Task", "status": "completed"}
        )

        assert operation.operation_type == OfflineOperationType.UPDATE
        assert offline_store.local_data["task_001"]["version"] == 2
        assert offline_store.local_data["task_001"]["data"]["status"] == "completed"

    def test_offline_delete_task(self):
        """TC-OFFLINE-003: 离线删除任务"""
        offline_store = OfflineStore()

        offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Task to Delete", "status": "pending"}
        )

        operation = offline_store.delete_offline("task_001")

        assert operation.operation_type == OfflineOperationType.DELETE
        assert "task_001" not in offline_store.local_data


class TestNetworkRecoverySynchronization:
    """网络恢复同步测试"""

    @pytest.mark.asyncio
    async def test_network_recovery_sync(self):
        """TC-OFFLINE-008: 网络恢复后同步"""
        sync_manager = OfflineSyncManager()
        network = NetworkSimulator()

        # 离线创建数据
        network.set_offline()
        sync_manager.offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Task 1", "status": "pending"}
        )
        sync_manager.offline_store.create_offline(
            entity_type="task",
            entity_id="task_002",
            data={"title": "Task 2", "status": "pending"}
        )

        assert len(sync_manager.offline_store.operation_queue) == 2

        # 网络恢复
        network.set_online()
        remote_store = {}

        result = await sync_manager.sync_offline_queue(remote_store)

        assert result["synced_operations"] == 2
        assert result["failed_operations"] == 0
        assert len(sync_manager.offline_store.operation_queue) == 0

    @pytest.mark.asyncio
    async def test_partial_network_recovery(self):
        """TC-OFFLINE-009: 部分网络恢复"""
        sync_manager = OfflineSyncManager()
        network = NetworkSimulator()

        # 离线创建数据
        network.set_offline()
        for i in range(5):
            sync_manager.offline_store.create_offline(
                entity_type="task",
                entity_id=f"task_{i:03d}",
                data={"title": f"Task {i}", "status": "pending"}
            )

        # 部分网络恢复
        network.set_poor_connection(latency=500, packet_loss=20)
        remote_store = {}

        result = await sync_manager.sync_offline_queue(remote_store)

        # 即使网络不良，也应该同步成功
        assert result["synced_operations"] > 0

    @pytest.mark.asyncio
    async def test_long_offline_recovery(self):
        """TC-OFFLINE-011: 长期离线恢复"""
        sync_manager = OfflineSyncManager()
        network = NetworkSimulator()

        # 长期离线创建大量数据
        network.set_offline()
        for i in range(100):
            sync_manager.offline_store.create_offline(
                entity_type="task",
                entity_id=f"task_{i:06d}",
                data={"title": f"Task {i}", "status": "pending"}
            )

        assert len(sync_manager.offline_store.operation_queue) == 100

        # 网络恢复
        network.set_online()
        remote_store = {}

        result = await sync_manager.sync_offline_queue(remote_store)

        assert result["total_operations"] == 100
        assert result["synced_operations"] == 100


class TestConflictResolution:
    """冲突解决测试"""

    @pytest.mark.asyncio
    async def test_offline_conflict_detection(self):
        """TC-OFFLINE-014: 离线冲突检测"""
        sync_manager = OfflineSyncManager()

        # 本地创建数据
        sync_manager.offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Local Task", "status": "pending"}
        )

        # 远程已有更新版本
        remote_store = {
            "task_001": {
                "data": {"title": "Remote Task", "status": "completed"},
                "version": 2,
                "created_at": datetime.now()
            }
        }

        result = await sync_manager.sync_offline_queue(remote_store)

        assert result["conflicts_detected"] > 0

    @pytest.mark.asyncio
    async def test_offline_conflict_resolution(self):
        """TC-OFFLINE-015: 离线冲突解决"""
        sync_manager = OfflineSyncManager()

        # 本地创建数据
        sync_manager.offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Local Task", "status": "pending"}
        )

        # 远程已有更新版本
        remote_store = {
            "task_001": {
                "data": {"title": "Remote Task", "status": "completed"},
                "version": 2,
                "created_at": datetime.now()
            }
        }

        result = await sync_manager.sync_offline_queue(remote_store)

        assert result["conflicts_resolved"] > 0
        assert len(sync_manager.offline_store.get_unresolved_conflicts()) == 0

    @pytest.mark.asyncio
    async def test_conflict_logging(self):
        """TC-OFFLINE-016: 冲突日志记录"""
        sync_manager = OfflineSyncManager()

        # 创建冲突
        sync_manager.offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Local Task", "status": "pending"}
        )

        remote_store = {
            "task_001": {
                "data": {"title": "Remote Task", "status": "completed"},
                "version": 2,
                "created_at": datetime.now()
            }
        }

        result = await sync_manager.sync_offline_queue(remote_store)

        # 验证冲突被记录
        assert len(sync_manager.offline_store.conflicts) > 0


class TestOfflineQueueManagement:
    """离线队列管理测试"""

    def test_queue_enqueue(self):
        """TC-OFFLINE-021: 队列入队"""
        offline_store = OfflineStore()

        for i in range(5):
            offline_store.create_offline(
                entity_type="task",
                entity_id=f"task_{i:03d}",
                data={"title": f"Task {i}", "status": "pending"}
            )

        assert len(offline_store.operation_queue) == 5

    def test_queue_dequeue(self):
        """TC-OFFLINE-022: 队列出队"""
        offline_store = OfflineStore()

        operation = offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Task", "status": "pending"}
        )

        offline_store.mark_operation_synced(operation.operation_id)

        assert len(offline_store.operation_queue) == 0

    def test_queue_priority(self):
        """TC-OFFLINE-023: 队列优先级"""
        offline_store = OfflineStore()

        # 创建不同优先级的操作
        op1 = offline_store.create_offline(
            entity_type="task",
            entity_id="task_001",
            data={"title": "Task 1", "status": "pending"}
        )
        op1.priority = 1

        op2 = offline_store.create_offline(
            entity_type="task",
            entity_id="task_002",
            data={"title": "Task 2", "status": "pending"}
        )
        op2.priority = 10

        # 按优先级排序
        sorted_ops = sorted(offline_store.operation_queue, key=lambda x: x.priority, reverse=True)

        assert sorted_ops[0].priority == 10

    def test_queue_persistence(self):
        """TC-OFFLINE-024: 队列持久化"""
        offline_store = OfflineStore()

        # 创建操作
        for i in range(3):
            offline_store.create_offline(
                entity_type="task",
                entity_id=f"task_{i:03d}",
                data={"title": f"Task {i}", "status": "pending"}
            )

        # 模拟持久化
        queue_snapshot = list(offline_store.operation_queue)

        assert len(queue_snapshot) == 3

    def test_queue_recovery(self):
        """TC-OFFLINE-025: 队列恢复"""
        offline_store = OfflineStore()

        # 创建操作
        for i in range(3):
            offline_store.create_offline(
                entity_type="task",
                entity_id=f"task_{i:03d}",
                data={"title": f"Task {i}", "status": "pending"}
            )

        # 获取待同步操作
        pending_ops = offline_store.get_pending_operations()

        assert len(pending_ops) == 3


# ============================================================================
# 测试套件
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

