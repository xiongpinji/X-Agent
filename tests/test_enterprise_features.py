"""Tests for enterprise features."""

import pytest
from datetime import UTC, datetime, timedelta

from backend.app.core.advanced_rbac import (
    AdvancedRBACEngine,
    Attribute,
    Permission,
    PermissionAction,
    ResourceType,
)
from backend.app.core.backup_recovery import (
    BackupRecoveryEngine,
    BackupStatus,
    BackupType,
    BackupStorageType,
)
from backend.app.core.compliance_reporting import (
    ComplianceFramework,
    ComplianceReportingEngine,
)
from backend.app.core.data_governance import (
    DataClassification,
    DataGovernanceEngine,
    SensitiveDataType,
)
from backend.app.core.high_availability import (
    HighAvailabilityEngine,
    HealthCheckType,
    HealthStatus,
    LoadBalancingAlgorithm,
    FailoverStrategy,
    RegionName,
)
from backend.app.core.enterprise_features import EnterpriseFeatures


class TestAdvancedRBAC:
    """Test Advanced RBAC functionality."""

    def test_create_role(self):
        rbac = AdvancedRBACEngine()
        role = rbac.create_role("Admin", "Administrator role")
        assert role.name == "Admin"
        assert role.id in rbac.roles

    def test_assign_role(self):
        rbac = AdvancedRBACEngine()
        role = rbac.create_role("Admin")
        assignment = rbac.assign_role("user1", role.id, "admin")
        assert assignment.user_id == "user1"
        assert assignment.role_id == role.id

    def test_permission_matching(self):
        rbac = AdvancedRBACEngine()
        role = rbac.create_role("Editor")

        perm = Permission(
            resource_type=ResourceType.WORKFLOW,
            action=PermissionAction.UPDATE,
            attributes=[
                Attribute(name="owner_id", value="user1", operator="equals")
            ]
        )
        rbac.add_permission_to_role(role.id, perm)
        rbac.assign_role("user1", role.id, "admin")

        allowed, reason = rbac.check_permission(
            "user1",
            ResourceType.WORKFLOW,
            PermissionAction.UPDATE,
            {"id": "wf1", "owner_id": "user1"}
        )
        assert allowed

    def test_permission_denial(self):
        rbac = AdvancedRBACEngine()
        role = rbac.create_role("Viewer")
        rbac.assign_role("user1", role.id, "admin")

        allowed, reason = rbac.check_permission(
            "user1",
            ResourceType.WORKFLOW,
            PermissionAction.DELETE,
            {"id": "wf1"}
        )
        assert not allowed

    def test_role_inheritance(self):
        rbac = AdvancedRBACEngine()
        base_role = rbac.create_role("Base")
        perm = Permission(
            resource_type=ResourceType.WORKFLOW,
            action=PermissionAction.READ
        )
        rbac.add_permission_to_role(base_role.id, perm)

        child_role = rbac.create_role("Child", parent_roles=[base_role.id])
        rbac.assign_role("user1", child_role.id, "admin")

        permissions = rbac.get_user_permissions("user1")
        assert len(permissions) > 0

    def test_audit_logging(self):
        rbac = AdvancedRBACEngine()
        role = rbac.create_role("Viewer")
        rbac.assign_role("user1", role.id, "admin")

        rbac.check_permission(
            "user1",
            ResourceType.WORKFLOW,
            PermissionAction.READ,
            {"id": "wf1"},
            ip_address="192.168.1.1"
        )

        logs = rbac.get_audit_logs("user1")
        assert len(logs) > 0
        assert logs[0].user_id == "user1"


