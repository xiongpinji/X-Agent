"""SOC 2 Type I 合规基础设施 — 证据收集、变更管理、事件响应。

P2-01: 为 SOC 2 Type I 认证建立代码层面的证据收集框架。
本模块不替代外部审计机构，而是提供：
1. 自动化证据收集（控制点验证快照）
2. 变更管理制度（代码化审批流）
3. 事件响应流程（结构化模板）
4. Trust Services Criteria 映射
"""

from backend.app.core.compliance.change_management import (
    ChangeManagementEngine,
    ChangeRequest,
    ChangeRisk,
    ChangeStatus,
)
from backend.app.core.compliance.evidence import ControlEvidence, EvidenceCollector
from backend.app.core.compliance.incident_response import (
    IncidentPhase,
    IncidentResponseEngine,
    IncidentSeverity,
    SecurityIncident,
)
from backend.app.core.compliance.trust_criteria import TrustServicesCriteria

__all__ = [
    "ChangeManagementEngine",
    "ChangeRequest",
    "ChangeRisk",
    "ChangeStatus",
    "ControlEvidence",
    "EvidenceCollector",
    "IncidentPhase",
    "IncidentResponseEngine",
    "IncidentSeverity",
    "SecurityIncident",
    "TrustServicesCriteria",
]
