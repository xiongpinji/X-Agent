"""Deep coverage tests for enterprise_migration.py, audit_export.py, audit_shipper.py."""
import asyncio
import json
import pytest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.enterprise_migration import (
    MigrationType, MigrationStatus, MigrationPhase,
    SourceSystem, TargetSystem, MigrationMapping, MigrationPlan, MigrationJob,
    DataValidationResult, OpenClawMigrator, HermesMigrator,
    DataExporter, DataImporter, ConfigurationTransformer,
)
from backend.app.core.audit_export import (
    ExportFrequency, ExportFormat, ExternalSystemType,
    ScheduledExport, ExternalSystemIntegration, ExportJob,
    SIEMEventAdapter, ScheduledExportManager, ExternalSystemIntegrationManager,
)
from backend.app.core.audit_shipper import (
    AuditExportUnavailable, RFC5424Formatter, AuditExporter,
    SyslogExporter, WebhookExporter, S3WormExporter,
    AuditShipperConfig, AuditShipper,
    SyslogChannelConfig, WebhookChannelConfig, S3WormChannelConfig,
    AuditShipperChannels, build_shipper,
)


# ═══════════════════════════════════════════════════════════════════════════════
# OpenClawMigrator TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestOpenClawMigrator:
    def _src(self):
        return SourceSystem(system_type="openclaw", system_name="src",
                            connection_string="pg://src", host="h", port=5432, database="db")

    def _tgt(self):
        return TargetSystem(system_name="tgt", connection_string="pg://tgt",
                            host="h", port=5432, database="db")

    def test_create_migration_plan(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt(), MigrationType.INCREMENTAL)
        assert plan.migration_type == MigrationType.INCREMENTAL
        assert plan.plan_id in m._plans

    def test_add_table_mapping_success(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        mapping = MigrationMapping(source_table="users", target_table="users_v2",
                                   field_mappings={"id": "id"})
        assert m.add_table_mapping(plan.plan_id, mapping) is True
        assert len(plan.table_mappings) == 1

    def test_add_table_mapping_not_found(self):
        m = OpenClawMigrator()
        mapping = MigrationMapping(source_table="a", target_table="b", field_mappings={})
        assert m.add_table_mapping("nope", mapping) is False

    def test_validate_source_data_found(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        m.add_table_mapping(plan.plan_id, MigrationMapping(
            source_table="t1", target_table="t1", field_mappings={"a": "a"}))
        result = m.validate_source_data(plan.plan_id)
        assert result["plan_id"] == plan.plan_id
        assert len(result["tables"]) == 1

    def test_validate_source_data_not_found(self):
        m = OpenClawMigrator()
        result = m.validate_source_data("nope")
        assert "error" in result

    def test_start_migration(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        assert job.status == MigrationStatus.VALIDATING

    def test_start_migration_not_found(self):
        m = OpenClawMigrator()
        with pytest.raises(ValueError):
            m.start_migration("nope")

    def test_get_migration_status(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        assert m.get_migration_status(job.job_id) is job
        assert m.get_migration_status("nope") is None

    def test_pause_migration_running(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        job.status = MigrationStatus.RUNNING
        assert m.pause_migration(job.job_id) is True
        assert job.status == MigrationStatus.PAUSED

    def test_pause_migration_not_running(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        assert m.pause_migration(job.job_id) is False

    def test_pause_migration_not_found(self):
        m = OpenClawMigrator()
        assert m.pause_migration("nope") is False

    def test_resume_migration_paused(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        job.status = MigrationStatus.PAUSED
        assert m.resume_migration(job.job_id) is True
        assert job.status == MigrationStatus.RUNNING

    def test_resume_migration_not_paused(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        assert m.resume_migration(job.job_id) is False

    def test_resume_migration_not_found(self):
        m = OpenClawMigrator()
        assert m.resume_migration("nope") is False

    def test_rollback_migration(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        assert m.rollback_migration(job.job_id) is True
        assert job.status == MigrationStatus.ROLLED_BACK

    def test_rollback_migration_not_found(self):
        m = OpenClawMigrator()
        assert m.rollback_migration("nope") is False

    def test_validate_migrated_data_success(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        job.total_records = 100
        job.migrated_records = 95
        job.failed_records = 0
        result = m.validate_migrated_data(job.job_id)
        assert result.validation_passed is True

    def test_validate_migrated_data_with_failures(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        job.failed_records = 5
        result = m.validate_migrated_data(job.job_id)
        assert result.validation_passed is False

    def test_validate_migrated_data_job_not_found(self):
        m = OpenClawMigrator()
        with pytest.raises(ValueError):
            m.validate_migrated_data("nope")

    def test_validate_migrated_data_plan_not_found(self):
        m = OpenClawMigrator()
        plan = m.create_migration_plan(self._src(), self._tgt())
        job = m.start_migration(plan.plan_id)
        del m._plans[plan.plan_id]
        with pytest.raises(ValueError):
            m.validate_migrated_data(job.job_id)


# ═══════════════════════════════════════════════════════════════════════════════
# HermesMigrator TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHermesMigrator:
    def _src(self):
        return SourceSystem(system_type="hermes", system_name="hermes_src",
                            connection_string="pg://h", host="h", port=5432, database="db")

    def _tgt(self):
        return TargetSystem(system_name="tgt", connection_string="pg://t",
                            host="h", port=5432, database="db")

    def test_create_snapshot(self):
        m = HermesMigrator()
        sid = m.create_snapshot(self._src())
        assert sid.startswith("snapshot_")
        assert sid in m._snapshots

    def test_analyze_schema_found(self):
        m = HermesMigrator()
        sid = m.create_snapshot(self._src())
        result = m.analyze_schema(sid)
        assert result["snapshot_id"] == sid

    def test_analyze_schema_not_found(self):
        m = HermesMigrator()
        result = m.analyze_schema("nope")
        assert "error" in result

    def test_generate_migration_script(self):
        m = HermesMigrator()
        sid = m.create_snapshot(self._src())
        script = m.generate_migration_script(sid, self._tgt())
        assert "BEGIN TRANSACTION" in script

    def test_generate_migration_script_not_found(self):
        m = HermesMigrator()
        with pytest.raises(ValueError):
            m.generate_migration_script("nope", self._tgt())

    def test_execute_migration_script(self):
        m = HermesMigrator()
        result = m.execute_migration_script("SELECT 1;", self._tgt())
        assert result["status"] == "success"

    def test_verify_migration(self):
        m = HermesMigrator()
        result = m.verify_migration(self._src(), self._tgt())
        assert result["overall_status"] == "passed"


# ═══════════════════════════════════════════════════════════════════════════════
# DataExporter / DataImporter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataExporter:
    def test_export_to_json(self):
        exp = DataExporter()
        eid = exp.export_to_json([{"a": 1}])
        data = exp.get_export(eid)
        assert data["format"] == "json"
        assert data["record_count"] == 1

    def test_export_to_json_custom_id(self):
        exp = DataExporter()
        eid = exp.export_to_json([], export_id="custom")
        assert eid == "custom"

    def test_export_to_csv(self):
        exp = DataExporter()
        eid = exp.export_to_csv([{"b": 2}])
        assert exp.get_export(eid)["format"] == "csv"

    def test_export_to_parquet(self):
        exp = DataExporter()
        eid = exp.export_to_parquet([{"c": 3}])
        assert exp.get_export(eid)["format"] == "parquet"

    def test_get_export_missing(self):
        exp = DataExporter()
        assert exp.get_export("nope") is None


class TestDataImporter:
    def test_import_from_json_list(self):
        imp = DataImporter()
        iid = imp.import_from_json('[{"x": 1}, {"x": 2}]')
        data = imp.get_import(iid)
        assert data["record_count"] == 2
        assert data["status"] == "success"

    def test_import_from_json_dict(self):
        imp = DataImporter()
        iid = imp.import_from_json('{"x": 1}')
        assert imp.get_import(iid)["record_count"] == 1

    def test_import_from_json_invalid(self):
        imp = DataImporter()
        with pytest.raises(json.JSONDecodeError):
            imp.import_from_json("not json{{{")

    def test_import_from_csv(self):
        imp = DataImporter()
        iid = imp.import_from_csv("a,b\n1,2")
        assert imp.get_import(iid)["format"] == "csv"

    def test_get_import_missing(self):
        imp = DataImporter()
        assert imp.get_import("nope") is None


# ═══════════════════════════════════════════════════════════════════════════════
# ConfigurationTransformer TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfigurationTransformer:
    def test_transform_xagent_v1_to_v2(self):
        v1 = {"app_name": "MyAgent", "database_url": "pg://x",
               "jwt_secret": "s", "openai_api_key": "k"}
        v2 = ConfigurationTransformer.transform_xagent_v1_to_v2(v1)
        assert v2["version"] == "2.0"
        assert v2["app_name"] == "MyAgent"
        assert v2["database"]["url"] == "pg://x"
        assert v2["llm"]["openai_api_key"] == "k"

    def test_transform_xagent_v1_to_v2_defaults(self):
        v2 = ConfigurationTransformer.transform_xagent_v1_to_v2({})
        assert v2["app_name"] == "X-Agent"
        assert v2["database"]["pool_size"] == 20

    def test_transform_openclaw_to_xagent(self):
        oc = {"name": "Claw", "db_connection_string": "pg://oc", "jwt_secret": "j"}
        result = ConfigurationTransformer.transform_openclaw_to_xagent(oc)
        assert result["app_name"] == "Claw"
        assert result["database"]["url"] == "pg://oc"

    def test_transform_hermes_to_xagent(self):
        hc = {"application_name": "Hermes", "database_url": "pg://h"}
        result = ConfigurationTransformer.transform_hermes_to_xagent(hc)
        assert result["app_name"] == "Hermes"
        assert result["database"]["url"] == "pg://h"


# ═══════════════════════════════════════════════════════════════════════════════
# SIEMEventAdapter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSIEMEventAdapter:
    RECORD = {
        "id": "abc123", "created_at": "2025-01-01T00:00:00+00:00",
        "tenant_id": "t1", "actor_id": "u1", "action": "login",
        "resource_type": "user", "resource_id": "r1", "outcome": "success",
        "details": {}, "duration_ms": 42, "ip_address": "1.2.3.4",
    }

    def test_to_splunk_event(self):
        event = SIEMEventAdapter.to_splunk_event(self.RECORD)
        assert event["source"] == "xagent-audit"
        assert event["event"]["action"] == "login"

    def test_to_elasticsearch_doc(self):
        doc = SIEMEventAdapter.to_elasticsearch_doc(self.RECORD)
        assert doc["source"] == "xagent-audit"
        assert "login" in doc["message"]

    def test_to_datadog_event(self):
        event = SIEMEventAdapter.to_datadog_event(self.RECORD)
        assert event["host"] == "xagent"
        assert "tenant:t1" in event["ddtags"]

    def test_to_syslog_message(self):
        msg = SIEMEventAdapter.to_syslog_message(self.RECORD)
        assert "<134>" in msg
        assert "action=login" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# ScheduledExportManager TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestScheduledExportManager:
    def _export(self, **kw):
        defaults = dict(name="test", frequency=ExportFrequency.DAILY,
                        format=ExportFormat.JSON)
        defaults.update(kw)
        return ScheduledExport(**defaults)

    def test_create_and_get(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        assert mgr.get_export(exp.id) is exp
        assert exp.next_export_at is not None

    def test_update_export(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        updated = mgr.update_export(exp.id, {"name": "new_name"})
        assert updated.name == "new_name"

    def test_update_export_not_found(self):
        mgr = ScheduledExportManager()
        assert mgr.update_export("nope", {"name": "x"}) is None

    def test_delete_export(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        assert mgr.delete_export(exp.id) is True
        assert mgr.delete_export(exp.id) is False

    def test_list_exports(self):
        mgr = ScheduledExportManager()
        mgr.create_export(self._export(name="a"))
        mgr.create_export(self._export(name="b"))
        assert len(mgr.list_exports()) == 2

    def test_get_due_exports(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        exp.next_export_at = datetime.now(UTC) - timedelta(hours=1)
        due = mgr.get_due_exports()
        assert len(due) == 1

    def test_get_due_exports_disabled(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export(enabled=False))
        exp.next_export_at = datetime.now(UTC) - timedelta(hours=1)
        assert len(mgr.get_due_exports()) == 0

    def test_get_due_exports_future(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        exp.next_export_at = datetime.now(UTC) + timedelta(hours=1)
        assert len(mgr.get_due_exports()) == 0

    def test_record_export(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export())
        job = ExportJob(export_config_id=exp.id, status="completed",
                        completed_at=datetime.now(UTC))
        mgr.record_export(exp.id, job)
        assert exp.export_count == 1
        assert exp.last_export_at is not None

    def test_record_export_unknown_id(self):
        mgr = ScheduledExportManager()
        job = ExportJob(export_config_id="nope")
        mgr.record_export("nope", job)  # should not crash
        assert len(mgr._jobs) == 1

    def test_get_export_jobs_all(self):
        mgr = ScheduledExportManager()
        mgr._jobs.append(ExportJob(export_config_id="a"))
        mgr._jobs.append(ExportJob(export_config_id="b"))
        assert len(mgr.get_export_jobs()) == 2

    def test_get_export_jobs_filtered(self):
        mgr = ScheduledExportManager()
        mgr._jobs.append(ExportJob(export_config_id="a"))
        mgr._jobs.append(ExportJob(export_config_id="b"))
        assert len(mgr.get_export_jobs(export_id="a")) == 1

    def test_calculate_next_export_hourly(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export(frequency=ExportFrequency.HOURLY))
        assert exp.next_export_at > datetime.now(UTC)

    def test_calculate_next_export_daily_past_time(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export(frequency=ExportFrequency.DAILY,
                                             time_of_day="00:00"))
        # 00:00 is likely in the past today, so next should be tomorrow
        assert exp.next_export_at > datetime.now(UTC)

    def test_calculate_next_export_weekly(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export(frequency=ExportFrequency.WEEKLY,
                                             day_of_week=0, time_of_day="03:00"))
        assert exp.next_export_at is not None

    def test_calculate_next_export_monthly(self):
        mgr = ScheduledExportManager()
        exp = mgr.create_export(self._export(frequency=ExportFrequency.MONTHLY,
                                             day_of_month=1, time_of_day="02:00"))
        assert exp.next_export_at is not None

    def test_calculate_next_export_monthly_december(self):
        mgr = ScheduledExportManager()
        exp = self._export(frequency=ExportFrequency.MONTHLY,
                           day_of_month=1, time_of_day="00:00")
        mgr._exports[exp.id] = exp
        # Simulate December
        with patch("backend.app.core.audit_export.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 15, tzinfo=UTC)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mgr._calculate_next_export(exp)
        assert exp.next_export_at.month == 1
        assert exp.next_export_at.year == 2026

    def test_persistence(self, tmp_path):
        path = tmp_path / "exports.jsonl"
        mgr = ScheduledExportManager(storage_path=path)
        exp = mgr.create_export(self._export(name="persist"))
        # Reload
        mgr2 = ScheduledExportManager(storage_path=path)
        assert mgr2.get_export(exp.id) is not None
        assert mgr2.get_export(exp.id).name == "persist"


# ═══════════════════════════════════════════════════════════════════════════════
# ExternalSystemIntegrationManager TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestExternalSystemIntegrationManager:
    def _integ(self, **kw):
        defaults = dict(name="test", system_type=ExternalSystemType.WEBHOOK,
                        endpoint="http://localhost:9999")
        defaults.update(kw)
        return ExternalSystemIntegration(**defaults)

    def test_create_and_get(self):
        mgr = ExternalSystemIntegrationManager()
        integ = mgr.create_integration(self._integ())
        assert mgr.get_integration(integ.id) is integ

    def test_update_integration(self):
        mgr = ExternalSystemIntegrationManager()
        integ = mgr.create_integration(self._integ())
        updated = mgr.update_integration(integ.id, {"name": "new"})
        assert updated.name == "new"

    def test_update_integration_not_found(self):
        mgr = ExternalSystemIntegrationManager()
        assert mgr.update_integration("nope", {}) is None

    def test_delete_integration(self):
        mgr = ExternalSystemIntegrationManager()
        integ = mgr.create_integration(self._integ())
        assert mgr.delete_integration(integ.id) is True
        assert mgr.delete_integration(integ.id) is False

    def test_list_integrations(self):
        mgr = ExternalSystemIntegrationManager()
        mgr.create_integration(self._integ(name="a"))
        mgr.create_integration(self._integ(name="b"))
        assert len(mgr.list_integrations()) == 2

    async def test_send_event_enabled(self):
        mgr = ExternalSystemIntegrationManager()
        mgr.create_integration(self._integ())
        await mgr.send_event({"action": "login"})
        assert len(mgr._event_queue) == 1

    async def test_send_event_disabled(self):
        mgr = ExternalSystemIntegrationManager()
        mgr.create_integration(self._integ(enabled=False))
        await mgr.send_event({"action": "login"})
        assert len(mgr._event_queue) == 0

    async def test_send_event_include_filter(self):
        mgr = ExternalSystemIntegrationManager()
        mgr.create_integration(self._integ(include_actions=["logout"]))
        await mgr.send_event({"action": "login"})
        assert len(mgr._event_queue) == 0

    async def test_send_event_exclude_filter(self):
        mgr = ExternalSystemIntegrationManager()
        mgr.create_integration(self._integ(exclude_actions=["login"]))
        await mgr.send_event({"action": "login"})
        assert len(mgr._event_queue) == 0

    async def test_flush_events_empty(self):
        mgr = ExternalSystemIntegrationManager()
        await mgr.flush_events()  # no crash

    async def test_flush_events_sends(self):
        mgr = ExternalSystemIntegrationManager()
        integ = mgr.create_integration(self._integ(
            system_type=ExternalSystemType.WEBHOOK))
        mgr._event_queue.append({"integration_id": integ.id,
                                  "record": {"action": "x"},
                                  "timestamp": datetime.now(UTC)})
        with patch.object(mgr, "_send_to_integration", new_callable=AsyncMock):
            await mgr.flush_events()
        assert len(mgr._event_queue) == 0

    def test_persistence(self, tmp_path):
        path = tmp_path / "integrations.jsonl"
        mgr = ExternalSystemIntegrationManager(storage_path=path)
        integ = mgr.create_integration(self._integ(name="persist"))
        mgr2 = ExternalSystemIntegrationManager(storage_path=path)
        assert mgr2.get_integration(integ.id).name == "persist"


# ═══════════════════════════════════════════════════════════════════════════════
# RFC5424Formatter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRFC5424Formatter:
    def test_format_basic(self):
        fmt = RFC5424Formatter(hostname="testhost", app_name="app")
        record = {"action": "login", "outcome": "success", "tenant_id": "t1",
                  "created_at": "2025-01-01T12:00:00+00:00", "id": "rec1"}
        msg = fmt.format(record)
        assert "<110>1" in msg  # facility=13, severity=6 -> 13*8+6=110
        assert "testhost" in msg
        assert "login" in msg

    def test_severity_for_various_outcomes(self):
        fmt = RFC5424Formatter()
        assert fmt.severity_for({"outcome": "success"}) == 6
        assert fmt.severity_for({"outcome": "failure"}) == 4
        assert fmt.severity_for({"outcome": "error"}) == 3
        assert fmt.severity_for({"outcome": "partial"}) == 5
        assert fmt.severity_for({}) == 6  # default

    def test_format_timestamp_datetime(self):
        ts = RFC5424Formatter._format_timestamp(datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC))
        assert "2025-06-15T10:30:00" in ts

    def test_format_timestamp_string(self):
        ts = RFC5424Formatter._format_timestamp("2025-06-15T10:30:00+00:00")
        assert "2025-06-15" in ts

    def test_format_timestamp_invalid(self):
        ts = RFC5424Formatter._format_timestamp("not-a-date")
        assert "T" in ts  # falls back to now

    def test_format_timestamp_naive(self):
        ts = RFC5424Formatter._format_timestamp(datetime(2025, 1, 1, 0, 0, 0))
        assert "Z" in ts

    def test_escape_sd(self):
        assert RFC5424Formatter._escape_sd('a"b]c\\d') == 'a\\"b\\]c\\\\d'

    def test_format_no_sd_fields(self):
        fmt = RFC5424Formatter(hostname="h")
        record = {"action": None, "outcome": "success"}
        msg = fmt.format(record)
        assert " - " in msg  # structured_data = "-"


# ═══════════════════════════════════════════════════════════════════════════════
# SyslogExporter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSyslogExporter:
    def test_invalid_protocol(self):
        with pytest.raises(ValueError):
            SyslogExporter("localhost", protocol="icmp")

    def test_udp_send(self):
        exp = SyslogExporter("127.0.0.1", 15140, protocol="udp")
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)
            exp._send_udp(["<110>1 msg"])
            mock_sock.sendto.assert_called_once()

    def test_tcp_send(self):
        exp = SyslogExporter("127.0.0.1", 15141, protocol="tcp")
        with patch("socket.create_connection") as mock_conn:
            mock_sock = MagicMock()
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            exp._send_tcp(["<110>1 msg1", "<110>1 msg2"])
            mock_sock.sendall.assert_called_once()

    async def test_send_udp_async(self):
        exp = SyslogExporter("127.0.0.1", 15142, protocol="udp")
        with patch.object(exp, "_send_udp") as mock:
            await exp.send([{"action": "x", "outcome": "success"}])
            mock.assert_called_once()

    async def test_send_tcp_async(self):
        exp = SyslogExporter("127.0.0.1", 15143, protocol="tcp")
        with patch.object(exp, "_send_tcp") as mock:
            await exp.send([{"action": "x", "outcome": "success"}])
            mock.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# WebhookExporter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookExporter:
    async def test_send_success(self):
        exp = WebhookExporter("http://example.com/hook")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        exp._client = mock_client
        await exp.send([{"action": "test"}])
        mock_client.post.assert_called_once()

    async def test_send_with_bearer_and_hmac(self):
        exp = WebhookExporter("http://example.com/hook",
                              bearer_token="tok", hmac_secret="sec")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        exp._client = mock_client
        await exp.send([{"action": "test"}])
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert "Authorization" in headers
        assert "X-XAgent-Signature-256" in headers

    async def test_send_failure(self):
        exp = WebhookExporter("http://example.com/hook")
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        exp._client = mock_client
        with pytest.raises(RuntimeError, match="webhook export failed"):
            await exp.send([{"action": "test"}])

    async def test_close(self):
        exp = WebhookExporter("http://example.com")
        mock_client = AsyncMock()
        exp._client = mock_client
        await exp.close()
        mock_client.aclose.assert_called_once()
        assert exp._client is None

    async def test_close_no_client(self):
        exp = WebhookExporter("http://example.com")
        await exp.close()  # no crash


# ═══════════════════════════════════════════════════════════════════════════════
# S3WormExporter TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestS3WormExporter:
    def test_available_with_client(self):
        exp = S3WormExporter("bucket", client=MagicMock())
        assert exp.available is True

    def test_not_available_no_boto3(self):
        with patch.dict("sys.modules", {"boto3": None}):
            exp = S3WormExporter("bucket")
            exp._boto3 = None
            exp._client = None
            assert exp.available is False

    def test_get_client_raises_without_boto3(self):
        exp = S3WormExporter("bucket")
        exp._boto3 = None
        exp._client = None
        with pytest.raises(AuditExportUnavailable):
            exp._get_client()

    async def test_send_with_mock_client(self):
        mock_client = MagicMock()
        exp = S3WormExporter("my-bucket", client=mock_client, prefix="logs/")
        await exp.send([{"action": "test"}])
        mock_client.put_object.assert_called_once()
        call_kw = mock_client.put_object.call_args[1]
        assert call_kw["Bucket"] == "my-bucket"
        assert "logs/" in call_kw["Key"]


# ═══════════════════════════════════════════════════════════════════════════════
# AuditShipper TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditShipper:
    def test_enqueue_success(self):
        shipper = AuditShipper([])
        assert shipper.enqueue({"action": "x"}) is True
        assert shipper._stats["queued"] == 1

    def test_enqueue_full_queue(self):
        cfg = AuditShipperConfig(queue_maxsize=1)
        shipper = AuditShipper([], config=cfg)
        shipper.enqueue({"a": 1})
        result = shipper.enqueue({"a": 2})
        assert result is False
        assert shipper._stats["dropped"] == 1

    def test_enqueue_event_pydantic(self):
        shipper = AuditShipper([])
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"action": "test"}
        assert shipper.enqueue_event(mock_model) is True
        mock_model.model_dump.assert_called_once_with(mode="json")

    def test_enqueue_event_dict(self):
        shipper = AuditShipper([])
        assert shipper.enqueue_event({"action": "x"}) is True

    def test_pending(self):
        shipper = AuditShipper([])
        shipper.enqueue({"a": 1})
        assert shipper.pending == 1

    def test_stats(self):
        shipper = AuditShipper([])
        s = shipper.stats()
        assert "queued" in s
        assert "exporters" in s

    async def test_start_stop(self):
        shipper = AuditShipper([])
        await shipper.start()
        assert shipper._task is not None
        await shipper.start()  # idempotent
        await shipper.stop()
        assert shipper._task is None

    async def test_stop_without_start(self):
        shipper = AuditShipper([])
        await shipper.stop()  # no crash

    async def test_send_with_retry_success(self):
        exporter = AsyncMock(spec=AuditExporter)
        exporter.name = "test"
        exporter.send = AsyncMock()
        shipper = AuditShipper([exporter])
        await shipper._send_with_retry(exporter, [{"a": 1}])
        assert shipper._stats["sent"] == 1

    async def test_send_with_retry_exhausted(self):
        exporter = AsyncMock(spec=AuditExporter)
        exporter.name = "fail_exp"
        exporter.send = AsyncMock(side_effect=RuntimeError("fail"))
        cfg = AuditShipperConfig(retry_attempts=2, retry_base_delay_seconds=0.01)
        shipper = AuditShipper([exporter], config=cfg)
        await shipper._send_with_retry(exporter, [{"a": 1}])
        assert shipper._stats["failed_batches"] == 1
        assert shipper._stats["dead_lettered"] == 1

    def test_dead_letter_no_path(self):
        shipper = AuditShipper([])
        shipper._dead_letter([{"a": 1}], reason="test")
        assert shipper._stats["dead_lettered"] == 1

    def test_dead_letter_with_path(self, tmp_path):
        dl = tmp_path / "dead.jsonl"
        cfg = AuditShipperConfig(dead_letter_path=dl)
        shipper = AuditShipper([], config=cfg)
        shipper._dead_letter([{"a": 1}], reason="test")
        assert dl.exists()
        content = dl.read_text()
        assert "test" in content

    def test_dead_letter_os_error(self, tmp_path):
        # Use an invalid path that will cause OSError
        cfg = AuditShipperConfig(dead_letter_path=Path("/nonexistent_root_xyz/dead.jsonl"))
        shipper = AuditShipper([], config=cfg)
        # Should not raise
        shipper._dead_letter([{"a": 1}], reason="err")


# ═══════════════════════════════════════════════════════════════════════════════
# build_shipper TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildShipper:
    def test_build_empty(self):
        channels = AuditShipperChannels()
        shipper = build_shipper(channels)
        assert len(shipper.exporters) == 0

    def test_build_syslog(self):
        channels = AuditShipperChannels(
            syslog=SyslogChannelConfig(enabled=True, host="10.0.0.1", port=1514))
        shipper = build_shipper(channels)
        assert len(shipper.exporters) == 1
        assert shipper.exporters[0].name == "syslog"

    def test_build_webhook(self):
        channels = AuditShipperChannels(
            webhook=WebhookChannelConfig(enabled=True, url="http://x.com/hook",
                                         bearer_token="tok"))
        shipper = build_shipper(channels)
        assert len(shipper.exporters) == 1
        assert shipper.exporters[0].name == "webhook"

    def test_build_s3(self):
        channels = AuditShipperChannels(
            s3_worm=S3WormChannelConfig(enabled=True, bucket="b"))
        shipper = build_shipper(channels)
        assert len(shipper.exporters) == 1
        assert shipper.exporters[0].name == "s3_worm"

    def test_build_all(self):
        channels = AuditShipperChannels(
            syslog=SyslogChannelConfig(enabled=True),
            webhook=WebhookChannelConfig(enabled=True, url="http://x.com"),
            s3_worm=S3WormChannelConfig(enabled=True, bucket="b"))
        shipper = build_shipper(channels)
        assert len(shipper.exporters) == 3
