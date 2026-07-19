"""X-Agent v2 InitializationPhase - Quick Reference Guide

## 快速开始

### 导入
```python
from backend.app.core.agent_v2 import (
    InitializationPhase,
    PhaseContext,
)
from backend.app.core.contracts import (
    RunContext,
    TaskFrame,
    ExecutionFrame,
    PlanFrame,
)
```

### 基本用法
```python
# 1. 创建 PhaseContext
phase_ctx = PhaseContext(
    loop=agent_loop,
    context=run_context,
    task="Fix the bug in utils.py",
    trajectory=agent_trajectory,
    extra_context={"root": "/path/to/repo"},
    execution_frame=ExecutionFrame(...),
    task_frame=TaskFrame(...),
    plan_frame=PlanFrame(...),
    compact_context={},
)

# 2. 执行初始化
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# 3. 使用填充的上下文
print(f"Goal: {phase_ctx.task_frame.goal}")
print(f"Plan: {phase_ctx.plan_frame.steps}")
```

## 关键概念

### PhaseContext
共享执行上下文，包含所有阶段需要的状态。

**主要属性**:
- `loop`: AgentLoop 实例
- `context`: RunContext (trace_id, tenant_id 等)
- `task`: 任务字符串
- `trajectory`: 任务分解和进度
- `execution_frame`: 追踪和状态
- `task_frame`: 目标和风险等级
- `plan_frame`: 执行计划
- `compact_context`: 压缩上下文

### InitializationPhase
初始化执行上下文和状态。

**职责**:
1. 压缩和索引代码
2. 创建任务框架
3. 初始化状态
4. 构建执行框架
5. 运行编排
6. 初始化恢复框架
7. 构建测试和执行计划
8. 处理运行恢复

## 方法参考

### execute(phase_ctx: PhaseContext) -> None
执行初始化阶段。

**参数**:
- `phase_ctx`: PhaseContext 实例

**修改的属性**:
- `phase_ctx.task_frame`: 创建的 TaskFrame
- `phase_ctx.execution_frame`: 创建的 ExecutionFrame
- `phase_ctx.compact_context`: 填充的压缩上下文
- `phase_ctx.plan_frame`: 设置的计划框架
- `phase_ctx.trajectory`: 如果恢复则填充

**异常**:
- `ValueError`: 如果上下文无效
- `Exception`: 如果初始化失败

### 私有方法

#### _compress_and_index(loop, phase_ctx, task, extra_context)
压缩上下文并索引代码库。

**功能**:
- 压缩 extra_context
- 索引代码库
- 映射测试文件

#### _build_task_frame(loop, context, task, compact_context)
构建任务框架。

**返回**: TaskFrame 实例

#### _build_execution_frame(context, task_frame)
构建执行框架。

**返回**: ExecutionFrame 实例

#### _run_orchestration(loop, phase_ctx, task)
运行编排。

**功能**:
- 准备编排上下文
- 草拟计划
- 选择工具

#### _build_test_and_execution_plan(loop, phase_ctx, task)
构建测试映射和执行计划。

**功能**:
- 验证总结
- 执行计划构建

#### _handle_resumption(loop, phase_ctx, trajectory)
处理运行恢复。

**功能**:
- 从 run_store 加载前一次运行
- 恢复子任务和状态
- 更新执行框架

## 常见用例

### 基本初始化
```python
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)
```

### 带恢复的初始化
```python
phase_ctx.extra_context["resume_trace_id"] = "prev-run-123"
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# 检查是否恢复
if phase_ctx.trajectory.stage.startswith("resuming:"):
    print("Resumed from previous run")
```

### 自定义代码索引
```python
phase_ctx.extra_context["root"] = "/custom/path"
phase_ctx.extra_context["index_limit"] = 5000
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)
```

### 检查编排决策
```python
await init_phase.execute(phase_ctx)

capability = phase_ctx.compact_context.get("capability_decision", {})
tool = phase_ctx.compact_context.get("tool_decision", {})

print(f"Capability: {capability.get('name')}")
print(f"Tool: {tool.get('tool_name')}")
```

## 错误处理

### 验证上下文
```python
try:
    await init_phase.execute(phase_ctx)
except ValueError as e:
    logger.error(f"Invalid context: {e}")
    # 处理无效上下文
except Exception as e:
    logger.error(f"Initialization failed: {e}")
    # 处理其他错误
```

### 检查恢复状态
```python
await init_phase.execute(phase_ctx)

resume_policy = phase_ctx.execution_frame.execution_summary.get("resume_policy", {})
if resume_policy.get("subtasks_inherited"):
    print("Subtasks inherited from previous run")
```

## 性能优化

### 限制代码索引
```python
phase_ctx.extra_context["index_limit"] = 1000  # 默认 2000
```

### 限制测试映射
```python
# 在 _compress_and_index 中修改
test_mapping = test_mapper.map(task, limit=3)  # 默认 6
```

## 调试

### 启用详细日志
```python
import logging
logger = logging.getLogger("agent_v2.initialization")
logger.setLevel(logging.DEBUG)
```

### 检查压缩上下文
```python
await init_phase.execute(phase_ctx)
print(json.dumps(phase_ctx.compact_context, indent=2, default=str))
```

### 检查执行框架
```python
await init_phase.execute(phase_ctx)
print(phase_ctx.execution_frame.model_dump(indent=2))
```

## 与其他阶段的集成

### 完整管道
```python
from backend.app.core.agent_v2 import (
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    CompletionPhase,
)

# 初始化
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# 规划
planning_phase = PlanningPhase()
plan = await planning_phase.execute(phase_ctx)

# 执行
execution_phase = ExecutionPhase()
answer, tool_calls = await execution_phase.execute(phase_ctx, plan)

# 完成
completion_phase = CompletionPhase()
response = await completion_phase.execute(phase_ctx)
```

## 已知限制

1. 代码索引限制为 2000 个文件（可配置）
2. 测试映射限制为 6 个文件（可配置）
3. 恢复仅支持单个前一次运行
4. 不支持并行初始化

## 后续改进

- [ ] 支持增量代码索引
- [ ] 支持多个前一次运行的恢复
- [ ] 支持并行初始化
- [ ] 缓存编排决策
- [ ] 支持自定义初始化钩子
"""
