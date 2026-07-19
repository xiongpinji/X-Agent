"""Comprehensive test suite for audit logging system."""

import pytest
from datetime import datetime, UTC, timedelta
from backend.app.core.audit_enhanced import (
    AuditStore,
    AuditLogRecord,
    AuditSearchCriteria,
    AuditPolicy,
    AuditLevel,
    AuditScope,
    DataChange,
    ComplianceReport,
)


class TestAuditLogRecord:
    """Test audit log record creation and validation."""

    def test_create_basic_record(self):
        """Test creating a basic audit record."""
        record = AuditLogRecord(
            action="create",
            resource_type="workflow",
            resource_id="wf-123",
            tenant_id="tenant-1",
            actor_id="user-1",
        )

        assert record.id is not None
        assert record.action == "create"
        assert record.resource_type == "workflow"
        assert record.resource_id == "wf-123"
        assert record.tenant_id == "tenant-1"
        assert record.actor_id == "user-1"
        assert record.outcome == "success"

    def test_record_with_data_changes(self):
        """Test recording data changes."""
        changes = [
            DataChange(field="status", before="draft", after="published"),
            DataChange(field="title", before="Old Title", after="New Title"),
        ]

        record = AuditLogRecord(
            action="update",
            resource_type="workflow",
            resource_id="wf-123",
            changes=changes,
        )

        assert len(record.changes) == 2
        assert record.changes[0].field == "status"
        assert record.changes[0].before == "draft"
        assert record.changes[0].after == "published"

    def test_record_with_snapshots(self):
        """Test recording before/after snapshots."""
        before = {"status": "draft", "title": "Old Title"}
        after = {"status": "published", "title": "New Title"}

        record = AuditLogRecord(
            action="update",
            resource_type="workflow",
            snapshot_before=before,
            snapshot_after=after,
        )

        assert record.snapshot_before == before
        assert record.snapshot_after == after


class TestAuditStore:
    """Test audit store functionality."""

    @pytest.fixture
    def store(self):
        """Create an in-memory audit store."""
        return AuditStore(hmac_secret="test-secret")

    def test_record_audit_event(self, store):
        """Test recording an audit event."""
        record = store.record(
            action="create",
            resource_type="workflow",
            tenant_id="tenant-1",
            actor_id="user-1",
        )

        assert record.id is not None
        assert record.hash is not None
        assert record.signature is not None

    def test_list_records(self, store):
        """Test listing audit records."""
        store.record(action="create", resource_type="workflow", tenant_id="tenant-1")
        store.record(action="update", resource_type="workflow", tenant_id="tenant-1")
        store.record(action="delete", resource_type="workflow", tenant_id="tenant-2")

        records = store.list(limit=10)
        assert len(records) == 3

        records = store.list(limit=10, tenant_id="tenant-1")
        assert len(records) == 2

        records = store.list(limit=10, action="create")
        assert len(records) == 1

    def test_search_with_criteria(self, store):
        """Test advanced search with criteria."""
        store.record(
            action="create",
            resource_type="workflow",
            tenant_id="tenant-1",
            actor_id="user-1",
        )
        store.record(
            action="update",
            resource_type="workflow",
            tenant_id="tenant-1",
            actor_id="user-2",
        )
        store.record(
            action="delete",
            resource_type="agent",
            tenant_id="tenant-1",
            actor_id="user-1",
        )

        criteria = AuditSearchCriteria(
            tenant_id="tenant-1",
            actor_id="user-1",
            limit=10,
        )
        records, total = store.search(criteria)

        assert total == 2
        assert len(records) == 2

    def test_search_with_time_range(self, store):
        """Test search with time range."""
        now = datetime.now(UTC)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        store.record(action="create", resource_type="workflow")

        criteria = AuditSearchCriteria(
            start_time=past,
            end_time=future,
            limit=10,
        )
        records, total = store.search(criteria)

        assert total == 1
        assert len(records) == 1

    def test_verify_chain_integrity(self, store):
        """Test audit chain verification."""
        store.record(action="create", resource_type="workflow")
        store.record(action="update", resource_type="workflow")
        store.record(action="delete", resource_type="workflow")

        verification = store.verify_chain()

        assert verification.valid is True
        assert verification.checked == 3
        assert verification.signed == 3

    def test_export_csv(self, store):
        """Test CSV export."""
        store.record(
            action="create",
            resource_type="workflow",
            tenant_id="tenant-1",
            actor_id="user-1",
        )
        store.record(
            action="update",
            resource_type="workflow",
            tenant_id="tenant-1",
            actor_id="user-2",
        )

        csv_content = store.export_csv(tenant_id="tenant-1")

        assert "id" in csv_content
        assert "created_at" in csv_content
        assert "action" in csv_content
        assert "create" in csv_content
        assert "update" in csv_content

    def test_export_json(self, store):
        """Test JSON export."""
        store.record(
            action="create",
            resource_type="workflow",
            tenant_id="tenant-1",
        )

        json_data = store.export_json(tenant_id="tenant-1")

        assert len(json_data) == 1
        assert json_data[0]["action"] == "create"
        assert json_data[0]["resource_type"] == "workflow"

    def test_export_xml(self, store):
        """Test XML export."""
        store.record(
            action="create",
            resource_type="workflow",
            tenant_id="tenant-1",
        )

        xml_content = store.export_xml(tenant_id="tenant-1")

        assert "<audit_logs" in xml_content
        assert "<record" in xml_content
        assert "create" in xml_content


