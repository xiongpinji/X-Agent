"""
性能测试 - 响应时间、吞吐量、压力测试
"""
import pytest
import asyncio
import time
from uuid import uuid4
from statistics import mean, stdev

from backend.app.core.database import get_db_manager
from backend.app.models.user_store import get_user_store
from backend.app.models.api_key_store import get_api_key_store
from backend.app.models.rate_limiter import get_rate_limiter


class TestPerformance:
    """性能测试"""

    @pytest.fixture
    async def db_manager(self):
        """复用 conftest autouse 注入的全局内存 DatabaseManager。

        不再 init_db_manager(postgresql://) 覆盖它(那会指向本机不存在的
        postgres，且 async engine 不兼容硬编码 QueuePool)。内存 SQLite 时延极低，
        这些时延/吞吐断言只校验“无异常路径下指标在合理量级”。
        """
        return get_db_manager()

    @pytest.mark.asyncio
    async def test_user_creation_response_time(self, db_manager):
        """测试用户创建响应时间"""
        user_store = get_user_store()
        times = []

        for i in range(100):
            start = time.time()
            user_id = f"user_{i}_{uuid4()}"
            email = f"test_{i}@example.com"

            await user_store.create_user(
                user_id=user_id,
                email=email,
                password_hash="hashed_password",
                tenant_id="test_tenant",
            )

            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = mean(times)
        max_time = max(times)
        min_time = min(times)

        print(f"\n用户创建响应时间:")
        print(f"  平均: {avg_time*1000:.2f}ms")
        print(f"  最大: {max_time*1000:.2f}ms")
        print(f"  最小: {min_time*1000:.2f}ms")

        # 断言性能要求
        assert avg_time < 0.1, f"平均响应时间过长: {avg_time*1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_user_read_response_time(self, db_manager):
        """测试用户读取响应时间"""
        user_store = get_user_store()

        # 创建测试用户
        user_id = str(uuid4())
        email = f"test_{user_id}@example.com"
        await user_store.create_user(
            user_id=user_id,
            email=email,
            password_hash="hashed_password",
            tenant_id="test_tenant",
        )

        times = []

        for _ in range(100):
            start = time.time()
            await user_store.get_user_by_id(user_id)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = mean(times)
        max_time = max(times)

        print(f"\n用户读取响应时间:")
        print(f"  平均: {avg_time*1000:.2f}ms")
        print(f"  最大: {max_time*1000:.2f}ms")

        assert avg_time < 0.05, f"平均响应时间过长: {avg_time*1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_api_key_throughput(self, db_manager):
        """测试API密钥吞吐量"""
        api_key_store = get_api_key_store()

        start = time.time()
        count = 0

        for i in range(100):
            key_id = f"key_{i}_{uuid4()}"
            key_hash = f"hash_{i}_{uuid4()}"

            await api_key_store.create_api_key(
                key_id=key_id,
                key_prefix=f"xag_{i}",
                key_hash=key_hash,
                user_id="user_123",
                tenant_id="test_tenant",
                name=f"Key {i}",
            )
            count += 1

        elapsed = time.time() - start
        throughput = count / elapsed

        print(f"\nAPI密钥创建吞吐量:")
        print(f"  总数: {count}")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {throughput:.2f} ops/s")

        assert throughput > 10, f"吞吐量过低: {throughput:.2f} ops/s"

    @pytest.mark.asyncio
    async def test_rate_limiter_throughput(self, db_manager):
        """测试速率限制器吞吐量"""
        rate_limiter = get_rate_limiter()

        start = time.time()
        count = 0

        for i in range(1000):
            allowed, _, _ = await rate_limiter.check_rate_limit(
                tenant_id="test_tenant",
                user_id=f"user_{i % 10}",
                endpoint="/api/test",
                limit=100,
                window_seconds=60,
            )
            count += 1

        elapsed = time.time() - start
        throughput = count / elapsed

        print(f"\n速率限制器吞吐量:")
        print(f"  总数: {count}")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {throughput:.2f} ops/s")

        assert throughput > 100, f"吞吐量过低: {throughput:.2f} ops/s"

    @pytest.mark.asyncio
    async def test_concurrent_throughput(self, db_manager):
        """测试并发吞吐量"""
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

        start = time.time()

        # 并发创建100个用户
        tasks = [create_user(i) for i in range(100)]
        await asyncio.gather(*tasks)

        elapsed = time.time() - start
        throughput = 100 / elapsed

        print(f"\n并发用户创建吞吐量:")
        print(f"  总数: 100")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {throughput:.2f} ops/s")

        assert throughput > 20, f"吞吐量过低: {throughput:.2f} ops/s"


