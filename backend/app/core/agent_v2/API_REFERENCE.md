# X-Agent v2 API 参考

## 目录

1. [PhaseContext](#phasecontext)
2. [ExecutionPhase](#executionphase)
3. [InitializationPhase](#initializationphase)
4. [PlanningPhase](#planningphase)
5. [ExecutionPhase](#executionphase-1)
6. [RecoveryPhase](#recoveryphase)
7. [CompletionPhase](#completionphase)
8. [数据模型](#数据模型)
9. [异常](#异常)

---

## PhaseContext

### 类定义

```python
@dataclass
class PhaseContext:
    """所有执行阶段的共享上下文。
    
    这个数据类封装了初始化、规划、执行和完成阶段所需的所有状态。
    它减少了参数传递，并为阶段交互提供了清晰的契约。
    """
```

### 属性

#### 核心引用

| 属性 | 类型 | 说明 |
|------|------|------|
| `loop` | `AgentLoop` | Agent 循环实例 |
| `context` | `RunContext` | 运行上下文（追踪、租户、用户、预算） |
| `trajectory` | `AgentTrajectory` | 任务轨迹（任务分解、进度） |

#### 框架对象

| 属性 | 类型 | 说明 |
|------|------|------|
| `execution_frame` | `ExecutionFrame` | 执行框架（追踪、状态管理） |
| `task_frame` | `TaskFrame` | 任务框架（目标、描述、风险等级） |
| `plan_frame` | `PlanFrame` | 计划框架（步骤、状态） |

#### 执行状态

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tool_calls` | `list[ToolCallRecord]` | `[]` | 执行的工具调用记录 |
| `observations` | `list[str]` | `[]` | 来自记忆和工具的观察 |
| `answer` | `str` | `""` | 最终答案（执行期间填充） |
| `iteration` | `int` | `0` | 当前迭代数（执行期间填充） |

#### 上下文数据

| 属性 | 类型 | 说明 |
|------|------|------|
| `task` | `str` | 原始任务字符串 |
| `extra_context` | `dict[str, object]` | 调用者传递的额外上下文 |
| `compact_context` | `dict[str, object]` | 压缩的上下文（用于 LLM 和编排） |

### 方法

#### get_session_id()

```python
def get_session_id(self) -> str | None:
    """获取会话 ID。
    
    从 context 或 extra_context 中获取会话 ID。
    
    Returns:
        会话 ID（如果可用），否则返回 None
    """
```

**示例**：
```python
session_id = phase_ctx.get_session_id()
if session_id:
    print(f"Session: {session_id}")
```

#### get_resume_trace_id()

```python
def get_resume_trace_id(self) -> str:
    """获取恢复追踪 ID。
    
    从 extra_context 中获取恢复追踪 ID。
    
    Returns:
        恢复追踪 ID（如果可用），否则返回空字符串
    """
```

**示例**：
```python
resume_id = phase_ctx.get_resume_trace_id()
if resume_id:
    print(f"Resuming from: {resume_id}")
```

#### is_resuming()

```python
def is_resuming(self) -> bool:
    """检查这是否为恢复执行。
    
    Returns:
        如果 resume_trace_id 存在且非空，返回 True
    """
```

**示例**：
```python
if phase_ctx.is_resuming():
    print("This is a resumed execution")
```

---

## ExecutionPhase

### 类定义

```python
class ExecutionPhase:
    """所有执行阶段的抽象基类。
    
    定义了标准的阶段执行接口和上下文验证方法。
    """
```

### 方法

#### execute()

```python
async def execute(self, phase_ctx: PhaseContext) -> Any:
    """执行阶段的主方法。
    
    Args:
        phase_ctx: 共享的执行上下文
    
    Returns:
        阶段特定的返回值
    
    Raises:
        ValueError: 如果上下文验证失败
        Exception: 如果执行失败
    """
```

#### _validate_context()

```python
def _validate_context(self, phase_ctx: PhaseContext) -> None:
    """验证上下文的完整性。
    
    Args:
        phase_ctx: 要验证的上下文
    
    Raises:
        ValueError: 如果必需的字段缺失
    """
```

---

## InitializationPhase

### 类定义

```python
class InitializationPhase(ExecutionPhase):
    """初始化执行上下文和状态。
    
    设置任务框架、执行框架、状态管理器和编排决策。
    这个阶段为规划和执行阶段准备所有必要的上下文。
    """
```

### 方法

#### execute()

```python
async def execute(self, phase_ctx: PhaseContext) -> None:
    """执行初始化阶段。
    
    Args:
        phase_ctx: 共享上下文。在原地修改以填充
                  task_frame、execution_frame 和 compact_context。
    
    Raises:
        ValueError: 如果必需的上下文缺失
        Exception: 如果编排或状态设置失败
    """
```

**执行步骤**：
1. 压缩上下文并索引代码
2. 创建任务框架
3. 初始化状态
4. 构建执行框架
5. 运行编排
6. 初始化恢复框架
7. 构建测试映射和执行计划
8. 处理运行恢复（如果适用）

**示例**：
```python
init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# 现在 phase_ctx 包含：
# - task_frame：任务目标和描述
# - execution_frame：执行追踪框架
# - compact_context：压缩的上下文
# - plan_frame：初始计划框架
```

### 私有方法

#### _compress_and_index()

```python
def _compress_and_index(
    self,
    loop: AgentLoop,
    phase_ctx: PhaseContext,
    task: str,
    extra_context: dict[str, object],
) -> None:
    """压缩上下文并索引代码库。
    
    Args:
        loop: AgentLoop 实例
        phase_ctx: 要填充的阶段上下文
        task: 原始任务
        extra_context: 额外上下文
    """
```

#### _build_task_frame()

```python
def _build_task_frame(
    self,
    loop: AgentLoop,
    context: RunContext,
    task: str,
    compact_context: dict[str, object],
) -> TaskFrame:
    """创建任务框架。
    
    Args:
        loop: AgentLoop 实例
        context: 运行上下文
        task: 任务字符串
        compact_context: 压缩的上下文
    
    Returns:
        填充的 TaskFrame
    """
```

#### _build_execution_frame()

```python
def _build_execution_frame(
    self,
    context: RunContext,
    task_frame: TaskFrame,
) -> ExecutionFrame:
    """创建执行框架。
    
    Args:
        context: 运行上下文
        task_frame: 任务框架
    
    Returns:
        初始化的 ExecutionFrame
    """
```

#### _run_orchestration()

```python
async def _run_orchestration(
    self,
    loop: AgentLoop,
    phase_ctx: PhaseContext,
    task: str,
) -> None:
    """运行编排决策。
    
    Args:
        loop: AgentLoop 实例
        phase_ctx: 阶段上下文
        task: 任务字符串
    """
```

#### _handle_resumption()

```python
async def _handle_resumption(
    self,
    loop: AgentLoop,
    phase_ctx: PhaseContext,
) -> None:
    """处理运行恢复。
    
    Args:
        loop: AgentLoop 实例
        phase_ctx: 阶段上下文
    """
```

---

## PlanningPhase

### 类定义

```python
class PlanningPhase(ExecutionPhase):
    """生成和优化执行计划。
    
    通过以下方式编排规划过程：
    1. 从 LLM 生成初始计划
    2. 应用执行计划优化
    3. 与子任务对齐
    4. 去重步骤
    """
```

### 方法

#### execute()

```python
async def execute(self, phase_ctx: PhaseContext) -> list[AgentPlanStep]:
    """执行规划阶段。
    
    Args:
        phase_ctx: 共享的执行上下文
    
    Returns:
        准备好执行的优化计划步骤列表
    
    Raises:
        Exception: 如果计划生成失败
    """
```

**执行步骤**：
1. 生成初始计划
2. 应用执行计划优化
3. 初始化计划框架（如需要）
4. 处理恢复场景
5. 发出任务分解事件
6. 最终去重
7. 更新计划框架
8. 记录计划创建事件

**示例**：
```python
planning_phase = PlanningPhase()
plan = await planning_phase.execute(phase_ctx)

# plan 是 AgentPlanStep 列表
for step in plan:
    print(f"Step: {step.kind} - {step.instruction}")
```

### 私有方法

#### _generate_plan()

```python
async def _generate_plan(
    self,
    loop: AgentLoop,
    context: RunContext,
    trajectory: AgentTrajectory,
    compact_context: dict[str, object],
) -> list[AgentPlanStep]:
    """从编排器和 LLM 生成初始计划。
    
    Args:
        loop: AgentLoop 实例
        context: 运行上下文
        trajectory: 任务轨迹
        compact_context: 压缩的上下文
    
    Returns:
        初始计划步骤列表
    """
```

#### _initialize_plan_frame()

```python
def _initialize_plan_frame(
    self,
    phase_ctx: PhaseContext,
    plan: list[AgentPlanStep],
) -> None:
    """初始化计划框架（如需要）。
    
    Args:
        phase_ctx: 阶段上下文
        plan: 计划步骤列表
    """
```

#### _handle_resume()

```python
async def _handle_resume(
    self,
    loop: AgentLoop,
    context: RunContext,
    phase_ctx: PhaseContext,
    plan: list[AgentPlanStep],
    resume_trace_id: str,
) -> list[AgentPlanStep]:
    """处理恢复场景。
    
    Args:
        loop: AgentLoop 实例
        context: 运行上下文
        phase_ctx: 阶段上下文
        plan: 当前计划
        resume_trace_id: 恢复追踪 ID
    
    Returns:
        过滤后的计划（跳过已完成的步骤）
    """
```

#### _finalize_plan_frame()

```python
def _finalize_plan_frame(
    self,
    phase_ctx: PhaseContext,
    plan: list[AgentPlanStep],
) -> None:
    """完成计划框架。
    
    Args:
        phase_ctx: 阶段上下文
        plan: 最终计划步骤列表
    """
```

---

## ExecutionPhase

### 类定义

```python
class ExecutionPhase(ExecutionPhase):
    """迭代执行计划步骤。
    
    主循环处理步骤顺序：observe -> tool -> reflect -> final。
    每个步骤类型都有专用的处理器方法（< 30 行）。
    主执行方法保持 < 50 行。
    """
```

### 方法

#### execute()

```python
async def execute(
    self,
    phase_ctx: PhaseContext,
    plan: list[AgentPlanStep],
) -> tuple[str, list[ToolCallRecord]]:
    """迭代执行计划步骤。
    
    Args:
        phase_ctx: 共享的执行上下文
        plan: 要执行的计划步骤列表
    
    Returns:
        (最终答案, 工具调用记录列表) 的元组
    """
```

**执行循环**：
```
while iteration < max_iterations and plan:
    step = plan.pop(0)
    
    # 检查步骤是否应该延迟
    if should_defer(step):
        plan.append(step)
        continue
    
    # 分派到处理器
    if step.kind == "observe":
        await _handle_observe_step(step)
    elif step.kind == "tool":
        await _handle_tool_step(step)
    elif step.kind == "reflect":
        await _handle_reflect_step(step)
    elif step.kind == "final":
        await _handle_final_step(step)
```

**示例**：
```python
execution_phase = ExecutionPhase()
answer, tool_calls = await execution_phase.execute(phase_ctx, plan)

print(f"Answer: {answer}")
print(f"Tool calls: {len(tool_calls)}")
```

### 私有方法

#### _handle_observe_step()

```python
async def _handle_observe_step(
    self,
    phase_ctx: PhaseContext,
    step: AgentPlanStep,
) -> None:
    """处理观察步骤。
    
    从记忆和工具中收集观察。
    
    Args:
        phase_ctx: 阶段上下文
        step: 观察步骤
    """
```

#### _handle_tool_step()

```python
async def _handle_tool_step(
    self,
    phase_ctx: PhaseContext,
    step: AgentPlanStep,
) -> None:
    """处理工具步骤。
    
    调用指定的工具并记录结果。
    
    Args:
        phase_ctx: 阶段上下文
        step: 工具步骤
    """
```

#### _handle_reflect_step()

```python
async def _handle_reflect_step(
    self,
    phase_ctx: PhaseContext,
    step: AgentPlanStep,
) -> None:
    """处理反思步骤。
    
    进行推理和反思。
    
    Args:
        phase_ctx: 阶段上下文
        step: 反思步骤
    """
```

#### _handle_final_step()

```python
async def _handle_final_step(
    self,
    phase_ctx: PhaseContext,
    step: AgentPlanStep,
) -> None:
    """处理最终步骤。
    
    生成最终答案。
    
    Args:
        phase_ctx: 阶段上下文
        step: 最终步骤
    """
```

---

## RecoveryPhase

### 类定义

```python
class RecoveryPhase(ExecutionPhase):
    """处理执行失败和重试调度。
    
    分析失败、生成修复建议并在适当时调度重试。
    """
```

### 方法

#### can_skip()

```python
def can_skip(self, phase_ctx: PhaseContext) -> bool:
    """检查恢复阶段是否可以跳过。
    
    如果工具调用中没有失败，恢复会被跳过。
    
    Args:
        phase_ctx: 共享的执行上下文
    
    Returns:
        如果没有失败存在，返回 True；否则返回 False
    """
```

**示例**：
```python
recovery_phase = RecoveryPhase()
if not recovery_phase.can_skip(phase_ctx):
    await recovery_phase.execute(phase_ctx)
```

#### execute()

```python
async def execute(self, phase_ctx: PhaseContext) -> None:
    """执行恢复阶段。
    
    分析失败、生成修复建议并调度重试。
    
    Args:
        phase_ctx: 共享的执行上下文（包含工具调用记录）
    """
```

**执行步骤**：
1. 收集失败的工具调用
2. 对每个失败进行分析
3. 生成修复建议
4. 调度重试
5. 更新恢复框架

**示例**：
```python
recovery_phase = RecoveryPhase()
await recovery_phase.execute(phase_ctx)

# 检查修复建议
repairs = phase_ctx.execution_frame.execution_summary.get("repair_suggestions", [])
for repair in repairs:
    print(f"Repair: {repair['suggestion']['reason']}")
```

### 私有方法

#### _analyze_failure()

```python
def _analyze_failure(
    self,
    loop: AgentLoop,
    failure: ToolCallRecord,
) -> tuple[Any, Any]:
    """分析工具调用失败。
    
    Args:
        loop: AgentLoop 实例
        failure: 失败的工具调用记录
    
    Returns:
        (验证结果, 修复建议) 的元组
    """
```

#### _schedule_retry()

```python
def _schedule_retry(
    self,
    phase_ctx: PhaseContext,
    failure: ToolCallRecord,
    repair_suggestion: Any,
) -> None:
    """调度重试。
    
    Args:
        phase_ctx: 阶段上下文
        failure: 失败的工具调用
        repair_suggestion: 修复建议
    """
```

---

## CompletionPhase

### 类定义

```python
class CompletionPhase(ExecutionPhase):
    """完成执行并构建响应。
    
    存储执行结果、构建执行摘要、更新会话记忆并创建最终响应。
    """
```

### 方法

#### execute()

```python
async def execute(self, phase_ctx: PhaseContext) -> AgentRunResponse:
    """执行完成阶段。
    
    通过存储结果和构建响应来完成执行。
    
    Args:
        phase_ctx: 包含执行结果的共享执行上下文
    
    Returns:
        包含最终执行结果的 AgentRunResponse
    """
```

**执行步骤**：
1. 记录审计
2. 确定会话 ID
3. 更新执行框架
4. 构建执行摘要
5. 存储记忆
6. 更新会话摘要
7. 创建最终响应
8. 保存运行记录
9. 发出完成追踪事件

**示例**：
```python
completion_phase = CompletionPhase()
response = await completion_phase.execute(phase_ctx)

print(f"Status: {response.status}")
print(f"Answer: {response.answer}")
print(f"Tool calls: {len(response.tool_calls)}")
```

### 私有方法

#### _build_execution_summary()

```python
def _build_execution_summary(
    self,
    loop: AgentLoop,
    trajectory: AgentTrajectory,
    observations: list[str],
    tool_calls: list[ToolCallRecord],
) -> dict[str, object]:
    """构建执行摘要。
    
    Args:
        loop: AgentLoop 实例
        trajectory: 任务轨迹
        observations: 观察列表
        tool_calls: 工具调用列表
    
    Returns:
        执行摘要字典
    """
```

#### _store_memory()

```python
async def _store_memory(
    self,
    loop: AgentLoop,
    context: RunContext,
    phase_ctx: PhaseContext,
    execution_summary: dict[str, object],
) -> None:
    """存储执行记忆。
    
    Args:
        loop: AgentLoop 实例
        context: 运行上下文
        phase_ctx: 阶段上下文
        execution_summary: 执行摘要
    """
```

#### _create_response()

```python
def _create_response(
    self,
    context: RunContext,
    phase_ctx: PhaseContext,
    execution_summary: dict[str, object],
) -> AgentRunResponse:
    """创建最终响应。
    
    Args:
        context: 运行上下文
        phase_ctx: 阶段上下文
        execution_summary: 执行摘要
    
    Returns:
        AgentRunResponse 对象
    """
```

---

## 数据模型

### AgentPlanStep

```python
class AgentPlanStep:
    """执行计划中的单个步骤。
    
    Attributes:
        kind: 步骤类型 ("observe", "tool", "reflect", "final")
        instruction: 步骤指令
        tool_name: 工具名称（如果 kind == "tool"）
        parameters: 工具参数（如果 kind == "tool"）
    """
```

### ToolCallRecord

```python
class ToolCallRecord:
    """工具调用的记录。
    
    Attributes:
        tool_name: 工具名称
        arguments: 工具参数
        result: 工具执行结果
        success: 是否成功
        error: 错误信息（如果失败）
        duration: 执行时间（毫秒）
    """
```

### ExecutionFrame

```python
class ExecutionFrame:
    """执行追踪框架。
    
    Attributes:
        plan: 执行计划
        memory: 记忆信息
        tool_history: 工具调用历史
        execution_summary: 执行摘要
        recovery: 恢复信息
    """
```

### TaskFrame

```python
class TaskFrame:
    """任务框架。
    
    Attributes:
        goal: 任务目标
        description: 任务描述
        risk_level: 风险等级
        steps: 任务步骤
    """
```

### PlanFrame

```python
class PlanFrame:
    """计划框架。
    
    Attributes:
        steps: 计划步骤列表
        status: 计划状态 ("draft", "ready", "executing", "completed")
        revision: 修订号
    """
```

### AgentRunResponse

```python
class AgentRunResponse:
    """Agent 运行的最终响应。
    
    Attributes:
        status: 运行状态 ("success", "failure", "partial")
        answer: 最终答案
        tool_calls: 工具调用列表
        observations: 观察列表
        execution_summary: 执行摘要
        trace_id: 追踪 ID
    """
```

---

## 异常

### ValueError

```python
raise ValueError("Required context field is missing")
```

在以下情况下抛出：
- 必需的上下文字段缺失
- 上下文验证失败

### RuntimeError

```python
raise RuntimeError("Phase execution failed")
```

在以下情况下抛出：
- 阶段执行失败
- 依赖项不可用

### TimeoutError

```python
raise TimeoutError("Phase execution timed out")
```

在以下情况下抛出：
- 阶段执行超时
- 工具调用超时

---

## 使用示例

### 基本使用

```python
from backend.app.core.agent_v2 import (
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
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

completion_phase = CompletionPhase()
response = await completion_phase.execute(phase_ctx)
```

### 错误处理

```python
try:
    await init_phase.execute(phase_ctx)
except ValueError as e:
    logger.error(f"Context validation failed: {e}")
    return error_response
except Exception as e:
    logger.error(f"Initialization failed: {e}")
    return error_response
```

### 恢复执行

```python
# 恢复执行
phase_ctx.extra_context["resume_trace_id"] = previous_trace_id

init_phase = InitializationPhase()
await init_phase.execute(phase_ctx)

# InitializationPhase 会自动处理恢复
```

---

## 版本信息

- **版本**：2.0.0
- **发布日期**：2026-05-26
- **状态**：生产就绪
