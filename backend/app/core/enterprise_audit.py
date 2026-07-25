"""
企业级审计日志系统

功能:
- 完整的操作审计日志
- 实时日志流
- 日志查询和过滤
- 可视化仪表板
- 合规报告生成
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# 审计日志模型
# ============================================================================

class AuditEventType(StrEnum):
    """审计事件类型"""
    # 认证事件
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # 用户管理
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"

    # 资源操作
    RESOURCE_CREATED = "resource_created"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_DELETED = "resource_deleted"
    RESOURCE_ACCESSED = "resource_accessed"

    # 权限管理
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"

    # 系统事件
    CONFIG_CHANGED = "config_changed"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"

    # 安全事件
    SECURITY_ALERT = "security_alert"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    POLICY_VIOLATION = "policy_violation"
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"

    # API事件
    API_CALL = "api_call"
    API_ERROR = "api_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class AuditSeverity(StrEnum):
    """审计事件严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogEntry(BaseModel):
    """审计日志条目"""
    log_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    tenant_id: str
    user_id: str | None = None
    actor_type: str = "user"  # "user", "system", "service"
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    action: str
    status: str = "success"  # "success", "failure"
    status_code: int | None = None
    error_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    session_id: str | None = None
    changes: dict[str, tuple[Any, Any]] = Field(default_factory=dict)  # {field: (old_value, new_value)}
    tags: list[str] = Field(default_factory=list)
    hash: str | None = None  # 用于链式验证

    def compute_hash(self, previous_hash: str | None = None) -> str:
        """计算日志条目的哈希值（用于链式验证）"""
        data = {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "status": self.status,
            "previous_hash": previous_hash or "",
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class AuditLogFilter(BaseModel):
    """审计日志过滤条件"""
    tenant_id: str | None = None
    user_id: str | None = None
    event_type: AuditEventType | None = None
    severity: AuditSeverity | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    tags: list[str] | None = None
    search_text: str | None = None
    limit: int = 100
    offset: int = 0


# ============================================================================
# 审计日志存储
# ============================================================================

class AuditLogStore:
    """审计日志存储"""

    def __init__(self):
        self._logs: dict[str, AuditLogEntry] = {}
        self._tenant_logs: dict[str, list[str]] = {}  # tenant_id -> [log_id, ...]
        self._user_logs: dict[str, list[str]] = {}  # user_id -> [log_id, ...]
        self._resource_logs: dict[str, list[str]] = {}  # resource_id -> [log_id, ...]
        self._previous_hash: str | None = None

    def append_log(self, entry: AuditLogEntry) -> AuditLogEntry:
        """追加审计日志"""
        # 计算哈希值用于链式验证
        entry.hash = entry.compute_hash(self._previous_hash)
        self._previous_hash = entry.hash

        self._logs[entry.log_id] = entry

        # 索引
        if entry.tenant_id not in self._tenant_logs:
            self._tenant_logs[entry.tenant_id] = []
        self._tenant_logs[entry.tenant_id].append(entry.log_id)

        if entry.user_id:
            if entry.user_id not in self._user_logs:
                self._user_logs[entry.user_id] = []
            self._user_logs[entry.user_id].append(entry.log_id)

        if entry.resource_id:
            if entry.resource_id not in self._resource_logs:
                self._resource_logs[entry.resource_id] = []
            self._resource_logs[entry.resource_id].append(entry.log_id)

        logger.info(f"Appended audit log: {entry.log_id} ({entry.event_type.value})")
        return entry

    def query_logs(self, filter: AuditLogFilter) -> tuple[list[AuditLogEntry], int]:
        """查询审计日志"""
        results = []

        for log_id in self._tenant_logs.get(filter.tenant_id or "", []):
            entry = self._logs.get(log_id)
            if not entry:
                continue

            # 应用过滤条件
            if filter.user_id and entry.user_id != filter.user_id:
                continue
            if filter.event_type and entry.event_type != filter.event_type:
                continue
            if filter.severity and entry.severity != filter.severity:
                continue
            if filter.resource_type and entry.resource_type != filter.resource_type:
                continue
            if filter.resource_id and entry.resource_id != filter.resource_id:
                continue
            if filter.status and entry.status != filter.status:
                continue
            if filter.start_time and entry.timestamp < filter.start_time:
                continue
            if filter.end_time and entry.timestamp > filter.end_time:
                continue
            if filter.tags and not any(tag in entry.tags for tag in filter.tags):
                continue
            if filter.search_text and filter.search_text.lower() not in entry.action.lower():
                continue

            results.append(entry)

        # 排序（最新的在前）
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # 分页
        total = len(results)
        results = results[filter.offset:filter.offset + filter.limit]

        return results, total

    def get_log(self, log_id: str) -> AuditLogEntry | None:
        """获取单条日志"""
        return self._logs.get(log_id)

    def verify_log_chain(self, start_log_id: str | None = None) -> bool:
        """验证日志链的完整性"""
        log_ids = sorted(
            self._logs.keys(),
            key=lambda x: self._logs[x].timestamp
        )

        if start_log_id:
            try:
                start_idx = log_ids.index(start_log_id)
                log_ids = log_ids[start_idx:]
            except ValueError:
                return False

        previous_hash = None
        for log_id in log_ids:
            entry = self._logs[log_id]
            expected_hash = entry.compute_hash(previous_hash)
            if entry.hash != expected_hash:
                logger.error(f"Log chain verification failed at {log_id}")
                return False
            previous_hash = entry.hash

        logger.info("Log chain verification passed")
        return True

    def get_user_activity_summary(self, user_id: str, days: int = 7) -> dict[str, Any]:
        """获取用户活动摘要"""
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        logs = [
            self._logs[log_id] for log_id in self._user_logs.get(user_id, [])
            if self._logs[log_id].timestamp >= cutoff_time
        ]

        event_counts = {}
        for log in logs:
            event_type = log.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "user_id": user_id,
            "period_days": days,
            "total_events": len(logs),
            "event_counts": event_counts,
            "first_event": min((log.timestamp for log in logs), default=None),
            "last_event": max((log.timestamp for log in logs), default=None),
        }

    def get_resource_audit_trail(self, resource_id: str) -> list[AuditLogEntry]:
        """获取资源的完整审计跟踪"""
        log_ids = self._resource_logs.get(resource_id, [])
        logs = [self._logs[log_id] for log_id in log_ids]
        logs.sort(key=lambda x: x.timestamp)
        return logs


