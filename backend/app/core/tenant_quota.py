"""Tenant Quota Manager — enforce usage limits per tenant.

Lightweight, file-backed quota tracking for commercial deployment.
Operates independently of the subscription/billing QuotaManager (which
requires a database). This module provides:

- Per-tenant resource limits (agents, workflows, API calls/day, memory, etc.)
- File-based usage persistence (JSON)
- Daily counter reset via scheduler hook
- Middleware-friendly synchronous check/increment API
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Data Models ────────────────────────────────────────────────────────────────


@dataclass
class QuotaLimits:
    """Per-tenant resource limits."""

    max_agents: int = 10
    max_workflows: int = 20
    max_api_calls_per_day: int = 10_000
    max_memory_items: int = 5_000
    max_concurrent_runs: int = 5
    max_storage_mb: int = 1024


@dataclass
class UsageStats:
    """Current usage snapshot for a tenant."""

    agents_count: int = 0
    workflows_count: int = 0
    api_calls_today: int = 0
    memory_items_count: int = 0
    concurrent_runs: int = 0
    storage_used_mb: float = 0.0
    last_reset_date: str = ""  # ISO date string of last daily reset


@dataclass
class _TenantRecord:
    """Internal persistence record per tenant."""

    limits: QuotaLimits = field(default_factory=QuotaLimits)
    usage: UsageStats = field(default_factory=UsageStats)


# ─── Resource Mapping ───────────────────────────────────────────────────────────

# Maps resource name → (limit_field, usage_field)
_RESOURCE_MAP: dict[str, tuple[str, str]] = {
    "agents": ("max_agents", "agents_count"),
    "workflows": ("max_workflows", "workflows_count"),
    "api_calls": ("max_api_calls_per_day", "api_calls_today"),
    "memory_items": ("max_memory_items", "memory_items_count"),
    "concurrent_runs": ("max_concurrent_runs", "concurrent_runs"),
    "storage": ("max_storage_mb", "storage_used_mb"),
}


# ─── Quota Manager ──────────────────────────────────────────────────────────────


class TenantQuotaManager:
    """Enforce per-tenant resource quotas with file-based persistence.

    Thread-safe: all mutations are guarded by a reentrant lock.
    """

    def __init__(self, store_path: str | Path = "data/quotas.json") -> None:
        self._store_path = Path(store_path)
        self._lock = threading.RLock()
        self._tenants: dict[str, _TenantRecord] = {}
        self._load()

    # ─── Public API ─────────────────────────────────────────────────────────

    def get_limits(self, tenant_id: str) -> QuotaLimits:
        """Return the quota limits for a tenant (creates default if absent)."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            return record.limits

    def set_limits(self, tenant_id: str, limits: QuotaLimits) -> QuotaLimits:
        """Update quota limits for a tenant. Persists immediately."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            record.limits = limits
            self._save()
            return record.limits

    def get_usage(self, tenant_id: str) -> UsageStats:
        """Return current usage stats for a tenant."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            self._maybe_reset_daily(record)
            return record.usage

    def check_quota(self, tenant_id: str, resource: str) -> tuple[bool, str]:
        """Check if tenant can use more of a resource.

        Returns:
            (allowed, reason) — allowed=True means within quota.
        """
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            self._maybe_reset_daily(record)

            mapping = _RESOURCE_MAP.get(resource)
            if mapping is None:
                return True, f"Unknown resource '{resource}', not quota-controlled"

            limit_field, usage_field = mapping
            limit_val = getattr(record.limits, limit_field)
            usage_val = getattr(record.usage, usage_field)

            if usage_val >= limit_val:
                return False, (
                    f"Quota exceeded for '{resource}': "
                    f"used {usage_val}/{limit_val}"
                )
            return True, "OK"

    def increment_usage(self, tenant_id: str, resource: str, amount: int | float = 1) -> None:
        """Increment a usage counter for a tenant. Persists immediately."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            self._maybe_reset_daily(record)

            mapping = _RESOURCE_MAP.get(resource)
            if mapping is None:
                logger.warning("increment_usage: unknown resource '%s'", resource)
                return

            _, usage_field = mapping
            current = getattr(record.usage, usage_field)
            setattr(record.usage, usage_field, current + amount)
            self._save()

    def decrement_usage(self, tenant_id: str, resource: str, amount: int | float = 1) -> None:
        """Decrement a usage counter (e.g. concurrent_runs when a run finishes)."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            mapping = _RESOURCE_MAP.get(resource)
            if mapping is None:
                return
            _, usage_field = mapping
            current = getattr(record.usage, usage_field)
            setattr(record.usage, usage_field, max(0, current - amount))
            self._save()

    def reset_daily_counters(self) -> int:
        """Reset daily API call counts for all tenants.

        Called by scheduler (e.g. midnight cron). Returns number of tenants reset.
        """
        today = date.today().isoformat()
        count = 0
        with self._lock:
            for record in self._tenants.values():
                if record.usage.last_reset_date != today:
                    record.usage.api_calls_today = 0
                    record.usage.last_reset_date = today
                    count += 1
            if count:
                self._save()
        logger.info("Daily quota counters reset for %d tenant(s)", count)
        return count

    def get_full_report(self, tenant_id: str) -> dict[str, Any]:
        """Return a combined limits + usage report for API responses."""
        with self._lock:
            record = self._ensure_tenant(tenant_id)
            self._maybe_reset_daily(record)
            limits = asdict(record.limits)
            usage = asdict(record.usage)

        # Build per-resource breakdown
        breakdown: dict[str, dict[str, Any]] = {}
        for resource, (limit_field, usage_field) in _RESOURCE_MAP.items():
            limit_val = limits[limit_field]
            usage_val = usage[usage_field]
            pct = (usage_val / limit_val * 100) if limit_val else 0.0
            breakdown[resource] = {
                "used": usage_val,
                "limit": limit_val,
                "remaining": max(0, limit_val - usage_val),
                "usage_percent": round(pct, 1),
            }

        return {
            "tenant_id": tenant_id,
            "limits": limits,
            "usage": usage,
            "breakdown": breakdown,
        }

    # ─── Internal ───────────────────────────────────────────────────────────

    def _ensure_tenant(self, tenant_id: str) -> _TenantRecord:
        if tenant_id not in self._tenants:
            self._tenants[tenant_id] = _TenantRecord()
        return self._tenants[tenant_id]

    def _maybe_reset_daily(self, record: _TenantRecord) -> None:
        """Auto-reset daily counters if the date has rolled over."""
        today = date.today().isoformat()
        if record.usage.last_reset_date != today:
            record.usage.api_calls_today = 0
            record.usage.last_reset_date = today

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
            for tid, data in raw.items():
                limits = QuotaLimits(**data.get("limits", {}))
                usage = UsageStats(**data.get("usage", {}))
                self._tenants[tid] = _TenantRecord(limits=limits, usage=usage)
            logger.info("Loaded quota data for %d tenant(s) from %s", len(self._tenants), self._store_path)
        except Exception as exc:
            logger.error("Failed to load quota store %s: %s", self._store_path, exc)

    def _save(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, Any] = {}
            for tid, record in self._tenants.items():
                data[tid] = {
                    "limits": asdict(record.limits),
                    "usage": asdict(record.usage),
                }
            self._store_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to persist quota store %s: %s", self._store_path, exc)


# ─── Singleton ──────────────────────────────────────────────────────────────────

_instance: TenantQuotaManager | None = None
_instance_lock = threading.Lock()


def get_tenant_quota_manager() -> TenantQuotaManager:
    """Get or create the global TenantQuotaManager singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                from backend.app.settings import get_settings

                settings = get_settings()
                _instance = TenantQuotaManager(
                    store_path=settings.quota_store_path,
                )
    return _instance
