"""证据驱动完成（Evidence-Driven Completion）模块。

任务完成必须附运行证据（测试通过/截图/diff/日志/指标），替代"自称完成"。
"""

from backend.app.core.evidence.collector import EvidenceCollector
from backend.app.core.evidence.contracts import (
    CompletionEvidence,
    EvidenceItem,
    EvidenceKind,
)
from backend.app.core.evidence.storage import EvidenceStorage
from backend.app.core.evidence.verifier import EvidenceVerifier

__all__ = [
    "CompletionEvidence",
    "EvidenceCollector",
    "EvidenceItem",
    "EvidenceKind",
    "EvidenceStorage",
    "EvidenceVerifier",
]
