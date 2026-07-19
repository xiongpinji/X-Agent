# X-Agent 视频教程脚本

完整的视频教程脚本，用于创建 YouTube、B站等平台的教程视频。

## 视频 1: X-Agent 快速开始 (5 分钟)

**标题**: X-Agent 快速开始 - 5 分钟创建你的第一个 Agent

**描述**:
在这个视频中，我们将展示如何快速开始使用 X-Agent。你将学到：
- 安装 X-Agent
- 配置环境
- 创建第一个 Agent
- 执行第一个任务

**脚本**:

```
[00:00-00:15] 开场
你好，欢迎来到 X-Agent 教程。
在这个视频中，我们将在 5 分钟内创建你的第一个 AI Agent。

[00:15-00:45] 安装
首先，让我们安装 X-Agent。
打开终端，运行以下命令：

git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

[00:45-01:30] 配置
接下来，我们需要配置环境变量。
复制 .env.example 到 .env：

cp .env.example .env

然后编辑 .env 文件，添加你的 API 密钥：

OPENAI_API_KEY=sk-your-key-here

[01:30-02:30] 启动服务
现在启动 X-Agent 服务：

uvicorn backend.app.main:app --reload --port 8000

你可以在 http://localhost:8000/docs 查看 API 文档。

[02:30-04:00] 创建 Agent
现在让我们创建第一个 Agent。
创建一个文件 my_first_agent.py：

import asyncio
from backend.app.core.agent import Agent
from backend.app.core.llm import LLMRouter

async def main():
    llm_router = LLMRouter()
    agent = Agent(
        name="MyFirstAgent",
        description="我的第一个 Agent",
        llm_router=llm_router
    )
    
    result = await agent.execute(
        task="请告诉我今天的日期"
    )
    
    print(f"Agent 响应: {result.output}")

asyncio.run(main())

[04:00-04:45] 运行 Agent
运行 Agent：

python my_first_agent.py

你应该会看到 Agent 的响应。

[04:45-05:00] 总结
恭喜！你已经创建了你的第一个 Agent。
接下来，你可以：
- 添加更多工具
- 创建工作流
- 使用记忆系统

更多信息请访问我们的文档。
```

## 视频 2: Agent 功能详解 (10 分钟)

**标题**: X-Agent Agent 功能详解 - 工具、记忆和协作

**描述**:
深入了解 X-Agent 的 Agent 功能：
- 如何添加工具
- 如何使用记忆系统
- 如何实现多 Agent 协作

**脚本**:

```
[00:00-00:30] 开场
在上一个视频中，我们创建了第一个 Agent。
在这个视频中，我们将深入了解 Agent 的高级功能。

[00:30-03:00] 添加工具
首先，让我们为 Agent 添加工具。
工具是 Agent 可以调用的外部服务或功能。

from backend.app.core.tool_registry import ToolRegistry

registry = ToolRegistry()
tools = registry.get_all_tools()

# 为 Agent 添加工具
agent.add_tool(registry.get_tool("query_database"))
agent.add_tool(registry.get_tool("send_email"))

现在 Agent 可以使用这些工具来完成任务。

[03:00-06:00] 使用记忆系统
接下来，让我们使用记忆系统。
记忆系统允许 Agent 存储和检索信息。

from backend.app.core.memory import MemoryManager

memory = MemoryManager()

# 存储信息
await memory.store(
    key="user_preferences",
    value={"theme": "dark"}
)

# 检索信息
preferences = await memory.retrieve("user_preferences")

# 搜索相似信息
results = await memory.search("用户偏好")

[06:00-09:00] 多 Agent 协作
最后，让我们实现多 Agent 协作。
这允许多个 Agent 一起工作来完成复杂任务。

from backend.app.core.collaboration import AgentCollaborator

collaborator = AgentCollaborator()
collaborator.add_agent(agent1)
collaborator.add_agent(agent2)

result = await collaborator.execute(task)

[09:00-10:00] 总结
现在你已经了解了 Agent 的高级功能。
在下一个视频中，我们将学习工作流编排。
```

## 视频 3: 工作流编排 (12 分钟)

**标题**: X-Agent 工作流编排 - 从简单到复杂

