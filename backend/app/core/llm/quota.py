"""Tenant/user-level token quota enforcement for the LLM router (P1-08).

Metering is token-based: every successful chat accumulates ``tokens_used``
(and cost, for reporting) against a tenant bucket and a user bucket for the
current period window. When a bucket reaches its limit the request is rejected
BEFORE any provider call with :class:`QuotaExceededError` — a deliberate
``RuntimeError`` (not ``LLMBackendError``) so the router's provider-fallback
loop does not mask the rejection by silently trying the next backend.

Storage reuses the existing cache abstraction
(``backend.app.core.cache.get_cache_manager``) — L1 in-memory today, L2 Redis
when configured — instead of introducing a new storage system.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from backend.app.core.cache import get_cache_manager

logger = logging.getLogger(__name__)

VALID_PERIODS = ("day", "month", "total")

# TTL buffer so a period bucket outlives its window slightly (clock skew,
# late writes). "total" buckets never expire.
_PERIOD_TTL_SECONDS = {
    "day": 2 * 24 * 3600,
    "month": 32 * 24 * 3600,
    "total": None,
}


class QuotaExceededError(RuntimeError):
    """Raised when a tenant or user has exhausted its token quota."""

    def __init__(
        self,
        *,
        scope: str,
        identifier: str,
        used_tokens: int,
        limit_tokens: int,
        period: str,
    ) -> None:
        self.scope = scope
        self.identifier = identifier
        self.used_tokens = used_tokens
        self.limit_tokens = limit_tokens
        self.period = period
        super().__init__(
            f"LLM token quota exceeded for {scope} '{identifier}': "
            f"{used_tokens}/{limit_tokens} tokens already used in the current "
            f"{period} window. Request rejected before any provider call; "
            f"raise the quota (XAGENT_LLM_QUOTA_* / quota overrides) or wait "
            f"for the next window."
        )


class TokenQuotaManager:
    """Accumulate per-tenant / per-user token usage and enforce limits."""

    def __init__(
        self,
        cache_manager: Any | None = None,
        *,
        enabled: bool = True,
        period: str = "day",
        default_tenant_tokens: int = 1_000_000,
        default_user_tokens: int = 100_000,
        tenant_overrides: dict[str, int] | None = None,
        user_overrides: dict[str, int] | None = None,
    ) -> None:
        if period not in VALID_PERIODS:
            raise ValueError(
                f"invalid quota period '{period}'; valid: {', '.join(VALID_PERIODS)}"
            )
        self._cache = cache_manager or get_cache_manager()
        self.enabled = enabled
        self.period = period
        self.default_tenant_tokens = int(default_tenant_tokens)
        self.default_user_tokens = int(default_user_tokens)
        self._tenant_overrides = dict(tenant_overrides or {})
        self._user_overrides = dict(user_overrides or {})
        # Serializes read-modify-write against the non-atomic cache backend.
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def set_tenant_quota(self, tenant_id: str, tokens: int) -> None:
        """Override the per-period token limit for a tenant."""
        self._tenant_overrides[tenant_id] = int(tokens)

    def set_user_quota(self, user_id: str, tokens: int) -> None:
        """Override the per-period token limit for a user."""
        self._user_overrides[user_id] = int(tokens)

    def tenant_limit(self, tenant_id: str) -> int:
        return self._tenant_overrides.get(tenant_id, self.default_tenant_tokens)

    def user_limit(self, user_id: str) -> int:
        return self._user_overrides.get(user_id, self.default_user_tokens)

    # ------------------------------------------------------------------
    # Bucket addressing
    # ------------------------------------------------------------------
    def _period_key(self) -> str:
        now = datetime.now()
        if self.period == "day":
            return now.strftime("%Y%m%d")
        if self.period == "month":
            return now.strftime("%Y%m")
        return "all"

    def _bucket_key(self, scope: str, identifier: str) -> str:
        return f"llm:quota:{self.period}:{self._period_key()}:{scope}:{identifier}"

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    async def check_quota(
        self,
        tenant_id: str | None,
        user_id: str | None,
    ) -> None:
        """Raise QuotaExceededError if the tenant or user is out of tokens."""
        if not self.enabled:
            return
        tenant = tenant_id or "default"
        user = user_id or "anonymous"

        tenant_usage = await self._read_bucket("tenant", tenant)
        tenant_limit = self.tenant_limit(tenant)
        if tenant_usage["tokens"] >= tenant_limit:
            raise QuotaExceededError(
                scope="tenant",
                identifier=tenant,
                used_tokens=tenant_usage["tokens"],
                limit_tokens=tenant_limit,
                period=self.period,
            )

        user_usage = await self._read_bucket("user", user)
        user_limit = self.user_limit(user)
        if user_usage["tokens"] >= user_limit:
            raise QuotaExceededError(
                scope="user",
                identifier=user,
                used_tokens=user_usage["tokens"],
                limit_tokens=user_limit,
                period=self.period,
            )

    async def record_usage(
        self,
        tenant_id: str | None,
        user_id: str | None,
        tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        """Accumulate tokens (and cost) against tenant and user buckets."""
        if not self.enabled or tokens <= 0:
            return
        tenant = tenant_id or "default"
        user = user_id or "anonymous"
        async with self._lock:
            await self._accumulate("tenant", tenant, tokens, cost_usd)
            await self._accumulate("user", user, tokens, cost_usd)

    async def get_status(
        self,
        tenant_id: str | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        """Return current usage vs limits for both scopes (observability)."""
        tenant = tenant_id or "default"
        user = user_id or "anonymous"
        tenant_usage = await self._read_bucket("tenant", tenant)
        user_usage = await self._read_bucket("user", user)
        return {
            "enabled": self.enabled,
            "period": self.period,
            "period_key": self._period_key(),
            "tenant": {
                "id": tenant,
                "used_tokens": tenant_usage["tokens"],
                "limit_tokens": self.tenant_limit(tenant),
                "cost_usd": tenant_usage["cost_usd"],
            },
            "user": {
                "id": user,
                "used_tokens": user_usage["tokens"],
                "limit_tokens": self.user_limit(user),
                "cost_usd": user_usage["cost_usd"],
            },
        }

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------
    async def _read_bucket(self, scope: str, identifier: str) -> dict[str, Any]:
        key = self._bucket_key(scope, identifier)
        raw = await self._cache.get(key)
        if isinstance(raw, dict):
            return {
                "tokens": int(raw.get("tokens", 0)),
                "cost_usd": float(raw.get("cost_usd", 0.0)),
            }
        return {"tokens": 0, "cost_usd": 0.0}

    async def _accumulate(
        self,
        scope: str,
        identifier: str,
        tokens: int,
        cost_usd: float,
    ) -> None:
        key = self._bucket_key(scope, identifier)
        bucket = await self._read_bucket(scope, identifier)
        bucket["tokens"] += int(tokens)
        bucket["cost_usd"] += float(cost_usd)
        bucket["updated_at"] = datetime.now().isoformat()
        await self._cache.set(key, bucket, ttl=_PERIOD_TTL_SECONDS[self.period])


def build_quota_manager_from_config(
    *,
    enabled: bool,
    period: str = "day",
    default_tenant_tokens: int = 1_000_000,
    default_user_tokens: int = 100_000,
    tenant_overrides: dict[str, int] | None = None,
    user_overrides: dict[str, int] | None = None,
) -> TokenQuotaManager | None:
    """Factory used by build_llm_router.

    Returns None when quotas are disabled so routers stay zero-overhead in the
    default configuration.
    """
    if not enabled:
        return None
    return TokenQuotaManager(
        enabled=True,
        period=period,
        default_tenant_tokens=default_tenant_tokens,
        default_user_tokens=default_user_tokens,
        tenant_overrides=tenant_overrides,
        user_overrides=user_overrides,
    )


def get_quota_manager() -> TokenQuotaManager | None:
    """Return the quota manager attached to the shared LLM router (P1-08).

    Observability accessor for API layers (status/tenant-quota endpoints).
    Returns None when quotas are disabled (the default) or the shared router
    cannot be built (e.g. no LLM credentials configured). Bucket storage
    reuses the shared cache manager, so any router built via
    ``build_llm_router`` observes the same usage data.
    """
    try:
        from backend.app.dependencies import get_llm_router

        return getattr(get_llm_router(), "quota_manager", None)
    except Exception:  # pragma: no cover - router build failures are environmental
        logger.debug("get_quota_manager: shared LLM router unavailable", exc_info=True)
        return None
