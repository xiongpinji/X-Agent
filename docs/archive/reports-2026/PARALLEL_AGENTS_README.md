# X-Agent 多代理并行执行系统

## 概述

X-Agent 多代理并行执行系统提供了完整的并行任务执行、代理间通信、结果聚合和任务依赖分析功能。该系统设计用于支持高效的多代理协作和任务并行化。

## 核心模块

### 1. ParallelAgentExecutor（并行执行器）

**文件**: `backend/app/core/parallel_agent_executor.py`

负责并行启动和管理多个代理实例。

**主要功能**:
- 支持3种隔离模式：process（进程）、thread（线程）、worktree（git工作树）
- 任务分发和调度
- 结果收集和聚合
- 超时控制和重试机制
- 错误处理

**核心方法**:
```python
async def spawn_agents(
    tasks: List[AgentTask],
    isolation: IsolationMode = IsolationMode.THREAD,
    max_parallel: int = 3
) -> BatchExecutionResult
```

**使用示例**:
```python
from backend.app.core.parallel_agent_executor import (
    ParallelAgentExecutor,
    AgentTask,
    IsolationMode,
)

executor = ParallelAgentExecutor(max_workers=3)

tasks = [
    AgentTask(goal="Task 1", timeout_seconds=60),
    AgentTask(goal="Task 2", timeout_seconds=60),
    AgentTask(goal="Task 3", timeout_seconds=60),
]

result = await executor.spawn_agents(
    tasks=tasks,
    isolation=IsolationMode.THREAD,
    max_parallel=3,
)

print(f"Completed: {result.completed_tasks}/{result.total_tasks}")
print(f"Duration: {result.total_duration_seconds:.2f}s")
```

### 2. AgentCommunicationBus（代理通信总线）

**文件**: `backend/app/core/agent_communication_bus.py`

实现代理间的消息传递和协调。

**主要功能**:
- 点对点消息传递
- 广播消息
- 主题订阅/发布
- 消息优先级
- 消息过期时间（TTL）
- 消息历史记录

**核心方法**:
```python
async def send_message(
    from_agent: str,
    to_agent: str,
    content: Any,
    priority: MessagePriority = MessagePriority.NORMAL,
) -> str

async def broadcast(
    from_agent: str,
    content: Any,
) -> str

async def publish(
    topic: str,
    content: Any,
    from_agent: Optional[str] = None,
) -> str

async def subscribe(
    agent_id: str,
    topic: str,
) -> None
```

**使用示例**:
```python
from backend.app.core.agent_communication_bus import (
    AgentCommunicationBus,
    MessagePriority,
)

bus = AgentCommunicationBus(enable_persistence=True)

# 发送直接消息
message_id = await bus.send_message(
    from_agent="agent_1",
    to_agent="agent_2",
    content={"task": "process_data"},
    priority=MessagePriority.HIGH,
)

# 接收消息
message = await bus.receive_message("agent_2")

# 发布到主题
await bus.publish(
    topic="results",
    content={"status": "completed"},
)

# 订阅主题
await bus.subscribe(agent_id="agent_3", topic="results")
```

### 3. ResultAggregator（结果聚合器）

**文件**: `backend/app/core/result_aggregator.py`

收集和合并多个代理的执行结果。

**主要功能**:
- 多种合并策略（merge、concat、reduce、first、last）
- 上下文合并
- 冲突检测和解决
- 结果验证和去重

**合并策略**:
- `MERGE`: 深度合并字典
- `CONCAT`: 连接列表
- `REDUCE`: 应用归约函数
- `FIRST`: 取第一个结果
- `LAST`: 取最后一个结果
- `CUSTOM`: 使用自定义函数

**使用示例**:
```python
from backend.app.core.result_aggregator import (
    ResultAggregator,
    AggregationConfig,
    MergeStrategy,
)

aggregator = ResultAggregator()

results = [
    {"output": {"a": 1}},
    {"output": {"b": 2}},
]

config = AggregationConfig(
    merge_strategy=MergeStrategy.MERGE,
)

aggregated = await aggregator.collect_results(results, config)
print(aggregated.merged_output)  # {"a": 1, "b": 2}
```

### 4. AgentIsolationManager（隔离管理器）

