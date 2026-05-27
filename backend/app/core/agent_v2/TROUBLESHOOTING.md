# X-Agent v2 故障排除指南

## 概述

本指南帮助诊断和解决 X-Agent v2 执行过程中的常见问题。

---

## 初始化阶段问题

### 问题 1: 上下文验证失败

**症状**：
```
ValueError: Required context field is missing
```

**原因**：
- `PhaseContext` 中缺少必需的字段
- 字段值为 `None` 或无效

**诊断**：
```python
# 检查上下文完整性
def validate_context(phase_ctx):
    required_fields = [
        'loop', 'context', 'task', 'trajectory',
        'execution_frame', 'task_frame', 'plan_frame'
    ]
    for field in required_fields:
        value = getattr(phase_ctx, field, None)
        if value is None:
            print(f"Missing field: {field}")
        else:
            print(f"✓ {field}: {type(value).__name__}")
```

**解决方案**：
```python
# 确保所有必需字段都已初始化
phase_ctx = PhaseContext(
    loop=agent_loop,                    # ✓ 必需
    context=run_context,                # ✓ 必需
    task="Fix the bug",                 # ✓ 必需
    trajectory=agent_trajectory,        # ✓ 必需
    extra_context={},                   # ✓ 必需
    execution_frame=ExecutionFrame(),   # ✓ 必需
    task_frame=TaskFrame(),             # ✓ 必需
    plan_frame=PlanFrame(),             # ✓ 必需
    compact_context={},                 # ✓ 必需
)
```

### 问题 2: 代码索引失败

**症状**：
```
Exception: Failed to index code repository
```

**原因**：
- 代码库路径不存在
- 权限不足
- 代码库太大

**诊断**：
```python
# 检查代码库路径
import os
repo_path = phase_ctx.extra_context.get("repo_path")
if not os.path.exists(repo_path):
    print(f"Repository path not found: {repo_path}")
else:
    print(f"✓ Repository path exists: {repo_path}")
    print(f"  Size: {sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, dirnames, filenames in os.walk(repo_path) for filename in filenames)} bytes")
```

**解决方案**：
```python
# 1. 检查路径
assert os.path.exists(repo_path), f"Repository not found: {repo_path}"

# 2. 检查权限
assert os.access(repo_path, os.R_OK), f"No read permission: {repo_path}"

# 3. 限制索引大小
phase_ctx.extra_context["max_index_size"] = 100 * 1024 * 1024  # 100MB

# 4. 使用增量索引
phase_ctx.extra_context["incremental_index"] = True
```

### 问题 3: 编排失败

**症状**：
```
Exception: Orchestration failed
```

**原因**：
- 编排器未初始化
- LLM 调用失败
- 工具选择失败

**诊断**：
```python
# 检查编排器
if not hasattr(phase_ctx.loop, 'orchestrator'):
    print("✗ Orchestrator not initialized")
else:
    print("✓ Orchestrator initialized")

# 检查 LLM
if not hasattr(phase_ctx.loop, 'llm'):
    print("✗ LLM not initialized")
else:
    print("✓ LLM initialized")

# 检查工具
if not hasattr(phase_ctx.loop, 'tools'):
    print("✗ Tools not initialized")
else:
    print(f"✓ Tools initialized: {len(phase_ctx.loop.tools)} tools")
```

**解决方案**：
```python
# 1. 初始化编排器
if not hasattr(phase_ctx.loop, 'orchestrator'):
    phase_ctx.loop.orchestrator = Orchestrator(...)

# 2. 初始化 LLM
if not hasattr(phase_ctx.loop, 'llm'):
    phase_ctx.loop.llm = LLMClient(...)

# 3. 初始化工具
if not hasattr(phase_ctx.loop, 'tools'):
    phase_ctx.loop.tools = load_tools()

# 4. 添加重试逻辑
max_retries = 3
for attempt in range(max_retries):
    try:
        await init_phase.execute(phase_ctx)
        break
    except Exception as e:
        if attempt < max_retries - 1:
            logger.warning(f"Orchestration attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)  # 指数退避
        else:
            raise
```

