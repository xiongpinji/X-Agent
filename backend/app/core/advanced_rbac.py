"""Advanced Role-Based Access Control (RBAC) with Attribute-Based Access Control (ABAC).

Implements:
- Attribute-Based Access Control (ABAC)
- Dynamic permission evaluation
- Permission inheritance and delegation
- Audit logging
- Permission analytics
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PermissionAction(StrEnum):
    """Standard permission actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    DELEGATE = "delegate"
    AUDIT = "audit"


class ResourceType(StrEnum):
    """Resource types in the system."""
    WORKFLOW = "workflow"
    AGENT = "agent"
    TOOL = "tool"
    DATA = "data"
    USER = "user"
    ROLE = "role"
    POLICY = "policy"
    AUDIT_LOG = "audit_log"
    BACKUP = "backup"
    REPORT = "report"


class DataClassification(StrEnum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class Attribute(BaseModel):
    """Attribute for ABAC evaluation."""
    name: str
    value: Any
    operator: str = "equals"  # equals, contains, greater_than, less_than, in, regex

    def evaluate(self, actual_value: Any) -> bool:
        """Evaluate attribute against actual value."""
        if self.operator == "equals":
            return actual_value == self.value
        elif self.operator == "contains":
            return self.value in actual_value if isinstance(actual_value, (list, str)) else False
        elif self.operator == "greater_than":
            return actual_value > self.value
        elif self.operator == "less_than":
            return actual_value < self.value
        elif self.operator == "in":
            return actual_value in self.value if isinstance(self.value, (list, set)) else False
        elif self.operator == "regex":
            import re
            return bool(re.match(self.value, str(actual_value)))
        return False


class Permission(BaseModel):
    """Fine-grained permission definition."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    resource_type: ResourceType
    action: PermissionAction
    attributes: list[Attribute] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)  # time-based, location-based, etc.
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        """Check if permission has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def matches(self, resource_type: ResourceType, action: PermissionAction,
                resource_attributes: dict[str, Any]) -> bool:
        """Check if permission matches the requested action."""
        if self.is_expired():
            return False

        if self.resource_type != resource_type or self.action != action:
            return False

        # Evaluate all attributes
        for attr in self.attributes:
            if attr.name not in resource_attributes:
                return False
            if not attr.evaluate(resource_attributes[attr.name]):
                return False

        return True


class Role(BaseModel):
    """Role with permissions and inheritance."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    permissions: list[Permission] = Field(default_factory=list)
    parent_roles: list[str] = Field(default_factory=list)  # Role IDs for inheritance
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoleAssignment(BaseModel):
    """Assignment of role to user with optional delegation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    role_id: str
    assigned_by: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    delegated_to: list[str] = Field(default_factory=list)  # User IDs who can use this role
    scope: dict[str, Any] = Field(default_factory=dict)  # Scope constraints (e.g., project_id)

    def is_active(self) -> bool:
        """Check if assignment is still active."""
        if self.expires_at is None:
            return True
        return datetime.now(UTC) <= self.expires_at


class AuditLogEntry(BaseModel):
    """Audit log for permission-related actions."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: str
    action: str
    resource_type: ResourceType
    resource_id: str
    result: str  # "allowed", "denied", "error"
    reason: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None


class PermissionAnalytics(BaseModel):
    """Analytics for permission usage."""
    total_checks: int = 0
    allowed_count: int = 0
    denied_count: int = 0
    error_count: int = 0
    most_used_permissions: dict[str, int] = Field(default_factory=dict)
    most_denied_permissions: dict[str, int] = Field(default_factory=dict)
    user_permission_distribution: dict[str, int] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AdvancedRBACEngine:
    """Advanced RBAC engine with ABAC support."""

    def __init__(self):
        self.roles: dict[str, Role] = {}
        self.role_assignments: dict[str, list[RoleAssignment]] = {}
        self.audit_logs: list[AuditLogEntry] = []
        self.analytics = PermissionAnalytics()

    def create_role(self, name: str, description: str = "",
                   permissions: list[Permission] | None = None,
                   parent_roles: list[str] | None = None) -> Role:
        """Create a new role."""
        role = Role(
            name=name,
            description=description,
            permissions=permissions or [],
            parent_roles=parent_roles or []
        )
        self.roles[role.id] = role
        return role

    def assign_role(self, user_id: str, role_id: str, assigned_by: str,
                   expires_at: datetime | None = None,
                   scope: dict[str, Any] | None = None) -> RoleAssignment:
        """Assign role to user."""
        if role_id not in self.roles:
            raise ValueError(f"Role {role_id} not found")

        assignment = RoleAssignment(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            expires_at=expires_at,
            scope=scope or {}
        )

        if user_id not in self.role_assignments:
            self.role_assignments[user_id] = []

        self.role_assignments[user_id].append(assignment)
        return assignment

    def delegate_role(self, assignment_id: str, delegate_to_user_id: str) -> None:
        """Delegate role to another user."""
        for assignments in self.role_assignments.values():
            for assignment in assignments:
                if assignment.id == assignment_id:
                    if delegate_to_user_id not in assignment.delegated_to:
                        assignment.delegated_to.append(delegate_to_user_id)
                    return
        raise ValueError(f"Assignment {assignment_id} not found")

    def get_user_permissions(self, user_id: str) -> list[Permission]:
        """Get all permissions for a user (including inherited)."""
        permissions = []

        if user_id not in self.role_assignments:
            return permissions

        visited_roles = set()
        max_depth = 100  # Prevent infinite recursion

        def collect_permissions(role_id: str, depth: int = 0):
            if role_id in visited_roles or depth > max_depth:
                return
            visited_roles.add(role_id)

            if role_id not in self.roles:
                return

            role = self.roles[role_id]
            permissions.extend(role.permissions)

            # Collect from parent roles
            for parent_id in role.parent_roles:
                collect_permissions(parent_id, depth + 1)

        for assignment in self.role_assignments[user_id]:
            if assignment.is_active():
                collect_permissions(assignment.role_id)

        return permissions

    def check_permission(self, user_id: str, resource_type: ResourceType,
                        action: PermissionAction, resource_attributes: dict[str, Any],
                        ip_address: str | None = None,
                        user_agent: str | None = None) -> tuple[bool, str]:
        """Check if user has permission for action."""
        self.analytics.total_checks += 1

        permissions = self.get_user_permissions(user_id)

        for permission in permissions:
            if permission.matches(resource_type, action, resource_attributes):
                self.analytics.allowed_count += 1
                self._log_audit(user_id, action.value, resource_type,
                              resource_attributes.get("id", "unknown"),
                              "allowed", "", resource_attributes, ip_address, user_agent)
                return True, "Permission granted"

        self.analytics.denied_count += 1
        reason = f"No permission for {action.value} on {resource_type.value}"
        self._log_audit(user_id, action.value, resource_type,
                       resource_attributes.get("id", "unknown"),
                       "denied", reason, resource_attributes, ip_address, user_agent)
        return False, reason

    def _log_audit(self, user_id: str, action: str, resource_type: ResourceType,
                  resource_id: str, result: str, reason: str,
                  attributes: dict[str, Any], ip_address: str | None,
                  user_agent: str | None) -> None:
        """Log audit entry."""
        entry = AuditLogEntry(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            reason=reason,
            attributes=attributes,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.audit_logs.append(entry)

    def get_audit_logs(self, user_id: str | None = None,
                      days: int = 30) -> list[AuditLogEntry]:
        """Get audit logs."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        logs = [log for log in self.audit_logs if log.timestamp >= cutoff]

        if user_id:
            logs = [log for log in logs if log.user_id == user_id]

        return logs

    def get_analytics(self) -> PermissionAnalytics:
        """Get permission analytics."""
        self.analytics.last_updated = datetime.now(UTC)
        return self.analytics

    def revoke_role(self, user_id: str, role_id: str) -> None:
        """Revoke role from user."""
        if user_id in self.role_assignments:
            self.role_assignments[user_id] = [
                a for a in self.role_assignments[user_id] if a.role_id != role_id
            ]

    def add_permission_to_role(self, role_id: str, permission: Permission) -> None:
        """Add permission to role."""
        if role_id not in self.roles:
            raise ValueError(f"Role {role_id} not found")
        self.roles[role_id].permissions.append(permission)
        self.roles[role_id].updated_at = datetime.now(UTC)
