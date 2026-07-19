# X-Agent v2 迁移指南

## 概述

本指南帮助开发者从 X-Agent v1（单体 `AgentLoop.run()` 方法）迁移到 X-Agent v2（阶段化架构）。

### 为什么迁移？

| 方面 | v1 | v2 |
|------|----|----|
| 代码行数 | 500+ | 分散到 5 个阶段 |
| 圈复杂度 | 35-40 | 每个阶段 < 10 |
| 可测试性 | 困难 | 每个阶段独立测试 |
| 可维护性 | 低 | 高 |
| 扩展性 | 困难 | 容易添加新阶段 |
| 错误处理 | 集中 | 分散到各阶段 |

---

## 迁移路径

### 阶段 1：准备（1-2 天）

#### 1.1 理解新架构

阅读以下文档：
- [README.md](README.md) - 架构总览
- [API_REFERENCE.md](API_REFERENCE.md) - API 详细说明
- [phases/INTEGRATION_GUIDE.md](phases/INTEGRATION_GUIDE.md) - 规划阶段集成

#### 1.2 设置开发环境

```bash
# 克隆最新代码
git clone <repo>
cd X-Agent

# 安装依赖
pip install -r requirements.txt

# 运行现有测试
pytest backend/app/core/agent_v2/phases/test_planning.py -v
```

#### 1.3 备份现有代码

```bash
# 创建备份分支
git checkout -b backup/v1-original
git push origin backup/v1-original

# 返回主分支
git checkout main
```

### 阶段 2：创建新的执行入口（2-3 天）

#### 2.1 创建 AgentExecutor 类

```python
# backend/app/core/agent_v2/agent_executor.py

from backend.app.core.agent_v2 import (
    InitializationPhase,
    PlanningPhase,
    ExecutionPhase,
    RecoveryPhase,
    CompletionPhase,
    PhaseContext,
)

class AgentExecutor:
    """新的 Agent 执行器，使用阶段化架构。"""
    
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
        self.init_phase = InitializationPhase()
        self.planning_phase = PlanningPhase()
        self.execution_phase = ExecutionPhase()
        self.recovery_phase = RecoveryPhase()
        self.completion_phase = CompletionPhase()
    
    async def execute(
        self,
        task: str,
        context: RunContext,
        trajectory: AgentTrajectory,
        extra_context: dict = None,
    ) -> AgentRunResponse:
        """执行 Agent 任务。
        
        Args:
            task: 任务字符串
            context: 运行上下文
            trajectory: 任务轨迹
            extra_context: 额外上下文
        
        Returns:
            Agent 运行响应
        """
        # 创建阶段上下文
        phase_ctx = PhaseContext(
            loop=self.agent_loop,
            context=context,
            task=task,
            trajectory=trajectory,
            extra_context=extra_context or {},
            execution_frame=ExecutionFrame(),
            task_frame=TaskFrame(),
            plan_frame=PlanFrame(),
            compact_context={},
        )
        
        try:
            # 1. 初始化
            await self.init_phase.execute(phase_ctx)
            
            # 2. 规划
            plan = await self.planning_phase.execute(phase_ctx)
            
            # 3. 执行
            answer, tool_calls = await self.execution_phase.execute(
                phase_ctx, plan
            )
            phase_ctx.answer = answer
            phase_ctx.tool_calls = tool_calls
            
            # 4. 恢复（如果需要）
            if not self.recovery_phase.can_skip(phase_ctx):
                await self.recovery_phase.execute(phase_ctx)
            
            # 5. 完成
            response = await self.completion_phase.execute(phase_ctx)
            
            return response
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return self._create_error_response(context, str(e))
    
    def _create_error_response(
        self,
        context: RunContext,
        error: str,
    ) -> AgentRunResponse:
        """创建错误响应。"""
        return AgentRunResponse(
            status="failure",
            answer=f"Execution failed: {error}",
            tool_calls=[],
            observations=[],
            execution_summary={"error": error},
            trace_id=context.trace_id,
        )
```

#### 2.2 更新 AgentLoop 以支持新执行器

```python
# backend/app/core/agent.py

class AgentLoop:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self.executor = AgentExecutor(self)
    
    async def run_v2(
        self,
        task: str,
        context: RunContext,
        trajectory: AgentTrajectory,
        extra_context: dict = None,
    ) -> AgentRunResponse:
        """使用新的阶段化架构运行 Agent。"""
        return await self.executor.execute(
            task, context, trajectory, extra_context
        )
    
    # 保留旧的 run() 方法以保持向后兼容
    async def run(self, ...):
        """旧的执行方法（已弃用）。"""
        # ... 现有实现 ...
```

### 阶段 3：迁移 API 端点（2-3 天）

#### 3.1 创建新的 API 端点

```python
# backend/app/api/agent.py

from backend.app.core.agent_v2 import AgentExecutor

@router.post("/v2/run")
async def run_agent_v2(request: AgentRunRequest) -> AgentRunResponse:
    """使用新的阶段化架构运行 Agent。"""
    agent_loop = get_agent_loop()
    
    response = await agent_loop.run_v2(
        task=request.task,
        context=request.context,
        trajectory=request.trajectory,
        extra_context=request.extra_context,
    )
    
    return response
```

