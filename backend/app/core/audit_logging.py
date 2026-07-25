"""
Enterprise Audit Logging and Visualization System

Provides:
- Complete operation audit trail
- Real-time log streaming
- Advanced log querying and filtering
- Compliance reporting
- Dashboard visualization
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEventType(StrEnum):
    """Audit event types."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_MFA = "auth.mfa"

    # User management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"

    # Resource access
    RESOURCE_READ = "resource.read"
    RESOURCE_CREATE = "resource.create"
    RESOURCE_UPDATE = "resource.update"
    RESOURCE_DELETE = "resource.delete"

    # Agent execution
    AGENT_START = "agent.start"
    AGENT_STOP = "agent.stop"
    AGENT_ERROR = "agent.error"
    AGENT_COMPLETE = "agent.complete"

    # Configuration
    CONFIG_CHANGE = "config.change"
    CONFIG_DELETE = "config.delete"

    # Security
    SECURITY_POLICY_CHANGE = "security.policy_change"
    SECURITY_ALERT = "security.alert"
    PERMISSION_DENIED = "permission.denied"

    # System
    SYSTEM_START = "system.start"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"


class AuditSeverity(StrEnum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventStatus(StrEnum):
    """Audit event status."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class AuditEvent(BaseModel):
    """Audit event model."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    status: AuditEventStatus = AuditEventStatus.SUCCESS

    # Actor information
    actor_id: str = Field(..., description="User/service performing action")
    actor_type: str = Field(default="user", description="Type of actor (user, service, system)")
    tenant_id: str = Field(..., description="Tenant ID")

    # Resource information
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None

    # Action details
    action: str = Field(..., description="Action performed")
    description: str | None = None
    changes: dict[str, Any] = Field(default_factory=dict, description="Changed fields")

    # Request information
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    # Result information
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None

    # Compliance
    compliance_relevant: bool = False
    compliance_tags: list[str] = Field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self) if hasattr(self, '__dataclass_fields__') else self.dict()
        # Convert enums to strings
        if isinstance(data.get('event_type'), Enum):
            data['event_type'] = data['event_type'].value
        if isinstance(data.get('severity'), Enum):
            data['severity'] = data['severity'].value
        if isinstance(data.get('status'), Enum):
            data['status'] = data['status'].value
        # Convert datetime to ISO string
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data


class AuditLogQuery(BaseModel):
    """Query parameters for audit logs."""

    # Time range
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Filtering
    event_types: list[AuditEventType] = Field(default_factory=list)
    severity_levels: list[AuditSeverity] = Field(default_factory=list)
    actor_ids: list[str] = Field(default_factory=list)
    resource_types: list[str] = Field(default_factory=list)
    resource_ids: list[str] = Field(default_factory=list)
    tenant_ids: list[str] = Field(default_factory=list)
    statuses: list[AuditEventStatus] = Field(default_factory=list)

    # Search
    search_text: str | None = None
    compliance_relevant_only: bool = False

    # Pagination
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: str = Field(default="timestamp", description="Field to sort by")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")