class TestDataGovernance:
    """Test Data Governance functionality."""

    def test_register_data(self):
        dg = DataGovernanceEngine()
        record = dg.register_data(
            "customer_data",
            DataClassification.CONFIDENTIAL,
            "owner1"
        )
        assert record.name == "customer_data"
        assert record.id in dg.data_records

    def test_detect_sensitive_data(self):
        dg = DataGovernanceEngine()
        record = dg.register_data(
            "user_info",
            DataClassification.CONFIDENTIAL,
            "owner1"
        )

        content = "Contact: john@example.com, Phone: 555-123-4567"
        detected = dg.detect_sensitive_data(record.id, content)
        assert len(detected) > 0

    def test_mask_sensitive_data(self):
        dg = DataGovernanceEngine()
        content = "Email: test@example.com"
        masked = dg.mask_sensitive_data(content)
        assert "@" not in masked or masked.count("*") > 0

    def test_data_quality_metrics(self):
        dg = DataGovernanceEngine()
        record = dg.register_data(
            "data1",
            DataClassification.INTERNAL,
            "owner1"
        )

        metric = dg.record_quality_metric(
            record.id,
            completeness=95.0,
            accuracy=90.0,
            consistency=85.0,
            timeliness=92.0,
            validity=88.0
        )
        assert metric.overall_score() > 0

    def test_compliance_check(self):
        dg = DataGovernanceEngine()
        record = dg.register_data(
            "data1",
            DataClassification.RESTRICTED,
            "owner1"
        )

        result = dg.check_compliance(record.id, ComplianceFramework.GDPR)
        assert result.framework == ComplianceFramework.GDPR

    def test_cleanup_expired_data(self):
        dg = DataGovernanceEngine()
        record = dg.register_data(
            "data1",
            DataClassification.INTERNAL,
            "owner1",
            retention_days=0
        )

        deleted = dg.cleanup_expired_data()
        assert record.id in deleted


class TestHighAvailability:
    """Test High Availability functionality."""

    def test_register_node(self):
        ha = HighAvailabilityEngine()
        node = ha.register_node(
            "node1",
            RegionName.US_EAST_1,
            "10.0.0.1"
        )
        assert node.name == "node1"
        assert node.id in ha.nodes

    def test_health_check(self):
        ha = HighAvailabilityEngine()
        node = ha.register_node(
            "node1",
            RegionName.US_EAST_1,
            "10.0.0.1"
        )
        hc = ha.create_health_check(node.id, HealthCheckType.HTTP)
        assert hc.node_id == node.id

    def test_health_check_result(self):
        ha = HighAvailabilityEngine()
        node = ha.register_node(
            "node1",
            RegionName.US_EAST_1,
            "10.0.0.1"
        )
        hc = ha.create_health_check(node.id, HealthCheckType.HTTP)

        result = ha.record_health_check_result(hc.id, True, 50)
        assert result.success
        assert node.status == HealthStatus.HEALTHY

    def test_load_balancer(self):
        ha = HighAvailabilityEngine()
        node1 = ha.register_node("node1", RegionName.US_EAST_1, "10.0.0.1")
        node2 = ha.register_node("node2", RegionName.US_EAST_1, "10.0.0.2")

        lb = ha.create_load_balancer(
            "lb1",
            LoadBalancingAlgorithm.ROUND_ROBIN,
            FailoverStrategy.ACTIVE_PASSIVE,
            [node1.id, node2.id]
        )
        assert lb.id in ha.load_balancers

    def test_failover(self):
        ha = HighAvailabilityEngine()
        node1 = ha.register_node("node1", RegionName.US_EAST_1, "10.0.0.1")
        node2 = ha.register_node("node2", RegionName.US_EAST_1, "10.0.0.2")

        failover = ha.trigger_failover(node1.id, node2.id, "Node1 unhealthy")
        assert failover.from_node_id == node1.id
        assert failover.to_node_id == node2.id

    def test_availability_calculation(self):
        ha = HighAvailabilityEngine()
        node = ha.register_node("node1", RegionName.US_EAST_1, "10.0.0.1")
        hc = ha.create_health_check(node.id, HealthCheckType.HTTP)

        for _ in range(10):
            ha.record_health_check_result(hc.id, True)

        availability = ha.calculate_availability(node.id, 24)
        assert availability == 100.0


