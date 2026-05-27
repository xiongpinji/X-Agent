# X-Agent v2 架构总览

## 概述

X-Agent v2 是一个基于**阶段化执行**的 Agent 核心架构，将复杂的 Agent 运行流程分解为独立、可测试、可扩展的执行阶段。

### 核心设计理念

- **单一职责**：每个阶段只负责一个明确的功能
- **低耦合**：阶段之间通过 `PhaseContext` 通信，减少依赖
- **高可测试性**：每个阶段可独立测试，无需完整的 Agent 环境
- **易于扩展**：新增功能只需添加新阶段或扩展现有阶段
- **可观测性**：完整的追踪、审计和日志支持

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      用户任务请求                              │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   InitializationPhase           │
        │  (初始化 & 编排准备)              │
        │  - 上下文压缩                    │
        │  - 代码索引                      │
        │  - 任务框架创建                  │
        │  - 编排决策                      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   PlanningPhase                 │
        │  (计划生成 & 优化)               │
        │  - LLM 计划生成                  │
        │  - 执行计划优化                  │
        │  - 步骤去重                      │
        │  - 恢复处理                      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   ExecutionPhase                │
        │  (迭代执行)                      │
        │  - 步骤分派                      │
        │  - 工具调用                      │
        │  - 观察收集                      │
        │  - 反思推理                      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   RecoveryPhase (可选)          │
        │  (故障恢复)                      │
        │  - 失败分析                      │
        │  - 修复建议                      │
        │  - 重试调度                      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   CompletionPhase               │
        │  (完成 & 响应)                   │
        │  - 结果存储                      │
        │  - 记忆更新                      │
        │  - 响应构建                      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │      最终响应返回                 │
        └────────────────────────────────┘
```

## 核心组件

### 1. PhaseContext（阶段上下文）

所有阶段共享的执行上下文，包含：

```python
@dataclass
class PhaseContext:
    # 核心引用
    loop: AgentLoop                          # Agent 循环实例
    context: RunContext                      # 运行上下文
    trajectory: AgentTrajectory              # 任务轨迹
    
    # 框架对象
    execution_frame: ExecutionFrame          # 执行框架
    task_frame: TaskFrame                    # 任务框架
    plan_frame: PlanFrame                    # 计划框架
    
    # 执行状态
    tool_calls: list[ToolCallRecord]         # 工具调用记录
    observations: list[str]                  # 观察结果
    answer: str                              # 最终答案
    iteration: int                           # 当前迭代数
    
    # 上下文数据
    task: str                                # 原始任务
    extra_context: dict[str, object]         # 额外上下文
    compact_context: dict[str, object]       # 压缩上下文
```

**关键方法**：
- `get_session_id()` - 获取会话 ID
- `get_resume_trace_id()` - 获取恢复追踪 ID
- `is_resuming()` - 检查是否为恢复执行

### 2. ExecutionPhase（抽象基类）

所有执行阶段的基类，定义标准接口：

```python
class ExecutionPhase:
    async def execute(self, phase_ctx: PhaseContext) -> Any:
        """执行阶段的主方法"""
        pass
    
    def _validate_context(self, phase_ctx: PhaseContext) -> None:
        """验证上下文完整性"""
        pass
```

### 3. 具体阶段实现

#### InitializationPhase（初始化阶段）

**职责**：
- 压缩和验证输入上下文
- 索引代码库
- 创建任务框架
- 初始化执行框架
- 运行编排决策
- 设置恢复框架

**关键方法**：
- `execute()` - 主执行方法（83 行，CC=1）
- `_compress_and_index()` - 上下文压缩和代码索引
- `_build_task_frame()` - 创建任务框架
- `_build_execution_frame()` - 创建执行框架
- `_run_orchestration()` - 运行编排
- `_handle_resumption()` - 处理恢复

**性能指标**：
- 代码行数：387 行（含文档）
- 圈复杂度：< 10
- 类型注解覆盖率：100%

#### PlanningPhase（规划阶段）

**职责**：
- 从 LLM 生成初始计划
- 应用执行计划优化
- 处理恢复场景
- 去重计划步骤
- 更新计划框架

**关键方法**：
- `execute()` - 主执行方法（35 行，CC=4）
- `_generate_plan()` - 生成初始计划
- `_initialize_plan_frame()` - 初始化计划框架
- `_handle_resume()` - 处理恢复
- `_finalize_plan_frame()` - 完成计划框架

**性能指标**：
- 代码行数：280 行（含文档）
- 圈复杂度：4
- 计划生成时间：100-500ms
- 去重时间：10-50ms

#### ExecutionPhase（执行阶段）

**职责**：
- 迭代执行计划步骤
- 分派步骤到处理器
- 管理工具执行
- 收集观察结果
- 处理反思推理

**关键方法**：
- `execute()` - 主执行循环（< 50 行）
- `_handle_observe_step()` - 处理观察步骤
- `_handle_tool_step()` - 处理工具步骤
- `_handle_reflect_step()` - 处理反思步骤
- `_handle_final_step()` - 处理最终步骤

**性能指标**：
- 每个处理器 < 30 行
- 主循环 < 50 行
- 支持最多 100 次迭代

#### RecoveryPhase（恢复阶段）

**职责**：
- 分析工具调用失败
- 生成修复建议
- 调度重试
- 更新恢复框架
- 跟踪重试预算

**关键方法**：
- `can_skip()` - 检查是否可跳过
- `execute()` - 主执行方法（< 60 行）
- `_analyze_failure()` - 分析失败
- `_schedule_retry()` - 调度重试

#### CompletionPhase（完成阶段）

**职责**：
- 构建执行摘要
- 存储记忆
- 更新会话摘要
- 创建最终响应
- 保存运行记录

**关键方法**：
- `execute()` - 主执行方法（< 80 行）
- `_build_execution_summary()` - 构建摘要
- `_store_memory()` - 存储记忆
- `_create_response()` - 创建响应

## 执行流程

### 标准执行流程

```python
# 1. 初始化
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# 2. 规划
planning_phase = PlanningPhase()
plan = await planning_phase.execute(phase_ctx)

