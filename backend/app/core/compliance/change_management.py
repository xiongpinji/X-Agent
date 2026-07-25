"""SOC 2 变更管理制度 — 代码化变更审批与追踪。

CC8.1: 变更管理控制点 — 所有生产变更须经审批、测试、记录。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ChangeRisk(StrEnum):
    """变更风险等级。"""

    LOW = "low"  # 文档/配置微调
    MEDIUM = "medium"  # 功能变更、非核心模块
    HIGH = "high"  # 核心架构、安全相关、数据迁移
    CRITICAL = "critical"  # 生产数据库 schema、认证流程、密钥轮换


class ChangeStatus(StrEnum):
    """变更状态。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    CLOSED = "closed"


class ChangeType(StrEnum):
    """变更类型。"""

    CODE = "code"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    SECURITY = "security"
    DEPENDENCY = "dependency"


@dataclass
class ChangeApproval:
    """变更审批记录。"""

    approver: str
    role: str
    decision: str  # approved | rejected
    comment: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ChangeRequest:
    """变更请求 — SOC 2 变更管理的核心实体。"""

    change_id: str = field(default_factory=lambda: f"CR-{uuid4().hex[:8].upper()}")
    title: str = ""
    description: str = ""
    change_type: ChangeType = ChangeType.CODE
    risk_level: ChangeRisk = ChangeRisk.MEDIUM
    status: ChangeStatus = ChangeStatus.DRAFT
    requester: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # 审批要求
    required_approvals: int = 1
    approvals: list[ChangeApproval] = field(default_factory=list)

    # 测试证据
    test_evidence: dict[str, Any] = field(default_factory=dict)
    ci_pipeline_url: str = ""
    regression_passed: bool = False

    # 部署信息
    deployment_window: str = ""
    rollback_plan: str = ""
    deployed_at: datetime | None = None
    deployed_by: str = ""

    # 关联
    related_incidents: list[str] = field(default_factory=list)
    related_controls: list[str] = field(default_factory=list)  # SOC 2 控制点 ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "title": self.title,
            "description": self.description,
            "change_type": self.change_type.value,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "requester": self.requester,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "required_approvals": self.required_approvals,
            "approvals": [
                {"approver": a.approver, "role": a.role, "decision": a.decision,
                 "comment": a.comment, "timestamp": a.timestamp.isoformat()}
                for a in self.approvals
            ],
            "test_evidence": self.test_evidence,
            "ci_pipeline_url": self.ci_pipeline_url,
            "regression_passed": self.regression_passed,
            "deployment_window": self.deployment_window,
            "rollback_plan": self.rollback_plan,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployed_by": self.deployed_by,
            "related_incidents": self.related_incidents,
            "related_controls": self.related_controls,
        }