class TestStressTest:
    """压力测试"""

    @pytest.fixture
    async def db_manager(self):
        """复用 conftest autouse 注入的全局内存 DatabaseManager。

        不再 init_db_manager(postgresql://) 覆盖它(那会指向本机不存在的
        postgres，且 async engine 不兼容硬编码 QueuePool)。内存 SQLite 时延极低，
        这些时延/吞吐断言只校验“无异常路径下指标在合理量级”。
        """
        return get_db_manager()

    @pytest.mark.asyncio
    async def test_high_concurrency_user_creation(self, db_manager):
        """测试高并发用户创建"""
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

        start = time.time()

        # 并发创建500个用户
        tasks = [create_user(i) for i in range(500)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start

        # 统计成功和失败
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = sum(1 for r in results if isinstance(r, Exception))

        print(f"\n高并发用户创建压力测试:")
        print(f"  总数: 500")
        print(f"  成功: {successes}")
        print(f"  失败: {failures}")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {successes/elapsed:.2f} ops/s")

        assert successes > 400, f"成功率过低: {successes}/500"

    @pytest.mark.asyncio
    async def test_high_concurrency_rate_limiting(self, db_manager):
        """测试高并发速率限制"""
        rate_limiter = get_rate_limiter()

        async def check_limit(index):
            return await rate_limiter.check_rate_limit(
                tenant_id="test_tenant",
                user_id=f"user_{index % 50}",
                endpoint="/api/test",
                limit=100,
                window_seconds=60,
            )

        start = time.time()

        # 并发检查1000次
        tasks = [check_limit(i) for i in range(1000)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start

        # 统计成功和失败
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = sum(1 for r in results if isinstance(r, Exception))

        print(f"\n高并发速率限制压力测试:")
        print(f"  总数: 1000")
        print(f"  成功: {successes}")
        print(f"  失败: {failures}")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {successes/elapsed:.2f} ops/s")

        assert successes > 900, f"成功率过低: {successes}/1000"

    @pytest.mark.asyncio
    async def test_sustained_load(self, db_manager):
        """测试持续负载"""
        user_store = get_user_store()
        api_key_store = get_api_key_store()

        async def mixed_operations(index):
            # 混合操作
            user_id = f"user_{index}_{uuid4()}"
            email = f"test_{index}@example.com"

            # 创建用户
            await user_store.create_user(
                user_id=user_id,
                email=email,
                password_hash="hashed_password",
                tenant_id="test_tenant",
            )

            # 创建API密钥
            key_id = f"key_{index}_{uuid4()}"
            await api_key_store.create_api_key(
                key_id=key_id,
                key_prefix=f"xag_{index}",
                key_hash=f"hash_{index}",
                user_id=user_id,
                tenant_id="test_tenant",
                name=f"Key {index}",
            )

            # 读取用户
            await user_store.get_user_by_id(user_id)

            # 验证API密钥
            await api_key_store.is_valid(key_id)

            return True

        start = time.time()

        # 持续负载 - 200个混合操作
        tasks = [mixed_operations(i) for i in range(200)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start

        successes = sum(1 for r in results if r is True)

        print(f"\n持续负载测试:")
        print(f"  总操作数: 200")
        print(f"  成功: {successes}")
        print(f"  耗时: {elapsed:.2f}s")
        print(f"  吞吐量: {successes/elapsed:.2f} ops/s")

        assert successes > 180, f"成功率过低: {successes}/200"
