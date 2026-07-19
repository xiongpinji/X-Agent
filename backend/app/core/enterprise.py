"""
Enterprise-grade functionality module for X-Agent.

Provides multi-tenancy, SSO, team collaboration, RBAC, and audit logging.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class TenantPlan(str, Enum):
    """Tenant subscription plans."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class RoleType(str, Enum):
    """Role-based access control types."""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    TEAM_LEAD = "team_lead"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    GUEST = "guest"


class PermissionType(str, Enum):
    """Fine-grained permissions."""
    # Tenant management
    TENANT_READ = "tenant:read"
    TENANT_WRITE = "tenant:write"
    TENANT_DELETE = "tenant:delete"
    TENANT_BILLING = "tenant:billing"

    # Team management
    TEAM_READ = "team:read"
    TEAM_WRITE = "team:write"
    TEAM_DELETE = "team:delete"

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # Agent/Workflow execution
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_EXECUTE = "agent:execute"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    WORKFLOW_EXECUTE = "workflow:execute"

    # Audit and compliance
    AUDIT_READ = "audit:read"
    COMPLIANCE_READ = "compliance:read"

    # API and integrations
    API_KEY_MANAGE = "api_key:manage"
    INTEGRATION_MANAGE = "integration:manage"


class AuditEventType(str, Enum):
    """Types of audit events."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"

    TEAM_CREATED = "team_created"
    TEAM_DELETED = "team_deleted"
    TEAM_MEMBER_ADDED = "team_member_added"
    TEAM_MEMBER_REMOVED = "team_member_removed"

    AGENT_EXECUTED = "agent_executed"
    WORKFLOW_EXECUTED = "workflow_executed"
    WORKFLOW_APPROVED = "workflow_approved"
    WORKFLOW_REJECTED = "workflow_rejected"

    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"

    POLICY_CHANGED = "policy_changed"
    SECURITY_EVENT = "security_event"


# ============================================================================
# DATA MODELS
# ============================================================================

class EnterpriseUser(BaseModel):
    """Enterprise user with extended attributes."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    display_name: str
    tenant_id: str
    role: RoleType = RoleType.DEVELOPER
    permissions: list[PermissionType] = Field(default_factory=list)

    # SSO integration
    sso_provider: Optional[str] = None  # "okta", "azure_ad", "google", etc.
    sso_id: Optional[str] = None

    # Account status
    is_active: bool = True
    is_verified: bool = False

    # Metadata
    department: Optional[str] = None
    manager_id: Optional[str] = None
    phone: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: Optional[datetime] = None


class Team(BaseModel):
    """Team within a tenant."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    name: str
    description: Optional[str] = None

    # Team members
    owner_id: str
    member_ids: list[str] = Field(default_factory=list)

    # Permissions
    default_role: RoleType = RoleType.DEVELOPER

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EnterpriseTenant(BaseModel):
    """Enterprise tenant with full configuration."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    plan: TenantPlan = TenantPlan.FREE

    # Organization info
    organization_name: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None

    # Billing
    billing_email: Optional[str] = None
    billing_address: Optional[str] = None
    tax_id: Optional[str] = None

    # SSO configuration
    sso_enabled: bool = False
    sso_provider: Optional[str] = None
    sso_config: dict[str, Any] = Field(default_factory=dict)

    # Security policies
    require_mfa: bool = False
    password_policy: dict[str, Any] = Field(default_factory=dict)
    ip_whitelist: list[str] = Field(default_factory=list)

    # Feature flags
    features_enabled: dict[str, bool] = Field(default_factory=dict)

    # Limits
    max_users: int = 10
    max_teams: int = 5
    max_api_keys: int = 20

    # Status
    is_active: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class APIKey(BaseModel):
    """API key for programmatic access."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    user_id: str

    name: str
    key_hash: str  # Hashed for security

    # Permissions
    permissions: list[PermissionType] = Field(default_factory=list)

    # Rate limiting
    rate_limit: Optional[int] = None  # requests per minute

    # Expiration
    expires_at: Optional[datetime] = None

    # Status
    is_active: bool = True
    last_used: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditLog(BaseModel):
    """Audit log entry for compliance and security."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str

    event_type: AuditEventType
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None

    resource_type: str  # "user", "team", "agent", "workflow", etc.
    resource_id: str

    action: str  # "create", "update", "delete", "execute", etc.

    # Change tracking
    changes: dict[str, Any] = Field(default_factory=dict)

    # Context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Status
    status: str = "success"  # "success", "failure"
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccessPolicy(BaseModel):
    """Access control policy for a tenant."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str

    name: str
    description: Optional[str] = None

    # Policy rules
    rules: list[dict[str, Any]] = Field(default_factory=list)

    # Conditions
    conditions: dict[str, Any] = Field(default_factory=dict)

    # Status
    is_active: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ComplianceReport(BaseModel):
    """Compliance and audit report."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str

    report_type: str  # "soc2", "gdpr", "hipaa", "iso27001", etc.
    period_start: datetime
    period_end: datetime

    # Findings
    total_events: int = 0
    security_events: int = 0
    policy_violations: int = 0

    # Details
    summary: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ============================================================================
