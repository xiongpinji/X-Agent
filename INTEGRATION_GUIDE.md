# X-Agent v2 集成指南

**版本**: 2.0  
**日期**: 2026-05-26  
**状态**: 生产就绪

---

## 目录

1. [快速开始](#快速开始)
2. [架构概述](#架构概述)
3. [集成步骤](#集成步骤)
4. [API 参考](#api-参考)
5. [常见问题](#常见问题)
6. [故障排除](#故障排除)
7. [最佳实践](#最佳实践)

---

## 快速开始

### 基本使用

```python
from backend.app.core.agent_v2 import (
    AgentExecutor,
    AgentState,
    PhaseContext,
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    CompletionPhase,
)
from backend.app.core.contracts import RunContext
from backend.app.core.agent import AgentLoop, AgentTrajectory
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.tools import ToolRegistry

# 1. 创建必需的组件
llm_router = LLMRouter()
memory = InMemoryMemorySystem()
tools = ToolRegistry()
loop = AgentLoop(
    llm_router=llm_router,
    memory=memory,
    tools=tools,
)

# 2. 创建执行器
executor = AgentExecutor(max_iterations=4)

# 3. 创建运行上下文
context = RunContext(
    trace_id="my-trace-001",
    tenant_id="my-tenant",
    user_id="my-user",
)

# 4. 创建阶段上下文
trajectory = AgentTrajectory(
    task="My task",
    goal="My goal",
)
phase_context = PhaseContext(
    loop=loop,
    context=context,
    task="My task",
    trajectory=trajectory,
    extra_context={},
    execution_frame=...,  # 由初始化阶段填充
    task_frame=...,       # 由初始化阶段填充
    plan_frame=...,       # 由规划阶段填充
    compact_context={},
)

# 5. 创建阶段
init_phase = InitializationPhase()
planning_phase = PlanningPhase()
execution_phase = ExecutionPhase()
completion_phase = CompletionPhase()

# 6. 执行
phases = [
    (AgentState.INITIALIZING, init_phase),
    (AgentState.PLANNING, planning_phase),
    (AgentState.EXECUTING, execution_phase),
    (AgentState.COMPLETING, completion_phase),
]

response = await executor.execute(
    context=context,
    task="My task",
    phase_context=phase_context,
    phases=phases,
)

print(f"Status: {response.status}")
print(f"Answer: {response.answer}")
```

---

## 架构概述

### 执行流程

```
┌─────────────────────────────────────────────────────────┐
│                    AgentExecutor                        │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ State Machine                                    │  │
│  │ IDLE → INITIALIZING → PLANNING → EXECUTING →    │  │
│  │ COMPLETING → COMPLETED                          │  │
│  │                    ↕                             │  │
│  │                 RECOVERING                       │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Phase Execution                                  │  │
│  │ ├─ InitializationPhase                          │  │
│  │ ├─ PlanningPhase                                │  │
│  │ ├─ ExecutionPhase                               │  │
│  │ ├─ RecoveryPhase (optional)                     │  │
│  │ └─ CompletionPhase                              │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Shared Context (PhaseContext)                    │  │
│  │ ├─ RunContext (trace, auth, budget)             │  │
│  │ ├─ TaskFrame (goal, constraints)                │  │
│  │ ├─ PlanFrame (steps, dependencies)              │  │
│  │ ├─ ExecutionFrame (status, history)             │  │
│  │ └─ Tool calls, observations, answer             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 组件交互

```
AgentExecutor
    ├─ LLMRouter (规划和决策)
    ├─ MemorySystem (上下文和学习)
    ├─ ToolRegistry (工具执行)
    ├─ TraceStore (执行追踪)
    ├─ RunStore (运行持久化)
    └─ AgentStateManager (状态管理)
```

---

## 集成步骤

### 步骤 1: 安装依赖

```bash
# 确保已安装所有必需的依赖
pip install pydantic asyncio
```

### 步骤 2: 导入必需的模块

```python
from backend.app.core.agent_v2 import (
    AgentExecutor,
    AgentState,
    AgentStateManager,
    PhaseContext,
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    CompletionPhase,
    RecoveryPhase,
)
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.agent import AgentLoop
```

### 步骤 3: 初始化组件

```python
# 创建 LLM 路由器
llm_router = LLMRouter()

# 创建内存系统
memory = InMemoryMemorySystem()

# 创建工具注册表
tools = ToolRegistry()

# 创建代理循环
loop = AgentLoop(
    llm_router=llm_router,
    memory=memory,
    tools=tools,
    max_iterations=4,
)

# 创建追踪存储
trace_store = TraceStore()

# 创建运行存储
run_store = RunStore()
```

### 步骤 4: 创建执行器

```python
executor = AgentExecutor(max_iterations=4)
```

### 步骤 5: 准备执行上下文

```python
# 创建运行上下文
context = RunContext(
    trace_id="unique-trace-id",
    tenant_id="tenant-id",
    user_id="user-id",
    agent_id="agent-id",
    budget_tokens=16_000,
    budget_usd=1.0,
)

# 创建轨迹
trajectory = AgentTrajectory(
    task="User task",
    goal="Task goal",
)

# 创建阶段上下文
phase_context = PhaseContext(
    loop=loop,
    context=context,
    task="User task",
    trajectory=trajectory,
    extra_context={},
    execution_frame=ExecutionFrame(...),
    task_frame=TaskFrame(goal="Task goal"),
    plan_frame=PlanFrame(goal="Task goal"),
    compact_context={},
)
```

### 步骤 6: 创建和注册阶段

```python
# 创建阶段实例
init_phase = InitializationPhase()
planning_phase = PlanningPhase()
execution_phase = ExecutionPhase()
completion_phase = CompletionPhase()

# 注册阶段（可选）
executor.register_phase(AgentState.INITIALIZING, init_phase)
executor.register_phase(AgentState.PLANNING, planning_phase)
executor.register_phase(AgentState.EXECUTING, execution_phase)
executor.register_phase(AgentState.COMPLETING, completion_phase)
```

### 步骤 7: 执行

```python
# 定义阶段列表
phases = [
    (AgentState.INITIALIZING, init_phase),
    (AgentState.PLANNING, planning_phase),
    (AgentState.EXECUTING, execution_phase),
    (AgentState.COMPLETING, completion_phase),
]

# 执行
try:
    response = await executor.execute(
        context=context,
        task="User task",
        phase_context=phase_context,
        phases=phases,
    )
    
    # 处理响应
    if response.status == RunStatus.COMPLETED:
        print(f"Success: {response.answer}")
    else:
        print(f"Failed: {response.error}")
        
    # 保存运行记录
    run_store.save(context, "User task", response)
    
except Exception as e:
    print(f"Execution error: {e}")
```

### 步骤 8: 处理结果

```python
# 检查执行状态
if executor.is_completed():
    print("Execution completed")
    
# 获取状态历史
history = executor.get_state_history()
for state, timestamp in history:
    print(f"{state}: {timestamp}")
    
# 查询追踪事件
events = trace_store.list_events(context.trace_id)
for event in events:
    print(f"{event.event}: {event.data}")
```

---

## API 参考

### AgentExecutor

#### 初始化

```python
executor = AgentExecutor(max_iterations: int = 4)
```

**参数**:
- `max_iterations`: 最大迭代次数

#### 方法

##### execute()

```python
async def execute(
    context: RunContext,
    task: str,
    phase_context: PhaseContext,
    phases: list[tuple[AgentState, object]],
) -> AgentRunResponse
```

执行完整的代理工作流。

**参数**:
- `context`: 运行上下文
- `task`: 任务描述
- `phase_context`: 阶段共享上下文
- `phases`: 阶段列表

**返回**: AgentRunResponse

**异常**: Exception (执行失败时)

##### get_state()

```python
def get_state() -> AgentState
```

获取当前执行状态。

**返回**: 当前代理状态

##### get_state_history()

```python
def get_state_history() -> list[tuple[str, str]]
```

获取状态转换历史。

**返回**: (状态, 时间戳) 元组列表

##### is_completed()

```python
def is_completed() -> bool
```

检查执行是否完成。

**返回**: True 如果在 COMPLETED 或 FAILED 状态

##### pause()

```python
def pause() -> None
```

暂停执行。

##### resume()

```python
def resume() -> None
```

从暂停恢复执行。

##### reset()

```python
def reset() -> None
```

重置执行器到初始状态。

### AgentStateManager

#### 初始化

```python
state_manager = AgentStateManager()
```

#### 方法

##### transition_to()

```python
def transition_to(new_state: AgentState) -> None
```

转换到新状态。

**参数**:
- `new_state`: 目标状态

**异常**: InvalidStateTransitionError (无效转换)

##### get_state()

```python
def get_state() -> AgentState
```

获取当前状态。

**返回**: 当前状态

##### get_history()

```python
def get_history() -> list[tuple[AgentState, datetime]]
```

获取状态历史。

**返回**: (状态, 时间戳) 元组列表

##### is_terminal_state()

```python
def is_terminal_state() -> bool
```

检查是否在终止状态。

**返回**: True 如果在 COMPLETED 或 FAILED

##### is_paused()

```python
def is_paused() -> bool
```

检查是否暂停。

**返回**: True 如果暂停

##### reset()

```python
def reset() -> None
```

重置到初始状态。

### PhaseContext

#### 属性

```python
@dataclass
class PhaseContext:
    loop: AgentLoop                    # 代理循环引用
    context: RunContext                # 运行上下文
    task: str                          # 任务描述
    trajectory: AgentTrajectory        # 执行轨迹
    extra_context: dict                # 额外上下文
    execution_frame: ExecutionFrame    # 执行框架
    task_frame: TaskFrame              # 任务框架
    plan_frame: PlanFrame              # 计划框架
    compact_context: dict              # 压缩上下文
    tool_calls: list[ToolCallRecord]   # 工具调用
    observations: list[str]            # 观察
    answer: str                        # 最终答案
    iteration: int                     # 迭代计数
```

#### 方法

##### get_session_id()

```python
def get_session_id() -> str | None
```

获取会话 ID。

**返回**: 会话 ID 或 None

##### get_resume_trace_id()

```python
def get_resume_trace_id() -> str
```

获取恢复追踪 ID。

**返回**: 恢复追踪 ID 或空字符串

##### is_resuming()

```python
def is_resuming() -> bool
```

检查是否恢复执行。

**返回**: True 如果恢复

---

## 常见问题

### Q1: 如何处理执行失败？

**A**: 使用 try-except 块捕获异常，并检查响应状态：

```python
try:
    response = await executor.execute(...)
    if response.status == RunStatus.FAILED:
        print(f"Execution failed: {response.error}")
except Exception as e:
    print(f"Exception: {e}")
```

### Q2: 如何暂停和恢复执行？

**A**: 使用 pause() 和 resume() 方法：

```python
executor.pause()
# ... 做其他事情 ...
executor.resume()
```

### Q3: 如何访问执行历史？

**A**: 使用 get_state_history() 方法：

```python
history = executor.get_state_history()
for state, timestamp in history:
    print(f"{state}: {timestamp}")
```

### Q4: 如何自定义阶段？

**A**: 创建继承自基类的自定义阶段：

```python
class CustomPhase:
    async def execute(self, phase_context: PhaseContext) -> None:
        # 自定义逻辑
        pass
```

### Q5: 如何处理超时？

**A**: 使用 asyncio.wait_for()：

```python
try:
    response = await asyncio.wait_for(
        executor.execute(...),
        timeout=30.0
    )
except asyncio.TimeoutError:
    print("Execution timeout")
```

### Q6: 如何集成自定义工具？

**A**: 注册工具到 ToolRegistry：

```python
async def my_tool(arg1: str) -> str:
    return f"Result: {arg1}"

tool_def = ToolDefinition(
    name="my_tool",
    description="My custom tool",
    handler=my_tool,
    risk_level=RiskLevel.LOW,
)
tools.register(tool_def)
```

### Q7: 如何访问内存？

**A**: 使用 MemorySystem 接口：

```python
# 存储
memory_item = await memory.store(
    context=context,
    content="Important info",
    layer=1,
    tags=["important"],
)

# 检索
results = await memory.retrieve(
    context=context,
    query="Important",
    limit=10,
)
```

### Q8: 如何记录追踪事件？

**A**: 使用 TraceStore：

```python
trace_store.record(
    context=context,
    event="agent.started",
    task="My task",
)
```

---

## 故障排除

### 问题: InvalidStateTransitionError

**原因**: 尝试了无效的状态转换

**解决方案**: 检查状态转换规则，确保转换有效

```python
# 有效的转换
executor.state_manager.transition_to(AgentState.INITIALIZING)
executor.state_manager.transition_to(AgentState.PLANNING)

# 无效的转换（会抛出异常）
executor.state_manager.transition_to(AgentState.COMPLETED)  # 从 PLANNING 不能直接到 COMPLETED
```

### 问题: 执行超时

**原因**: 阶段执行耗时过长

**解决方案**: 增加超时时间或优化阶段逻辑

```python
# 增加超时
response = await asyncio.wait_for(
    executor.execute(...),
    timeout=60.0  # 60 秒
)
```

### 问题: 内存不足

**原因**: 存储了过多的追踪事件或运行记录

**解决方案**: 定期清理旧数据

```python
# 清理旧追踪
old_traces = trace_store.list_trace_ids()[100:]  # 保留最新 100 个
for trace_id in old_traces:
    # 删除逻辑
    pass
```

### 问题: 工具执行失败

**原因**: 工具不存在或参数错误

**解决方案**: 检查工具注册和参数

```python
# 检查工具是否存在
tool = tools.get("my_tool")
if tool is None:
    print("Tool not found")
    
# 检查参数
result = await tools.execute(
    context=context,
    tool_name="my_tool",
    arguments={"arg1": "value"},
)
```

### 问题: 追踪事件丢失

**原因**: 未正确记录事件

**解决方案**: 确保在正确的时间记录事件

```python
# 在执行开始时记录
trace_store.record(context, "agent.started")

# 在执行结束时记录
trace_store.record(context, "agent.completed")
```

---

## 最佳实践

### 1. 错误处理

始终使用 try-except 块处理异常：

```python
try:
    response = await executor.execute(...)
except Exception as e:
    logger.error(f"Execution failed: {e}")
    # 清理资源
    executor.reset()
```

### 2. 资源管理

在完成后清理资源：

```python
try:
    response = await executor.execute(...)
finally:
    # 清理资源
    executor.reset()
```

### 3. 日志记录

记录关键事件：

```python
logger.info(f"Starting execution: {context.trace_id}")
response = await executor.execute(...)
logger.info(f"Execution completed: {response.status}")
```

### 4. 监控

监控执行性能：

```python
import time

start = time.time()
response = await executor.execute(...)
duration = time.time() - start

logger.info(f"Execution took {duration:.2f}s")
```

### 5. 测试

编写全面的测试：

```python
@pytest.mark.asyncio
async def test_execution():
    executor = AgentExecutor()
    response = await executor.execute(...)
    assert response.status == RunStatus.COMPLETED
```

### 6. 文档

记录自定义阶段和工具：

```python
class CustomPhase:
    """Custom execution phase.
    
    Handles custom logic during execution.
    """
    
    async def execute(self, phase_context: PhaseContext) -> None:
        """Execute custom phase.
        
        Args:
            phase_context: Shared execution context
        """
        pass
```

### 7. 版本控制

跟踪 API 版本：

```python
from backend.app.core.agent_v2 import __version__

print(f"Agent v2 version: {__version__}")
```

### 8. 性能优化

- 使用异步操作
- 缓存频繁访问的数据
- 批量处理操作

```python
# 异步执行多个任务
tasks = [
    executor.execute(...),
    executor.execute(...),
    executor.execute(...),
]
responses = await asyncio.gather(*tasks)
```

---

## 总结

X-Agent v2 提供了一个模块化、可扩展的执行架构。通过遵循本指南，你可以轻松集成新架构到现有系统中。

有问题？查看[常见问题](#常见问题)或[故障排除](#故障排除)部分。

---

**文档版本**: 2.0  
**最后更新**: 2026-05-26  
**维护者**: X-Agent 团队
