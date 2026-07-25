"""Enterprise Features API - Advanced RBAC, Data Governance, HA, Backup, Compliance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.advanced_rbac import (
    PermissionAction,
    ResourceType,
)
from backend.app.core.backup_recovery import BackupStorageType, BackupType
from backend.app.core.compliance_reporting import ComplianceFramework
from backend.app.core.data_governance import DataClassification
from backend.app.core.enterprise_features import EnterpriseFeatures
from backend.app.core.high_availability import (
    FailoverStrategy,
    HealthCheckType,
    LoadBalancingAlgorithm,
    RegionName,
)

# Request/Response Models

class PermissionCheckRequest(BaseModel):
    """Permission check request."""
    user_id: str
    resource_type: str
    action: str
    resource_attributes: dict[str, Any]
    ip_address: str | None = None


class PermissionCheckResponse(BaseModel):
    """Permission check response."""
    allowed: bool
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoleAssignmentRequest(BaseModel):
    """Role assignment request."""
    user_id: str
    role_id: str
    expires_at: datetime | None = None
    scope: dict[str, Any] | None = None


class DataRegistrationRequest(BaseModel):
    """Data registration request."""
    name: str
    classification: str
    owner_id: str
    retention_days: int = 365
    compliance_frameworks: list[str] | None = None


class BackupScheduleRequest(BaseModel):
    """Backup schedule request."""
    name: str
    source_id: str
    backup_type: str
    frequency_hours: int
    retention_days: int
    storage_type: str
    storage_location: str


class NodeRegistrationRequest(BaseModel):
    """Node registration request."""
    name: str
    region: str
    endpoint: str
    port: int = 8000
    weight: int = 1


class HealthCheckRequest(BaseModel):
    """Health check request."""
    node_id: str
    check_type: str
    endpoint: str = "/health"
    interval_seconds: int = 30


class LoadBalancerRequest(BaseModel):
    """Load balancer request."""
    name: str
    algorithm: str
    strategy: str
    node_ids: list[str]


class ComplianceReportRequest(BaseModel):
    """Compliance report request."""
    organization_id: str
    framework: str
    period_days: int = 90


class EnterpriseAPIClient:
    """Enterprise Features API Client."""

    def __init__(self):
        self.ef = EnterpriseFeatures()

    # RBAC Endpoints

    def check_permission(self, request: PermissionCheckRequest) -> PermissionCheckResponse:
        """Check if user has permission."""
        try:
            resource_type = ResourceType(request.resource_type)
            action = PermissionAction(request.action)

            allowed, reason = self.ef.rbac.check_permission(
                user_id=request.user_id,
                resource_type=resource_type,
                action=action,
                resource_attributes=request.resource_attributes,
                ip_address=request.ip_address
            )

            return PermissionCheckResponse(allowed=allowed, reason=reason)
        except Exception as e:
            return PermissionCheckResponse(allowed=False, reason=str(e))

    def assign_role(self, request: RoleAssignmentRequest) -> dict[str, Any]:
        """Assign role to user."""
        try:
            assignment = self.ef.rbac.assign_role(
                user_id=request.user_id,
                role_id=request.role_id,
                assigned_by="system",
                expires_at=request.expires_at,
                scope=request.scope
            )
            return {
                "success": True,
                "assignment_id": assignment.id,
                "user_id": assignment.user_id,
                "role_id": assignment.role_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_permissions(self, user_id: str) -> dict[str, Any]:
        """Get user permissions."""
        try:
            permissions = self.ef.rbac.get_user_permissions(user_id)
            return {
                "user_id": user_id,
                "permission_count": len(permissions),
                "permissions": [
                    {
                        "resource_type": p.resource_type.value,
                        "action": p.action.value,
                        "expired": p.is_expired()
                    }
                    for p in permissions
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    def get_audit_logs(self, user_id: str | None = None, days: int = 30) -> dict[str, Any]:
        """Get audit logs."""
        try:
            logs = self.ef.rbac.get_audit_logs(user_id, days)
            return {
                "total_logs": len(logs),
                "logs": [
                    {
                        "timestamp": log.timestamp.isoformat(),
                        "user_id": log.user_id,
                        "action": log.action,
                        "result": log.result,
                        "reason": log.reason
                    }
                    for log in logs
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    # Data Governance Endpoints

    def register_data(self, request: DataRegistrationRequest) -> dict[str, Any]:
        """Register data record."""
        try:
            classification = DataClassification(request.classification)
            frameworks = [ComplianceFramework(f) for f in (request.compliance_frameworks or [])]

            record = self.ef.data_governance.register_data(
                name=request.name,
                classification=classification,
                owner_id=request.owner_id,
                retention_days=request.retention_days,
                compliance_frameworks=frameworks
            )

            return {
                "success": True,
                "data_id": record.id,
                "name": record.name,
                "classification": record.classification.value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_sensitive_data(self, data_id: str, content: str) -> dict[str, Any]:
        """Detect sensitive data in content."""
        try:
            detected = self.ef.data_governance.detect_sensitive_data(data_id, content)
            return {
                "data_id": data_id,
                "detected_count": len(detected),
                "detected_types": [
                    {
                        "type": dt.value,
                        "matches_count": len(matches)
                    }
                    for dt, matches in detected
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    def mask_sensitive_data(self, content: str) -> dict[str, Any]:
        """Mask sensitive data in content."""
        try:
            masked = self.ef.data_governance.mask_sensitive_data(content)
            return {
                "original_length": len(content),
                "masked_length": len(masked),
                "masked_content": masked
            }
        except Exception as e:
            return {"error": str(e)}

    def get_data_quality_metrics(self, data_id: str, days: int = 30) -> dict[str, Any]:
        """Get data quality metrics."""
        try:
            metrics = self.ef.data_governance.get_quality_metrics(data_id, days)
            return {
                "data_id": data_id,
                "metrics_count": len(metrics),
                "latest_score": metrics[-1].overall_score() if metrics else 0.0
            }
        except Exception as e:
            return {"error": str(e)}

    def check_data_compliance(self, data_id: str, framework: str) -> dict[str, Any]:
        """Check data compliance."""
        try:
            fw = ComplianceFramework(framework)
            result = self.ef.data_governance.check_compliance(data_id, fw)
            return {
                "data_id": data_id,
                "framework": framework,
                "passed": result.passed,
                "issues": result.issues
            }
        except Exception as e:
            return {"error": str(e)}

    # High Availability Endpoints

    def register_node(self, request: NodeRegistrationRequest) -> dict[str, Any]:
        """Register deployment node."""
        try:
            region = RegionName(request.region)
            node = self.ef.high_availability.register_node(
                name=request.name,
                region=region,
                endpoint=request.endpoint,
                port=request.port,
                weight=request.weight
            )
            return {
                "success": True,
                "node_id": node.id,
                "name": node.name,
                "region": node.region.value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_health_check(self, request: HealthCheckRequest) -> dict[str, Any]:
        """Create health check."""
        try:
            check_type = HealthCheckType(request.check_type)
            hc = self.ef.high_availability.create_health_check(
                node_id=request.node_id,
                check_type=check_type,
                endpoint=request.endpoint,
                interval_seconds=request.interval_seconds
            )
            return {
                "success": True,
                "health_check_id": hc.id,
                "node_id": hc.node_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_node_status(self) -> dict[str, Any]:
        """Get node status summary."""
        try:
            status = self.ef.high_availability.get_node_status_summary()
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "status": status
            }
        except Exception as e:
            return {"error": str(e)}

    def create_load_balancer(self, request: LoadBalancerRequest) -> dict[str, Any]:
        """Create load balancer."""
        try:
            algorithm = LoadBalancingAlgorithm(request.algorithm)
            strategy = FailoverStrategy(request.strategy)

            lb = self.ef.high_availability.create_load_balancer(
                name=request.name,
                algorithm=algorithm,
                strategy=strategy,
                node_ids=request.node_ids
            )
            return {
                "success": True,
                "lb_id": lb.id,
                "name": lb.name,
                "algorithm": lb.algorithm.value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_failover_history(self, days: int = 30) -> dict[str, Any]:
        """Get failover history."""
        try:
            failovers = self.ef.high_availability.get_failover_history(days)
            return {
                "period_days": days,
                "failover_count": len(failovers),
                "failovers": [
                    {
                        "timestamp": f.timestamp.isoformat(),
                        "from_node": f.from_node_id,
                        "to_node": f.to_node_id,
                        "reason": f.reason
                    }
                    for f in failovers
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    # Backup & Recovery Endpoints

    def create_backup_schedule(self, request: BackupScheduleRequest) -> dict[str, Any]:
        """Create backup schedule."""
        try:
            backup_type = BackupType(request.backup_type)
            storage_type = BackupStorageType(request.storage_type)

            schedule = self.ef.backup_recovery.create_backup_schedule(
                name=request.name,
                source_id=request.source_id,
                backup_type=backup_type,
                frequency_hours=request.frequency_hours,
                retention_days=request.retention_days,
                storage_type=storage_type,
                storage_location=request.storage_location
            )
            return {
                "success": True,
                "schedule_id": schedule.id,
                "name": schedule.name
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_backup_statistics(self) -> dict[str, Any]:
        """Get backup statistics."""
        try:
            stats = self.ef.backup_recovery.get_backup_statistics()
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "statistics": stats
            }
        except Exception as e:
            return {"error": str(e)}

    def get_recovery_statistics(self) -> dict[str, Any]:
        """Get recovery statistics."""
        try:
            stats = self.ef.backup_recovery.get_recovery_statistics()
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "statistics": stats
            }
        except Exception as e:
            return {"error": str(e)}

    # Compliance Endpoints

    def generate_compliance_report(self, request: ComplianceReportRequest) -> dict[str, Any]:
        """Generate compliance report."""
        try:
            framework = ComplianceFramework(request.framework)
            report = self.ef.compliance.generate_compliance_report(
                organization_id=request.organization_id,
                framework=framework,
                period_days=request.period_days
            )
            return {
                "success": True,
                "report_id": report.id,
                "framework": report.framework.value,
                "compliance_score": report.compliance_score,
                "status": report.status.value
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_compliance_dashboard(self, organization_id: str) -> dict[str, Any]:
        """Get compliance dashboard."""
        try:
            dashboard = self.ef.compliance.get_compliance_dashboard(organization_id)
            return {
                "organization_id": organization_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "dashboard": dashboard
            }
        except Exception as e:
            return {"error": str(e)}

    def create_data_subject_request(self, organization_id: str, request_type: str,
                                   subject_id: str) -> dict[str, Any]:
        """Create data subject request (GDPR)."""
        try:
            request = self.ef.compliance.create_data_subject_request(
                request_type=request_type,
                subject_id=subject_id
            )
            return {
                "success": True,
                "request_id": request.id,
                "request_type": request.request_type,
                "due_date": request.due_date.isoformat()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # System Endpoints

    def get_enterprise_status(self) -> dict[str, Any]:
        """Get enterprise system status."""
        return self.ef.get_enterprise_status()

    def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        return self.ef.health_check()

    def generate_enterprise_report(self) -> dict[str, Any]:
        """Generate comprehensive enterprise report."""
        return self.ef.generate_enterprise_report()
