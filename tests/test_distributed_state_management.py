"""
单元测试 - Store类的CRUD操作
"""
import pytest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.models.user_store import UserStorePostgres
from backend.app.models.api_key_store import APIKeyStorePostgres
from backend.app.models.approval_store import ApprovalStorePostgres
from backend.app.models.rate_limiter import RateLimiterRedis
from backend.app.models.csrf_token_store import CSRFTokenStoreRedis


class TestUserStore:
    """用户存储测试"""

    @pytest.fixture
    async def user_store(self):
        return UserStorePostgres()

    @pytest.mark.asyncio
    async def test_create_user(self, user_store):
        """测试创建用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        user = await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
            full_name="Test User",
            role="developer",
        )

        assert user.user_id == user_id
        assert user.email == email
        assert user.role == "developer"
        assert user.is_active is True
        assert user.is_verified is False

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, user_store):
        """测试根据ID获取用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        user = await user_store.get_user_by_id(user_id)
        assert user is not None
        assert user.user_id == user_id
        assert user.email == email

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, user_store):
        """测试根据邮箱获取用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        user = await user_store.get_user_by_email(email, "test_tenant")
        assert user is not None
        assert user.user_id == user_id

    @pytest.mark.asyncio
    async def test_update_user(self, user_store):
        """测试更新用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        updated_user = await user_store.update_user(
            user_id,
            full_name="Updated Name",
            role="admin",
        )

        assert updated_user.full_name == "Updated Name"
        assert updated_user.role == "admin"

    @pytest.mark.asyncio
    async def test_delete_user(self, user_store):
        """测试删除用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        deleted = await user_store.delete_user(user_id)
        assert deleted is True

        user = await user_store.get_user_by_id(user_id)
        assert user is None

    @pytest.mark.asyncio
    async def test_verify_user(self, user_store):
        """测试验证用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        verified_user = await user_store.verify_user(user_id)
        assert verified_user.is_verified is True

    @pytest.mark.asyncio
    async def test_deactivate_user(self, user_store):
        """测试停用用户"""
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        deactivated_user = await user_store.deactivate_user(user_id)
        assert deactivated_user.is_active is False


class TestAPIKeyStore:
    """API密钥存储测试"""

    @pytest.fixture
    async def api_key_store(self):
        return APIKeyStorePostgres()

    @pytest.mark.asyncio
    async def test_create_api_key(self, api_key_store):
        """测试创建API密钥"""
        key_id = str(uuid4())
        key_prefix = "xag_test123"
        key_hash = "hashed_key"

        api_key = await api_key_store.create_api_key(
            key_id=key_id,
            key_prefix=key_prefix,
            key_hash=key_hash,
            user_id="user_123",
            tenant_id="test_tenant",
            name="Test Key",
            role="developer",
            scopes=["agent:run", "tools:read"],
        )

        assert api_key.key_id == key_id
        assert api_key.key_prefix == key_prefix
        assert api_key.revoked is False

    @pytest.mark.asyncio
    async def test_get_api_key_by_hash(self, api_key_store):
        """测试根据哈希获取API密钥"""
        key_id = str(uuid4())
        key_hash = "hashed_key_123"

        await api_key_store.create_api_key(
            key_id=key_id,
            key_prefix="xag_test",
            key_hash=key_hash,
            user_id="user_123",
            tenant_id="test_tenant",
            name="Test Key",
        )

        api_key = await api_key_store.get_api_key_by_hash(key_hash)
        assert api_key is not None
        assert api_key.key_id == key_id

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api_key_store):
        """测试撤销API密钥"""
        key_id = str(uuid4())

        await api_key_store.create_api_key(
            key_id=key_id,
            key_prefix="xag_test",
            key_hash="hashed_key",
            user_id="user_123",
            tenant_id="test_tenant",
            name="Test Key",
        )

        revoked_key = await api_key_store.revoke_api_key(key_id)
        assert revoked_key.revoked is True
        assert revoked_key.revoked_at is not None

    @pytest.mark.asyncio
    async def test_is_valid_api_key(self, api_key_store):
        """测试检查API密钥有效性"""
        key_id = str(uuid4())

        await api_key_store.create_api_key(
            key_id=key_id,
            key_prefix="xag_test",
            key_hash="hashed_key",
            user_id="user_123",
            tenant_id="test_tenant",
            name="Test Key",
        )

        is_valid = await api_key_store.is_valid(key_id)
        assert is_valid is True

        # 撤销后应该无效
        await api_key_store.revoke_api_key(key_id)
        is_valid = await api_key_store.is_valid(key_id)
        assert is_valid is False