---

## 规划阶段问题

### 问题 1: 计划为空

**症状**：
```
plan = await planning_phase.execute(phase_ctx)
assert len(plan) > 0  # 失败
```

**原因**：
- LLM 返回空计划
- 计划生成超时
- 工具列表为空

**诊断**：
```python
# 检查 LLM 响应
logger.debug(f"LLM response: {llm_response}")

# 检查工具列表
tools = phase_ctx.loop.tools
print(f"Available tools: {len(tools)}")
for tool in tools:
    print(f"  - {tool.name}: {tool.description}")

# 检查计划生成时间
import time
start = time.time()
plan = await planning_phase.execute(phase_ctx)
duration = time.time() - start
print(f"Plan generation took {duration:.2f}s")
```

**解决方案**：
```python
# 1. 检查 LLM 配置
assert phase_ctx.loop.llm is not None, "LLM not configured"
assert phase_ctx.loop.llm.model is not None, "LLM model not set"

# 2. 检查工具列表
assert len(phase_ctx.loop.tools) > 0, "No tools available"

# 3. 增加超时时间
phase_ctx.extra_context["planning_timeout"] = 60  # 秒

# 4. 使用默认计划
if len(plan) == 0:
    logger.warning("Empty plan, using default")
    plan = [
        AgentPlanStep(kind="observe", instruction="Observe the task"),
        AgentPlanStep(kind="final", instruction="Provide final answer"),
    ]
```

### 问题 2: 计划步骤无效

**症状**：
```
Exception: Invalid plan step kind: 'unknown'
```

**原因**：
- LLM 生成了无效的步骤类型
- 步骤缺少必需的字段

**诊断**：
```python
# 检查步骤类型
valid_kinds = ["observe", "tool", "reflect", "final"]
for step in plan:
    if step.kind not in valid_kinds:
        print(f"✗ Invalid step kind: {step.kind}")
    else:
        print(f"✓ Valid step kind: {step.kind}")
    
    # 检查必需字段
    if not hasattr(step, 'instruction') or not step.instruction:
        print(f"✗ Missing instruction for step {step.kind}")
    else:
        print(f"✓ Instruction: {step.instruction[:50]}...")
```

**解决方案**：
```python
# 1. 验证和修复步骤
def validate_and_fix_plan(plan):
    valid_kinds = ["observe", "tool", "reflect", "final"]
    fixed_plan = []
    
    for step in plan:
        # 修复步骤类型
        if step.kind not in valid_kinds:
            logger.warning(f"Fixing invalid step kind: {step.kind}")
            step.kind = "reflect"  # 默认为反思
        
        # 修复缺失的指令
        if not step.instruction:
            logger.warning(f"Fixing missing instruction for step {step.kind}")
            step.instruction = f"Execute {step.kind} step"
        
        fixed_plan.append(step)
    
    return fixed_plan

plan = validate_and_fix_plan(plan)
```

### 问题 3: 计划去重失败

**症状**：
```
Exception: Deduplication failed
```

**原因**：
- 去重算法出错
- 计划步骤格式不一致

**诊断**：
```python
# 检查重复步骤
from collections import Counter

instructions = [step.instruction for step in plan]
duplicates = [instr for instr, count in Counter(instructions).items() if count > 1]

if duplicates:
    print(f"Found {len(duplicates)} duplicate instructions:")
    for instr in duplicates:
        print(f"  - {instr}")
else:
    print("✓ No duplicate instructions found")
```

