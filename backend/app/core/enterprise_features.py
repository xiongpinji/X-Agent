"""Enterprise Features Integration module.

Integrates all enterprise-grade features:
- Advanced RBAC with ABAC
- Data Governance
- High Availability
- Backup and Recovery
- Compliance Reporting
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.app.core.advanced_rbac import (
    AdvancedRBACEngine,
    Permission,
    PermissionAction,
    ResourceType,
    Role,
)
from backend.app.core.backup_recovery import BackupRecoveryEngine
from backend.app.core.compliance_reporting import ComplianceReportingEngine
from backend.app.core.data_governance import DataGovernanceEngine
from backend.app.core.high_availability import HighAvailabilityEngine


class EnterpriseFeatures:
    """Unified enterprise features manager."""

    def __init__(self):
        self.rbac = AdvancedRBACEngine()
        self.data_governance = DataGovernanceEngine()
        self.high_availability = HighAvailabilityEngine()
        self.backup_recovery = BackupRecoveryEngine()
        self.compliance = ComplianceReportingEngine()
        self.initialized_at = datetime.now(UTC)

    def setup_enterprise_roles(self) -> dict[str, Role]:
        """Set up standard enterprise roles."""
        roles = {}

        # Admin role - full access
        admin_role = self.rbac.create_role(
            name="Enterprise Admin",
            description="Full administrative access"
        )
        admin_perms = [
            Permission(
                resource_type=ResourceType.POLICY,
                action=PermissionAction.CREATE,
            ),
            Permission(
                resource_type=ResourceType.POLICY,
                action=PermissionAction.UPDATE,
            ),
            Permission(
                resource_type=ResourceType.POLICY,
                action=PermissionAction.DELETE,
            ),
            Permission(
                resource_type=ResourceType.AUDIT_LOG,
                action=PermissionAction.READ,
            ),
        ]
        for perm in admin_perms:
            self.rbac.add_permission_to_role(admin_role.id, perm)
        roles["admin"] = admin_role

        # Security Officer role
        security_role = self.rbac.create_role(
            name="Security Officer",
            description="Security and compliance management"
        )
        security_perms = [
            Permission(
                resource_type=ResourceType.AUDIT_LOG,
                action=PermissionAction.READ,
            ),
            Permission(
                resource_type=ResourceType.REPORT,
                action=PermissionAction.READ,
            ),
            Permission(
                resource_type=ResourceType.BACKUP,
                action=PermissionAction.READ,
            ),
        ]
        for perm in security_perms:
            self.rbac.add_permission_to_role(security_role.id, perm)
        roles["security"] = security_role

        # Data Officer role
        data_role = self.rbac.create_role(
            name="Data Officer",
            description="Data governance and protection"
        )
        data_perms = [
            Permission(
                resource_type=ResourceType.DATA,
                action=PermissionAction.READ,
            ),
            Permission(
                resource_type=ResourceType.DATA,
                action=PermissionAction.UPDATE,
            ),
        ]
        for perm in data_perms:
            self.rbac.add_permission_to_role(data_role.id, perm)
        roles["data"] = data_role

        # Operations role
        ops_role = self.rbac.create_role(
            name="Operations",
            description="System operations and monitoring"
        )
        ops_perms = [
            Permission(
                resource_type=ResourceType.BACKUP,
                action=PermissionAction.READ,
            ),
            Permission(
                resource_type=ResourceType.BACKUP,
                action=PermissionAction.EXECUTE,
            ),
        ]
        for perm in ops_perms:
            self.rbac.add_permission_to_role(ops_role.id, perm)
        roles["operations"] = ops_role

        return roles

    def get_enterprise_status(self) -> dict[str, Any]:
        """Get overall enterprise system status."""
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "rbac": {
                "total_roles": len(self.rbac.roles),
                "total_users": len(self.rbac.role_assignments),
                "audit_logs": len(self.rbac.audit_logs),
                "analytics": self.rbac.get_analytics().model_dump()
            },
            "data_governance": {
                "total_records": len(self.data_governance.data_records),
                "sensitive_data_inventory": self.data_governance.get_sensitive_data_inventory(),
                "quality_metrics_count": sum(len(m) for m in self.data_governance.quality_metrics.values())
            },
            "high_availability": {
                "total_nodes": len(self.high_availability.nodes),
                "node_status": self.high_availability.get_node_status_summary(),
                "load_balancers": len(self.high_availability.load_balancers),
                "failovers_30d": len(self.high_availability.get_failover_history(30))
            },
            "backup_recovery": {
                "total_backups": len(self.backup_recovery.backups),
                "backup_stats": self.backup_recovery.get_backup_statistics(),
                "recovery_stats": self.backup_recovery.get_recovery_statistics(),
                "schedules": len(self.backup_recovery.schedules)
            },
            "compliance": {
                "gdpr_tracked": len(self.compliance.gdpr_compliance),
                "hipaa_tracked": len(self.compliance.hipaa_compliance),
                "soc2_tracked": len(self.compliance.soc2_compliance),
                "open_findings": sum(1 for f in self.compliance.audit_findings if f.status == "open"),
                "pending_dsr": sum(1 for r in self.compliance.data_subject_requests if r.status == "pending")
            }
        }

    def health_check(self) -> dict[str, Any]:
        """Perform enterprise health check."""
        health = {
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "healthy",
            "components": {}
        }

        # Check RBAC
        health["components"]["rbac"] = {
            "status": "healthy" if len(self.rbac.roles) > 0 else "warning",
            "roles": len(self.rbac.roles)
        }

        # Check HA
        node_status = self.high_availability.get_node_status_summary()
        unhealthy = node_status.get("unhealthy", 0)
        health["components"]["high_availability"] = {
            "status": "healthy" if unhealthy == 0 else "warning",
            "unhealthy_nodes": unhealthy
        }

        # Check Backups
        backup_stats = self.backup_recovery.get_backup_statistics()
        failed = backup_stats.get("failed", 0)
        health["components"]["backup_recovery"] = {
            "status": "healthy" if failed == 0 else "warning",
            "failed_backups": failed
        }

        # Check Compliance
        open_findings = sum(1 for f in self.compliance.audit_findings if f.status == "open")
        health["components"]["compliance"] = {
            "status": "healthy" if open_findings == 0 else "warning",
            "open_findings": open_findings
        }

        # Overall status
        if any(c["status"] == "warning" for c in health["components"].values()):
            health["status"] = "warning"

        return health

    def generate_enterprise_report(self) -> dict[str, Any]:
        """Generate comprehensive enterprise report."""
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "system_status": self.get_enterprise_status(),
            "health_check": self.health_check(),
            "rbac_summary": {
                "total_roles": len(self.rbac.roles),
                "total_assignments": sum(len(a) for a in self.rbac.role_assignments.values()),
                "audit_entries_30d": len(self.rbac.get_audit_logs(days=30))
            },
            "data_governance_summary": {
                "total_records": len(self.data_governance.data_records),
                "by_classification": {
                    "public": len(self.data_governance.get_data_by_classification("public")),
                    "internal": len(self.data_governance.get_data_by_classification("internal")),
                    "confidential": len(self.data_governance.get_data_by_classification("confidential")),
                    "restricted": len(self.data_governance.get_data_by_classification("restricted"))
                }
            },
            "ha_summary": {
                "regions": len(set(n.region for n in self.high_availability.nodes.values())),
                "total_nodes": len(self.high_availability.nodes),
                "failovers_30d": len(self.high_availability.get_failover_history(30))
            },
            "backup_summary": {
                "total_backups": len(self.backup_recovery.backups),
                "schedules": len(self.backup_recovery.schedules),
                "recovery_jobs": len(self.backup_recovery.recovery_jobs)
            },
            "compliance_summary": {
                "frameworks_tracked": {
                    "gdpr": len(self.compliance.gdpr_compliance),
                    "hipaa": len(self.compliance.hipaa_compliance),
                    "soc2": len(self.compliance.soc2_compliance)
                },
                "total_findings": len(self.compliance.audit_findings),
                "open_findings": sum(1 for f in self.compliance.audit_findings if f.status == "open")
            }
        }
