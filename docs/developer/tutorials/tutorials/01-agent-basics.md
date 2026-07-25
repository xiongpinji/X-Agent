# Agent 使用教程

学习如何创建、配置和使用 X-Agent 中的 Agent。

## 目录

1. [Agent 基础](#agent-基础)
2. [创建 Agent](#创建-agent)
3. [配置工具](#配置工具)
4. [执行任务](#执行任务)
5. [处理失败](#处理失败)
6. [高级特性](#高级特性)

## Agent 基础

### 什么是 Agent？

Agent 是一个自主的执行单元，可以：

- 理解自然语言任务
- 制定执行计划
- 调用工具和服务
- 从失败中恢复
- 学习和改进

### Agent 的生命周期

```
初始化 → 规划 → 执行 → 验证 → 完成/恢复
```

1. **初始化**：创建 Agent，加载配置和工具
2. **规划**：分析任务，制定执行计划
3. **执行**：按计划执行步骤，调用工具
4. **验证**：检查执行结果是否符合预期
5. **完成/恢复**：返回结果或进入恢复流程

## 创建 Agent

### 基础创建

```python
from backend.app.core.agent import Agent
from backend.app.core.llm import LLMRouter

# 初始化 LLM 路由器
llm_router = LLMRouter(
    default_model="gpt-4",
    fallback_model="gpt-3.5-turbo"
)

# 创建 Agent
agent = Agent(
    name="DataAnalystAgent",
    description="数据分析 Agent，可以处理数据分析任务",
    llm_router=llm_router,
    max_iterations=10,  # 最大迭代次数
    timeout=300  # 超时时间（秒）
)
```

### 使用配置文件

创建 `agent_config.yaml`：

```yaml
name: DataAnalystAgent
description: 数据分析 Agent
llm:
  default_model: gpt-4
  fallback_model: gpt-3.5-turbo
  temperature: 0.7
  max_tokens: 2000
execution:
  max_iterations: 10
  timeout: 300
  retry_count: 3
memory:
  enabled: true
  backend: postgres
  ttl: 86400
tools:
  - name: query_database
    enabled: true
  - name: analyze_data
    enabled: true
  - name: generate_report
    enabled: true
```

加载配置：

```python
from backend.app.core.agent import Agent

agent = Agent.from_config("agent_config.yaml")
```

## 配置工具

### 添加工具

```python
from backend.app.core.tool_registry import ToolRegistry

# 获取工具注册表
registry = ToolRegistry()

# 获取特定工具
query_tool = registry.get_tool("query_database")
analyze_tool = registry.get_tool("analyze_data")

# 添加工具到 Agent
agent.add_tool(query_tool)
agent.add_tool(analyze_tool)
```

### 创建自定义工具

```python
from backend.app.core.tool_schema import Tool, ToolParameter
from typing import Any

class CustomTool:
    """自定义工具"""
    
    @staticmethod
    def get_definition() -> Tool:
        return Tool(
            name="custom_analysis",
            description="执行自定义分析",
            parameters=[
                ToolParameter(
                    name="data",
                    type="array",
                    description="输入数据",
                    required=True
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="分析方法",
                    enum=["mean", "median", "std"],
                    required=True
                )
            ],
            returns={
                "type": "object",
                "properties": {
                    "result": {"type": "number"},
                    "confidence": {"type": "number"}
                }
            }
        )
    
    @staticmethod
    async def execute(data: list, method: str) -> dict:
        """执行工具"""
        import statistics
        
        if method == "mean":
            result = statistics.mean(data)
        elif method == "median":
            result = statistics.median(data)
        elif method == "std":
            result = statistics.stdev(data)
        else:
            raise ValueError(f"未知方法: {method}")
        
        return {
            "result": result,
            "confidence": 0.95
        }

# 注册工具
registry.register(CustomTool)

# 添加到 Agent
agent.add_tool(registry.get_tool("custom_analysis"))
```

### 工具权限控制

```python
from backend.app.core.policy import PolicyEngine

# 创建策略引擎
policy_engine = PolicyEngine()

# 定义工具使用策略
policy_engine.add_policy(
    name="restrict_delete",
    description="限制删除操作",
    rules=[
        {
            "tool": "delete_data",
            "action": "deny",
            "reason": "删除操作需要人工审批"
        }
    ]
)

# 应用策略到 Agent
agent.set_policy_engine(policy_engine)
```

## 执行任务

### 简单任务执行

```python
import asyncio

async def main():
    # 执行任务
    result = await agent.execute(
        task="分析过去一个月的销售数据，找出销售趋势"
    )
    
    print(f"执行状态: {result.status}")
    print(f"执行结果: {result.output}")
    print(f"执行时间: {result.duration}s")

asyncio.run(main())
```

### 带上下文的任务执行

```python
async def main():
    # 准备上下文
    context = {
        "user_id": "user123",
        "department": "sales",
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-01-31"
        }
    }
    
    # 执行任务
    result = await agent.execute(
        task="分析销售数据",
        context=context
    )
    
    print(result.output)

asyncio.run(main())
```

### 流式执行

```python
async def main():
    # 流式执行任务，实时获取中间结果
    async for step in agent.execute_stream(
        task="分析数据并生成报告"
    ):
        print(f"步骤: {step.name}")
        print(f"状态: {step.status}")
        print(f"输出: {step.output}")

asyncio.run(main())
```

### 批量执行

```python
async def main():
    tasks = [
        "分析 2024 年 1 月销售数据",
        "分析 2024 年 2 月销售数据",
        "分析 2024 年 3 月销售数据"
    ]
    
    # 并行执行多个任务
    results = await agent.execute_batch(tasks)
    
    for task, result in zip(tasks, results):
        print(f"任务: {task}")
        print(f"结果: {result.output}")

asyncio.run(main())
```

## 处理失败

### 自动重试

```python
# 配置重试策略
agent.set_retry_policy(
    max_retries=3,
    backoff_factor=2,  # 指数退避
    retry_on=[
        "timeout",
        "rate_limit",
        "temporary_error"
    ]
)

# 执行任务
result = await agent.execute(
    task="调用外部 API"
)
```

### 错误处理

```python
async def main():
    try:
        result = await agent.execute(
            task="执行可能失败的任务"
        )
    except Exception as e:
        print(f"执行失败: {e}")
        
        # 获取失败信息
        failure_info = agent.get_failure_info()
        print(f"失败原因: {failure_info.reason}")
        print(f"失败步骤: {failure_info.step}")
        print(f"建议: {failure_info.suggestion}")

asyncio.run(main())
```

### 恢复流程

```python
async def main():
    # 执行任务
    result = await agent.execute(
        task="执行任务"
    )
    
    # 如果失败，进入恢复流程
    if result.status == "failed":
        # 获取恢复选项
        recovery_options = agent.get_recovery_options()
        
        # 选择恢复策略
        recovery_result = await agent.recover(
            strategy="retry_with_different_approach"
        )
        
        print(f"恢复结果: {recovery_result.output}")

asyncio.run(main())
```

## 高级特性

### 1. 记忆集成

```python
from backend.app.core.memory import MemoryManager

# 创建记忆管理器
memory = MemoryManager()

# 将记忆集成到 Agent
agent.set_memory_manager(memory)

# 执行任务时自动使用记忆
result = await agent.execute(
    task="基于历史数据分析趋势"
)

# Agent 会自动检索相关的历史信息
```

### 2. 多 Agent 协作

```python
from backend.app.core.collaboration import AgentCollaborator

# 创建协作器
collaborator = AgentCollaborator()

# 添加多个 Agent
agent1 = Agent(name="DataCollectorAgent")
agent2 = Agent(name="DataAnalystAgent")
agent3 = Agent(name="ReportGeneratorAgent")

collaborator.add_agent(agent1)
collaborator.add_agent(agent2)
collaborator.add_agent(agent3)

# 定义协作流程
collaborator.define_workflow([
    ("DataCollectorAgent", "collect_data"),
    ("DataAnalystAgent", "analyze_data"),
    ("ReportGeneratorAgent", "generate_report")
])

# 执行协作任务
result = await collaborator.execute(
    task="收集、分析数据并生成报告"
)
```

### 3. 审批工作流

```python
from backend.app.core.approvals import ApprovalManager

# 创建审批管理器
approval_manager = ApprovalManager()

# 定义需要审批的操作
approval_manager.add_approval_rule(
    operation="delete_data",
    approvers=["admin@company.com"],
    timeout=3600
)

# 将审批管理器集成到 Agent
agent.set_approval_manager(approval_manager)

# 执行需要审批的操作
result = await agent.execute(
    task="删除过期数据",
    require_approval=True
)

# Agent 会自动请求审批
```

### 4. 性能监控

```python
from backend.app.core.monitoring import PerformanceMonitor

# 创建性能监控器
monitor = PerformanceMonitor()

# 将监控器集成到 Agent
agent.set_performance_monitor(monitor)

# 执行任务
result = await agent.execute(task="执行任务")

# 获取性能指标
metrics = monitor.get_metrics()
print(f"执行时间: {metrics.execution_time}s")
print(f"工具调用次数: {metrics.tool_calls}")
print(f"LLM 调用次数: {metrics.llm_calls}")
print(f"成功率: {metrics.success_rate}%")
```

### 5. 自定义提示词

```python
# 定义自定义提示词
system_prompt = """
你是一个专业的数据分析师。
你的职责是：
1. 理解用户的数据分析需求
2. 制定分析计划
3. 执行分析
4. 生成清晰的报告

在执行分析时，请遵循以下原则：
- 数据准确性优先
- 提供详细的分析过程
- 给出明确的结论和建议
"""

# 应用自定义提示词
agent.set_system_prompt(system_prompt)

# 执行任务
result = await agent.execute(
    task="分析销售数据"
)
```

## 最佳实践

1. **明确定义任务**：提供清晰、具体的任务描述
2. **提供上下文**：为 Agent 提供必要的背景信息
3. **配置合适的工具**：只添加必要的工具，避免工具过多
4. **设置合理的超时**：根据任务复杂度设置超时时间
5. **监控执行过程**：使用流式执行或监控工具跟踪进度
6. **处理失败情况**：实现适当的错误处理和恢复机制
7. **记录审计日志**：记录所有重要操作以便审计

## 下一步

- 阅读 [工作流编排教程](./02-workflow-orchestration.md)
- 阅读 [记忆系统教程](./03-memory-system.md)
- 阅读 [最佳实践](../../best-practices/best-practices/README.md)
- 探索 [示例代码库](../../examples/)