**解决方案**：
```python
# 1. 禁用去重
phase_ctx.extra_context["skip_deduplication"] = True

# 2. 使用自定义去重逻辑
def custom_dedupe(plan):
    seen = set()
    deduped = []
    for step in plan:
        # 使用步骤类型和指令的哈希作为键
        key = (step.kind, step.instruction[:50])
        if key not in seen:
            seen.add(key)
            deduped.append(step)
    return deduped

plan = custom_dedupe(plan)
```

---

## 执行阶段问题

### 问题 1: 工具调用失败

**症状**：
```
ToolCallRecord(success=False, error="Tool execution failed")
```

**原因**：
- 工具不存在
- 工具参数无效
- 工具执行超时
- 工具返回错误

**诊断**：
```python
# 检查失败的工具调用
for call in phase_ctx.tool_calls:
    if not call.success:
        print(f"✗ Tool call failed: {call.tool_name}")
        print(f"  Arguments: {call.arguments}")
        print(f"  Error: {call.error}")
        print(f"  Duration: {call.duration}ms")
```

**解决方案**：
```python
# 1. 检查工具是否存在
tool_name = "file_read"
if tool_name not in [t.name for t in phase_ctx.loop.tools]:
    print(f"✗ Tool not found: {tool_name}")
    # 列出可用工具
    print("Available tools:")
    for tool in phase_ctx.loop.tools:
        print(f"  - {tool.name}")
else:
    print(f"✓ Tool found: {tool_name}")

# 2. 验证工具参数
tool = next(t for t in phase_ctx.loop.tools if t.name == tool_name)
required_params = tool.required_parameters
provided_params = call.arguments.keys()

missing_params = set(required_params) - set(provided_params)
if missing_params:
    print(f"✗ Missing parameters: {missing_params}")
else:
    print(f"✓ All required parameters provided")

# 3. 增加超时时间
phase_ctx.extra_context["tool_timeout"] = 30  # 秒

# 4. 添加重试逻辑
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await call_tool(tool_name, arguments)
        break
    except Exception as e:
        if attempt < max_retries - 1:
            logger.warning(f"Tool call attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)
        else:
            raise
```

### 问题 2: 迭代次数过多

**症状**：
```
Warning: Max iterations reached (100)
```

**原因**：
- 计划步骤过多
- 步骤执行缓慢
- 无限循环

**诊断**：
```python
# 检查迭代数
print(f"Iterations: {phase_ctx.iteration}")
print(f"Max iterations: {phase_ctx.loop.max_iterations}")

# 检查剩余步骤
print(f"Remaining steps: {len(plan)}")

# 检查每个步骤的执行时间
for i, call in enumerate(phase_ctx.tool_calls):
    print(f"Step {i}: {call.tool_name} - {call.duration}ms")
```

**解决方案**：
```python
# 1. 增加最大迭代数
phase_ctx.loop.max_iterations = 200

# 2. 优化计划（减少步骤数）
# 合并相关步骤
# 移除不必要的步骤

# 3. 添加迭代超时
phase_ctx.extra_context["iteration_timeout"] = 300  # 秒

# 4. 检测无限循环
def detect_infinite_loop(phase_ctx):
    if phase_ctx.iteration > phase_ctx.loop.max_iterations * 0.9:
        # 检查最后 10 个步骤是否重复
        last_steps = phase_ctx.tool_calls[-10:]
        if len(set(call.tool_name for call in last_steps)) == 1:
            logger.warning("Possible infinite loop detected")
            return True
    return False
```

### 问题 3: 观察为空

**症状**：
```
observations = []  # 空列表
```

**原因**：
- 观察步骤未执行
- 记忆系统未初始化
- 工具未返回结果

**诊断**：
```python
# 检查观察步骤
observe_steps = [step for step in plan if step.kind == "observe"]
print(f"Observe steps: {len(observe_steps)}")

# 检查记忆系统
if not hasattr(phase_ctx.loop, 'memory'):
    print("✗ Memory system not initialized")
else:
    print("✓ Memory system initialized")

# 检查工具结果
for call in phase_ctx.tool_calls:
    if call.result:
        print(f"✓ Tool {call.tool_name} returned result")
    else:
        print(f"✗ Tool {call.tool_name} returned empty result")
```

