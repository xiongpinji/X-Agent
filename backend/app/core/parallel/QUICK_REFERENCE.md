# X-Agent 并行执行引擎 - 快速参考指南

## 模块概览

```
backend/app/core/parallel/
├── dependency_analyzer.py    # DAG构建、依赖分析、拓扑排序
├── tool_executor.py          # 工具并行执行、缓存、重试
├── agent_executor.py         # Agent并行执行、池管理、协调
├── communication_bus.py      # 消息、RPC、事件系统
├── integration.py            # 配置、管理、统计
└── __init__.py              # 导出接口
```

## API速查表

### 工具并行执行

```python
from backend.app.core.parallel import ParallelToolExecutor, ToolCall

# 创建执行器
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=10,
    default_timeout=30.0
)

# 定义工具调用
calls = [
    ToolCall(
        tool_name="tool1",
        arguments={"param": "value"},
        timeout_seconds=30,
        max_retries=3
    ),
    # ...
]

# 执行（无依赖）
results = await executor.execute_batch(calls)

# 执行（有依赖）
results_dict = await executor.execute_with_dependencies(calls)

# 获取统计
stats = executor.get_stats()
print(f"加速比: {stats.parallelism_factor}x")
print(f"成功: {stats.successful_calls}/{stats.total_calls}")
```

### Agent并行执行

```python
from backend.app.core.parallel import ParallelAgentExecutor, AgentTask

# 创建执行器
executor = ParallelAgentExecutor(
    max_workers=3,
    collaboration_mode="master_slave"
)

# 定义任务
tasks = [
    AgentTask(
        goal="Task 1",
        timeout_seconds=300,
        max_retries=3
    ),
    # ...
]

# 执行（无依赖）
result = await executor.execute_tasks(tasks, agent_factory)

# 执行（有依赖）
result = await executor.execute_with_coordination(tasks, agent_factory)

# 获取统计
stats = executor.get_pool_stats()
```

### Agent通信

```python
from backend.app.core.parallel import AgentCommunicationBus, MessagePriority

bus = AgentCommunicationBus()

# 直接消息
msg_id = await bus.send_direct(
    from_agent="agent1",
    to_agent="agent2",
    content={"data": "test"},
    priority=MessagePriority.HIGH
)

message = await bus.receive_direct("agent2", timeout_seconds=5.0)

# 广播消息
await bus.subscribe_broadcast("agent1")
msg_id = await bus.send_broadcast(
    from_agent="agent0",
    content={"data": "broadcast"}
)

# 主题消息
await bus.subscribe_topic("agent1", "task:completed")
msg_id = await bus.publish_topic(
    from_agent="agent0",
    topic="task:completed",
    content={"task_id": "123"}
)

# RPC调用
response = await bus.call_rpc(
    from_agent="agent1",
    to_agent="agent2",
    method="execute_task",
    params={"task_id": "123"}
)

# 事件系统
await bus.subscribe_event("task:started", event_handler)
await bus.publish_event(
    from_agent="agent1",
    event_type="task:started",
    event_data={"task_id": "123"}
)
```

### 系统集成

```python
from backend.app.core.parallel import (
    ParallelExecutionConfig,
    ParallelExecutionManager
)

# 配置
config = ParallelExecutionConfig(
    enable_tool_parallelism=True,
    enable_agent_parallelism=True,
    max_concurrent_tools=10,
    max_concurrent_agents=3,
    tool_timeout_seconds=30.0,
    agent_timeout_seconds=300,
    enable_caching=True,
    cache_ttl_seconds=3600,
    enable_communication_bus=True
)

# 创建管理器
manager = ParallelExecutionManager(tool_registry, config)

# 执行工具
results = await manager.execute_tools_parallel(
    tool_calls=[
        {"tool_name": "tool1", "arguments": {...}},
        # ...
    ]
)

# 执行Agent
results = await manager.execute_agents_parallel(
    tasks=[
        {"goal": "Task 1", ...},
        # ...
    ],
    agent_factory=agent_factory
)

# 发送消息
msg_id = await manager.send_message(
    from_agent="agent1",
    to_agent="agent2",
    content={"data": "test"},
    message_type="direct"
)

# 获取统计
stats = await manager.get_stats()
```

