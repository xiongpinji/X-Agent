"""SOC 2 事件响应流程 — 安全事件结构化处理。

CC7.3/CC7.4: 事件响应控制点 — 安全事件的检测、响应、恢复、复盘。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class IncidentSeverity(StrEnum):
    """事件严重等级。"""

    CRITICAL = "critical"  # 数据泄露、服务完全不可用
    HIGH = "high"  # 部分数据暴露、核心功能降级
    MEDIUM = "medium"  # 非核心功能异常、潜在风险
    LOW = "low"  # 信息性事件、无实际影响


class IncidentPhase(StrEnum):
    """事件响应阶段 (NIST SP 800-61)。"""

    DETECTION = "detection"  # 检测与确认
    CONTAINMENT = "containment"  # 遏制
    ERADICATION = "eradication"  # 根除
    RECOVERY = "recovery"  # 恢复
    POST_INCIDENT = "post_incident"  # 事后复盘
    CLOSED = "closed"  # 关闭


class IncidentCategory(StrEnum):
    """事件类别。"""

    DATA_BREACH = "data_breach"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    MALWARE = "malware"
    DOS = "denial_of_service"
    INSIDER_THREAT = "insider_threat"
    SUPPLY_CHAIN = "supply_chain"
    MISCONFIGURATION = "misconfiguration"
    OTHER = "other"


@dataclass
class IncidentAction:
    """事件响应动作记录。"""

    action: str
    actor: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: str = ""
    phase: IncidentPhase = IncidentPhase.DETECTION


@dataclass
class SecurityIncident:
    """安全事件 — SOC 2 事件响应的核心实体。"""

    incident_id: str = field(default_factory=lambda: f"INC-{uuid4().hex[:8].upper()}")
    title: str = ""
    description: str = ""
    category: IncidentCategory = IncidentCategory.OTHER
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    phase: IncidentPhase = IncidentPhase.DETECTION

    # 时间线
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    contained_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None

    # 响应
    incident_commander: str = ""
    response_team: list[str] = field(default_factory=list)
    actions: list[IncidentAction] = field(default_factory=list)

    # 影响评估
    affected_tenants: list[str] = field(default_factory=list)
    affected_users: int = 0
    data_exposed: bool = False
    services_impacted: list[str] = field(default_factory=list)

    # 根因与修复
    root_cause: str = ""
    remediation: str = ""
    prevention_measures: str = ""

    # 通知
    notifications_sent: list[dict[str, Any]] = field(default_factory=list)
    regulatory_notification_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "phase": self.phase.value,
            "detected_at": self.detected_at.isoformat(),
            "contained_at": self.contained_at.isoformat() if self.contained_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "incident_commander": self.incident_commander,
            "response_team": self.response_team,
            "actions": [
                {"action": a.action, "actor": a.actor,
                 "timestamp": a.timestamp.isoformat(), "details": a.details,
                 "phase": a.phase.value}
                for a in self.actions
            ],
            "affected_tenants": self.affected_tenants,
            "affected_users": self.affected_users,
            "data_exposed": self.data_exposed,
            "services_impacted": self.services_impacted,
            "root_cause": self.root_cause,
            "remediation": self.remediation,
            "prevention_measures": self.prevention_measures,
            "regulatory_notification_required": self.regulatory_notification_required,
        }


# 严重等级对应的响应 SLA（分钟）
SEVERITY_SLA: dict[IncidentSeverity, dict[str, int]] = {
    IncidentSeverity.CRITICAL: {"acknowledge": 15, "contain": 60, "resolve": 240},
    IncidentSeverity.HIGH: {"acknowledge": 30, "contain": 120, "resolve": 480},
    IncidentSeverity.MEDIUM: {"acknowledge": 120, "contain": 480, "resolve": 1440},
    IncidentSeverity.LOW: {"acknowledge": 480, "contain": 1440, "resolve": 4320},
}


class IncidentResponseEngine:
    """事件响应引擎 — 管理安全事件全生命周期。

    遵循 NIST SP 800-61 事件响应生命周期:
    Detection → Containment → Eradication → Recovery → Post-Incident
    """

    def __init__(self):
        self._incidents: dict[str, SecurityIncident] = {}

    def report_incident(
        self,
        title: str,
        description: str,
        category: IncidentCategory = IncidentCategory.OTHER,
        severity: IncidentSeverity = IncidentSeverity.MEDIUM,
        reporter: str = "system",
        affected_tenants: list[str] | None = None,
    ) -> SecurityIncident:
        """报告新安全事件。"""
        incident = SecurityIncident(
            title=title,
            description=description,
            category=category,
            severity=severity,
            affected_tenants=affected_tenants or [],
        )
        incident.actions.append(IncidentAction(
            action="incident_reported",
            actor=reporter,
            details=f"Severity: {severity.value}, Category: {category.value}",
            phase=IncidentPhase.DETECTION,
        ))

        # 数据暴露事件自动标记监管通知
        if category == IncidentCategory.DATA_BREACH:
            incident.regulatory_notification_required = True
            incident.data_exposed = True

        self._incidents[incident.incident_id] = incident
        sla = SEVERITY_SLA[severity]
        logger.warning(
            "Security incident reported: %s [%s] SLA: ack=%dmin contain=%dmin",
            incident.incident_id, severity.value,
            sla["acknowledge"], sla["contain"],
        )
        return incident

    def assign_commander(self, incident_id: str, commander: str, team: list[str] | None = None) -> bool:
        """指定事件指挥官和响应团队。"""
        inc = self._get(incident_id)
        inc.incident_commander = commander
        inc.response_team = team or [commander]
        inc.actions.append(IncidentAction(
            action="commander_assigned",
            actor=commander,
            details=f"Team: {', '.join(inc.response_team)}",
            phase=IncidentPhase.DETECTION,
        ))
        return True

    def contain(self, incident_id: str, action_taken: str, actor: str) -> bool:
        """遏制事件。"""
        inc = self._get(incident_id)
        if inc.phase != IncidentPhase.DETECTION:
            return False
        inc.phase = IncidentPhase.CONTAINMENT
        inc.contained_at = datetime.now(UTC)
        inc.actions.append(IncidentAction(
            action=f"containment: {action_taken}",
            actor=actor,
            phase=IncidentPhase.CONTAINMENT,
        ))
        logger.info("Incident %s contained", incident_id)
        return True

    def eradicate(self, incident_id: str, root_cause: str, action_taken: str, actor: str) -> bool:
        """根除威胁。"""
        inc = self._get(incident_id)
        if inc.phase != IncidentPhase.CONTAINMENT:
            return False
        inc.phase = IncidentPhase.ERADICATION
        inc.root_cause = root_cause
        inc.actions.append(IncidentAction(
            action=f"eradication: {action_taken}",
            actor=actor,
            details=f"Root cause: {root_cause}",
            phase=IncidentPhase.ERADICATION,
        ))
        return True

    def recover(self, incident_id: str, remediation: str, actor: str) -> bool:
        """恢复正常运营。"""
        inc = self._get(incident_id)
        if inc.phase != IncidentPhase.ERADICATION:
            return False
        inc.phase = IncidentPhase.RECOVERY
        inc.remediation = remediation
        inc.resolved_at = datetime.now(UTC)
        inc.actions.append(IncidentAction(
            action=f"recovery: {remediation}",
            actor=actor,
            phase=IncidentPhase.RECOVERY,
        ))
        logger.info("Incident %s recovered", incident_id)
        return True

    def post_incident_review(
        self,
        incident_id: str,
        prevention_measures: str,
        reviewer: str,
    ) -> bool:
        """事后复盘。"""
        inc = self._get(incident_id)
        if inc.phase != IncidentPhase.RECOVERY:
            return False
        inc.phase = IncidentPhase.POST_INCIDENT
        inc.prevention_measures = prevention_measures
        inc.actions.append(IncidentAction(
            action="post_incident_review",
            actor=reviewer,
            details=f"Prevention: {prevention_measures}",
            phase=IncidentPhase.POST_INCIDENT,
        ))
        return True

    def close_incident(self, incident_id: str, closed_by: str) -> bool:
        """关闭事件。"""
        inc = self._get(incident_id)
        if inc.phase != IncidentPhase.POST_INCIDENT:
            return False
        inc.phase = IncidentPhase.CLOSED
        inc.closed_at = datetime.now(UTC)
        inc.actions.append(IncidentAction(
            action="incident_closed",
            actor=closed_by,
            phase=IncidentPhase.CLOSED,
        ))
        logger.info("Incident %s closed", incident_id)
        return True

    def get_incident(self, incident_id: str) -> SecurityIncident | None:
        return self._incidents.get(incident_id)

    def list_incidents(
        self,
        severity: IncidentSeverity | None = None,
        phase: IncidentPhase | None = None,
    ) -> list[SecurityIncident]:
        results = list(self._incidents.values())
        if severity:
            results = [i for i in results if i.severity == severity]
        if phase:
            results = [i for i in results if i.phase == phase]
        return sorted(results, key=lambda i: i.detected_at, reverse=True)

    def check_sla_compliance(self, incident_id: str) -> dict[str, Any]:
        """检查事件响应 SLA 合规性。"""
        inc = self._get(incident_id)
        sla = SEVERITY_SLA[inc.severity]
        now = datetime.now(UTC)

        result: dict[str, Any] = {"incident_id": incident_id, "severity": inc.severity.value}

        # 确认 SLA
        ack_minutes = (inc.contained_at or now - inc.detected_at).total_seconds() / 60 if inc.contained_at else (now - inc.detected_at).total_seconds() / 60
        result["acknowledge_sla_met"] = ack_minutes <= sla["acknowledge"]

        # 遏制 SLA
        if inc.contained_at:
            contain_minutes = (inc.contained_at - inc.detected_at).total_seconds() / 60
            result["containment_sla_met"] = contain_minutes <= sla["contain"]
            result["containment_minutes"] = round(contain_minutes, 1)

        # 解决 SLA
        if inc.resolved_at:
            resolve_minutes = (inc.resolved_at - inc.detected_at).total_seconds() / 60
            result["resolution_sla_met"] = resolve_minutes <= sla["resolve"]
            result["resolution_minutes"] = round(resolve_minutes, 1)

        return result

    def _get(self, incident_id: str) -> SecurityIncident:
        if incident_id not in self._incidents:
            raise KeyError(f"Incident not found: {incident_id}")
        return self._incidents[incident_id]