# 3. 执行
execution_phase = ExecutionPhase()
answer, tool_calls = await execution_phase.execute(phase_ctx, plan)

# 4. 恢复（如果有失败）
if any(not call.success for call in tool_calls):
    recovery_phase = RecoveryPhase()
    await recovery_phase.execute(phase_ctx)

# 5. 完成
completion_phase = CompletionPhase()
response = await completion_phase.execute(phase_ctx)
```

### 恢复执行流程

```python
# 恢复执行时，InitializationPhase 会：
# 1. 检测 resume_trace_id
# 2. 从运行存储中加载前一次运行
# 3. 继承子任务、观察、工具结果
# 4. 调整计划以跳过已完成的步骤
# 5. 继续执行

phase_ctx.extra_context["resume_trace_id"] = previous_trace_id
await init_phase.execute(phase_ctx)
```

## 数据流

### 上下文流动

```
PhaseContext
├── 初始化阶段填充
│   ├── task_frame
│   ├── execution_frame
│   ├── compact_context
│   └── plan_frame
├── 规划阶段更新
│   ├── plan_frame.steps
│   └── plan_frame.status
├── 执行阶段更新
│   ├── tool_calls
│   ├── observations
│   ├── answer
│   └── iteration
├── 恢复阶段更新
│   └── execution_frame.recovery
└── 完成阶段最终化
    └── 所有字段冻结
```

### 事件追踪

每个阶段都会发出追踪事件：

```
InitializationPhase:
  - agent.run.started
  - agent.orchestration.prepared
  - agent.orchestration.drafted
  - agent.orchestration.tool_selected

PlanningPhase:
  - agent.task.decomposed
  - agent.plan.created

ExecutionPhase:
  - agent.iteration.started
  - agent.step.executed
  - agent.tool.called
  - agent.observation.recorded

RecoveryPhase:
  - agent.failure.analyzed
  - agent.retry.scheduled

CompletionPhase:
  - agent.run.completed
  - agent.memory.stored
```

## 集成指南

### 基本集成

```python
from backend.app.core.agent_v2 import (
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    RecoveryPhase,
    CompletionPhase,
    PhaseContext,
)

# 创建上下文
phase_ctx = PhaseContext(
    loop=agent_loop,
    context=run_context,
    task="Fix the bug",
    trajectory=agent_trajectory,
    extra_context={},
    execution_frame=ExecutionFrame(),
    task_frame=TaskFrame(),
    plan_frame=PlanFrame(),
    compact_context={},
)

# 执行阶段
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

planning_phase = PlanningPhase()
plan = await planning_phase.execute(phase_ctx)

execution_phase = ExecutionPhase()
answer, tool_calls = await execution_phase.execute(phase_ctx, plan)

# 检查是否需要恢复
if any(not call.success for call in tool_calls):
    recovery_phase = RecoveryPhase()
    await recovery_phase.execute(phase_ctx)

# 完成
completion_phase = CompletionPhase()
response = await completion_phase.execute(phase_ctx)
```

### 自定义阶段

```python
from backend.app.core.agent_v2 import ExecutionPhase, PhaseContext

class CustomPhase(ExecutionPhase):
    """自定义执行阶段"""
    
    async def execute(self, phase_ctx: PhaseContext) -> Any:
        """实现自定义逻辑"""
        # 验证上下文
        self._validate_context(phase_ctx)
        
        # 执行自定义逻辑
        result = await self._custom_logic(phase_ctx)
        
        # 更新上下文
        phase_ctx.answer = result
        
        return result
    
    async def _custom_logic(self, phase_ctx: PhaseContext) -> str:
        """自定义逻辑实现"""
        pass