**解决方案**：
```python
# 1. 确保有观察步骤
if not any(step.kind == "observe" for step in plan):
    plan.insert(0, AgentPlanStep(
        kind="observe",
        instruction="Observe the task and gather information"
    ))

# 2. 初始化记忆系统
if not hasattr(phase_ctx.loop, 'memory'):
    phase_ctx.loop.memory = MemorySystem(...)

# 3. 手动添加观察
phase_ctx.observations.append("Task: Fix the bug in main.py")
phase_ctx.observations.append("Status: In progress")
```

---

## 恢复阶段问题

### 问题 1: 恢复失败

**症状**：
```
Exception: Recovery failed
```

**原因**：
- 没有失败的工具调用
- 修复建议生成失败
- 重试调度失败

**诊断**：
```python
# 检查失败
failures = [call for call in phase_ctx.tool_calls if not call.success]
print(f"Failed tool calls: {len(failures)}")

# 检查修复建议
repairs = phase_ctx.execution_frame.execution_summary.get("repair_suggestions", [])
print(f"Repair suggestions: {len(repairs)}")

# 检查重试
retries = phase_ctx.execution_frame.execution_summary.get("retries", [])
print(f"Scheduled retries: {len(retries)}")
```

**解决方案**：
```python
# 1. 跳过恢复（如果没有失败）
if recovery_phase.can_skip(phase_ctx):
    logger.info("No failures, skipping recovery phase")
else:
    await recovery_phase.execute(phase_ctx)

# 2. 手动生成修复建议
def generate_repair_suggestion(failure):
    return {
        "tool_name": failure.tool_name,
        "should_retry": True,
        "reason": f"Tool {failure.tool_name} failed: {failure.error}",
        "arguments": failure.arguments,  # 使用相同的参数重试
    }

# 3. 禁用自动恢复
phase_ctx.extra_context["skip_recovery"] = True
```

### 问题 2: 重试预算耗尽

**症状**：
```
Warning: Retry budget exhausted
```

**原因**：
- 工具调用失败次数过多
- 重试次数超过限制

**诊断**：
```python
# 检查重试次数
retry_count = sum(
    1 for call in phase_ctx.tool_calls
    if call.retry_count > 0
)
print(f"Retried calls: {retry_count}")

# 检查重试预算
max_retries = phase_ctx.extra_context.get("max_retries", 3)
print(f"Max retries per call: {max_retries}")
```

**解决方案**：
```python
# 1. 增加重试预算
phase_ctx.extra_context["max_retries"] = 5

# 2. 使用指数退避
phase_ctx.extra_context["retry_backoff"] = "exponential"

# 3. 跳过失败的工具
phase_ctx.extra_context["skip_failed_tools"] = True
```

---

## 完成阶段问题

### 问题 1: 响应构建失败

**症状**：
```
Exception: Failed to build response
```

**原因**：
- 必需的字段缺失
- 数据格式不一致
- 序列化失败

**诊断**：
```python
# 检查必需字段
required_fields = ["status", "answer", "tool_calls", "trace_id"]
for field in required_fields:
    if not hasattr(phase_ctx, field):
        print(f"✗ Missing field: {field}")
    else:
        print(f"✓ Field present: {field}")

# 检查数据类型
print(f"Status type: {type(phase_ctx.execution_frame.status)}")
print(f"Answer type: {type(phase_ctx.answer)}")
print(f"Tool calls type: {type(phase_ctx.tool_calls)}")
```

