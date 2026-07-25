"""P2-12: 审计日志留存策略引擎.

功能:
- 留存策略配置 (保留天数/归档天数/WORM 不可变)
- 策略评估 (哪些记录该归档/删除)
- 策略执行 (清理过期记录)
- 合规状态报告

设计原则:
- WORM (Write Once Read Many) 语义: 留存期内记录不可删除/修改
- 归档与删除分离: 先归档再清理
- 合规审计: 可查询当前合规状态
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RetentionPolicy:
    """留存策略配置."""

    retention_days: int = 365  # 总保留天数
    archive_after_days: int = 90  # 多少天后归档
    immutable: bool = True  # WORM 语义: 留存期内不可删除
    max_records: int = 1_000_000  # 最大记录数
    compliance_standard: str = "SOC2"  # 合规标准

    def to_dict(self) -> dict[str, Any]:
        return {
            "retention_days": self.retention_days,
            "archive_after_days": self.archive_after_days,
            "immutable": self.immutable,
            "max_records": self.max_records,
            "compliance_standard": self.compliance_standard,
        }


@dataclass
class RetentionDecision:
    """留存评估决策."""

    total_records: int = 0
    active_records: int = 0  # 活跃 (未归档)
    archive_eligible: int = 0  # 可归档
    delete_eligible: int = 0  # 可删除 (超过保留期)
    protected_by_worm: int = 0  # WORM 保护中
    evaluated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "active_records": self.active_records,
            "archive_eligible": self.archive_eligible,
            "delete_eligible": self.delete_eligible,
            "protected_by_worm": self.protected_by_worm,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class EnforcementResult:
    """策略执行结果."""

    archived: int = 0
    deleted: int = 0
    protected: int = 0  # WORM 保护未删除
    errors: int = 0
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "archived": self.archived,
            "deleted": self.deleted,
            "protected": self.protected,
            "errors": self.errors,
            "executed_at": self.executed_at,
        }


@dataclass
class ComplianceStatus:
    """合规状态."""

    is_compliant: bool = True
    policy: dict[str, Any] | None = None
    total_records: int = 0
    oldest_record_age_days: int = 0
    records_beyond_retention: int = 0
    worm_enabled: bool = True
    last_enforcement: str | None = None
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_compliant": self.is_compliant,
            "policy": self.policy,
            "total_records": self.total_records,
            "oldest_record_age_days": self.oldest_record_age_days,
            "records_beyond_retention": self.records_beyond_retention,
            "worm_enabled": self.worm_enabled,
            "last_enforcement": self.last_enforcement,
            "issues": self.issues,
        }


class RetentionEngine:
    """审计日志留存策略引擎.

    管理审计记录的生命周期:
    活跃 → 归档 → 删除 (超过保留期)
    WORM 模式下留存期内记录不可删除。
    """

    def __init__(self, policy: RetentionPolicy | None = None):
        self._policy = policy or RetentionPolicy()
        self._archived_ids: set[str] = set()
        self._last_enforcement: str | None = None

    @property
    def policy(self) -> RetentionPolicy:
        return self._policy

    def configure(self, policy: RetentionPolicy) -> None:
        """更新留存策略."""
        self._policy = policy
        logger.info(
            "Retention policy updated: retention=%dd archive=%dd immutable=%s",
            policy.retention_days, policy.archive_after_days, policy.immutable,
        )

    def evaluate(self, records: list[dict[str, Any]]) -> RetentionDecision:
        """评估记录留存状态.

        Args:
            records: 审计记录列表 (含 created_at 字段)

        Returns:
            RetentionDecision 评估结果
        """
        now = datetime.now(UTC)
        decision = RetentionDecision(total_records=len(records))

        for record in records:
            created_at = self._parse_timestamp(record.get("created_at"))
            if created_at is None:
                continue

            age_days = (now - created_at).days
            record_id = record.get("id", "")

            if age_days > self._policy.retention_days:
                decision.delete_eligible += 1
            elif age_days > self._policy.archive_after_days:
                if record_id in self._archived_ids:
                    decision.archive_eligible += 1  # 已归档
                else:
                    decision.archive_eligible += 1
            else:
                decision.active_records += 1
                if self._policy.immutable:
                    decision.protected_by_worm += 1

        return decision

    def enforce(self, records: list[dict[str, Any]]) -> EnforcementResult:
        """执行留存策略.

        对记录列表执行归档和删除操作。
        WORM 模式下, 留存期内记录受保护不可删除。

        Args:
            records: 审计记录列表

        Returns:
            EnforcementResult 执行结果
        """
        now = datetime.now(UTC)
        result = EnforcementResult()

        for record in records:
            created_at = self._parse_timestamp(record.get("created_at"))
            if created_at is None:
                result.errors += 1
                continue

            age_days = (now - created_at).days
            record_id = record.get("id", "")

            if age_days > self._policy.retention_days:
                # 超过保留期 → 可删除
                if self._policy.immutable and age_days <= self._policy.retention_days:
                    result.protected += 1
                else:
                    result.deleted += 1
            elif age_days > self._policy.archive_after_days:
                # 超过归档期 → 归档
                if record_id not in self._archived_ids:
                    self._archived_ids.add(record_id)
                result.archived += 1
            else:
                # 留存期内 → WORM 保护
                if self._policy.immutable:
                    result.protected += 1

        self._last_enforcement = now.isoformat()
        logger.info(
            "Retention enforced: archived=%d deleted=%d protected=%d",
            result.archived, result.deleted, result.protected,
        )
        return result

    def get_compliance_status(self, records: list[dict[str, Any]]) -> ComplianceStatus:
        """获取合规状态.

        Args:
            records: 当前所有审计记录

        Returns:
            ComplianceStatus 合规状态
        """
        now = datetime.now(UTC)
        status = ComplianceStatus(
            policy=self._policy.to_dict(),
            total_records=len(records),
            worm_enabled=self._policy.immutable,
            last_enforcement=self._last_enforcement,
        )

        issues: list[str] = []

        # 检查最老记录
        oldest_age = 0
        beyond_retention = 0
        for record in records:
            created_at = self._parse_timestamp(record.get("created_at"))
            if created_at is None:
                continue
            age_days = (now - created_at).days
            oldest_age = max(oldest_age, age_days)
            if age_days > self._policy.retention_days:
                beyond_retention += 1

        status.oldest_record_age_days = oldest_age
        status.records_beyond_retention = beyond_retention

        # 合规检查
        if beyond_retention > 0:
            issues.append(f"{beyond_retention} 条记录超过保留期 ({self._policy.retention_days} 天)")
            status.is_compliant = False

        if not self._policy.immutable:
            issues.append("WORM 不可变模式未启用")

        if len(records) > self._policy.max_records:
            issues.append(f"记录数 ({len(records)}) 超过上限 ({self._policy.max_records})")
            status.is_compliant = False

        status.issues = issues
        return status

    @property
    def archived_count(self) -> int:
        """已归档记录数."""
        return len(self._archived_ids)

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """解析时间戳."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                return None
        return None
