"""Unit tests for tenant-level quota management (backend.app.core.tenant_quota)."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core.tenant_quota import (
    QuotaLimits,
    TenantQuotaManager,
)


@pytest.fixture()
def quota_file(tmp_path: Path) -> Path:
    return tmp_path / "quotas.json"


@pytest.fixture()
def manager(quota_file: Path) -> TenantQuotaManager:
    return TenantQuotaManager(store_path=quota_file)


class TestQuotaLimits:
    def test_defaults(self):
        limits = QuotaLimits()
        assert limits.max_agents == 10
        assert limits.max_workflows == 20
        assert limits.max_api_calls_per_day == 10_000
        assert limits.max_memory_items == 5_000
        assert limits.max_concurrent_runs == 5
        assert limits.max_storage_mb == 1024


class TestTenantQuotaManager:
    def test_get_limits_default(self, manager: TenantQuotaManager):
        limits = manager.get_limits("tenant-a")
        assert limits.max_agents == 10

    def test_set_and_get_limits(self, manager: TenantQuotaManager):
        new_limits = QuotaLimits(max_agents=50, max_api_calls_per_day=99_999)
        manager.set_limits("tenant-b", new_limits)
        fetched = manager.get_limits("tenant-b")
        assert fetched.max_agents == 50
        assert fetched.max_api_calls_per_day == 99_999

    def test_check_quota_allowed(self, manager: TenantQuotaManager):
        allowed, reason = manager.check_quota("t1", "agents")
        assert allowed is True
        assert reason == "OK"

    def test_check_quota_exceeded(self, manager: TenantQuotaManager):
        # Set limit to 2 and increment to 2
        manager.set_limits("t2", QuotaLimits(max_agents=2))
        manager.increment_usage("t2", "agents")
        manager.increment_usage("t2", "agents")
        allowed, reason = manager.check_quota("t2", "agents")
        assert allowed is False
        assert "exceeded" in reason.lower()

    def test_increment_and_get_usage(self, manager: TenantQuotaManager):
        manager.increment_usage("t3", "workflows", 5)
        usage = manager.get_usage("t3")
        assert usage.workflows_count == 5

    def test_decrement_usage(self, manager: TenantQuotaManager):
        manager.increment_usage("t4", "concurrent_runs", 3)
        manager.decrement_usage("t4", "concurrent_runs", 1)
        usage = manager.get_usage("t4")
        assert usage.concurrent_runs == 2

    def test_decrement_floor_zero(self, manager: TenantQuotaManager):
        manager.decrement_usage("t5", "concurrent_runs", 10)
        usage = manager.get_usage("t5")
        assert usage.concurrent_runs == 0

    def test_unknown_resource_allowed(self, manager: TenantQuotaManager):
        allowed, reason = manager.check_quota("t6", "unknown_thing")
        assert allowed is True
        assert "not quota-controlled" in reason

    def test_daily_reset(self, manager: TenantQuotaManager):
        manager.increment_usage("t7", "api_calls", 100)
        usage = manager.get_usage("t7")
        assert usage.api_calls_today == 100
        # Simulate yesterday's record by backdating last_reset_date
        record = manager._tenants["t7"]
        record.usage.last_reset_date = "2020-01-01"
        # Force reset
        count = manager.reset_daily_counters()
        assert count >= 1
        usage = manager.get_usage("t7")
        assert usage.api_calls_today == 0

    def test_persistence(self, quota_file: Path):
        m1 = TenantQuotaManager(store_path=quota_file)
        m1.set_limits("persist-t", QuotaLimits(max_agents=42))
        m1.increment_usage("persist-t", "agents", 7)

        # New instance loads from file
        m2 = TenantQuotaManager(store_path=quota_file)
        assert m2.get_limits("persist-t").max_agents == 42
        assert m2.get_usage("persist-t").agents_count == 7

    def test_full_report(self, manager: TenantQuotaManager):
        manager.increment_usage("t8", "agents", 3)
        report = manager.get_full_report("t8")
        assert report["tenant_id"] == "t8"
        assert "limits" in report
        assert "usage" in report
        assert "breakdown" in report
        assert report["breakdown"]["agents"]["used"] == 3
        assert report["breakdown"]["agents"]["limit"] == 10
        assert report["breakdown"]["agents"]["remaining"] == 7

    def test_storage_float_increment(self, manager: TenantQuotaManager):
        manager.increment_usage("t9", "storage", 128.5)
        usage = manager.get_usage("t9")
        assert usage.storage_used_mb == 128.5
