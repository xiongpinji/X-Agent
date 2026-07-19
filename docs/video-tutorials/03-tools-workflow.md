# 视频教程 3: 工具集成与工作流 (10-12分钟)

**视频标题**: X-Agent 工具集成 - 连接你的工作流

**目标受众**: 中级用户、想要自动化工作流的开发者

**学习成果**:
- 理解工具系统
- 集成外部工具
- 创建自定义工具
- 构建完整工作流

---

## 脚本

### [00:00-00:30] 开场

```
欢迎来到 X-Agent 工具集成教程！

Agent 的强大之处在于它能够使用工具。
工具让 Agent 可以：
- 查询数据库
- 调用 API
- 发送邮件
- 执行系统命令
- 与外部服务交互

在这个视频中，我们将学习如何集成工具和构建工作流。
```

**视觉**:
- 工具系统概念图
- 工具集成示例

---

### [00:30-02:00] 工具系统架构

```
首先，让我们理解工具系统的架构。

X-Agent 的工具系统包括：

1. 工具注册表 (Tool Registry)
   - 管理所有可用工具
   - 提供工具发现
   - 处理工具版本

2. 工具定义 (Tool Definition)
   - 工具名称和描述
   - 输入参数
   - 输出格式
   - 错误处理

3. 工具执行 (Tool Execution)
   - 参数验证
   - 执行工具
   - 结果处理
   - 错误恢复

4. 工具链 (Tool Chain)
   - 组合多个工具
   - 处理依赖关系
   - 管理数据流

X-Agent 提供了许多内置工具：
- 数据库查询
- HTTP 请求
- 文件操作
- 邮件发送
- 浏览器自动化
- 代码执行
```

**视觉**:
- 工具系统架构图
- 内置工具列表
- 工具执行流程

---

### [02:00-03:30] 使用内置工具

```
让我们学习如何使用内置工具。

首先，导入必要的模块：

from backend.app.core.agent import Agent
from backend.app.core.tool_registry import ToolRegistry
import asyncio

async def main():
    # 初始化工具注册表
    registry = ToolRegistry()
    
    # 获取所有可用工具
    all_tools = registry.get_all_tools()
    print(f"可用工具数: {len(all_tools)}")
    
    # 创建 Agent
    agent = Agent(name="DataAgent")
    
    # 添加特定工具
    agent.add_tool(registry.get_tool("query_database"))
    agent.add_tool(registry.get_tool("send_email"))
    agent.add_tool(registry.get_tool("http_request"))
    
    # 执行任务
    result = await agent.execute(
        task="查询用户表中的所有记录"
    )
    
    print(f"结果: {result.output}")

asyncio.run(main())

常用内置工具：

1. 数据库工具
   - query_database: 执行 SQL 查询
   - insert_data: 插入数据
   - update_data: 更新数据
   - delete_data: 删除数据

2. HTTP 工具
   - http_request: 发送 HTTP 请求
   - parse_html: 解析 HTML
   - extract_json: 提取 JSON

3. 文件工具
   - read_file: 读取文件
   - write_file: 写入文件
   - list_files: 列出文件

4. 邮件工具
   - send_email: 发送邮件
   - read_email: 读取邮件

5. 浏览器工具
   - navigate: 导航到网页
   - click: 点击元素
   - fill_form: 填充表单
```

**视觉**:
- 工具列表展示
- 代码示例
- 执行结果

---

### [03:30-05:30] 创建自定义工具

```
现在让我们创建自定义工具。

创建自定义工具的步骤：

1. 定义工具类

from backend.app.core.tool import BaseTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    city: str = Field(..., description="城市名称")
    unit: str = Field(default="celsius", description="温度单位")

class WeatherTool(BaseTool):
    name = "get_weather"
    description = "获取指定城市的天气信息"
    input_schema = WeatherInput
    
    async def execute(self, city: str, unit: str = "celsius"):
        # 实现工具逻辑
        # 这里可以调用天气 API
        weather_data = await self.fetch_weather(city, unit)
        return weather_data

2. 注册工具

from backend.app.core.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register_tool(WeatherTool())

3. 在 Agent 中使用

async def main():
    agent = Agent(name="WeatherAgent")
    agent.add_tool(registry.get_tool("get_weather"))
    
    result = await agent.execute(
        task="告诉我北京的天气"
    )
    print(result.output)

asyncio.run(main())

创建工具的最佳实践：

1. 清晰的名称和描述
   name = "get_weather"
   description = "获取指定城市的天气信息"

2. 定义输入模式
   class WeatherInput(BaseModel):
       city: str = Field(..., description="城市名称")

3. 实现错误处理
   async def execute(self, ...):
       try:
           result = await self.fetch_weather(...)
           return result
       except Exception as e:
           raise ToolExecutionError(f"获取天气失败: {e}")

4. 添加日志
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"获取 {city} 的天气")

5. 支持异步操作
   async def execute(self, ...):
       # 使用 await 调用异步函数
       result = await async_function()
```