**文件**: `backend/app/core/agent_isolation_manager.py`

管理代理的隔离执行环境。

**主要功能**:
- 进程隔离（multiprocessing）
- 线程隔离（threading）
- Git worktree隔离
- 资源限制（CPU、内存）
- 资源监控
- 自动清理

**使用示例**:
```python
from backend.app.core.agent_isolation_manager import (
    AgentIsolationManager,
    IsolationType,
    ResourceLimits,
)

manager = AgentIsolationManager(enable_resource_monitoring=True)

limits = ResourceLimits(
    max_cpu_percent=80.0,
    max_memory_mb=512,
)

env = await manager.create_isolated_environment(
    agent_id="agent_1",
    isolation_type=IsolationType.THREAD,
    resource_limits=limits,
)

# 监控资源
resources = await manager.monitor_resources(env.env_id)

# 清理环境
await manager.cleanup_environment(env.env_id)
```

### 5. TaskDependencyAnalyzer（任务依赖分析器）

**文件**: `backend/app/core/task_dependency_analyzer.py`

分析任务依赖关系并优化执行计划。

**主要功能**:
- 构建依赖图（DAG）
- 拓扑排序
- 循环依赖检测
- 执行计划生成
- 并行度优化
- 关键路径分析

**使用示例**:
```python
from backend.app.core.task_dependency_analyzer import (
    TaskDependencyAnalyzer,
    Task,
)

analyzer = TaskDependencyAnalyzer()

tasks = [
    Task(task_id="1", name="Setup", dependencies=[]),
    Task(task_id="2", name="Build", dependencies=["1"]),
    Task(task_id="3", name="Test", dependencies=["2"]),
]

# 构建依赖图
dag = analyzer.build_dependency_graph(tasks)

# 检测循环
cycles = analyzer.detect_cycles(dag)

# 拓扑排序
topo_order = analyzer.topological_sort(dag)

# 生成执行计划
plan = analyzer.build_execution_plan(tasks)
for i, layer in enumerate(plan.layers):
    print(f"Layer {i}: {layer}")

# 分析并行度
analysis = analyzer.analyze_parallelism(dag)
print(f"Speedup potential: {analysis['speedup_potential']:.2f}x")
```

## API 端点

**文件**: `backend/app/api/parallel_agents.py`

### 并行执行端点

#### POST /api/v1/agents/parallel/spawn
启动并行代理执行。

**请求体**:
```json
{
  "tasks": [
    {
      "goal": "Task 1",
      "description": "Description",
      "timeout_seconds": 300,
      "max_retries": 3
    }
  ],
  "isolation": "thread",
  "max_parallel": 3,
  "aggregate_results": true,
  "merge_strategy": "merge",
  "conflict_resolution": "keep_last"
}
```

**响应**:
```json
{
  "batch_id": "uuid",
  "status": "completed",
  "total_tasks": 3,
  "completed_tasks": 3,
  "failed_tasks": 0,
  "total_duration_seconds": 5.2,
  "results": [...],
  "aggregated": {...}
}
```

#### GET /api/v1/agents/parallel/{batch_id}/status
获取批次执行状态。

#### GET /api/v1/agents/parallel/{batch_id}/results
获取批次执行结果。

**查询参数**:
- `aggregate`: 是否聚合结果（默认false）
- `merge_strategy`: 合并策略（默认merge）
- `conflict_resolution`: 冲突解决策略（默认keep_last）

#### POST /api/v1/agents/parallel/{batch_id}/cancel
取消批次执行。

### 通信总线端点

#### POST /api/v1/agents/parallel/messages/send
发送直接消息。

#### POST /api/v1/agents/parallel/messages/broadcast
广播消息。

#### POST /api/v1/agents/parallel/messages/publish
发布到主题。

#### GET /api/v1/agents/parallel/messages/stats
获取通信总线统计信息。

## 隔离模式对比

| 特性 | Process | Thread | Worktree |
|------|---------|--------|----------|
| 隔离程度 | 完全隔离 | 共享内存 | 文件系统隔离 |
| 开销 | 高 | 低 | 中 |
| 启动时间 | 500ms+ | <10ms | 1-2s |
| 内存占用 | 高 | 低 | 中 |
| 适用场景 | CPU密集 | I/O密集 | 文件操作 |