**解决方案**：
```python
# 1. 确保所有字段都已填充
phase_ctx.answer = phase_ctx.answer or "Task completed"
phase_ctx.tool_calls = phase_ctx.tool_calls or []
phase_ctx.observations = phase_ctx.observations or []

# 2. 验证数据类型
assert isinstance(phase_ctx.answer, str), "Answer must be string"
assert isinstance(phase_ctx.tool_calls, list), "Tool calls must be list"

# 3. 处理序列化错误
try:
    response = await completion_phase.execute(phase_ctx)
except TypeError as e:
    logger.error(f"Serialization error: {e}")
    # 手动构建响应
    response = AgentRunResponse(
        status="success",
        answer=str(phase_ctx.answer),
        tool_calls=[call.model_dump() for call in phase_ctx.tool_calls],
        observations=phase_ctx.observations,
        trace_id=phase_ctx.context.trace_id,
    )
```

### 问题 2: 记忆存储失败

**症状**：
```
Exception: Failed to store memory
```

**原因**：
- 记忆系统未初始化
- 存储容量已满
- 权限不足

**诊断**：
```python
# 检查记忆系统
if not hasattr(phase_ctx.loop, 'memory'):
    print("✗ Memory system not initialized")
else:
    print("✓ Memory system initialized")

# 检查存储容量
memory_size = phase_ctx.loop.memory.get_size()
max_size = phase_ctx.loop.memory.max_size
print(f"Memory usage: {memory_size}/{max_size} bytes")

# 检查权限
import os
memory_path = phase_ctx.loop.memory.path
if os.access(memory_path, os.W_OK):
    print(f"✓ Write permission: {memory_path}")
else:
    print(f"✗ No write permission: {memory_path}")
```

**解决方案**：
```python
# 1. 初始化记忆系统
if not hasattr(phase_ctx.loop, 'memory'):
    phase_ctx.loop.memory = MemorySystem(...)

# 2. 清理旧记忆
phase_ctx.loop.memory.cleanup_old_entries(days=30)

# 3. 禁用记忆存储
phase_ctx.extra_context["skip_memory_storage"] = True

# 4. 使用备用存储
phase_ctx.extra_context["memory_backend"] = "redis"  # 或其他后端
```

---

## 性能问题

### 问题 1: 执行缓慢

**症状**：
```
Execution took 120 seconds (expected < 30 seconds)
```

**原因**：
- LLM 调用缓慢
- 工具执行缓慢
- 网络延迟

**诊断**：
```python
# 分析各阶段耗时
import time

phases = [
    ("Initialization", init_phase),
    ("Planning", planning_phase),
    ("Execution", execution_phase),
    ("Completion", completion_phase),
]

for name, phase in phases:
    start = time.time()
    # 执行阶段
    duration = time.time() - start
    print(f"{name}: {duration:.2f}s")

# 分析工具调用耗时
for call in phase_ctx.tool_calls:
    print(f"{call.tool_name}: {call.duration}ms")
```

**解决方案**：
```python
# 1. 启用缓存
phase_ctx.extra_context["enable_cache"] = True

# 2. 并行执行独立步骤
phase_ctx.extra_context["parallel_execution"] = True

# 3. 增加超时时间
phase_ctx.extra_context["execution_timeout"] = 300  # 秒

# 4. 使用更快的 LLM 模型
phase_ctx.loop.llm.model = "gpt-4-turbo"  # 更快的模型

# 5. 优化工具调用
# - 减少工具数量
# - 使用批量操作
# - 启用工具缓存
```

### 问题 2: 内存使用过高

**症状**：
```
MemoryError: Unable to allocate 2.5 GiB for an array
```

**原因**：
- 计划步骤过多
- 工具调用记录过多
- 观察列表过大

**诊断**：
```python
# 检查内存使用
import sys

print(f"Phase context size: {sys.getsizeof(phase_ctx)} bytes")
print(f"Tool calls size: {sys.getsizeof(phase_ctx.tool_calls)} bytes")
print(f"Observations size: {sys.getsizeof(phase_ctx.observations)} bytes")

# 检查对象数量
print(f"Tool calls count: {len(phase_ctx.tool_calls)}")
print(f"Observations count: {len(phase_ctx.observations)}")
```

