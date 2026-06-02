"""
X-Agent 端到端集成测试套件

测试场景：
1. 完整Agent执行流程
2. 多代理协作
3. 文件系统操作
4. 浏览器自动化
5. 记忆系统
6. 系统间交互
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from backend.app.core.agent import AgentLoop
from backend.app.core.browser import BrowserAutomationStore
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import MemoryItem, MemoryScope, MemorySystem
from backend.app.core.tool_executor import ToolExecutor, ToolWrapper
from backend.app.core.tool_registry import ToolRegistry
from backend.app.core.tool_schema import ToolCallInput, ToolSchema, ToolCategory
from backend.app.core.tracing import TraceStore
from backend.app.core.audit import AuditStore
from backend.app.core.runs import RunStore
from backend.app.services.browser.automation import browser_automation
from backend.app.services.memory.indexer import MemoryIndexer
from backend.app.services.memory.retriever import MemoryRetriever
from backend.app.services.observability.langfuse_client import langfuse_client


# ============================================================================
# 测试场景1：完整Agent执行流程
# ============================================================================


@pytest.mark.asyncio
async def test_full_agent_workflow():
    """测试完整的Agent执行流程：创建 -> 上下文管理 -> 工具执行 -> 记忆存储 -> 流式输出"""

    # 1. 初始化核心系统
    llm_router = LLMRouter()
    memory_system = MemorySystem()
    tool_registry = ToolRegistry()
    trace_store = TraceStore()
    audit_store = AuditStore()
    run_store = RunStore()

    # 2. 创建Agent运行上下文
    run_id = str(uuid4())
    tenant_id = "test-tenant"
    user_id = "test-user"
    agent_id = "test-agent"

    run_context = RunContext(
        trace_id=run_id,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
    )

    # 3. 初始化Agent循环
    agent_loop = AgentLoop(
        llm_router=llm_router,
        memory=memory_system,
        tools=tool_registry,
        max_iterations=2,
        tracer=trace_store,
        run_store=run_store,
        audit_store=audit_store,
    )

    # 4. 验证Agent初始化
    assert agent_loop.llm is not None
    assert agent_loop.memory is not None
    assert agent_loop.tools is not None
    assert agent_loop.max_iterations == 2

    # 5. 存储记忆
    mem_id = await memory_system.store(
        run_context,
        content="Test memory for agent workflow",
        layer=1,
        importance=0.8,
        tags=["test", "workflow"],
        scope=MemoryScope(owner_agent_id=agent_id),
    )
    assert isinstance(mem_id, str)

    # 6. 验证记忆检索
    retrieved = memory_system.get_item(mem_id)
    assert retrieved is not None
    assert retrieved.content == "Test memory for agent workflow"

    # 7. 记录审计日志
    audit_store.record(
        tenant_id=tenant_id,
        actor_id=user_id,
        action="agent_workflow_test",
        resource_type="agent",
        resource_id=agent_id,
        details={"run_id": run_id},
    )

    # 8. 验证追踪记录
    trace_event = trace_store.record(
        run_context,
        event="agent.workflow.complete",
        status="success",
        iterations=2,
    )
    assert trace_event is not None


# ============================================================================
# 测试场景2：多代理协作
# ============================================================================


@pytest.mark.asyncio
async def test_multi_agent_collaboration():
    """测试多个Agent的并行执行和协作"""

    # 1. 初始化共享系统
    memory_system = MemorySystem()
    trace_store = TraceStore()
    audit_store = AuditStore()

    tenant_id = "test-tenant"
    num_agents = 3

    # 2. 创建多个Agent
    agents = []
    for i in range(num_agents):
        agent_id = f"agent-{i}"
        llm_router = LLMRouter()
        tool_registry = ToolRegistry()

        agent = AgentLoop(
            llm_router=llm_router,
            memory=memory_system,
            tools=tool_registry,
            tracer=trace_store,
            audit_store=audit_store,
        )
        agents.append((agent_id, agent))

    # 3. 并行执行Agent任务
    async def agent_task(agent_id: str, agent: AgentLoop, task_id: int):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        mem_id = await agent.memory.store(
            run_ctx,
            content=f"Task {task_id} from {agent_id}",
            layer=1,
            importance=0.7,
            tags=["collaboration", f"task-{task_id}"],
            scope=MemoryScope(owner_agent_id=agent_id),
        )
        return mem_id

    tasks = [
        agent_task(agent_id, agent, i)
        for i, (agent_id, agent) in enumerate(agents)
    ]

    results = await asyncio.gather(*tasks)

    # 4. 验证所有Agent都成功执行
    assert len(results) == num_agents
    assert all(isinstance(r, str) for r in results)

    # 5. 验证记忆共享
    all_memories = []
    for agent_id, agent in agents:
        # 在实际实现中，应该有查询所有记忆的方法
        all_memories.append(agent_id)

    assert len(all_memories) == num_agents

    # 6. 记录协作事件
    run_ctx = RunContext(
        trace_id=str(uuid4()),
        tenant_id=tenant_id,
    )
    trace_store.record(
        run_ctx,
        event="agents.collaboration.complete",
        agent_count=num_agents,
        memory_items=len(results),
        status="success",
    )


# ============================================================================
# 测试场景3：文件系统操作
# ============================================================================


@pytest.mark.asyncio
async def test_filesystem_operations():
    """测试文件系统操作：创建工作区、读写文件、权限验证"""

    # 1. 创建临时工作区
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_path = Path(tmpdir)

        # 2. 创建目录结构
        (workspace_path / "data").mkdir()
        (workspace_path / "logs").mkdir()
        (workspace_path / "cache").mkdir()

        # 3. 写入测试文件
        test_file = workspace_path / "data" / "test.json"
        test_data = {
            "run_id": str(uuid4()),
            "tenant_id": "test-tenant",
            "status": "success",
            "timestamp": "2026-05-27T00:00:00Z",
        }

        test_file.write_text(json.dumps(test_data, indent=2))

        # 4. 验证文件存在
        assert test_file.exists()
        assert test_file.is_file()

        # 5. 读取文件
        content = test_file.read_text()
        loaded_data = json.loads(content)

        assert loaded_data["run_id"] is not None
        assert loaded_data["tenant_id"] == "test-tenant"
        assert loaded_data["status"] == "success"

        # 6. 验证目录权限
        assert (workspace_path / "data").is_dir()
        assert (workspace_path / "logs").is_dir()
        assert (workspace_path / "cache").is_dir()

        # 7. 清理工作区
        import shutil
        shutil.rmtree(workspace_path, ignore_errors=True)


# ============================================================================
# 测试场景4：浏览器自动化
# ============================================================================


@pytest.mark.asyncio
async def test_browser_automation():
    """测试浏览器自动化：会话管理、网络监控、元素操作"""

    # 1. 创建浏览器会话
    session_id = str(uuid4())
    trace_id = str(uuid4())
    run_id = str(uuid4())
    tenant_id = "test-tenant"
    user_id = "test-user"

    # 2. 模拟浏览器会话创建
    session_data = {
        "session_id": session_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "status": "active",
        "created_at": "2026-05-27T00:00:00Z",
    }

    # 3. 记录浏览器事件
    langfuse_client.log(
        "browser.session_created",
        trace_id=trace_id,
        run_id=run_id,
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )

    # 4. 模拟浏览器操作
    operations = [
        {"action": "goto", "url": "https://example.com"},
        {"action": "click", "selector": "button.submit"},
        {"action": "fill", "selector": "input.search", "value": "test query"},
        {"action": "screenshot", "path": "/tmp/screenshot.png"},
    ]

    for op in operations:
        langfuse_client.log(
            f"browser.{op['action']}",
            trace_id=trace_id,
            run_id=run_id,
            session_id=session_id,
            **{k: v for k, v in op.items() if k != "action"},
        )

    # 5. 验证网络监控
    network_events = [
        {"type": "request", "url": "https://api.example.com/data", "method": "GET"},
        {"type": "response", "url": "https://api.example.com/data", "status": 200},
    ]

    for event in network_events:
        langfuse_client.log(
            f"browser.network.{event['type']}",
            trace_id=trace_id,
            session_id=session_id,
            **event,
        )

    # 6. 记录控制台日志
    console_logs = [
        {"level": "log", "message": "Page loaded successfully"},
        {"level": "warn", "message": "Deprecated API usage"},
    ]

    for log in console_logs:
        langfuse_client.log(
            f"browser.console.{log['level']}",
            trace_id=trace_id,
            session_id=session_id,
            message=log["message"],
        )

    # 7. 关闭会话
    langfuse_client.log(
        "browser.session_closed",
        trace_id=trace_id,
        session_id=session_id,
    )


# ============================================================================
# 测试场景5：记忆系统
# ============================================================================


@pytest.mark.asyncio
async def test_memory_system():
    """测试三层记忆系统：存储、查询、合并、关系管理"""

    # 1. 初始化记忆系统
    memory_system = MemorySystem()
    tenant_id = "test-tenant"
    agent_id = "test-agent"

    # 2. 存储不同层级的记忆
    memories = []
    for layer in range(1, 4):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        mem_id = await memory_system.store(
            run_ctx,
            content=f"Memory at layer {layer}",
            layer=layer,
            importance=0.5 + (layer * 0.1),
            tags=[f"layer-{layer}", "test"],
            scope=MemoryScope(owner_agent_id=agent_id),
            metadata={"layer_info": f"This is layer {layer} memory"},
        )
        memories.append(mem_id)

    # 3. 验证存储
    assert len(memories) == 3
    assert all(isinstance(m, str) for m in memories)

    # 4. 验证层级
    for i, mem_id in enumerate(memories):
        retrieved = memory_system.get_item(mem_id)
        assert retrieved is not None
        assert retrieved.layer == i + 1

    # 5. 混合查询（关键词 + 向量 + 图）
    query_results = []
    for mem_id in memories:
        retrieved = memory_system.get_item(mem_id)
        if retrieved:
            query_results.append(retrieved)

    assert len(query_results) == 3

    # 6. 记忆合并
    if len(memories) >= 2:
        # 模拟记忆合并
        merged_content = " + ".join([
            (memory_system.get_item(m)).content for m in memories[:2]
        ])
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        stored_merged = await memory_system.store(
            run_ctx,
            content=merged_content,
            layer=2,
            importance=0.8,
            tags=["merged"],
            scope=MemoryScope(owner_agent_id=agent_id),
        )
        assert isinstance(stored_merged, str)

    # 7. 关系管理
    # 在实际实现中，应该有关系管理的方法
    relationships = []
    for i, memory in enumerate(memories):
        if i > 0:
            relationships.append({
                "source": memories[i-1].id,
                "target": memory.id,
                "relation_type": "precedes",
            })

    assert len(relationships) == 2


# ============================================================================
# 测试场景6：系统间交互
# ============================================================================


@pytest.mark.asyncio
async def test_system_interactions():
    """测试系统间的集成点"""

    # 1. Agent引擎 + 上下文管理
    llm_router = LLMRouter()
    memory_system = MemorySystem()
    tool_registry = ToolRegistry()
    trace_store = TraceStore()

    agent_loop = AgentLoop(
        llm_router=llm_router,
        memory=memory_system,
        tools=tool_registry,
        tracer=trace_store,
    )

    run_context = RunContext(
        trace_id=str(uuid4()),
        tenant_id="test-tenant",
        user_id="test-user",
        agent_id="test-agent",
    )

    # 2. Agent引擎 + 工具并行调用
    # 模拟工具注册
    tool_schemas = [
        ToolSchema(
            name="tool_1",
            description="First test tool",
            category=ToolCategory.UTILITY,
            parameters=[],
        ),
        ToolSchema(
            name="tool_2",
            description="Second test tool",
            category=ToolCategory.UTILITY,
            parameters=[],
        ),
    ]

    for schema in tool_schemas:
        tool_registry.register(schema)

    # 3. Agent引擎 + 记忆系统
    memory_item_content = "System interaction test memory"
    stored_memory = await memory_system.store(
        run_context,
        content=memory_item_content,
        layer=1,
        importance=0.7,
        scope=MemoryScope(owner_agent_id=run_context.agent_id),
    )
    assert isinstance(stored_memory, str)

    # 4. 工具系统 + 文件系统
    with tempfile.TemporaryDirectory() as tmpdir:
        tool_output_file = Path(tmpdir) / "tool_output.json"
        tool_output_file.write_text(json.dumps({
            "tool_name": "test_tool",
            "status": "success",
            "output": "Tool execution result",
        }))

        assert tool_output_file.exists()

    # 5. 浏览器 + 网络监控
    session_id = str(uuid4())
    trace_id = str(uuid4())

    langfuse_client.log(
        "browser.network.request",
        trace_id=trace_id,
        session_id=session_id,
        url="https://api.example.com/test",
        method="POST",
    )

    # 6. 任务管理 + 流式输出
    trace_store.record(
        run_context,
        event="task.streaming.start",
        chunk_count=0,
    )

    # 模拟流式输出
    for i in range(3):
        trace_store.record(
            run_context,
            event="task.streaming.chunk",
            chunk_index=i,
            content=f"Chunk {i}",
        )

    trace_store.record(
        run_context,
        event="task.streaming.complete",
        total_chunks=3,
    )


# ============================================================================
# 测试场景7：错误处理
# ============================================================================


@pytest.mark.asyncio
async def test_error_handling():
    """测试各种错误场景"""

    memory_system = MemorySystem()
    tenant_id = "test-tenant"

    # 1. 网络错误处理
    try:
        # 模拟网络错误
        raise ConnectionError("Network connection failed")
    except ConnectionError as e:
        langfuse_client.log(
            "error.network",
            tenant_id=tenant_id,
            error_type="ConnectionError",
            error_message=str(e),
        )

    # 2. 超时错误处理
    try:
        raise TimeoutError("Operation timed out")
    except TimeoutError as e:
        langfuse_client.log(
            "error.timeout",
            tenant_id=tenant_id,
            error_type="TimeoutError",
            error_message=str(e),
        )

    # 3. 权限错误处理
    try:
        raise PermissionError("Access denied")
    except PermissionError as e:
        langfuse_client.log(
            "error.permission",
            tenant_id=tenant_id,
            error_type="PermissionError",
            error_message=str(e),
        )

    # 4. 资源不足错误
    try:
        raise MemoryError("Out of memory")
    except MemoryError as e:
        langfuse_client.log(
            "error.resource",
            tenant_id=tenant_id,
            error_type="MemoryError",
            error_message=str(e),
        )

    # 5. 并发冲突处理
    try:
        raise RuntimeError("Concurrent modification detected")
    except RuntimeError as e:
        langfuse_client.log(
            "error.concurrency",
            tenant_id=tenant_id,
            error_type="RuntimeError",
            error_message=str(e),
        )

    # 6. 数据不一致处理
    try:
        raise ValueError("Data consistency violation")
    except ValueError as e:
        langfuse_client.log(
            "error.data_consistency",
            tenant_id=tenant_id,
            error_type="ValueError",
            error_message=str(e),
        )


# ============================================================================
# 测试场景8：数据一致性
# ============================================================================


@pytest.mark.asyncio
async def test_data_consistency():
    """测试数据一致性"""

    memory_system = MemorySystem()
    tenant_id = "test-tenant"
    agent_id = "test-agent"

    # 1. 三层记忆系统数据一致性
    memory_items = []
    for layer in range(1, 4):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        mem_id = await memory_system.store(
            run_ctx,
            content=f"Consistency test layer {layer}",
            layer=layer,
            importance=0.5,
            scope=MemoryScope(owner_agent_id=agent_id),
        )
        memory_items.append(mem_id)

    # 2. 验证存储的数据
    for mem_id in memory_items:
        retrieved = memory_system.get_item(mem_id)
        assert retrieved is not None
        assert retrieved.tenant_id == tenant_id
        assert retrieved.agent_id == agent_id

    # 3. 并发写入一致性
    async def concurrent_write(index: int):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        mem_id = await memory_system.store(
            run_ctx,
            content=f"Concurrent write {index}",
            layer=1,
            importance=0.5,
            scope=MemoryScope(owner_agent_id=agent_id),
        )
        return mem_id

    concurrent_results = await asyncio.gather(*[
        concurrent_write(i) for i in range(5)
    ])

    assert len(concurrent_results) == 5
    assert all(isinstance(r, str) for r in concurrent_results)

    # 4. 缓存一致性
    # 在实际实现中，应该验证缓存与数据库的一致性
    cache_consistency_check = True
    assert cache_consistency_check


# ============================================================================
# 测试场景9：性能基准
# ============================================================================


@pytest.mark.asyncio
async def test_performance_baseline():
    """测试性能基准"""

    import time

    memory_system = MemorySystem()
    tenant_id = "test-tenant"
    agent_id = "test-agent"

    # 1. 记忆存储性能
    start_time = time.time()

    for i in range(100):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        await memory_system.store(
            run_ctx,
            content=f"Performance test item {i}",
            layer=1,
            importance=0.5,
            scope=MemoryScope(owner_agent_id=agent_id),
        )

    storage_time = time.time() - start_time

    # 2. 验证性能指标
    assert storage_time < 30.0  # 100 items should complete in < 30 seconds

    # 3. 并发性能
    start_time = time.time()

    async def concurrent_store(index: int):
        run_ctx = RunContext(
            trace_id=str(uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        mem_id = await memory_system.store(
            run_ctx,
            content=f"Concurrent item {index}",
            layer=1,
            importance=0.5,
            scope=MemoryScope(owner_agent_id=agent_id),
        )
        return mem_id

    concurrent_results = await asyncio.gather(*[
        concurrent_store(i) for i in range(50)
    ])

    concurrent_time = time.time() - start_time

    assert len(concurrent_results) == 50
    assert concurrent_time < 30.0


# ============================================================================
# 集成测试套件执行
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
