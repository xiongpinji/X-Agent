"""Deep coverage tests for backend/app/services/subscription.py."""
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.services.subscription import (
    SubscriptionService,
    get_subscription_service,
)
from backend.app.models.subscription import (
    QuotaModel,
    SubscriptionHistoryModel,
    SubscriptionModel,
    SubscriptionPlan,
    SubscriptionStatus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN_CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanConfig:
    def test_free_plan(self):
        config = SubscriptionService.PLAN_CONFIG[SubscriptionPlan.FREE]
        assert config["price_per_month"] == 0.0
        assert config["api_calls_limit"] == 1000

    def test_starter_plan(self):
        config = SubscriptionService.PLAN_CONFIG[SubscriptionPlan.STARTER]
        assert config["price_per_month"] == 9.99

    def test_professional_plan(self):
        config = SubscriptionService.PLAN_CONFIG[SubscriptionPlan.PROFESSIONAL]
        assert config["price_per_month"] == 49.99

    def test_enterprise_plan(self):
        config = SubscriptionService.PLAN_CONFIG[SubscriptionPlan.ENTERPRISE]
        assert config["price_per_month"] == 299.99
        assert config["concurrent_connections_limit"] == 100


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — create_subscription
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateSubscription:
    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_create_free_subscription(self, mock_sm):
        session = AsyncMock()
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.create_subscription("u1", "t1", SubscriptionPlan.FREE)
        assert result.plan == SubscriptionPlan.FREE
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.trial_end is None
        session.add.assert_called()

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_create_paid_subscription_with_trial(self, mock_sm):
        session = AsyncMock()
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.create_subscription("u1", "t1", SubscriptionPlan.STARTER, trial_days=7)
        assert result.plan == SubscriptionPlan.STARTER
        assert result.status == SubscriptionStatus.TRIAL
        assert result.trial_end is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — get_subscription / get_user_subscription
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSubscription:
    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_get_subscription_found(self, mock_sm):
        session = AsyncMock()
        sub = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = sub
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.get_subscription("sub1")
        assert result is sub

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_get_subscription_not_found(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.get_subscription("nope")
        assert result is None

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_get_user_subscription(self, mock_sm):
        session = AsyncMock()
        sub = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = sub
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.get_user_subscription("u1", "t1")
        assert result is sub


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — upgrade / downgrade
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpgradeDowngrade:
    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_upgrade_subscription(self, mock_sm):
        session = AsyncMock()
        sub = MagicMock()
        sub.plan = SubscriptionPlan.FREE
        sub.user_id = "u1"
        sub.tenant_id = "t1"
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = sub
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with patch.object(svc, "_update_quota", new_callable=AsyncMock):
            with patch.object(svc, "_record_history", new_callable=AsyncMock):
                result = await svc.upgrade_subscription("sub1", SubscriptionPlan.PROFESSIONAL)
        assert result.plan == SubscriptionPlan.PROFESSIONAL
        assert result.price_per_month == 49.99

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_upgrade_not_found(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with pytest.raises(ValueError, match="订阅不存在"):
            await svc.upgrade_subscription("nope", SubscriptionPlan.PROFESSIONAL)

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_downgrade_subscription(self, mock_sm):
        session = AsyncMock()
        sub = MagicMock()
        sub.plan = SubscriptionPlan.PROFESSIONAL
        sub.user_id = "u1"
        sub.tenant_id = "t1"
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = sub
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with patch.object(svc, "_update_quota", new_callable=AsyncMock):
            with patch.object(svc, "_record_history", new_callable=AsyncMock):
                result = await svc.downgrade_subscription("sub1", SubscriptionPlan.STARTER)
        assert result.plan == SubscriptionPlan.STARTER

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_downgrade_not_found(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with pytest.raises(ValueError, match="订阅不存在"):
            await svc.downgrade_subscription("nope", SubscriptionPlan.FREE)


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — pause / resume / cancel / renew
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycleOperations:
    def _mock_session_with_sub(self, mock_sm, status=SubscriptionStatus.ACTIVE):
        session = AsyncMock()
        sub = MagicMock()
        sub.status = status
        sub.user_id = "u1"
        sub.tenant_id = "t1"
        sub.renewal_failed_count = 0
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = sub
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        return session, sub

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_pause_subscription(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm)
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.pause_subscription("sub1")
        assert result.status == SubscriptionStatus.PAUSED
        assert result.paused_at is not None

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_pause_not_found(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with pytest.raises(ValueError, match="订阅不存在"):
            await svc.pause_subscription("nope")

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_resume_subscription(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm, SubscriptionStatus.PAUSED)
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.resume_subscription("sub1")
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.paused_at is None

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_cancel_subscription(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm)
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.cancel_subscription("sub1")
        assert result.status == SubscriptionStatus.CANCELLED
        assert result.auto_renew is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_renew_subscription(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm, SubscriptionStatus.EXPIRED)
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.renew_subscription("sub1")
        assert result.status == SubscriptionStatus.ACTIVE
        assert result.renewal_failed_count == 0

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_mark_renewal_failed(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm)
        sub.renewal_failed_count = 2
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.mark_renewal_failed("sub1")
        assert result.renewal_failed_count == 3
        assert result.status == SubscriptionStatus.EXPIRED

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_mark_renewal_failed_under_threshold(self, mock_sm):
        session, sub = self._mock_session_with_sub(mock_sm)
        sub.renewal_failed_count = 0
        svc = SubscriptionService()
        with patch.object(svc, "_record_history", new_callable=AsyncMock):
            result = await svc.mark_renewal_failed("sub1")
        assert result.renewal_failed_count == 1
        assert result.status == SubscriptionStatus.ACTIVE


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — quota operations
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuotaOperations:
    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_get_quota(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.get_quota("sub1")
        assert result is quota

    @pytest.mark.asyncio
    async def test_check_quota_api_calls(self):
        svc = SubscriptionService()
        quota = MagicMock()
        quota.api_calls_used = 100
        quota.api_calls_limit = 1000
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=quota):
            assert await svc.check_quota("sub1", "api_calls", 50) is True
            assert await svc.check_quota("sub1", "api_calls", 950) is False

    @pytest.mark.asyncio
    async def test_check_quota_tokens(self):
        svc = SubscriptionService()
        quota = MagicMock()
        quota.tokens_used = 500
        quota.tokens_limit = 1000
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=quota):
            assert await svc.check_quota("sub1", "tokens", 400) is True
            assert await svc.check_quota("sub1", "tokens", 600) is False

    @pytest.mark.asyncio
    async def test_check_quota_storage(self):
        svc = SubscriptionService()
        quota = MagicMock()
        quota.storage_used_mb = 50
        quota.storage_limit_mb = 100
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=quota):
            assert await svc.check_quota("sub1", "storage", 40) is True
            assert await svc.check_quota("sub1", "storage", 60) is False

    @pytest.mark.asyncio
    async def test_check_quota_concurrent(self):
        svc = SubscriptionService()
        quota = MagicMock()
        quota.concurrent_connections_current = 5
        quota.concurrent_connections_limit = 10
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=quota):
            assert await svc.check_quota("sub1", "concurrent_connections", 3) is True
            assert await svc.check_quota("sub1", "concurrent_connections", 10) is False

    @pytest.mark.asyncio
    async def test_check_quota_no_quota(self):
        svc = SubscriptionService()
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=None):
            assert await svc.check_quota("sub1", "api_calls") is False

    @pytest.mark.asyncio
    async def test_check_quota_unknown_type(self):
        svc = SubscriptionService()
        quota = MagicMock()
        with patch.object(svc, "get_quota", new_callable=AsyncMock, return_value=quota):
            assert await svc.check_quota("sub1", "unknown") is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_consume_quota_api_calls(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        quota.api_calls_used = 100
        quota.api_calls_limit = 1000
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.consume_quota("sub1", "api_calls", 50)
        assert result is True
        assert quota.api_calls_used == 150

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_consume_quota_exceeded(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        quota.api_calls_used = 990
        quota.api_calls_limit = 1000
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.consume_quota("sub1", "api_calls", 50)
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_consume_quota_no_quota(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.consume_quota("sub1", "api_calls")
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_consume_quota_unknown_type(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.consume_quota("sub1", "unknown")
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_release_quota(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        quota.concurrent_connections_current = 5
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.release_quota("sub1", "concurrent_connections", 2)
        assert result is True
        assert quota.concurrent_connections_current == 3

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_release_quota_non_concurrent(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.release_quota("sub1", "api_calls")
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_reset_quota(self, mock_sm):
        session = AsyncMock()
        quota = MagicMock()
        quota.api_calls_used = 500
        quota.tokens_used = 10000
        quota.storage_used_mb = 50
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = quota
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.reset_quota("sub1")
        assert result.api_calls_used == 0
        assert result.tokens_used == 0
        assert result.storage_used_mb == 0

    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_reset_quota_not_found(self, mock_sm):
        session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        with pytest.raises(ValueError, match="配额不存在"):
            await svc.reset_quota("nope")


# ═══════════════════════════════════════════════════════════════════════════════
# SubscriptionService — history
# ═══════════════════════════════════════════════════════════════════════════════

class TestSubscriptionHistory:
    @pytest.mark.asyncio
    @patch("backend.app.services.subscription.SessionManager")
    async def test_get_history(self, mock_sm):
        session = AsyncMock()
        history = [MagicMock(), MagicMock()]
        exec_result = MagicMock()
        exec_result.scalars.return_value.all.return_value = history
        session.execute = AsyncMock(return_value=exec_result)
        mock_sm.get_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_sm.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = SubscriptionService()
        result = await svc.get_subscription_history("sub1", limit=10, offset=0)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# get_subscription_service
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSubscriptionService:
    def test_singleton(self):
        import backend.app.services.subscription as mod
        mod._subscription_service = None
        svc1 = get_subscription_service()
        svc2 = get_subscription_service()
        assert svc1 is svc2
        mod._subscription_service = None  # cleanup