class TestBackupRecovery:
    """Test Backup and Recovery functionality."""

    def test_create_backup_schedule(self):
        br = BackupRecoveryEngine()
        schedule = br.create_backup_schedule(
            "daily_backup",
            "db1",
            BackupType.FULL,
            24,
            30,
            BackupStorageType.S3,
            "s3://backups"
        )
        assert schedule.name == "daily_backup"

    def test_create_backup(self):
        br = BackupRecoveryEngine()
        backup = br.create_backup(
            "backup1",
            BackupType.FULL,
            "db1",
            BackupStorageType.S3,
            "s3://backups/backup1"
        )
        assert backup.id in br.backups

    def test_backup_lifecycle(self):
        br = BackupRecoveryEngine()
        backup = br.create_backup(
            "backup1",
            BackupType.FULL,
            "db1",
            BackupStorageType.S3,
            "s3://backups/backup1"
        )

        br.start_backup(backup.id)
        assert backup.status == BackupStatus.IN_PROGRESS

        br.complete_backup(backup.id, 1000000, 500000, "abc123")
        assert backup.status == BackupStatus.COMPLETED

    def test_recovery_job(self):
        br = BackupRecoveryEngine()
        backup = br.create_backup(
            "backup1",
            BackupType.FULL,
            "db1",
            BackupStorageType.S3,
            "s3://backups/backup1"
        )
        br.complete_backup(backup.id, 1000000, 500000, "abc123")

        job = br.start_recovery(backup.id, "db1_restored")
        assert job.status.value == "in_progress"

        br.complete_recovery(job.id, 1000000)
        assert job.status.value == "completed"

    def test_backup_verification(self):
        br = BackupRecoveryEngine()
        backup = br.create_backup(
            "backup1",
            BackupType.FULL,
            "db1",
            BackupStorageType.S3,
            "s3://backups/backup1"
        )
        br.complete_backup(backup.id, 1000000, 500000, "abc123")

        verification = br.verify_backup(backup.id)
        assert verification.success


class TestComplianceReporting:
    """Test Compliance Reporting functionality."""

    def test_gdpr_compliance(self):
        cr = ComplianceReportingEngine()
        compliance = cr.initialize_gdpr_compliance("org1")
        assert compliance.organization_id == "org1"

    def test_update_gdpr_compliance(self):
        cr = ComplianceReportingEngine()
        cr.initialize_gdpr_compliance("org1")
        updated = cr.update_gdpr_compliance(
            "org1",
            dpo_appointed=True,
            privacy_policy_updated=True
        )
        assert updated.dpo_appointed

    def test_data_subject_request(self):
        cr = ComplianceReportingEngine()
        request = cr.create_data_subject_request("access", "subject1")
        assert request.request_type == "access"
        assert request.status == "pending"

    def test_compliance_report_generation(self):
        cr = ComplianceReportingEngine()
        cr.initialize_gdpr_compliance("org1")
        cr.update_gdpr_compliance("org1", dpo_appointed=True)

        report = cr.generate_compliance_report("org1", ComplianceFramework.GDPR)
        assert report.framework == ComplianceFramework.GDPR

    def test_compliance_dashboard(self):
        cr = ComplianceReportingEngine()
        cr.initialize_gdpr_compliance("org1")
        cr.initialize_hipaa_compliance("org1")

        dashboard = cr.get_compliance_dashboard("org1")
        assert "gdpr" in dashboard
        assert "hipaa" in dashboard


class TestEnterpriseFeatures:
    """Test integrated Enterprise Features."""

    def test_enterprise_initialization(self):
        ef = EnterpriseFeatures()
        assert ef.rbac is not None
        assert ef.data_governance is not None
        assert ef.high_availability is not None
        assert ef.backup_recovery is not None
        assert ef.compliance is not None

    def test_setup_enterprise_roles(self):
        ef = EnterpriseFeatures()
        roles = ef.setup_enterprise_roles()
        assert "admin" in roles
        assert "security" in roles
        assert "data" in roles
        assert "operations" in roles

    def test_enterprise_status(self):
        ef = EnterpriseFeatures()
        status = ef.get_enterprise_status()
        assert "rbac" in status
        assert "data_governance" in status
        assert "high_availability" in status
        assert "backup_recovery" in status
        assert "compliance" in status

    def test_health_check(self):
        ef = EnterpriseFeatures()
        health = ef.health_check()
        assert health["status"] in ["healthy", "warning"]
        assert "components" in health

    def test_enterprise_report(self):
        ef = EnterpriseFeatures()
        report = ef.generate_enterprise_report()
        assert "system_status" in report
        assert "health_check" in report
        assert "rbac_summary" in report
        assert "compliance_summary" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