**视觉**:
- 工具创建流程图
- 代码示例
- 工具注册演示

---

### [05:30-07:30] 工作流编排

```
现在让我们学习工作流编排。

工作流是一系列有序的任务。

创建工作流的步骤：

1. 导入必要的模块

from backend.app.core.workflows import (
    Workflow,
    WorkflowNode,
    NodeType,
    EdgeCondition
)
import asyncio

2. 定义工作流

async def create_workflow():
    # 创建工作流
    workflow = Workflow(
        name="OrderProcessing",
        description="订单处理工作流"
    )
    
    # 添加节点
    validate_node = WorkflowNode(
        id="validate_order",
        name="验证订单",
        type=NodeType.TASK,
        action="validate_order_action"
    )
    
    check_inventory_node = WorkflowNode(
        id="check_inventory",
        name="检查库存",
        type=NodeType.TASK,
        action="check_inventory_action"
    )
    
    process_payment_node = WorkflowNode(
        id="process_payment",
        name="处理支付",
        type=NodeType.TASK,
        action="process_payment_action"
    )
    
    # 添加节点到工作流
    workflow.add_node(validate_node)
    workflow.add_node(check_inventory_node)
    workflow.add_node(process_payment_node)
    
    # 添加边（连接）
    workflow.add_edge(
        from_node="validate_order",
        to_node="check_inventory"
    )
    
    workflow.add_edge(
        from_node="check_inventory",
        to_node="process_payment"
    )
    
    return workflow

3. 执行工作流

async def execute_workflow():
    workflow = await create_workflow()
    
    # 执行工作流
    run = await workflow.execute(
        input_data={
            "order_id": "ORD-001",
            "customer_id": "CUST-123",
            "items": [...]
        }
    )
    
    print(f"工作流状态: {run.status}")
    print(f"执行时间: {run.duration}s")
    print(f"结果: {run.output}")

asyncio.run(execute_workflow())

工作流的高级特性：

1. 条件分支

workflow.add_edge(
    from_node="check_inventory",
    to_node="process_payment",
    condition="inventory_available == True"
)

workflow.add_edge(
    from_node="check_inventory",
    to_node="notify_customer",
    condition="inventory_available == False"
)

2. 并行执行

parallel_node = WorkflowNode(
    id="parallel_tasks",
    name="并行任务",
    type=NodeType.PARALLEL,
    nodes=["send_email", "update_db", "log_event"]
)

3. 错误处理

workflow.add_error_handler(
    node_id="process_payment",
    handler_action="handle_payment_error"
)

4. 重试机制

node = WorkflowNode(
    id="process_payment",
    retry_count=3,
    retry_delay=5
)

5. 超时设置

node = WorkflowNode(
    id="external_api_call",
    timeout=60  # 60 秒
)
```

**视觉**:
- 工作流图示
- 节点和边的可视化
- 条件分支演示
- 执行结果

---

### [07:30-09:00] 实战：完整工作流示例

