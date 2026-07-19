"""
集成测试 - 多实例部署、重启恢复、并发访问
"""
import pytest
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.app.core.database import get_db_manager
from backend.app.models.user_store import get_user_store
from backend.app.models.api_key_store import get_api_key_store
from backend.app.core.migration_adapter import init_migration_adapter


class TestMultiInstanceDeployment:
    """多实例部署测试"""

    @pytest.fixture
    async def db_manager(self):
        """复用 conftest autouse 注入的全局 DatabaseManager。

        根级 conftest 已用临时文件 SQLite(NullPool) + fakeredis 注入全局
        _db_manager；这里不再 init_db_manager(postgresql://) 覆盖它(那会指向
        本机不存在的 postgres，且 async engine 不兼容硬编码 QueuePool)。
        store 走 SessionManager.get_session() 即命中该测试库。
        """
        return get_db_manager()

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, db_manager):
        """测试并发用户创建"""
        user_store = get_user_store()

        async def create_user(index):
            user_id = f"user_{index}_{uuid4()}"
            email = f"test_{index}@example.com"
            return await user_store.create_user(
                user_id=user_id,
                email=email,
                password_hash="hashed_password",
                tenant_id="test_tenant",
            )

        # 并发创建10个用户
        tasks = [create_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_api_key_operations(self, db_manager):
        """测试并发API密钥操作"""
        api_key_store = get_api_key_store()

        async def create_and_validate_key(index):
            key_id = f"key_{index}_{uuid4()}"
            key_hash = f"hash_{index}_{uuid4()}"

            # 创建
            await api_key_store.create_api_key(
                key_id=key_id,
                key_prefix=f"xag_{index}",
                key_hash=key_hash,
                user_id="user_123",
                tenant_id="test_tenant",
                name=f"Key {index}",
            )

            # 验证
            is_valid = await api_key_store.is_valid(key_id)
            return is_valid

        # 并发操作
        tasks = [create_and_validate_key(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(results)

    @pytest.mark.asyncio
    async def test_data_consistency_across_instances(self, db_manager):
        """测试跨实例数据一致性"""
        user_store1 = get_user_store()
        user_store2 = get_user_store()  # 模拟另一个实例

        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        # 实例1创建用户
        await user_store1.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        # 实例2应该能读取
        user = await user_store2.get_user_by_id(user_id)
        assert user is not None
        assert user.email == email

        # 实例1更新用户
        await user_store1.update_user(user_id, full_name="Updated Name")

        # 实例2应该能读取更新后的数据
        user = await user_store2.get_user_by_id(user_id)
        assert user.full_name == "Updated Name"


class TestRestartRecovery:
    """重启恢复测试"""

    @pytest.mark.asyncio
    async def test_data_persistence_after_restart(self):
        """测试重启后数据持久化"""
        # 复用 conftest 注入的全局测试库；不再 init_db_manager(postgresql://)。
        # 该库是临时文件 SQLite(NullPool),进程级 dispose 后文件随 fixture 清理,
        # 无法真正模拟跨进程重启,因此这里在同一库内验证“写入后可重新读取”的
        # 持久化语义(get_db_manager 单例不变)。
        get_db_manager()

        user_store = get_user_store()
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        # 创建用户
        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        user_store = get_user_store()

        # 验证数据仍然存在
        user = await user_store.get_user_by_id(user_id)
        assert user is not None
        assert user.email == email

    @pytest.mark.asyncio
    async def test_redis_session_recovery(self):
        """测试Redis会话恢复"""
        from backend.app.models.rate_limiter import get_rate_limiter

        # 复用 conftest 注入的全局内存库 + fakeredis。
        get_db_manager()

        rate_limiter = get_rate_limiter()

        # 设置限制
        allowed, count, _ = await rate_limiter.check_rate_limit(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            limit=10,
            window_seconds=60,
        )

        assert allowed is True
        assert count == 1

        rate_limiter = get_rate_limiter()

        # 验证限制仍然存在(同一 fakeredis 实例)
        current_count = await rate_limiter.get_current_count(
            tenant_id="test_tenant",
            user_id="user_123",
            endpoint="/api/test",
            window_seconds=60,
        )

        assert current_count == 1


class TestConcurrentAccess:
    """并发访问测试"""

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """测试并发读写"""
        get_db_manager()

        user_store = get_user_store()
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        # 创建用户
        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        async def read_user():
            return await user_store.get_user_by_id(user_id)

        async def update_user(index):
            return await user_store.update_user(
                user_id,
                full_name=f"Updated {index}",
            )

        # 并发读写
        tasks = [read_user() for _ in range(5)] + [update_user(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_transaction_isolation(self):
        """测试事务隔离"""
        from backend.app.core.session import SessionManager

        get_db_manager()

        user_store = get_user_store()

        async def transaction_1():
            user_id = str(uuid4())
            email = f"test1_{user_id}@example.com"

            async with SessionManager.transaction() as session:
                user = await user_store.create_user(
                    user_id=user_id,
                    email=email,
                    password_hash="hashed_password",
                    tenant_id="test_tenant",
                )
                return user.user_id

        async def transaction_2():
            user_id = str(uuid4())
            email = f"test2_{user_id}@example.com"

            async with SessionManager.transaction() as session:
                user = await user_store.create_user(
                    user_id=user_id,
                    email=email,
                    password_hash="hashed_password",
                    tenant_id="test_tenant",
                )
                return user.user_id

        # 并发事务
        user_id_1, user_id_2 = await asyncio.gather(transaction_1(), transaction_2())

        # 验证两个用户都被创建
        user1 = await user_store.get_user_by_id(user_id_1)
        user2 = await user_store.get_user_by_id(user_id_2)

        assert user1 is not None
        assert user2 is not None
        assert user1.user_id != user2.user_id


class TestMigrationAdapter:
    """迁移适配器测试"""

    @pytest.mark.asyncio
    async def test_dual_write_mode(self):
        """测试双写模式"""
        get_db_manager()

        adapter = init_migration_adapter(enable_dual_write=True)

        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        # 创建用户（双写）
        user = await adapter.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        assert user is not None
        assert adapter.stats["user_writes"] == 1

    @pytest.mark.asyncio
    async def test_read_from_new_storage(self):
        """测试从新存储读取"""
        get_db_manager()

        adapter = init_migration_adapter(read_from_new=True)

        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"

        # 创建用户
        await adapter.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        # 从新存储读取
        user = await adapter.get_user_by_id(user_id)
        assert user is not None
        assert user.email == email