# ============================================================================
# 审计日志分析
# ============================================================================

class AuditAnalyzer:
    """审计日志分析器"""

    def __init__(self, store: AuditLogStore):
        self.store = store

    def detect_suspicious_activity(self, tenant_id: str, threshold: int = 5) -> list[dict[str, Any]]:
        """检测可疑活动"""
        suspicious_activities = []

        # 检测登录失败
        filter = AuditLogFilter(
            tenant_id=tenant_id,
            event_type=AuditEventType.LOGIN_FAILED,
            start_time=datetime.now(UTC) - timedelta(hours=1),
        )
        failed_logins, _ = self.store.query_logs(filter)

        # 按用户分组
        user_failures = {}
        for log in failed_logins:
            if log.user_id:
                user_failures[log.user_id] = user_failures.get(log.user_id, 0) + 1

        for user_id, count in user_failures.items():
            if count >= threshold:
                suspicious_activities.append({
                    "type": "brute_force_attempt",
                    "user_id": user_id,
                    "count": count,
                    "severity": "critical" if count >= threshold * 2 else "warning",
                })

        # 检测异常访问模式
        filter = AuditLogFilter(
            tenant_id=tenant_id,
            event_type=AuditEventType.RESOURCE_ACCESSED,
            start_time=datetime.now(UTC) - timedelta(hours=1),
        )
        accesses, _ = self.store.query_logs(filter)

        # 按用户和资源分组
        access_patterns = {}
        for log in accesses:
            key = (log.user_id, log.resource_type)
            access_patterns[key] = access_patterns.get(key, 0) + 1

        # 检测异常高频访问
        for (user_id, resource_type), count in access_patterns.items():
            if count > 100:  # 阈值
                suspicious_activities.append({
                    "type": "unusual_access_pattern",
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "count": count,
                    "severity": "warning",
                })

        return suspicious_activities

    def generate_compliance_report(self, tenant_id: str, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """生成合规报告"""
        filter = AuditLogFilter(
            tenant_id=tenant_id,
            start_time=start_date,
            end_time=end_date,
        )
        logs, total = self.store.query_logs(filter)

        # 统计各类事件
        event_stats = {}
        severity_stats = {}
        status_stats = {}

        for log in logs:
            event_type = log.event_type.value
            event_stats[event_type] = event_stats.get(event_type, 0) + 1

            severity = log.severity.value
            severity_stats[severity] = severity_stats.get(severity, 0) + 1

            status = log.status
            status_stats[status] = status_stats.get(status, 0) + 1

        # 检测安全事件
        security_events = [log for log in logs if log.severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]]

        return {
            "report_id": f"report_{uuid4().hex}",
            "tenant_id": tenant_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_events": total,
                "event_types": event_stats,
                "severity_distribution": severity_stats,
                "status_distribution": status_stats,
            },
            "security": {
                "critical_events": len([e for e in logs if e.severity == AuditSeverity.CRITICAL]),
                "error_events": len([e for e in logs if e.severity == AuditSeverity.ERROR]),
                "security_events": len(security_events),
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def get_user_access_report(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        """生成用户访问报告"""
        filter = AuditLogFilter(
            tenant_id=tenant_id,
            user_id=user_id,
        )
        logs, total = self.store.query_logs(filter)

        # 统计访问的资源
        resources_accessed = {}
        for log in logs:
            if log.resource_type and log.resource_id:
                key = f"{log.resource_type}:{log.resource_id}"
                resources_accessed[key] = resources_accessed.get(key, 0) + 1

        # 统计操作
        operations = {}
        for log in logs:
            operations[log.action] = operations.get(log.action, 0) + 1

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "total_events": total,
            "resources_accessed": resources_accessed,
            "operations": operations,
            "first_activity": min((log.timestamp for log in logs), default=None),
            "last_activity": max((log.timestamp for log in logs), default=None),
        }


# ============================================================================
# 审计日志仪表板数据
# ============================================================================

class DashboardMetrics(BaseModel):
    """仪表板指标"""
    total_events: int
    events_today: int
    events_this_week: int
    critical_events: int
    error_events: int
    warning_events: int
    success_rate: float
    top_event_types: dict[str, int]
    top_users: dict[str, int]
    top_resources: dict[str, int]
    suspicious_activities: list[dict[str, Any]]
    recent_events: list[AuditLogEntry]


class DashboardDataProvider:
    """仪表板数据提供者"""

    def __init__(self, store: AuditLogStore, analyzer: AuditAnalyzer):
        self.store = store
        self.analyzer = analyzer

    def get_dashboard_metrics(self, tenant_id: str) -> DashboardMetrics:
        """获取仪表板指标"""
        now = datetime.now(UTC)

        # 获取各时间段的日志
        filter_all = AuditLogFilter(tenant_id=tenant_id)
        all_logs, total_all = self.store.query_logs(filter_all)

        filter_today = AuditLogFilter(
            tenant_id=tenant_id,
            start_time=now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        _logs_today, total_today = self.store.query_logs(filter_today)

        filter_week = AuditLogFilter(
            tenant_id=tenant_id,
            start_time=now - timedelta(days=7),
        )
        _logs_week, total_week = self.store.query_logs(filter_week)

        # 统计事件类型
        event_counts = {}
        user_counts = {}
        resource_counts = {}
        severity_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        status_counts = {"success": 0, "failure": 0}

        for log in all_logs:
            event_counts[log.event_type.value] = event_counts.get(log.event_type.value, 0) + 1
            if log.user_id:
                user_counts[log.user_id] = user_counts.get(log.user_id, 0) + 1
            if log.resource_id:
                resource_counts[log.resource_id] = resource_counts.get(log.resource_id, 0) + 1
            severity_counts[log.severity.value] += 1
            status_counts[log.status] += 1

        # 计算成功率
        total_events = status_counts["success"] + status_counts["failure"]
        success_rate = (status_counts["success"] / total_events * 100) if total_events > 0 else 0

        # 获取可疑活动
        suspicious = self.analyzer.detect_suspicious_activity(tenant_id)

        # 获取最近事件
        filter_recent = AuditLogFilter(tenant_id=tenant_id, limit=10)
        recent_logs, _ = self.store.query_logs(filter_recent)

        return DashboardMetrics(
            total_events=total_all,
            events_today=total_today,
            events_this_week=total_week,
            critical_events=severity_counts["critical"],
            error_events=severity_counts["error"],
            warning_events=severity_counts["warning"],
            success_rate=success_rate,
            top_event_types=dict(sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            top_users=dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            top_resources=dict(sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            suspicious_activities=suspicious,
            recent_events=recent_logs,
        )