```
现在让我们构建一个完整的工作流示例。

场景：自动化数据分析工作流

class DataAnalysisWorkflow:
    def __init__(self):
        self.workflow = None
    
    async def create_workflow(self):
        workflow = Workflow(
            name="DataAnalysis",
            description="数据分析工作流"
        )
        
        # 节点 1: 获取数据
        fetch_node = WorkflowNode(
            id="fetch_data",
            name="获取数据",
            type=NodeType.TASK,
            action="fetch_data_from_db"
        )
        
        # 节点 2: 清洗数据
        clean_node = WorkflowNode(
            id="clean_data",
            name="清洗数据",
            type=NodeType.TASK,
            action="clean_data"
        )
        
        # 节点 3: 分析数据（并行）
        analyze_node = WorkflowNode(
            id="analyze_data",
            name="分析数据",
            type=NodeType.PARALLEL,
            nodes=["statistical_analysis", "trend_analysis"]
        )
        
        # 节点 4: 生成报告
        report_node = WorkflowNode(
            id="generate_report",
            name="生成报告",
            type=NodeType.TASK,
            action="generate_report"
        )
        
        # 节点 5: 发送通知
        notify_node = WorkflowNode(
            id="send_notification",
            name="发送通知",
            type=NodeType.TASK,
            action="send_notification"
        )
        
        # 添加节点
        for node in [fetch_node, clean_node, analyze_node, 
                     report_node, notify_node]:
            workflow.add_node(node)
        
        # 添加边
        workflow.add_edge("fetch_data", "clean_data")
        workflow.add_edge("clean_data", "analyze_data")
        workflow.add_edge("analyze_data", "generate_report")
        workflow.add_edge("generate_report", "send_notification")
        
        self.workflow = workflow
        return workflow
    
    async def execute(self, data_source):
        if not self.workflow:
            await self.create_workflow()
        
        run = await self.workflow.execute(
            input_data={"data_source": data_source}
        )
        
        return run

# 使用示例
async def main():
    workflow = DataAnalysisWorkflow()
    result = await workflow.execute("sales_data")
    
    print(f"分析完成！")
    print(f"报告: {result.output['report']}")
    print(f"执行时间: {result.duration}s")

asyncio.run(main())

这个工作流展示了：
- 顺序执行
- 并行处理
- 数据流转
- 完整的业务流程
```

**视觉**:
- 工作流图示
- 执行过程动画
- 结果展示

---

### [09:00-10:00] 监控和调试

```
工作流的监控和调试：

1. 查看执行日志

run = await workflow.execute(...)
print(f"执行日志:")
for log in run.logs:
    print(f"  {log.timestamp}: {log.message}")

2. 性能分析

print(f"节点执行时间:")
for node_id, duration in run.node_durations.items():
    print(f"  {node_id}: {duration}ms")

3. 错误追踪

if run.status == "failed":
    print(f"错误: {run.error}")
    print(f"失败节点: {run.failed_node}")
    print(f"堆栈跟踪: {run.stack_trace}")

4. 可视化工作流

# 生成工作流图
graph = workflow.to_graph()
graph.render("workflow.png")

5. 工作流版本控制

# 保存工作流版本
await workflow.save_version("v1.0")

# 加载特定版本
workflow_v1 = await Workflow.load_version(
    "DataAnalysis",
    "v1.0"
)
```

**视觉**:
- 日志输出
- 性能图表
- 工作流可视化

---

### [10:00-11:00] 最佳实践

```
工具和工作流的最佳实践：

1. 工具设计
   - 单一职责
   - 清晰的输入输出
   - 完善的错误处理
   - 详细的文档

2. 工作流设计
   - 清晰的节点命名
   - 合理的超时设置
   - 完善的错误处理
   - 适当的日志记录

3. 性能优化
   - 使用并行执行
   - 缓存中间结果
   - 优化数据库查询
   - 监控性能指标

4. 可维护性
   - 版本控制
   - 文档完整
   - 测试覆盖
   - 监控告警
```

**视觉**:
- 最佳实践清单
- 对比示例

---

### [11:00-12:00] 总结和资源

```
总结一下我们学到的内容：

✓ 工具系统架构
✓ 使用内置工具
✓ 创建自定义工具
✓ 工作流编排
✓ 监控和调试
✓ 最佳实践

更多资源：
- 工具文档: https://docs.x-agent.dev/tools
- 工作流文档: https://docs.x-agent.dev/workflows
- 示例代码: https://github.com/x-agent/examples

在下一个视频中，我们将学习多 Agent 协作。
```

**视觉**:
- 学习成果检查清单
- 资源链接
- 下一个视频预告

---

## 制作建议

### 关键演示
1. 工具系统架构动画
2. 工具创建和注册演示
3. 工作流执行的可视化
4. 完整工作流示例

### 代码高亮
- 关键代码行用不同颜色
- 参数说明用注释
- 输出结果用特殊格式

### 性能展示
- 工作流执行时间
- 节点执行时间对比
- 并行 vs 顺序执行对比