class TestApprovalStore:
    """审批存储测试"""

    @pytest.fixture
    async def approval_store(self):
        return ApprovalStorePostgres()

    @pytest.mark.asyncio
    async def test_create_approval(self, approval_store):
        """测试创建审批"""
        approval_id = str(uuid4())
        request_id = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        approval = await approval_store.create_approval(
            approval_id=approval_id,
            tenant_id="test_tenant",
            user_id="user_123",
            request_id=request_id,
            action="delete_user",
            resource_type="user",
            resource_id="user_456",
            details={"reason": "test"},
            expires_at=expires_at,
        )

        assert approval.approval_id == approval_id
        assert approval.status == "pending"

    @pytest.mark.asyncio
    async def test_approve_approval(self, approval_store):
        """测试批准审批"""
        approval_id = str(uuid4())
        request_id = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        await approval_store.create_approval(
            approval_id=approval_id,
            tenant_id="test_tenant",
            user_id="user_123",
            request_id=request_id,
            action="delete_user",
            resource_type="user",
            resource_id="user_456",
            details={"reason": "test"},
            expires_at=expires_at,
        )

        approved = await approval_store.approve(
            approval_id,
            approved_by="admin_123",
            reason="Approved",
        )

        assert approved.status == "approved"
        assert approved.approved_by == "admin_123"

    @pytest.mark.asyncio
    async def test_reject_approval(self, approval_store):
        """测试拒绝审批"""
        approval_id = str(uuid4())
        request_id = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        await approval_store.create_approval(
            approval_id=approval_id,
            tenant_id="test_tenant",
            user_id="user_123",
            request_id=request_id,
            action="delete_user",
            resource_type="user",
            resource_id="user_456",
            details={"reason": "test"},
            expires_at=expires_at,
        )

        rejected = await approval_store.reject(
            approval_id,
            approved_by="admin_123",
            reason="Rejected",
        )

        assert rejected.status == "rejected"


class TestRateLimiter:
    """速率限制器测试"""

    @pytest.fixture
    async def rate_limiter(self):
        return RateLimiterRedis()

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter):
        """测试速率限制 - 允许"""
        allowed, count, remaining = await rate_limiter.check_rate_limit(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            limit=10,
            window_seconds=60,
        )

        assert allowed is True
        assert count == 1
        assert remaining == 9

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter):
        """测试速率限制 - 超限"""
        # 达到限制
        for _ in range(5):
            await rate_limiter.check_rate_limit(
                tenant_id="test_tenant",
                user_id="user_123",
                endpoint="/api/test",
                limit=5,
                window_seconds=60,
            )

        # 第6次应该被拒绝
        allowed, count, remaining = await rate_limiter.check_rate_limit(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            limit=5,
            window_seconds=60,
        )

        assert allowed is False
        assert count == 5
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_reset_limit(self, rate_limiter):
        """测试重置限制"""
        await rate_limiter.check_rate_limit(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            limit=5,
            window_seconds=60,
        )

        reset = await rate_limiter.reset_limit(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
        )

        assert reset is True

        count = await rate_limiter.get_current_count(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            window_seconds=60,
        )

        assert count == 0


class TestCSRFTokenStore:
    """CSRF令牌存储测试"""

    @pytest.fixture
    async def csrf_token_store(self):
        return CSRFTokenStoreRedis()

    @pytest.mark.asyncio
    async def test_create_token(self, csrf_token_store):
        """测试创建CSRF令牌"""
        token_id = str(uuid4())
        token_hash = "hashed_token_123"
        session_id = str(uuid4())

        created = await csrf_token_store.create_token(
            token_id=token_id,
            token_hash=token_hash,
            tenant_id="test_tenant",
            user_id="user_123",
            session_id=session_id,
        )

        assert created is True

    @pytest.mark.asyncio
    async def test_validate_token(self, csrf_token_store):
        """测试验证CSRF令牌"""
        token_id = str(uuid4())
        token_hash = "hashed_token_123"
        session_id = str(uuid4())

        await csrf_token_store.create_token(
            token_id=token_id,
            token_hash=token_hash,
            tenant_id="test_tenant",
            user_id="user_123",
            session_id=session_id,
        )

        valid, data = await csrf_token_store.validate_token(token_hash, session_id)
        assert valid is True
        assert data["token_id"] == token_id

    @pytest.mark.asyncio
    async def test_revoke_token(self, csrf_token_store):
        """测试撤销CSRF令牌"""
        token_id = str(uuid4())
        token_hash = "hashed_token_123"
        session_id = str(uuid4())

        await csrf_token_store.create_token(
            token_id=token_id,
            token_hash=token_hash,
            tenant_id="test_tenant",
            user_id="user_123",
            session_id=session_id,
        )

        revoked = await csrf_token_store.revoke_token(token_hash)
        assert revoked is True

        valid, _ = await csrf_token_store.validate_token(token_hash, session_id)
        assert valid is False
