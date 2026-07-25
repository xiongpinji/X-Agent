"""Work Mode — 跨应用长任务编排（对标 ChatGPT Work）。

支持数小时持续工作，连接外部应用，自动产出工件。
利用 CheckpointStore 实现跨迭代持久化，里程碑间传递上下文。
"""

from backend.app.core.work_mode.connectors import (
    AppConnector,
    FileConnector,
    WebhookConnector,
)
from backend.app.core.work_mode.goal_decomposer import GoalDecomposer
from backend.app.core.work_mode.orchestrator import (
    Artifact,
    Milestone,
    WorkOrchestrator,
    WorkSession,
    WorkSessionStatus,
    get_work_orchestrator,
)

__all__ = [
    "AppConnector",
    "Artifact",
    "FileConnector",
    "GoalDecomposer",
    "Milestone",
    "WebhookConnector",
    "WorkOrchestrator",
    "WorkSession",
    "WorkSessionStatus",
    "get_work_orchestrator",
]