class TestAuditAnalytics:
    """Test audit analytics functionality."""

    @pytest.fixture
    def store_with_data(self):
        """Create store with sample data."""
        store = AuditStore(hmac_secret="test-secret")

        # Create various audit events
        for i in range(5):
            store.record(
                action="create",
                resource_type="workflow",
                tenant_id="tenant-1",
                actor_id="user-1",
                outcome="success",
            )

        for i in range(3):
            store.record(
                action="update",
                resource_type="workflow",
                tenant_id="tenant-1",
                actor_id="user-2",
                outcome="success",
            )

        for i in range(2):
            store.record(
                action="delete",
                resource_type="agent",
                tenant_id="tenant-1",
                actor_id="user-1",
                outcome="failure",
            )

        return store

    def test_get_analytics(self, store_with_data):
        """Test analytics generation."""
        analytics = store_with_data.get_analytics(tenant_id="tenant-1")

        assert analytics.total_records == 10
        assert analytics.by_action["create"] == 5
        assert analytics.by_action["update"] == 3
        assert analytics.by_action["delete"] == 2
        assert analytics.by_resource_type["workflow"] == 8
        assert analytics.by_resource_type["agent"] == 2
        assert analytics.by_outcome["success"] == 8
        assert analytics.by_outcome["failure"] == 2

    def test_anomaly_detection(self, store_with_data):
        """Test anomaly detection."""
        analytics = store_with_data.get_analytics(tenant_id="tenant-1")

        # Should detect failed operations
        assert len(analytics.failed_operations) > 0

    def test_analytics_by_actor(self, store_with_data):
        """Test analytics by actor."""
        analytics = store_with_data.get_analytics(tenant_id="tenant-1")

        assert analytics.by_actor["user-1"] == 7
        assert analytics.by_actor["user-2"] == 3


class TestComplianceReporting:
    """Test compliance report generation."""

    @pytest.fixture
    def store_with_data(self):
        """Create store with sample data."""
        store = AuditStore(hmac_secret="test-secret")

        # Create login events
        for i in range(10):
            store.record(
                action="login",
                resource_type="session",
                tenant_id="tenant-1",
                actor_id="user-1",
                outcome="success",
            )

        # Create failed login
        store.record(
            action="login",
            resource_type="session",
            tenant_id="tenant-1",
            actor_id="user-2",
            outcome="failure",
        )

        # Create permission changes
        for i in range(5):
            store.record(
                action="permission_grant",
                resource_type="role",
                tenant_id="tenant-1",
                actor_id="admin-1",
                outcome="success",
            )

        # Create data exports
        for i in range(20):
            store.record(
                action="export",
                resource_type="data",
                tenant_id="tenant-1",
                actor_id="user-1",
                outcome="success",
            )

        return store

    def test_generate_compliance_report(self, store_with_data):
        """Test compliance report generation."""
        report = store_with_data.generate_compliance_report(
            report_type="SOC2",
            tenant_id="tenant-1",
        )

        assert report.report_type == "SOC2"
        assert report.total_operations > 0
        assert report.login_attempts == 11
        assert report.failed_logins == 1
        assert report.permission_changes == 5
        assert report.data_exports == 20
        assert report.signature is not None

    def test_compliance_findings(self, store_with_data):
        """Test compliance findings generation."""
        report = store_with_data.generate_compliance_report(
            report_type="SOC2",
            tenant_id="tenant-1",
        )

        # Should have findings for high data export rate
        assert len(report.findings) > 0 or len(report.recommendations) > 0


class TestAuditPolicy:
    """Test audit policy configuration."""

    def test_default_policy(self):
        """Test default audit policy."""
        policy = AuditPolicy()

        assert policy.level == AuditLevel.STANDARD
        assert policy.scope == AuditScope.TENANT
        assert policy.retention_days == 365 * 7
        assert policy.archive_after_days == 90
        assert policy.enable_encryption is True
        assert policy.enable_signing is True

    def test_custom_policy(self):
        """Test custom audit policy."""
        policy = AuditPolicy(
            level=AuditLevel.DETAILED,
            scope=AuditScope.GLOBAL,
            retention_days=365 * 10,
            archive_after_days=180,
        )

        assert policy.level == AuditLevel.DETAILED
        assert policy.scope == AuditScope.GLOBAL
        assert policy.retention_days == 365 * 10
        assert policy.archive_after_days == 180


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