```

## 性能特性

### 时间复杂度

| 阶段 | 操作 | 复杂度 |
|------|------|--------|
| 初始化 | 上下文压缩 | O(n) |
| 初始化 | 代码索引 | O(m) |
| 规划 | 计划生成 | O(n) |
| 规划 | 去重 | O(m²) |
| 执行 | 步骤执行 | O(k) |
| 恢复 | 失败分析 | O(f) |

其中：n=工具数，m=计划步骤数，k=迭代数，f=失败数

### 空间复杂度

| 组件 | 复杂度 |
|------|--------|
| PhaseContext | O(1) |
| 计划存储 | O(m) |
| 工具调用记录 | O(k) |
| 观察列表 | O(k) |

### 典型性能指标

| 操作 | 时间 |
|------|------|
| 初始化阶段 | 200-800ms |
| 规划阶段 | 150-600ms |
| 单次迭代 | 500-2000ms |
| 恢复阶段 | 100-300ms |
| 完成阶段 | 50-200ms |

## 错误处理

### 异常处理策略

```python
try:
    await init_phase.execute(phase_ctx)
except ValueError as e:
    logger.error(f"Context validation failed: {e}")
    # 返回错误响应
except Exception as e:
    logger.error(f"Initialization failed: {e}")
    # 记录审计并返回错误
```

### 恢复机制

- **自动重试**：工具调用失败时自动重试（最多 3 次）
- **修复建议**：RecoveryPhase 生成修复建议
- **人工干预**：高风险操作需要审批
- **优雅降级**：失败时使用备选方案

## 可观测性

### 日志

```python
logger.info(f"Initialization phase: {len(phase_ctx.task_frame.steps)} steps")
logger.info(f"Planning phase: {len(plan)} plan steps")
logger.info(f"Execution phase: iteration {phase_ctx.iteration}")
logger.info(f"Recovery phase: {len(failures)} failures")
logger.info(f"Completion phase: {len(phase_ctx.tool_calls)} tool calls")
```

### 指标

- 阶段执行时间
- 计划步骤数
- 工具调用数
- 失败率
- 恢复成功率

### 追踪

所有阶段都通过 `loop._emit_trace()` 发出追踪事件，支持完整的执行链路追踪。

## 最佳实践

### 1. 上下文管理

```python
# 好的做法：在阶段间传递完整的上下文
phase_ctx = PhaseContext(...)
await init_phase.execute(phase_ctx)
await planning_phase.execute(phase_ctx)

# 避免：创建多个上下文
ctx1 = PhaseContext(...)
ctx2 = PhaseContext(...)  # 数据不同步
```

### 2. 错误处理

```python
# 好的做法：捕获特定异常
try:
    await phase.execute(phase_ctx)
except ValueError as e:
    logger.error(f"Validation error: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")

# 避免：捕获所有异常
try:
    await phase.execute(phase_ctx)
except:
    pass
```

### 3. 性能优化

```python
# 好的做法：缓存计划
plan = await planning_phase.execute(phase_ctx)
# 重用计划多次
for _ in range(3):
    await execution_phase.execute(phase_ctx, plan)

# 避免：重复生成计划
for _ in range(3):
    plan = await planning_phase.execute(phase_ctx)
```

## 常见问题

### Q: 如何添加新的执行阶段？

A: 继承 `ExecutionPhase` 并实现 `execute()` 方法：

```python
class CustomPhase(ExecutionPhase):
    async def execute(self, phase_ctx: PhaseContext) -> Any:
        # 实现自定义逻辑
        pass
```

### Q: 如何处理阶段间的数据传递？

A: 通过 `PhaseContext` 传递数据。每个阶段可以读取和修改上下文中的字段。

### Q: 如何调试阶段执行？

A: 启用详细日志并检查追踪事件：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Q: 如何优化性能？

A: 
- 缓存计划生成结果
- 并行执行独立步骤
- 使用增量代码索引
- 优化 LLM 调用

## 参考资源

- [API 参考](API_REFERENCE.md) - 详细的 API 文档
- [迁移指南](MIGRATION_GUIDE.md) - 从旧架构迁移
- [故障排除](TROUBLESHOOTING.md) - 常见问题解决
- [集成指南](phases/INTEGRATION_GUIDE.md) - 规划阶段集成
- [实现总结](phases/IMPLEMENTATION_SUMMARY.md) - 规划阶段实现细节

## 版本信息

- **版本**：2.0.0
- **发布日期**：2026-05-26
- **状态**：生产就绪
- **维护者**：X-Agent 开发团队
