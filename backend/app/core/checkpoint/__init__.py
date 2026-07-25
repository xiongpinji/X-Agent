"""断点续跑/失败恢复（Checkpoint & Resume）模块。

会话断点续跑、部分结果保留：自动/手动检查点 → 状态快照 → 恢复执行。
"""

from backend.app.core.checkpoint.manager import CheckpointManager
from backend.app.core.checkpoint.restorer import StateRestorer
from backend.app.core.checkpoint.snapshot import ExecutionSnapshot
from backend.app.core.checkpoint.store import (
    CheckpointData,
    CheckpointStore,
    CheckpointSummary,
    get_checkpoint_store,
)

__all__ = [
    "CheckpointData",
    "CheckpointManager",
    "CheckpointStore",
    "CheckpointSummary",
    "ExecutionSnapshot",
    "StateRestorer",
    "get_checkpoint_store",
]
