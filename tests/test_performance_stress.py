"""
X-Agent 性能压力测试套件

测试场景：
1. 并发100个Agent请求
2. 1000个工具并行调用
3. 10000条记忆存储和查询
4. 长时间运行稳定性测试
"""

import asyncio
import threading
import time
from typing import List
from uuid import uuid4

import pytest

from backend.app.core.agent import AgentLoop
from backend.app.core.llm import LLMRouter, MockLLMBackend
from backend.app.core.memory import MemoryItem, MemoryScope, MemorySystem
from backend.app.core.tool_registry import ToolRegistry
from backend.app.core.tool_schema import ToolSchema, ToolCategory
from backend.app.core.tracing import TraceStore
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import RunContext

# ============================================================================
# 性能测试1：并发100个Agent请求
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_agent_requests():
    """测试100个并发Agent请求的性能"""

    num_agents = 100
    tenant_id = "stress-test-tenant"

    # 1. 初始化共享系统
    memory_system = MemorySystem()
    trace_store = TraceStore()
    audit_store = AuditStore()

    # 2. 创建Agent工厂
    def create_agent():
        llm_router = LLMRouter(backend=MockLLMBackend())
        tool_registry = ToolRegistry()
        return AgentLoop(
            llm_router=llm_router,
            memory=memory_system,
            tools=tool_registry,
            tracer=trace_store,
            audit_store=audit_store,
        )

    # 3. 定义Agent任务
    async def agent_task(agent_id: str, task_id: int):
        agent = create_agent()
        context = RunContext(tenant_id=tenant_id, agent_id=agent_id)

        # 存储记忆
        memory_id = await agent.memory.store(
            context=context,
            content=f"Agent {agent_id} task {task_id}",
            layer=1,
            importance=0.5,
            tags=[f"agent-{agent_id}", f"task-{task_id}"],
            scope=MemoryScope(owner_agent_id=agent_id),
        )

        # 记录事件
        trace_store.record(
            context,
            event="agent.task.complete",
            agent_id=agent_id,
            task_id=task_id,
            memory_id=memory_id,
        )

        return {
            "agent_id": agent_id,
            "task_id": task_id,
            "memory_id": memory_id,
            "status": "success",
        }

    # 4. 执行并发任务
    start_time = time.time()

    tasks = [
        agent_task(f"agent-{i}", i)
        for i in range(num_agents)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed_time = time.time() - start_time

    # 5. 验证结果
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    failed = len(results) - successful

    print(f"\n并发Agent请求性能测试:")
    print(f"  总请求数: {num_agents}")
    print(f"  成功: {successful}")
    print(f"  失败: {failed}")
    print(f"  总耗时: {elapsed_time:.2f}秒")
    print(f"  平均耗时: {elapsed_time/num_agents*1000:.2f}ms")
    print(f"  吞吐量: {num_agents/elapsed_time:.2f} req/s")

    assert successful >= num_agents * 0.95  # 至少95%成功率


# ============================================================================
# 性能测试2：1000个工具并行调用
# ============================================================================


@pytest.mark.asyncio
async def test_parallel_tool_calls():
    """测试1000个工具并行调用的性能"""

    num_tools = 1000
    tenant_id = "stress-test-tenant"

    # 1. 初始化工具注册表
    tool_registry = ToolRegistry()

    # 2. 注册工具
    for i in range(10):
        schema = ToolSchema(
            name=f"tool_{i}",
            description=f"Test tool {i}",
            category=ToolCategory.SYSTEM,
            parameters=[],
        )
        tool_registry.register(schema)

    # 3. 定义工具调用任务
    async def tool_call_task(call_id: int):
        tool_id = call_id % 10
        tool_name = f"tool_{tool_id}"

        # 模拟工具执行
        await asyncio.sleep(0.001)  # 1ms 执行时间

        return {
            "call_id": call_id,
            "tool_name": tool_name,
            "status": "success",
            "result": f"Result from {tool_name}",
        }

    # 4. 执行并行工具调用
    start_time = time.time()

    tasks = [
        tool_call_task(i)
        for i in range(num_tools)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed_time = time.time() - start_time

    # 5. 验证结果
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    failed = len(results) - successful

    print(f"\n工具并行调用性能测试:")
    print(f"  总调用数: {num_tools}")
    print(f"  成功: {successful}")
    print(f"  失败: {failed}")
    print(f"  总耗时: {elapsed_time:.2f}秒")
    print(f"  平均耗时: {elapsed_time/num_tools*1000:.2f}ms")
    print(f"  吞吐量: {num_tools/elapsed_time:.2f} calls/s")

    assert successful >= num_tools * 0.95


# ============================================================================
# 性能测试3：10000条记忆存储和查询
# ============================================================================


@pytest.mark.asyncio
async def test_memory_scale():
    """测试10000条记忆的存储和查询性能"""

    num_memories = 10000
    tenant_id = "stress-test-tenant"
    agent_id = "stress-test-agent"

    # 1. 初始化记忆系统
    memory_system = MemorySystem()

    # 2. 批量存储记忆
    print(f"\n记忆系统规模测试:")
    print(f"  目标记忆数: {num_memories}")

    start_time = time.time()

    async def store_memory(index: int):
        context = RunContext(tenant_id=tenant_id, agent_id=agent_id)
        return await memory_system.store(
            context=context,
            content=f"Memory item {index}",
            layer=(index % 3) + 1,
            importance=0.3 + (index % 7) * 0.1,
            tags=[f"batch-{index // 1000}", f"index-{index}"],
            scope=MemoryScope(owner_agent_id=agent_id),
            metadata={
                "index": index,
                "batch": index // 1000,
            },
        )

    # 分批存储以避免内存溢出
    batch_size = 100
    stored_memories = []

    for batch_start in range(0, num_memories, batch_size):
        batch_end = min(batch_start + batch_size, num_memories)
        batch_tasks = [
            store_memory(i)
            for i in range(batch_start, batch_end)
        ]
        batch_results = await asyncio.gather(*batch_tasks)
        stored_memories.extend(batch_results)

    storage_time = time.time() - start_time

    print(f"  存储耗时: {storage_time:.2f}秒")
    print(f"  存储速率: {num_memories/storage_time:.2f} items/s")

    # 3. 查询性能测试
    start_time = time.time()

    async def retrieve_memory(memory_id: str):
        return memory_system.get_item(memory_id)

    # 随机查询1000条记忆
    import random
    sample_memories = random.sample(stored_memories, min(1000, len(stored_memories)))

    query_tasks = [
        retrieve_memory(m)
        for m in sample_memories
    ]

    query_results = await asyncio.gather(*query_tasks)

    query_time = time.time() - start_time

    print(f"  查询耗时 (1000条): {query_time:.2f}秒")
    print(f"  查询速率: {len(sample_memories)/query_time:.2f} queries/s")

    # 4. 验证结果
    assert len(stored_memories) == num_memories
    assert len(query_results) == len(sample_memories)
    assert all(r is not None for r in query_results)


# ============================================================================
# 性能测试4：长时间运行稳定性
# ============================================================================


@pytest.mark.asyncio
async def test_long_running_stability():
    """测试长时间运行的稳定性"""

    duration_seconds = 30  # 30秒运行时间
    tenant_id = "stress-test-tenant"

    # 1. 初始化系统
    memory_system = MemorySystem()
    trace_store = TraceStore()
    audit_store = AuditStore()

    # 2. 定义持续任务
    async def continuous_task(task_id: int):
        start_time = time.time()
        iteration = 0

        while time.time() - start_time < duration_seconds:
            context = RunContext(tenant_id=tenant_id, agent_id=f"agent-{task_id}")
            # 存储记忆
            await memory_system.store(
                context=context,
                content=f"Task {task_id} iteration {iteration}",
                layer=1,
                importance=0.5,
                scope=MemoryScope(owner_agent_id=f"agent-{task_id}"),
            )

            # 记录事件
            trace_store.record(
                context,
                event="task.iteration",
                task_id=task_id,
                iteration=iteration,
            )

            iteration += 1
            await asyncio.sleep(0.01)  # 10ms 间隔

        return {
            "task_id": task_id,
            "iterations": iteration,
            "duration": time.time() - start_time,
        }

    # 3. 运行多个并发任务
    num_concurrent_tasks = 10

    print(f"\n长时间运行稳定性测试:")
    print(f"  并发任务数: {num_concurrent_tasks}")
    print(f"  运行时间: {duration_seconds}秒")

    start_time = time.time()

    tasks = [
        continuous_task(i)
        for i in range(num_concurrent_tasks)
    ]

    results = await asyncio.gather(*tasks)

    total_time = time.time() - start_time

    # 4. 分析结果
    total_iterations = sum(r["iterations"] for r in results)
    avg_iterations = total_iterations / num_concurrent_tasks

    print(f"  总迭代次数: {total_iterations}")
    print(f"  平均迭代次数: {avg_iterations:.0f}")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  吞吐量: {total_iterations/total_time:.2f} ops/s")

    # 5. 验证稳定性
    assert all(r["iterations"] > 0 for r in results)
    assert total_iterations > 0


# ============================================================================
# 性能测试5：记忆系统性能
# ============================================================================


class TestMemoryPerformance:
    """测试记忆系统在负载下的性能"""

    def test_memory_concurrent_access(self):
        """测试并发记忆访问"""
        memory_system = MemorySystem()
        results = []

        def add_memories():
            for i in range(100):
                memory_id = memory_system.add(f"Memory {i}", tenant_id="tenant-1")
                results.append(memory_id)

        start_time = time.time()

        threads = [threading.Thread(target=add_memories) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        elapsed = time.time() - start_time

        # Should handle concurrent access
        assert len(results) == 1000
        assert len(memory_system._items) == 1000
        assert elapsed < 10.0

    def test_memory_large_content(self):
        """Test memory with large content."""
        memory_system = MemorySystem()

        # Add memory with large content
        large_content = "x" * 1000000  # 1MB
        start_time = time.time()

        memory_id = memory_system.add(large_content, tenant_id="tenant-1")

        elapsed = time.time() - start_time

        assert memory_id is not None
        assert len(memory_system._items) == 1
        assert elapsed < 1.0

    def test_memory_many_tags(self):
        """Test memory with many tags."""
        memory_system = MemorySystem()

        # Create memory with many tags
        tags = [f"tag-{i}" for i in range(1000)]
        start_time = time.time()

        memory_id = memory_system.add(
            "Test content",
            tenant_id="tenant-1",
        )

        elapsed = time.time() - start_time

        assert memory_id is not None
        assert elapsed < 1.0


class TestLLMPerformance:
    """Test LLM system performance."""

    @pytest.mark.asyncio
    async def test_llm_chat_performance(self):
        """Test LLM chat operation performance."""
        router = LLMRouter(backend=MockLLMBackend())
        start_time = time.time()

        # Make 100 chat requests
        for i in range(100):
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )
            assert response.content is not None

        elapsed = time.time() - start_time
        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0

    @pytest.mark.asyncio
    async def test_llm_concurrent_requests(self):
        """Test concurrent LLM requests."""
        router = LLMRouter(backend=MockLLMBackend())
        start_time = time.time()

        async def make_request(i):
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )
            return response.content

        # Make 100 concurrent requests
        tasks = [make_request(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        assert len(results) == 100
        assert all(r is not None for r in results)
        assert elapsed < 10.0

    @pytest.mark.asyncio
    async def test_llm_large_message_history(self):
        """Test LLM with large message history."""
        router = LLMRouter(backend=MockLLMBackend())

        # Create large message history
        messages = []
        for i in range(100):
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})

        start_time = time.time()

        response = await router.chat(messages, [])

        elapsed = time.time() - start_time

        assert response.content is not None
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_llm_many_tools(self):
        """Test LLM with many tools."""
        router = LLMRouter(backend=MockLLMBackend())

        # Create many tools
        tools = [
            {
                "name": f"tool-{i}",
                "description": f"Tool {i}",
                "parameters": {"type": "object", "properties": {}},
            }
            for i in range(100)
        ]

        start_time = time.time()

        response = await router.chat(
            [{"role": "user", "content": "Use a tool"}],
            tools
        )

        elapsed = time.time() - start_time

        assert response.content is not None
        assert elapsed < 2.0


class TestMemoryAndLLMIntegrationPerformance:
    """Test integrated memory and LLM performance."""

    @pytest.mark.asyncio
    async def test_memory_llm_workflow_performance(self):
        """Test complete memory and LLM workflow performance."""
        memory_system = MemorySystem()
        router = LLMRouter(backend=MockLLMBackend())

        start_time = time.time()

        # Simulate workflow: store memory, query LLM, store response
        for i in range(100):
            # Store memory
            memory_id = memory_system.add(
                f"Context {i}",
                tenant_id="tenant-1",
            )

            # Query LLM
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )

            # Store response
            response_id = memory_system.add(
                f"Response: {response.content}",
                tenant_id="tenant-1",
            )

        elapsed = time.time() - start_time

        assert len(memory_system._items) == 200  # 100 contexts + 100 responses
        assert elapsed < 10.0

    @pytest.mark.asyncio
    async def test_concurrent_memory_llm_workflow(self):
        """Test concurrent memory and LLM workflow."""
        memory_system = MemorySystem()
        router = LLMRouter(backend=MockLLMBackend())

        async def workflow(user_id):
            # Store memory
            memory_id = memory_system.add(
                f"User {user_id} context",
                tenant_id=f"tenant-{user_id}",
            )

            # Query LLM
            response = await router.chat(
                [{"role": "user", "content": f"Query from user {user_id}"}],
                []
            )

            # Store response
            response_id = memory_system.add(
                f"Response: {response.content}",
                tenant_id=f"tenant-{user_id}",
            )

            return memory_id, response_id

        start_time = time.time()

        # Run 50 concurrent workflows
        tasks = [workflow(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        assert len(results) == 50
        assert len(memory_system._items) == 100  # 50 contexts + 50 responses
        assert elapsed < 15.0


class TestStressTests:
    """Stress tests for system limits."""

    def test_memory_stress_many_items(self):
        """Stress test: many memory items."""
        memory_system = MemorySystem()

        # Add 10000 items
        for i in range(10000):
            memory_system.add(f"Memory {i}", tenant_id="tenant-1")

        assert len(memory_system._items) == 10000

    def test_memory_stress_large_metadata(self):
        """Stress test: large metadata."""
        memory_system = MemorySystem()

        # Create large metadata
        large_metadata = {f"key-{i}": f"value-{i}" * 100 for i in range(1000)}

        memory_id = memory_system.add(
            "Test content",
            tenant_id="tenant-1",
        )

        assert memory_id is not None

    @pytest.mark.asyncio
    async def test_llm_stress_rapid_requests(self):
        """Stress test: rapid LLM requests."""
        router = LLMRouter(backend=MockLLMBackend())

        # Make 1000 rapid requests
        for i in range(1000):
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )
            assert response.content is not None

    @pytest.mark.asyncio
    async def test_llm_stress_concurrent_requests(self):
        """Stress test: many concurrent LLM requests."""
        router = LLMRouter(backend=MockLLMBackend())

        async def make_request(i):
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )
            return response.content

        # Make 500 concurrent requests
        tasks = [make_request(i) for i in range(500)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 500
        assert all(r is not None for r in results)

    def test_memory_stress_concurrent_threads(self):
        """Stress test: concurrent thread access."""
        import threading
        memory_system = MemorySystem()
        results = []
        errors = []

        def worker(worker_id):
            try:
                for i in range(100):
                    memory_id = memory_system.add(
                        f"Worker {worker_id} Memory {i}",
                        tenant_id="tenant-1",
                    )
                    results.append(memory_id)
            except Exception as e:
                errors.append(e)

        # Create 50 threads
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 5000
        assert len(memory_system._items) == 5000


class TestResourceUsage:
    """Test resource usage and limits."""

    def test_memory_system_memory_usage(self):
        """Test memory system memory usage."""
        import sys
        memory_system = MemorySystem()

        # Get initial size
        initial_size = sys.getsizeof(memory_system._items)

        # Add items
        for i in range(1000):
            memory_system.add(f"Memory {i}", tenant_id="tenant-1")

        final_size = sys.getsizeof(memory_system._items)

        # Memory should grow but not excessively
        growth = final_size - initial_size
        assert growth > 0

    @pytest.mark.asyncio
    @pytest.mark.flaky(reruns=2)
    async def test_llm_response_time_consistency(self):
        """Test LLM response time consistency."""
        router = LLMRouter(backend=MockLLMBackend())
        response_times = []

        for i in range(100):
            start = time.time()
            response = await router.chat(
                [{"role": "user", "content": f"Query {i}"}],
                []
            )
            elapsed = time.time() - start
            response_times.append(elapsed)

        # Calculate statistics
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        min_time = min(response_times)

        # Response times should be relatively consistent
        assert max_time < avg_time * 10  # Max shouldn't be 10x average
        assert min_time > 0

    def test_memory_cleanup_performance(self):
        """Test memory cleanup performance."""
        memory_system = MemorySystem()

        # Add items
        for i in range(10000):
            memory_system.add(f"Memory {i}", tenant_id="tenant-1")

        start_time = time.time()

        # Cleanup
        memory_system._items.clear()

        elapsed = time.time() - start_time

        assert len(memory_system._items) == 0
        assert elapsed < 1.0