## 性能指标

### 目标性能

- 3个独立任务并行执行时间 < 1.5倍单任务时间
- 进程启动开销 < 500ms
- 消息传递延迟 < 10ms
- 支持至少10个并发代理

### 基准测试

运行测试套件获取性能基准：

```bash
pytest tests/test_parallel_agents.py::TestPerformance -v
```

## 测试

完整的测试套件位于 `tests/test_parallel_agents.py`。

### 运行所有测试

```bash
pytest tests/test_parallel_agents.py -v
```

### 运行特定测试类

```bash
# 并行执行器测试
pytest tests/test_parallel_agents.py::TestParallelAgentExecutor -v

# 通信总线测试
pytest tests/test_parallel_agents.py::TestAgentCommunicationBus -v

# 结果聚合器测试
pytest tests/test_parallel_agents.py::TestResultAggregator -v

# 性能测试
pytest tests/test_parallel_agents.py::TestPerformance -v
```

## 集成示例

### 完整工作流

```python
from backend.app.core.parallel_agents_integration import (
    example_complete_workflow,
)

# 运行完整工作流
await example_complete_workflow()
```

### 在FastAPI应用中集成

```python
from fastapi import FastAPI
from backend.app.api.parallel_agents import router

app = FastAPI()
app.include_router(router)
```

## 配置

在 `backend/app/core/parallel_agents_integration.py` 中修改 `ParallelAgentConfig` 类：

```python
class ParallelAgentConfig:
    MAX_WORKERS = 3
    DEFAULT_ISOLATION = "thread"
    ENABLE_PERSISTENCE = True
    MAX_QUEUE_SIZE = 10000
    ENABLE_RESOURCE_MONITORING = True
    MAX_CPU_PERCENT = 80.0
    MAX_MEMORY_MB = 512
```

## 最佳实践

### 1. 选择合适的隔离模式

- **Thread**: 适合I/O密集型任务（网络请求、数据库查询）
- **Process**: 适合CPU密集型任务（数据处理、计算）
- **Worktree**: 适合需要独立文件系统的任务

### 2. 设置合理的超时时间

```python
task = AgentTask(
    goal="Long running task",
    timeout_seconds=600,  # 10分钟
    max_retries=3,
)
```

### 3. 使用消息优先级

```python
await bus.send_message(
    from_agent="agent_1",
    to_agent="agent_2",
    content=data,
    priority=MessagePriority.HIGH,  # 高优先级
)
```

### 4. 监控资源使用

```python
resources = await manager.monitor_resources(env_id)
if resources["memory_mb"] > 500:
    logger.warning("High memory usage detected")
```

### 5. 处理依赖关系

```python
# 验证依赖关系
errors = analyzer.validate_dependencies(tasks)
if errors:
    raise ValueError(f"Invalid dependencies: {errors}")

# 生成执行计划
plan = analyzer.build_execution_plan(tasks)
```

## 故障排除

### 问题：任务超时

**解决方案**:
- 增加 `timeout_seconds`
- 检查系统资源是否充足
- 考虑使用更轻量级的隔离模式（thread）

### 问题：内存占用过高

**解决方案**:
- 减少 `max_parallel` 数量
- 使用 `ResourceLimits` 限制内存
- 定期清理环境

### 问题：消息丢失

**解决方案**:
- 启用 `enable_persistence=True`
- 检查消息队列大小
- 使用消息确认机制

### 问题：循环依赖

**解决方案**:
- 使用 `analyzer.detect_cycles()` 检测
- 使用 `analyzer.validate_dependencies()` 验证
- 重新设计任务依赖关系

## 扩展

### 自定义合并函数

```python
async def custom_merge(outputs):
    # 自定义合并逻辑
    return sum(outputs)

aggregator = ResultAggregatorFactory.create_custom_aggregator(
    merge_fn=custom_merge,
)
```

### 自定义隔离环境

继承 `AgentIsolationManager` 并实现自定义隔离逻辑。

### 自定义消息处理

```python
async def message_handler(message):
    print(f"Received: {message.content}")

await bus.register_handler("agent_1", message_handler)
```

## 许可证

MIT

## 贡献

欢迎提交问题和拉取请求。

## 联系方式

如有问题，请联系开发团队。