**描述**:
学习如何使用 X-Agent 的工作流编排功能：
- 定义工作流
- 添加节点和边
- 处理条件分支
- 错误处理和恢复

**脚本**:

```
[00:00-00:30] 开场
欢迎回到 X-Agent 教程。
在这个视频中，我们将学习工作流编排。

[00:30-03:00] 什么是工作流
工作流是一系列有序的任务节点。
它支持顺序执行、条件分支、并行执行等。

工作流适合结构化的业务流程，比如：
- 订单处理
- 数据处理
- 审批流程

[03:00-06:00] 定义工作流
让我们定义一个简单的工作流：

from backend.app.core.workflows import Workflow, WorkflowNode, NodeType

workflow = Workflow(
    name="OrderProcessing",
    description="订单处理工作流"
)

# 添加节点
node1 = WorkflowNode(
    id="validate_order",
    name="验证订单",
    type=NodeType.TASK,
    action="validate_order"
)

workflow.add_node(node1)

[06:00-09:00] 条件分支
现在让我们添加条件分支：

workflow.add_edge(
    from_node="validate_order",
    to_node="require_approval",
    condition="amount > 1000"
)

workflow.add_edge(
    from_node="validate_order",
    to_node="process_payment",
    condition="amount <= 1000"
)

[09:00-11:00] 执行工作流
最后，让我们执行工作流：

run = await workflow.execute(
    input_data={"order_id": "ORD-001"}
)

print(f"工作流状态: {run.status}")
print(f"执行时间: {run.duration}s")

[11:00-12:00] 总结
现在你已经学会了工作流编排。
在下一个视频中，我们将学习浏览器自动化。
```

## 视频 4: 浏览器自动化 (15 分钟)

**标题**: X-Agent 浏览器自动化 - 网页爬虫和数据提取

**描述**:
学习如何使用 X-Agent 的浏览器自动化功能：
- 页面导航
- 元素交互
- 数据提取
- 处理动态内容

**脚本**:

```
[00:00-00:30] 开场
欢迎来到浏览器自动化教程。
在这个视频中，我们将学习如何使用 X-Agent 进行网页自动化。

[00:30-03:00] 初始化浏览器
首先，让我们初始化浏览器：

from backend.app.core.browser import BrowserManager

browser_manager = BrowserManager()
browser = await browser_manager.launch(headless=True)
page = await browser.new_page()

[03:00-06:00] 页面导航
现在让我们导航到一个网页：

await page.goto("https://example.com")
await page.wait_for_load_state("networkidle")

title = await page.title()
print(f"页面标题: {title}")

[06:00-09:00] 元素交互
让我们与页面元素交互：

# 点击按钮
await page.click("button.submit")

# 输入文本
await page.fill("input.search", "搜索词")

# 提交表单
await page.press("input", "Enter")

[09:00-12:00] 数据提取
现在让我们提取数据：

# 提取文本
text = await page.text_content("div.content")

# 执行 JavaScript
data = await page.evaluate("""
    () => {
        return Array.from(document.querySelectorAll('div.item'))
            .map(item => ({
                title: item.querySelector('.title').textContent,
                price: item.querySelector('.price').textContent
            }));
    }
""")

[12:00-14:00] 处理动态内容
最后，让我们处理动态加载的内容：

# 等待元素出现
await page.wait_for_selector("div.content")

# 等待网络空闲
await page.wait_for_load_state("networkidle")

# 等待特定条件
await page.wait_for_function(
    "() => document.querySelectorAll('div.item').length > 0"
)

[14:00-15:00] 总结
现在你已经学会了浏览器自动化。
在下一个视频中，我们将学习最佳实践。
```

## 视频 5: 最佳实践和性能优化 (12 分钟)

**标题**: X-Agent 最佳实践 - 构建高效可靠的系统

**描述**:
学习如何使用 X-Agent 的最佳实践：
- Agent 设计最佳实践
- 工作流优化
- 性能优化
- 安全最佳实践

**脚本**:

```
[00:00-00:30] 开场
欢迎来到最佳实践教程。
在这个视频中，我们将学习如何构建高效可靠的 X-Agent 系统。

[00:30-03:00] Agent 设计最佳实践
首先，让我们讨论 Agent 设计最佳实践：

1. 明确定义职责
   - 每个 Agent 应该有单一的职责
   - 不要让 Agent 做太多事情

2. 提供清晰的系统提示词
   - 告诉 Agent 它的角色和职责
   - 定义禁止的操作

3. 合理配置工具
   - 只添加必要的工具
   - 避免工具过多

[03:00-06:00] 工作流优化
接下来，让我们讨论工作流优化：

1. 使用并行节点提高效率
   parallel_node = WorkflowNode(
       type=NodeType.PARALLEL,
       nodes=["send_email", "update_db", "log_event"]
   )

2. 合理设置超时时间
   node = WorkflowNode(
       timeout=300  # 5 分钟
   )

3. 完善错误处理
   workflow.add_compensation(
       node_id="create_shipment",
       compensation_action="cancel_shipment"
   )

[06:00-09:00] 性能优化
现在让我们讨论性能优化：

1. 使用缓存
   cached = await memory.retrieve(key)
   if cached:
       return cached

2. 使用批量操作
   await memory.store_batch({...})

3. 使用异步操作
   results = await asyncio.gather(*tasks)

[09:00-12:00] 安全最佳实践
最后，让我们讨论安全最佳实践：

1. 输入验证
   from pydantic import BaseModel, validator

2. 权限控制
   if not await check_permission(user, task):
       raise PermissionError()

3. 审计日志
   await audit_logger.log(action, user, task)

[12:00-12:00] 总结
现在你已经学会了最佳实践。
感谢观看！
```

## 视频 6: 完整项目示例 (20 分钟)

**标题**: X-Agent 完整项目 - 构建数据分析系统

**描述**:
通过一个完整的项目示例，学习如何使用 X-Agent 构建实际应用：
- 项目规划
- 系统设计
- 代码实现
- 部署和监控

**脚本**:

```
[00:00-01:00] 开场和项目介绍
欢迎来到完整项目教程。
在这个视频中，我们将构建一个完整的数据分析系统。

项目需求：
- 从多个数据源获取数据
- 进行数据清洗和转换
- 执行数据分析
- 生成分析报告

[01:00-05:00] 系统设计
首先，让我们设计系统架构：

1. 数据收集层
   - 从数据库获取数据
   - 从 API 获取数据

2. 数据处理层
   - 数据清洗
   - 数据转换
   - 数据验证

3. 分析层
   - 统计分析
   - 趋势分析
   - 异常检测

4. 报告层
   - 生成报告
   - 发送通知

[05:00-10:00] 代码实现
现在让我们实现系统：

class AnalyticsSystem:
    def __init__(self):
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        workflow = Workflow(...)
        # 添加节点和边
        return workflow
    
    async def run_analysis(self, data_source):
        run = await self.workflow.execute(...)
        return run.output

[10:00-15:00] 工作流定义
让我们定义工作流：

nodes = [
    WorkflowNode(id="fetch_data", ...),
    WorkflowNode(id="clean_data", ...),
    WorkflowNode(id="analyze_data", ...),
    WorkflowNode(id="generate_report", ...)
]

workflow.add_edge("fetch_data", "clean_data")
workflow.add_edge("clean_data", "analyze_data")
workflow.add_edge("analyze_data", "generate_report")

[15:00-18:00] 测试和调试
现在让我们测试系统：

async def test_analytics():
    system = AnalyticsSystem()
    result = await system.run_analysis("test_data")
    assert result is not None

[18:00-20:00] 部署和监控
最后，让我们部署系统：

1. 使用 Docker 容器化
2. 配置监控和告警
3. 设置备份和恢复

感谢观看！
```

## 下一步

- 上传视频到 YouTube 或 B站
- 在视频描述中添加文档链接
- 鼓励观众查看完整文档
- 收集反馈并改进教程

## 视频制作建议

1. **录制工具**：使用 OBS Studio 或 ScreenFlow
2. **编辑工具**：使用 DaVinci Resolve 或 Adobe Premiere
3. **字幕**：添加中英文字幕
4. **缩略图**：创建吸引人的缩略图
5. **标签**：使用相关的标签提高搜索排名

## 下一步

- 阅读 [最佳实践](../best-practices/README.md)
- 阅读 [故障排除](../troubleshooting/COMMON_ISSUES.md)
- 探索 [示例代码库](../../examples/)