# STORES
# ============================================================================

class EnterpriseUserStore:
    """Store for enterprise users."""

    def __init__(self) -> None:
        self._records: dict[str, EnterpriseUser] = {}
        self._lock = RLock()

    def create(self, user: EnterpriseUser) -> EnterpriseUser:
        """Create a new user."""
        with self._lock:
            self._records[user.id] = user
            return user

    def get(self, user_id: str) -> Optional[EnterpriseUser]:
        """Get user by ID."""
        with self._lock:
            return self._records.get(user_id)

    def get_by_email(self, email: str) -> Optional[EnterpriseUser]:
        """Get user by email."""
        with self._lock:
            for user in self._records.values():
                if user.email == email:
                    return user
            return None

    def list_by_tenant(self, tenant_id: str) -> list[EnterpriseUser]:
        """List all users in a tenant."""
        with self._lock:
            return [u for u in self._records.values() if u.tenant_id == tenant_id]

    def update(self, user_id: str, updates: dict[str, Any]) -> Optional[EnterpriseUser]:
        """Update user."""
        with self._lock:
            user = self._records.get(user_id)
            if user:
                user_dict = user.model_dump()
                user_dict.update(updates)
                user_dict["updated_at"] = datetime.now(UTC)
                self._records[user_id] = EnterpriseUser(**user_dict)
                return self._records[user_id]
            return None

    def delete(self, user_id: str) -> bool:
        """Delete user."""
        with self._lock:
            if user_id in self._records:
                del self._records[user_id]
                return True
            return False