**解决方案**：
```python
# 1. 限制计划大小
phase_ctx.extra_context["max_plan_size"] = 50

# 2. 定期清理记录
def cleanup_records(phase_ctx):
    # 保留最后 100 个工具调用
    if len(phase_ctx.tool_calls) > 100:
        phase_ctx.tool_calls = phase_ctx.tool_calls[-100:]
    
    # 保留最后 100 个观察
    if len(phase_ctx.observations) > 100:
        phase_ctx.observations = phase_ctx.observations[-100:]

cleanup_records(phase_ctx)

# 3. 使用流式处理
phase_ctx.extra_context["streaming"] = True

# 4. 启用垃圾回收
import gc
gc.collect()
```

---

## 调试技巧

### 启用详细日志

```python
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

# 为特定模块启用调试
logging.getLogger("backend.app.core.agent_v2").setLevel(logging.DEBUG)

# 添加文件处理器
handler = logging.FileHandler("agent_v2_debug.log")
handler.setLevel(logging.DEBUG)
logging.getLogger("backend.app.core.agent_v2").addHandler(handler)
```

### 使用调试器

```python
import pdb

# 在关键点设置断点
async def execute_with_debug(phase_ctx):
    pdb.set_trace()  # 在这里暂停
    await init_phase.execute(phase_ctx)
```

### 添加追踪

```python
# 添加追踪装饰器
def trace_execution(func):
    async def wrapper(*args, **kwargs):
        logger.debug(f"Entering {func.__name__}")
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Exiting {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper

@trace_execution
async def execute_phase(phase_ctx):
    # ...
```

### 使用性能分析器

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# 执行代码
await executor.execute(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(20)
```

---

## 常见错误代码

| 代码 | 含义 | 解决方案 |
|------|------|---------|
| E001 | 上下文验证失败 | 检查 PhaseContext 完整性 |
| E002 | 代码索引失败 | 检查代码库路径和权限 |
| E003 | 编排失败 | 初始化编排器和 LLM |
| E004 | 计划为空 | 检查 LLM 响应和工具列表 |
| E005 | 工具调用失败 | 检查工具参数和超时 |
| E006 | 迭代超限 | 增加最大迭代数或优化计划 |
| E007 | 恢复失败 | 检查失败的工具调用 |
| E008 | 响应构建失败 | 检查必需字段 |
| E009 | 记忆存储失败 | 初始化记忆系统 |
| E010 | 执行超时 | 增加超时时间或优化性能 |

---

## 获取帮助

### 查看日志

```bash
# 查看最近的日志
tail -f agent_v2_debug.log

# 搜索错误
grep "ERROR" agent_v2_debug.log

# 查看特定阶段的日志
grep "InitializationPhase" agent_v2_debug.log
```

### 收集诊断信息

```python
def collect_diagnostics(phase_ctx):
    """收集诊断信息。"""
    return {
        "context": {
            "task": phase_ctx.task,
            "session_id": phase_ctx.get_session_id(),
            "is_resuming": phase_ctx.is_resuming(),
        },
        "execution": {
            "iteration": phase_ctx.iteration,
            "tool_calls": len(phase_ctx.tool_calls),
            "observations": len(phase_ctx.observations),
        },
        "frames": {
            "task_frame": phase_ctx.task_frame is not None,
            "execution_frame": phase_ctx.execution_frame is not None,
            "plan_frame": phase_ctx.plan_frame is not None,
        },
    }

diagnostics = collect_diagnostics(phase_ctx)
print(json.dumps(diagnostics, indent=2))
```

### 联系支持

- 开发团队：dev-team@xagent.com
- 问题跟踪：https://github.com/xagent/issues
- 文档：https://docs.xagent.com

---

## 版本信息

- **版本**：2.0.0
- **发布日期**：2026-05-26
- **状态**：生产就绪