#### 3.2 添加功能开关

```python
# backend/app/config.py

class Config:
    # 功能开关
    USE_AGENT_V2 = os.getenv("USE_AGENT_V2", "false").lower() == "true"
    AGENT_V2_ROLLOUT_PERCENTAGE = int(
        os.getenv("AGENT_V2_ROLLOUT_PERCENTAGE", "0")
    )
```

#### 3.3 实现渐进式推出

```python
# backend/app/api/agent.py

import random

@router.post("/run")
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """根据功能开关选择执行器。"""
    agent_loop = get_agent_loop()
    
    # 检查是否应该使用 v2
    use_v2 = (
        Config.USE_AGENT_V2 and
        random.randint(0, 100) < Config.AGENT_V2_ROLLOUT_PERCENTAGE
    )
    
    if use_v2:
        logger.info("Using Agent v2 executor")
        return await agent_loop.run_v2(
            task=request.task,
            context=request.context,
            trajectory=request.trajectory,
            extra_context=request.extra_context,
        )
    else:
        logger.info("Using Agent v1 executor")
        return await agent_loop.run(
            task=request.task,
            context=request.context,
            trajectory=request.trajectory,
            extra_context=request.extra_context,
        )
```

### 阶段 4：测试和验证（3-5 天）

#### 4.1 编写单元测试

```python
# backend/app/core/agent_v2/test_agent_executor.py

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_agent_executor_basic():
    """测试基本执行流程。"""
    # 创建 mock
    agent_loop = MagicMock()
    agent_loop._compress_context = MagicMock(return_value={})
    agent_loop._derive_goal = MagicMock(return_value="Test goal")
    # ... 更多 mock ...
    
    # 创建执行器
    executor = AgentExecutor(agent_loop)
    
    # 执行
    response = await executor.execute(
        task="Test task",
        context=RunContext(...),
        trajectory=AgentTrajectory(...),
    )
    
    # 验证
    assert response.status == "success"
    assert response.answer is not None
```

#### 4.2 编写集成测试

```python
# backend/app/core/agent_v2/test_integration.py

@pytest.mark.asyncio
async def test_agent_executor_integration():
    """测试完整的执行流程。"""
    # 使用真实的 AgentLoop
    agent_loop = create_test_agent_loop()
    executor = AgentExecutor(agent_loop)
    
    # 执行
    response = await executor.execute(
        task="Fix the bug in main.py",
        context=create_test_context(),
        trajectory=create_test_trajectory(),
    )
    
    # 验证
    assert response.status in ["success", "partial"]
    assert len(response.tool_calls) > 0
```

#### 4.3 性能测试

```python
# backend/app/core/agent_v2/test_performance.py

@pytest.mark.asyncio
async def test_agent_executor_performance():
    """测试执行性能。"""
    import time
    
    agent_loop = create_test_agent_loop()
    executor = AgentExecutor(agent_loop)
    
    start = time.time()
    response = await executor.execute(
        task="Simple task",
        context=create_test_context(),
        trajectory=create_test_trajectory(),
    )
    duration = time.time() - start
    
    # 验证性能
    assert duration < 10.0, f"Execution took {duration}s, expected < 10s"
```

#### 4.4 运行测试

```bash
# 运行所有测试
pytest backend/app/core/agent_v2/ -v

# 运行特定测试
pytest backend/app/core/agent_v2/test_agent_executor.py -v

# 运行性能测试
pytest backend/app/core/agent_v2/test_performance.py -v

# 生成覆盖率报告
pytest backend/app/core/agent_v2/ --cov=backend.app.core.agent_v2
```

### 阶段 5：监控和优化（持续）

#### 5.1 添加监控

```python
# backend/app/core/agent_v2/monitoring.py

import time
from prometheus_client import Histogram, Counter

# 定义指标
phase_duration = Histogram(
    "agent_phase_duration_seconds",
    "Duration of each phase",
    labelnames=["phase"],
)

phase_errors = Counter(
    "agent_phase_errors_total",
    "Total errors in each phase",
    labelnames=["phase"],
)

# 在执行器中使用
class AgentExecutor:
    async def execute(self, ...):
        # 初始化
        start = time.time()
        try:
            await self.init_phase.execute(phase_ctx)
            phase_duration.labels(phase="initialization").observe(
                time.time() - start
            )
        except Exception as e:
            phase_errors.labels(phase="initialization").inc()
            raise
```

#### 5.2 设置告警

```yaml
# monitoring/alerts.yaml

groups:
  - name: agent_v2
    rules:
      - alert: AgentV2HighErrorRate
        expr: rate(agent_phase_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate in Agent v2"
      
      - alert: AgentV2SlowExecution
        expr: agent_phase_duration_seconds > 30
        for: 5m
        annotations:
          summary: "Agent v2 execution is slow"
```

#### 5.3 收集指标

```python
# 在仪表板中查看指标
# - 平均执行时间
# - 错误率
# - 各阶段耗时分布
# - 工具调用成功率
```