## 常见场景

### 场景1：并行执行多个独立工具

```python
# 问题：需要并行调用多个API
# 解决方案：使用execute_batch

calls = [
    ToolCall(tool_name="api1", arguments={"query": "data1"}),
    ToolCall(tool_name="api2", arguments={"query": "data2"}),
    ToolCall(tool_name="api3", arguments={"query": "data3"}),
]

results = await executor.execute_batch(calls)
# 串行: 3s → 并行: 1s (3x加速)
```

### 场景2：处理工具间的依赖

```python
# 问题：Tool2需要Tool1的输出
# 解决方案：使用execute_with_dependencies

calls = [
    ToolCall(tool_name="fetch_data", arguments={}),
    ToolCall(tool_name="process_data", arguments={"input": "${fetch_data.output}"}),
    ToolCall(tool_name="save_data", arguments={"input": "${process_data.output}"}),
]

results = await executor.execute_with_dependencies(calls)
# 自动识别依赖，分层执行
```

### 场景3：并行执行多个Agent任务

```python
# 问题：需要并行处理多个子任务
# 解决方案：使用execute_tasks

tasks = [
    AgentTask(goal="分析数据集1"),
    AgentTask(goal="分析数据集2"),
    AgentTask(goal="分析数据集3"),
]

result = await executor.execute_tasks(tasks, agent_factory)
# 3个Agent并行执行，3x加速
```

### 场景4：Agent间的协调

```python
# 问题：Agent2需要Agent1的结果
# 解决方案：使用execute_with_coordination

tasks = [
    AgentTask(task_id="task1", goal="收集数据"),
    AgentTask(task_id="task2", goal="分析数据", dependencies=["task1"]),
    AgentTask(task_id="task3", goal="生成报告", dependencies=["task2"]),
]

result = await executor.execute_with_coordination(tasks, agent_factory)
# 自动识别依赖，分层执行
```

### 场景5：Agent间的消息传递

```python
# 问题：Agent1需要发送消息给Agent2
# 解决方案：使用通信总线

# Agent1发送
await bus.send_direct(
    from_agent="agent1",
    to_agent="agent2",
    content={"task_id": "123", "data": {...}}
)

# Agent2接收
message = await bus.receive_direct("agent2")
task_id = message.content["task_id"]
```

### 场景6：事件驱动的Agent协调

```python
# 问题：多个Agent需要响应事件
# 解决方案：使用事件系统

# 订阅事件
async def on_task_completed(message):
    print(f"任务完成: {message.content['task_id']}")

await bus.subscribe_event("task:completed", on_task_completed)

# 发布事件
await bus.publish_event(
    from_agent="agent1",
    event_type="task:completed",
    event_data={"task_id": "123"}
)
```

## 性能优化建议

### 1. 调整并发度

```python
# 根据系统资源调整
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=20  # 增加并发度
)
```

### 2. 启用结果缓存

```python
from backend.app.core.parallel.tool_executor import ToolResultCache

cache = ToolResultCache(
    max_size=1000,
    ttl_seconds=3600
)

executor = ParallelToolExecutor(
    tool_registry=registry,
    cache=cache
)
```

### 3. 优化超时设置

```python
# 根据工具特性设置超时
calls = [
    ToolCall(tool_name="fast_api", arguments={}, timeout_seconds=5),
    ToolCall(tool_name="slow_api", arguments={}, timeout_seconds=60),
]
```

### 4. 使用优先级调度

```python
# 高优先级任务优先执行
await bus.send_direct(
    from_agent="agent1",
    to_agent="agent2",
    content={"urgent": True},
    priority=MessagePriority.CRITICAL
)
```