class TeamStore:
    """Store for teams."""

    def __init__(self) -> None:
        self._records: dict[str, Team] = {}
        self._lock = RLock()

    def create(self, team: Team) -> Team:
        """Create a new team."""
        with self._lock:
            self._records[team.id] = team
            return team

    def get(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        with self._lock:
            return self._records.get(team_id)

    def list_by_tenant(self, tenant_id: str) -> list[Team]:
        """List all teams in a tenant."""
        with self._lock:
            return [t for t in self._records.values() if t.tenant_id == tenant_id]

    def add_member(self, team_id: str, user_id: str) -> bool:
        """Add member to team."""
        with self._lock:
            team = self._records.get(team_id)
            if team and user_id not in team.member_ids:
                team.member_ids.append(user_id)
                team.updated_at = datetime.now(UTC)
                return True
            return False

    def remove_member(self, team_id: str, user_id: str) -> bool:
        """Remove member from team."""
        with self._lock:
            team = self._records.get(team_id)
            if team and user_id in team.member_ids:
                team.member_ids.remove(user_id)
                team.updated_at = datetime.now(UTC)
                return True
            return False


class EnterpriseTenantStore:
    """Store for enterprise tenants."""

    def __init__(self) -> None:
        self._records: dict[str, EnterpriseTenant] = {}
        self._lock = RLock()

    def create(self, tenant: EnterpriseTenant) -> EnterpriseTenant:
        """Create a new tenant."""
        with self._lock:
            self._records[tenant.id] = tenant
            return tenant

    def get(self, tenant_id: str) -> Optional[EnterpriseTenant]:
        """Get tenant by ID."""
        with self._lock:
            return self._records.get(tenant_id)

    def list_all(self) -> list[EnterpriseTenant]:
        """List all tenants."""
        with self._lock:
            return list(self._records.values())

    def update(self, tenant_id: str, updates: dict[str, Any]) -> Optional[EnterpriseTenant]:
        """Update tenant."""
        with self._lock:
            tenant = self._records.get(tenant_id)
            if tenant:
                tenant_dict = tenant.model_dump()
                tenant_dict.update(updates)
                tenant_dict["updated_at"] = datetime.now(UTC)
                self._records[tenant_id] = EnterpriseTenant(**tenant_dict)
                return self._records[tenant_id]
            return None


class APIKeyStore:
    """Store for API keys."""

    def __init__(self) -> None:
        self._records: dict[str, APIKey] = {}
        self._lock = RLock()

    def create(self, api_key: APIKey) -> APIKey:
        """Create a new API key."""
        with self._lock:
            self._records[api_key.id] = api_key
            return api_key

    def get(self, key_id: str) -> Optional[APIKey]:
        """Get API key by ID."""
        with self._lock:
            return self._records.get(key_id)

    def list_by_user(self, user_id: str) -> list[APIKey]:
        """List all API keys for a user."""
        with self._lock:
            return [k for k in self._records.values() if k.user_id == user_id]

    def revoke(self, key_id: str) -> bool:
        """Revoke an API key."""
        with self._lock:
            key = self._records.get(key_id)
            if key:
                key.is_active = False
                return True
            return False


class AuditLogStore:
    """Store for audit logs."""

    def __init__(self) -> None:
        self._records: list[AuditLog] = []
        self._lock = RLock()

    def log(self, event: AuditLog) -> AuditLog:
        """Log an audit event."""
        with self._lock:
            self._records.append(event)
            return event

    def get(self, log_id: str) -> Optional[AuditLog]:
        """Get audit log by ID."""
        with self._lock:
            for log in self._records:
                if log.id == log_id:
                    return log
            return None

    def list_by_tenant(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
    ) -> list[AuditLog]:
        """List audit logs for a tenant."""
        with self._lock:
            results = [l for l in self._records if l.tenant_id == tenant_id]

            if start_date:
                results = [l for l in results if l.created_at >= start_date]
            if end_date:
                results = [l for l in results if l.created_at <= end_date]
            if event_type:
                results = [l for l in results if l.event_type == event_type]

            return sorted(results, key=lambda x: x.created_at, reverse=True)


# ============================================================================
# SERVICES
# ============================================================================

class EnterpriseService:
    """Main enterprise service."""

    def __init__(self) -> None:
        self.users = EnterpriseUserStore()
        self.teams = TeamStore()
        self.tenants = EnterpriseTenantStore()
        self.api_keys = APIKeyStore()
        self.audit_logs = AuditLogStore()

    def check_permission(
        self,
        user: EnterpriseUser,
        permission: PermissionType,
    ) -> bool:
        """Check if user has permission."""
        # Super admin has all permissions
        if user.role == RoleType.SUPER_ADMIN:
            return True

        # Check explicit permissions
        return permission in user.permissions

    def check_resource_access(
        self,
        user: EnterpriseUser,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> bool:
        """Check if user can access a resource."""
        # Super admin can access everything
        if user.role == RoleType.SUPER_ADMIN:
            return True

        # Tenant admin can access tenant resources
        if user.role == RoleType.TENANT_ADMIN:
            # Would need to check if resource belongs to user's tenant
            return True

        # Other roles have limited access
        return False

    def log_event(
        self,
        tenant_id: str,
        event_type: AuditEventType,
        resource_type: str,
        resource_id: str,
        action: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        changes: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log an audit event."""
        event = AuditLog(
            tenant_id=tenant_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            changes=changes or {},
            ip_address=ip_address,
            status=status,
            error_message=error_message,
        )
        return self.audit_logs.log(event)

    def generate_compliance_report(
        self,
        tenant_id: str,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
    ) -> ComplianceReport:
        """Generate a compliance report."""
        logs = self.audit_logs.list_by_tenant(
            tenant_id,
            start_date=period_start,
            end_date=period_end,
        )

        security_events = sum(
            1 for log in logs
            if log.event_type == AuditEventType.SECURITY_EVENT
        )

        report = ComplianceReport(
            tenant_id=tenant_id,
            report_type=report_type,
            period_start=period_start,
            period_end=period_end,
            total_events=len(logs),
            security_events=security_events,
            summary=f"Compliance report for {report_type}",
        )

        return report