### 阶段 6：完全迁移（1-2 周）

#### 6.1 逐步提高推出百分比

```bash
# 第 1 天：10% 流量
export AGENT_V2_ROLLOUT_PERCENTAGE=10

# 第 2 天：25% 流量
export AGENT_V2_ROLLOUT_PERCENTAGE=25

# 第 3 天：50% 流量
export AGENT_V2_ROLLOUT_PERCENTAGE=50

# 第 4 天：75% 流量
export AGENT_V2_ROLLOUT_PERCENTAGE=75

# 第 5 天：100% 流量
export AGENT_V2_ROLLOUT_PERCENTAGE=100
```

#### 6.2 监控每个阶段

在每个阶段，监控：
- 错误率
- 执行时间
- 用户反馈
- 系统资源使用

#### 6.3 回滚计划

如果出现问题，立即回滚：

```bash
# 降低推出百分比
export AGENT_V2_ROLLOUT_PERCENTAGE=0

# 或者完全禁用
export USE_AGENT_V2=false
```

---

## 常见迁移问题

### Q1: 如何处理现有的自定义逻辑？

**A**: 将自定义逻辑迁移到相应的阶段：

```python
# v1 中的自定义逻辑
class CustomAgentLoop(AgentLoop):
    async def run(self, ...):
        # 自定义初始化
        self._custom_init()
        
        # 调用父类
        return await super().run(...)
    
    def _custom_init(self):
        # 自定义逻辑
        pass

# v2 中的自定义逻辑
class CustomInitializationPhase(InitializationPhase):
    async def execute(self, phase_ctx):
        # 自定义初始化
        await self._custom_init(phase_ctx)
        
        # 调用父类
        return await super().execute(phase_ctx)
    
    async def _custom_init(self, phase_ctx):
        # 自定义逻辑
        pass
```

### Q2: 如何处理向后兼容性？

**A**: 保留旧的 `run()` 方法并添加新的 `run_v2()` 方法：

```python
class AgentLoop:
    async def run(self, ...):
        """旧方法（已弃用）"""
        # 现有实现
    
    async def run_v2(self, ...):
        """新方法"""
        # 新实现
```

### Q3: 如何处理现有的测试？

**A**: 为新的执行器编写新的测试，保留旧的测试：

```python
# 旧测试
def test_agent_loop_run():
    """测试旧的 run() 方法"""
    # ...

# 新测试
def test_agent_executor_run():
    """测试新的执行器"""
    # ...
```

### Q4: 如何处理性能差异？

**A**: 如果 v2 性能不如 v1，进行优化：

1. 分析瓶颈（使用 profiler）
2. 优化慢的阶段
3. 添加缓存
4. 并行化独立操作

```python
# 使用 cProfile 分析
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

await executor.execute(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(10)
```

### Q5: 如何处理错误恢复？

**A**: 使用 RecoveryPhase 处理失败：

```python
# 自动恢复
if not recovery_phase.can_skip(phase_ctx):
    await recovery_phase.execute(phase_ctx)

# 手动恢复
try:
    await execution_phase.execute(phase_ctx, plan)
except Exception as e:
    logger.error(f"Execution failed: {e}")
    # 手动修复并重试
    await recovery_phase.execute(phase_ctx)
```

---

## 迁移检查清单

### 准备阶段
- [ ] 阅读新架构文档
- [ ] 设置开发环境
- [ ] 备份现有代码
- [ ] 创建迁移分支

### 开发阶段
- [ ] 创建 AgentExecutor 类
- [ ] 更新 AgentLoop
- [ ] 创建新的 API 端点
- [ ] 添加功能开关

### 测试阶段
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 编写性能测试
- [ ] 所有测试通过

### 部署阶段
- [ ] 代码审查
- [ ] 部署到测试环境
- [ ] 部署到预发布环境
- [ ] 部署到生产环境

### 监控阶段
- [ ] 设置监控和告警
- [ ] 收集性能指标
- [ ] 监控错误率
- [ ] 收集用户反馈

### 完成阶段
- [ ] 达到 100% 推出
- [ ] 移除旧代码
- [ ] 更新文档
- [ ] 发布新版本

---

## 时间表

| 阶段 | 任务 | 时间 |
|------|------|------|
| 1 | 准备 | 1-2 天 |
| 2 | 开发 | 2-3 天 |
| 3 | API 迁移 | 2-3 天 |
| 4 | 测试 | 3-5 天 |
| 5 | 监控 | 持续 |
| 6 | 完全迁移 | 1-2 周 |
| **总计** | | **2-3 周** |

---

## 支持和帮助

### 文档
- [README.md](README.md) - 架构总览
- [API_REFERENCE.md](API_REFERENCE.md) - API 详细说明
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 故障排除

### 联系方式
- 开发团队：dev-team@xagent.com
- 技术支持：support@xagent.com
- 问题跟踪：https://github.com/xagent/issues

---

## 版本信息

- **版本**：2.0.0
- **发布日期**：2026-05-26
- **状态**：生产就绪