class AuditLogStore:
    """In-memory audit log store (production should use database)."""

    def __init__(self, max_events: int = 100000):
        self.events: list[AuditEvent] = []
        self.max_events = max_events
        self.event_index: dict[str, list[int]] = defaultdict(list)
        self.logger = logging.getLogger(f"{__name__}.AuditLogStore")

    def add_event(self, event: AuditEvent) -> None:
        """Add audit event.

        Args:
            event: Audit event to add
        """
        if len(self.events) >= self.max_events:
            # Remove oldest events
            removed = self.events.pop(0)
            self.logger.warning(f"Audit log store full, removing oldest event: {removed.event_id}")

        self.events.append(event)
        idx = len(self.events) - 1

        # Update indices
        self.event_index[event.event_type.value].append(idx)
        self.event_index[event.actor_id].append(idx)
        self.event_index[event.tenant_id].append(idx)

        self.logger.debug(f"Added audit event: {event.event_id} ({event.event_type.value})")

    def query(self, query: AuditLogQuery) -> tuple[list[AuditEvent], int]:
        """Query audit logs.

        Args:
            query: Query parameters

        Returns:
            Tuple of (events, total_count)
        """
        results = self.events

        # Filter by time range
        if query.start_time:
            results = [e for e in results if e.timestamp >= query.start_time]
        if query.end_time:
            results = [e for e in results if e.timestamp <= query.end_time]

        # Filter by event types
        if query.event_types:
            results = [e for e in results if e.event_type in query.event_types]

        # Filter by severity
        if query.severity_levels:
            results = [e for e in results if e.severity in query.severity_levels]

        # Filter by actor
        if query.actor_ids:
            results = [e for e in results if e.actor_id in query.actor_ids]

        # Filter by resource
        if query.resource_types:
            results = [e for e in results if e.resource_type in query.resource_types]
        if query.resource_ids:
            results = [e for e in results if e.resource_id in query.resource_ids]

        # Filter by tenant
        if query.tenant_ids:
            results = [e for e in results if e.tenant_id in query.tenant_ids]

        # Filter by status
        if query.statuses:
            results = [e for e in results if e.status in query.statuses]

        # Filter by compliance relevance
        if query.compliance_relevant_only:
            results = [e for e in results if e.compliance_relevant]

        # Text search
        if query.search_text:
            search_lower = query.search_text.lower()
            results = [
                e for e in results
                if search_lower in (e.description or "").lower()
                or search_lower in (e.action or "").lower()
                or search_lower in (e.error_message or "").lower()
            ]

        total_count = len(results)

        # Sort
        reverse = query.sort_order.lower() == "desc"
        if query.sort_by == "timestamp":
            results.sort(key=lambda e: e.timestamp, reverse=reverse)
        elif query.sort_by == "severity":
            severity_order = {s.value: i for i, s in enumerate(AuditSeverity)}
            results.sort(
                key=lambda e: severity_order.get(e.severity.value, 0),
                reverse=reverse
            )

        # Paginate
        start = query.offset
        end = start + query.limit
        results = results[start:end]

        return results, total_count

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Get audit event by ID.

        Args:
            event_id: Event ID

        Returns:
            AuditEvent or None
        """
        for event in self.events:
            if event.event_id == event_id:
                return event
        return None


class AuditAnalytics:
    """Audit log analytics."""

    def __init__(self, store: AuditLogStore):
        self.store = store
        self.logger = logging.getLogger(f"{__name__}.AuditAnalytics")

    def get_event_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get event statistics.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            Statistics dictionary
        """
        if start_time is None:
            start_time = datetime.now(UTC) - timedelta(days=7)
        if end_time is None:
            end_time = datetime.now(UTC)

        events = [
            e for e in self.store.events
            if start_time <= e.timestamp <= end_time
        ]

        stats = {
            'total_events': len(events),
            'by_event_type': defaultdict(int),
            'by_severity': defaultdict(int),
            'by_status': defaultdict(int),
            'by_actor': defaultdict(int),
            'by_tenant': defaultdict(int),
            'failed_events': 0,
            'critical_events': 0,
        }

        for event in events:
            stats['by_event_type'][event.event_type.value] += 1
            stats['by_severity'][event.severity.value] += 1
            stats['by_status'][event.status.value] += 1
            stats['by_actor'][event.actor_id] += 1
            stats['by_tenant'][event.tenant_id] += 1

            if event.status == AuditEventStatus.FAILURE:
                stats['failed_events'] += 1
            if event.severity == AuditSeverity.CRITICAL:
                stats['critical_events'] += 1

        return stats

    def get_user_activity(
        self,
        actor_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get user activity summary.

        Args:
            actor_id: Actor ID
            start_time: Start time
            end_time: End time

        Returns:
            Activity summary
        """
        if start_time is None:
            start_time = datetime.now(UTC) - timedelta(days=7)
        if end_time is None:
            end_time = datetime.now(UTC)

        events = [
            e for e in self.store.events
            if e.actor_id == actor_id and start_time <= e.timestamp <= end_time
        ]

        return {
            'actor_id': actor_id,
            'total_actions': len(events),
            'first_action': min((e.timestamp for e in events), default=None),
            'last_action': max((e.timestamp for e in events), default=None),
            'action_types': list({e.event_type.value for e in events}),
            'failed_actions': sum(1 for e in events if e.status == AuditEventStatus.FAILURE),
            'resources_accessed': list({e.resource_id for e in events if e.resource_id}),
        }

    def get_compliance_report(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Generate compliance report.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            Compliance report
        """
        if start_time is None:
            start_time = datetime.now(UTC) - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now(UTC)

        events = [
            e for e in self.store.events
            if e.compliance_relevant and start_time <= e.timestamp <= end_time
        ]

        report = {
            'report_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            },
            'total_compliance_events': len(events),
            'by_compliance_tag': defaultdict(int),
            'by_severity': defaultdict(int),
            'critical_findings': [],
            'failed_compliance_checks': [],
        }

        for event in events:
            for tag in event.compliance_tags:
                report['by_compliance_tag'][tag] += 1

            report['by_severity'][event.severity.value] += 1

            if event.severity == AuditSeverity.CRITICAL:
                report['critical_findings'].append({
                    'event_id': event.event_id,
                    'timestamp': event.timestamp.isoformat(),
                    'event_type': event.event_type.value,
                    'description': event.description,
                })

            if event.status == AuditEventStatus.FAILURE:
                report['failed_compliance_checks'].append({
                    'event_id': event.event_id,
                    'timestamp': event.timestamp.isoformat(),
                    'action': event.action,
                    'error': event.error_message,
                })

        return report

    def detect_anomalies(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Detect anomalies in audit logs.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            List of detected anomalies
        """
        if start_time is None:
            start_time = datetime.now(UTC) - timedelta(days=7)
        if end_time is None:
            end_time = datetime.now(UTC)

        events = [
            e for e in self.store.events
            if start_time <= e.timestamp <= end_time
        ]

        anomalies = []

        # Detect multiple failed login attempts
        failed_logins = defaultdict(int)
        for event in events:
            if event.event_type == AuditEventType.AUTH_FAILED:
                failed_logins[event.actor_id] += 1

        for actor_id, count in failed_logins.items():
            if count >= 5:
                anomalies.append({
                    'type': 'multiple_failed_logins',
                    'severity': 'high',
                    'actor_id': actor_id,
                    'count': count,
                    'description': f"User {actor_id} had {count} failed login attempts",
                })

        # Detect unusual access patterns
        access_by_hour = defaultdict(lambda: defaultdict(int))
        for event in events:
            if event.event_type in [AuditEventType.RESOURCE_READ, AuditEventType.RESOURCE_CREATE]:
                hour = event.timestamp.hour
                access_by_hour[event.actor_id][hour] += 1

        for actor_id, hours in access_by_hour.items():
            max_hour = max(hours.values()) if hours else 0
            if max_hour > 100:  # Threshold
                anomalies.append({
                    'type': 'high_access_volume',
                    'severity': 'medium',
                    'actor_id': actor_id,
                    'max_requests_per_hour': max_hour,
                    'description': f"User {actor_id} made {max_hour} requests in one hour",
                })

        return anomalies


# Global audit store
_audit_store = AuditLogStore()
_audit_analytics = AuditAnalytics(_audit_store)


def get_audit_store() -> AuditLogStore:
    """Get global audit store."""
    return _audit_store


def get_audit_analytics() -> AuditAnalytics:
    """Get global audit analytics."""
    return _audit_analytics


def log_audit_event(
    event_type: AuditEventType,
    actor_id: str,
    tenant_id: str,
    action: str,
    **kwargs
) -> AuditEvent:
    """Log audit event.

    Args:
        event_type: Event type
        actor_id: Actor ID
        tenant_id: Tenant ID
        action: Action description
        **kwargs: Additional event fields

    Returns:
        Created AuditEvent
    """
    event = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        tenant_id=tenant_id,
        action=action,
        **kwargs
    )

    _audit_store.add_event(event)
    return event