## 故障排查

### 问题1：任务超时

**症状**：任务执行超过timeout_seconds

**解决方案**：
```python
# 增加超时时间
ToolCall(tool_name="tool1", arguments={}, timeout_seconds=60)

# 或启用自适应超时
config = ParallelExecutionConfig(
    tool_timeout_seconds=60.0
)
```

### 问题2：循环依赖

**症状**：ValueError: Circular dependencies detected

**解决方案**：
```python
# 检查工具调用的依赖关系
# Tool1 -> Tool2 -> Tool1 (循环)
# 修改为：Tool1 -> Tool2 (无循环)
```

### 问题3：内存溢出

**症状**：内存使用持续增长

**解决方案**：
```python
# 减少并发度
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=5  # 降低并发
)

# 清空缓存
cache.clear()
```

### 问题4：消息丢失

**症状**：接收不到消息

**解决方案**：
```python
# 检查订阅
await bus.subscribe_topic("agent1", "task:completed")

# 增加超时时间
message = await bus.receive_direct("agent2", timeout_seconds=10.0)

# 检查消息TTL
await bus.send_direct(
    from_agent="agent1",
    to_agent="agent2",
    content={...},
    ttl_seconds=3600  # 设置足够长的TTL
)
```

## 监控和调试

### 获取执行统计

```python
stats = executor.get_stats()
print(f"总调用: {stats.total_calls}")
print(f"成功: {stats.successful_calls}")
print(f"失败: {stats.failed_calls}")
print(f"缓存: {stats.cached_calls}")
print(f"总延迟: {stats.total_latency_ms}ms")
print(f"执行层: {stats.execution_layers}")
print(f"加速比: {stats.parallelism_factor}x")
```

### 获取通信统计

```python
stats = await bus.get_stats()
print(f"总消息: {stats['total_messages']}")
print(f"直接队列: {stats['direct_queues']}")
print(f"主题队列: {stats['topic_queues']}")
print(f"RPC处理器: {stats['rpc_handlers']}")
print(f"事件处理器: {stats['event_handlers']}")
```

### 获取消息历史

```python
history = await bus.get_message_history(limit=100)
for msg in history:
    print(f"{msg['timestamp']}: {msg['from_agent']} -> {msg['to_agent']}")
    print(f"  内容: {msg['content']}")
```

## 最佳实践

### 1. 合理设置超时

```python
# 根据工具特性设置
- 快速API: 5-10秒
- 中等API: 30秒
- 慢速API: 60-300秒
```

### 2. 启用缓存

```python
# 对于幂等操作启用缓存
cache = ToolResultCache(ttl_seconds=3600)
executor = ParallelToolExecutor(tool_registry, cache=cache)
```

### 3. 监控性能

```python
# 定期检查加速比
stats = executor.get_stats()
if stats.parallelism_factor < 1.5:
    # 调查性能问题
    pass
```

### 4. 优雅处理错误

```python
# 使用allow_partial_failure
results = await executor.execute_batch(
    calls,
    allow_partial_failure=True
)

# 检查失败
for result in results:
    if not result.success:
        print(f"失败: {result.error}")
```

### 5. 使用优先级

```python
# 重要消息使用高优先级
await bus.send_direct(
    from_agent="agent1",
    to_agent="agent2",
    content={...},
    priority=MessagePriority.HIGH
)
```

## 参考资源

- **架构设计**: `ARCHITECTURE.md`
- **实现总结**: `IMPLEMENTATION_SUMMARY.md`
- **完成报告**: `COMPLETION_REPORT.md`
- **测试用例**: `tests/test_parallel_execution.py`
- **源代码**: `backend/app/core/parallel/`

## 支持和反馈

如有问题或建议，请：
1. 查看文档和示例
2. 运行测试用例
3. 检查日志和统计信息
4. 提交问题报告