class ChangeManagementEngine:
    """变更管理引擎 — 执行 SOC 2 变更控制流程。

    流程: DRAFT → PENDING_REVIEW → APPROVED → IN_PROGRESS → DEPLOYED → CLOSED
    高风险变更需要额外审批和回滚计划。
    """

    # 风险等级对应的最低审批人数
    RISK_APPROVAL_REQUIREMENTS: dict[ChangeRisk, int] = {
        ChangeRisk.LOW: 1,
        ChangeRisk.MEDIUM: 1,
        ChangeRisk.HIGH: 2,
        ChangeRisk.CRITICAL: 2,
    }

    def __init__(self):
        self._changes: dict[str, ChangeRequest] = {}

    def create_change(
        self,
        title: str,
        description: str,
        change_type: ChangeType = ChangeType.CODE,
        risk_level: ChangeRisk = ChangeRisk.MEDIUM,
        requester: str = "system",
    ) -> ChangeRequest:
        """创建变更请求。"""
        cr = ChangeRequest(
            title=title,
            description=description,
            change_type=change_type,
            risk_level=risk_level,
            requester=requester,
            required_approvals=self.RISK_APPROVAL_REQUIREMENTS[risk_level],
        )
        # 高风险变更必须提供回滚计划
        if risk_level in (ChangeRisk.HIGH, ChangeRisk.CRITICAL):
            cr.rollback_plan = "REQUIRED - must be filled before approval"
        self._changes[cr.change_id] = cr
        logger.info("Change request created: %s (%s)", cr.change_id, title)
        return cr

    def submit_for_review(self, change_id: str) -> bool:
        """提交变更请求进入审批流程。"""
        cr = self._get(change_id)
        if cr.status != ChangeStatus.DRAFT:
            return False
        cr.status = ChangeStatus.PENDING_REVIEW
        cr.updated_at = datetime.now(UTC)
        return True

    def approve(
        self,
        change_id: str,
        approver: str,
        role: str = "reviewer",
        comment: str = "",
    ) -> bool:
        """审批变更请求。"""
        cr = self._get(change_id)
        if cr.status != ChangeStatus.PENDING_REVIEW:
            return False

        cr.approvals.append(ChangeApproval(
            approver=approver,
            role=role,
            decision="approved",
            comment=comment,
        ))
        cr.updated_at = datetime.now(UTC)

        # 检查是否达到审批要求
        approval_count = sum(1 for a in cr.approvals if a.decision == "approved")
        if approval_count >= cr.required_approvals:
            cr.status = ChangeStatus.APPROVED
            logger.info("Change %s approved (%d/%d)", change_id, approval_count, cr.required_approvals)
        return True

    def reject(
        self,
        change_id: str,
        approver: str,
        role: str = "reviewer",
        comment: str = "",
    ) -> bool:
        """拒绝变更请求。"""
        cr = self._get(change_id)
        if cr.status != ChangeStatus.PENDING_REVIEW:
            return False

        cr.approvals.append(ChangeApproval(
            approver=approver,
            role=role,
            decision="rejected",
            comment=comment,
        ))
        cr.status = ChangeStatus.REJECTED
        cr.updated_at = datetime.now(UTC)
        logger.info("Change %s rejected by %s", change_id, approver)
        return True

    def start_deployment(self, change_id: str) -> bool:
        """开始部署（需已审批 + 回归测试通过）。"""
        cr = self._get(change_id)
        if cr.status != ChangeStatus.APPROVED:
            return False
        if not cr.regression_passed:
            logger.warning("Change %s: regression tests not passed", change_id)
            return False
        cr.status = ChangeStatus.IN_PROGRESS
        cr.updated_at = datetime.now(UTC)
        return True

    def complete_deployment(self, change_id: str, deployed_by: str) -> bool:
        """完成部署。"""
        cr = self._get(change_id)
        if cr.status != ChangeStatus.IN_PROGRESS:
            return False
        cr.status = ChangeStatus.DEPLOYED
        cr.deployed_at = datetime.now(UTC)
        cr.deployed_by = deployed_by
        cr.updated_at = datetime.now(UTC)
        logger.info("Change %s deployed by %s", change_id, deployed_by)
        return True

    def rollback(self, change_id: str, reason: str) -> bool:
        """回滚变更。"""
        cr = self._get(change_id)
        if cr.status not in (ChangeStatus.DEPLOYED, ChangeStatus.IN_PROGRESS):
            return False
        cr.status = ChangeStatus.ROLLED_BACK
        cr.updated_at = datetime.now(UTC)
        cr.test_evidence["rollback_reason"] = reason
        logger.warning("Change %s rolled back: %s", change_id, reason)
        return True

    def close(self, change_id: str) -> bool:
        """关闭变更请求。"""
        cr = self._get(change_id)
        if cr.status not in (ChangeStatus.DEPLOYED, ChangeStatus.ROLLED_BACK, ChangeStatus.REJECTED):
            return False
        cr.status = ChangeStatus.CLOSED
        cr.updated_at = datetime.now(UTC)
        return True

    def get_change(self, change_id: str) -> ChangeRequest | None:
        return self._changes.get(change_id)

    def list_changes(
        self,
        status: ChangeStatus | None = None,
        risk_level: ChangeRisk | None = None,
    ) -> list[ChangeRequest]:
        """列出变更请求（可按状态/风险过滤）。"""
        results = list(self._changes.values())
        if status:
            results = [cr for cr in results if cr.status == status]
        if risk_level:
            results = [cr for cr in results if cr.risk_level == risk_level]
        return sorted(results, key=lambda cr: cr.created_at, reverse=True)

    def get_audit_trail(self, change_id: str) -> list[dict[str, Any]]:
        """获取变更的完整审计轨迹。"""
        cr = self._get(change_id)
        trail = [
            {
                "event": "created",
                "timestamp": cr.created_at.isoformat(),
                "actor": cr.requester,
            }
        ]
        for approval in cr.approvals:
            trail.append({
                "event": f"review_{approval.decision}",
                "timestamp": approval.timestamp.isoformat(),
                "actor": approval.approver,
                "comment": approval.comment,
            })
        if cr.deployed_at:
            trail.append({
                "event": "deployed",
                "timestamp": cr.deployed_at.isoformat(),
                "actor": cr.deployed_by,
            })
        return trail

    def _get(self, change_id: str) -> ChangeRequest:
        if change_id not in self._changes:
            raise KeyError(f"Change request not found: {change_id}")
        return self._changes[change_id]
