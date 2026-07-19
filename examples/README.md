# X-Agent 示例代码库

完整的示例代码，展示如何使用 X-Agent 的各项功能。

## 目录

1. [基础示例](#基础示例)
2. [高级示例](#高级示例)
3. [实际场景示例](#实际场景示例)
4. [完整项目示例](#完整项目示例)

## 基础示例

### 示例 1: 创建第一个 Agent

**文件**: `examples/01_basic_agent.py`

```python
import asyncio
from backend.app.core.agent import Agent
from backend.app.core.llm import LLMRouter

async def main():
    # 初始化 LLM 路由器
    llm_router = LLMRouter(default_model="gpt-4")
    
    # 创建 Agent
    agent = Agent(
        name="GreeterAgent",
        description="一个简单的问候 Agent",
        llm_router=llm_router
    )
    
    # 执行任务
    result = await agent.execute(
        task="请用中文问候我，并告诉我今天的日期"
    )
    
    print(f"Agent 响应: {result.output}")
    print(f"执行时间: {result.duration}s")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 2: 创建第一个工作流

**文件**: `examples/02_basic_workflow.py`

```python
import asyncio
from backend.app.core.workflows import Workflow, WorkflowNode, NodeType

async def main():
    # 创建工作流
    workflow = Workflow(
        name="SimpleWorkflow",
        description="一个简单的工作流"
    )
    
    # 添加节点
    node1 = WorkflowNode(
        id="step1",
        name="第一步",
        type=NodeType.TASK,
        action="print_message",
        params={"message": "开始执行"}
    )
    
    node2 = WorkflowNode(
        id="step2",
        name="第二步",
        type=NodeType.TASK,
        action="print_message",
        params={"message": "执行中..."}
    )
    
    node3 = WorkflowNode(
        id="step3",
        name="第三步",
        type=NodeType.TASK,
        action="print_message",
        params={"message": "执行完成"}
    )
    
    # 添加节点
    workflow.add_node(node1)
    workflow.add_node(node2)
    workflow.add_node(node3)
    
    # 定义依赖关系
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    
    # 执行工作流
    run = await workflow.execute()
    
    print(f"工作流状态: {run.status}")
    print(f"执行时间: {run.duration}s")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 3: 使用记忆系统

**文件**: `examples/03_memory_system.py`

```python
import asyncio
from backend.app.core.memory import MemoryManager, MemoryType

async def main():
    # 创建记忆管理器
    memory = MemoryManager()
    
    # 存储用户偏好
    await memory.store(
        key="user_preferences",
        value={
            "theme": "dark",
            "language": "zh",
            "notifications": True
        },
        memory_type=MemoryType.LONG_TERM
    )
    
    # 检索用户偏好
    preferences = await memory.retrieve("user_preferences")
    print(f"用户偏好: {preferences}")
    
    # 存储向量记忆
    documents = [
        "Python 是一种高级编程语言",
        "机器学习是人工智能的一个分支",
        "数据分析用于从数据中提取有用信息"
    ]
    
    for i, doc in enumerate(documents):
        await memory.store(
            key=f"doc_{i}",
            value=doc,
            memory_type=MemoryType.VECTOR
        )
    
    # 搜索相似文档
    results = await memory.search(
        query="编程语言",
        memory_type=MemoryType.VECTOR,
        top_k=3
    )
    
    print(f"搜索结果:")
    for result in results:
        print(f"  相似度: {result.similarity:.2f}")
        print(f"  内容: {result.value}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 高级示例

### 示例 4: 多 Agent 协作

**文件**: `examples/04_multi_agent_collaboration.py`

```python
import asyncio
from backend.app.core.agent import Agent
from backend.app.core.collaboration import AgentCollaborator
from backend.app.core.llm import LLMRouter

async def main():
    llm_router = LLMRouter(default_model="gpt-4")
    
    # 创建多个 Agent
    collector_agent = Agent(
        name="DataCollectorAgent",
        description="数据收集 Agent",
        llm_router=llm_router
    )
    
    analyzer_agent = Agent(
        name="DataAnalyzerAgent",
        description="数据分析 Agent",
        llm_router=llm_router
    )
    
    reporter_agent = Agent(
        name="ReportGeneratorAgent",
        description="报告生成 Agent",
        llm_router=llm_router
    )
    
    # 创建协作器
    collaborator = AgentCollaborator()
    collaborator.add_agent(collector_agent)
    collaborator.add_agent(analyzer_agent)
    collaborator.add_agent(reporter_agent)
    
    # 定义协作流程
    collaborator.define_workflow([
        ("DataCollectorAgent", "收集销售数据"),
        ("DataAnalyzerAgent", "分析数据趋势"),
        ("ReportGeneratorAgent", "生成分析报告")
    ])
    
    # 执行协作任务
    result = await collaborator.execute(
        task="生成 2024 年销售分析报告"
    )
    
    print(f"协作结果: {result.output}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 5: 浏览器自动化

**文件**: `examples/05_browser_automation.py`

```python
import asyncio
from backend.app.core.browser import BrowserManager

async def main():
    browser_manager = BrowserManager()
    browser = await browser_manager.launch(headless=True)
    page = await browser.new_page()
    
    try:
        # 访问网站
        await page.goto("https://example.com")
        await page.wait_for_load_state("networkidle")
        
        # 获取页面标题
        title = await page.title()
        print(f"页面标题: {title}")
        
        # 提取数据
        content = await page.text_content("body")
        print(f"页面内容长度: {len(content)} 字符")
        
        # 执行 JavaScript
        result = await page.evaluate("""
            () => {
                return {
                    title: document.title,
                    url: window.location.href,
                    links: document.querySelectorAll('a').length
                };
            }
        """)
        
        print(f"页面信息: {result}")
        
        # 截图
        await page.screenshot(path="screenshot.png")
        print("截图已保存")
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 实际场景示例

### 示例 6: 数据处理自动化

**文件**: `examples/06_data_processing.py`

```python
import asyncio
from backend.app.core.workflows import Workflow, WorkflowNode, NodeType

async def main():
    # 创建数据处理工作流
    workflow = Workflow(
        name="DataProcessing",
        description="数据处理自动化工作流"
    )
    
    # 定义工作流节点
    nodes = [
        WorkflowNode(
            id="fetch_data",
            name="获取数据",
            type=NodeType.TASK,
            action="fetch_from_database",
            params={"table": "sales"}
        ),
        WorkflowNode(
            id="clean_data",
            name="数据清洗",
            type=NodeType.TASK,
            action="clean_data",
            params={"remove_duplicates": True}
        ),
        WorkflowNode(
            id="transform_data",
            name="数据转换",
            type=NodeType.TASK,
            action="transform_data",
            params={"format": "json"}
        ),
        WorkflowNode(
            id="analyze_data",
            name="数据分析",
            type=NodeType.TASK,
            action="analyze_data",
            params={"metrics": ["mean", "median", "std"]}
        ),
        WorkflowNode(
            id="generate_report",
            name="生成报告",
            type=NodeType.TASK,
            action="generate_report",
            params={"format": "pdf"}
        )
    ]
    
    # 添加节点
    for node in nodes:
        workflow.add_node(node)
    
    # 定义依赖关系
    workflow.add_edge("fetch_data", "clean_data")
    workflow.add_edge("clean_data", "transform_data")
    workflow.add_edge("transform_data", "analyze_data")
    workflow.add_edge("analyze_data", "generate_report")
    
    # 执行工作流
    run = await workflow.execute(
        input_data={"date_range": "2024-01-01 to 2024-12-31"}
    )
    
    print(f"工作流执行完成")
    print(f"状态: {run.status}")
    print(f"执行时间: {run.duration}s")
    print(f"输出: {run.output}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 示例 7: 网页内容监控

**文件**: `examples/07_web_monitoring.py`

```python
import asyncio
from backend.app.core.browser import BrowserManager
from backend.app.core.memory import MemoryManager, MemoryType

async def main():
    browser_manager = BrowserManager()
    memory = MemoryManager()
    
    browser = await browser_manager.launch(headless=True)
    page = await browser.new_page()
    
    try:
        # 访问网站
        await page.goto("https://example.com/news")
        await page.wait_for_load_state("networkidle")
        
        # 提取新闻标题
        titles = await page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('h2.title'))
                    .map(h => h.textContent);
            }
        """)
        
        print(f"发现 {len(titles)} 条新闻")
        
        # 检查是否有新闻
        stored_titles = await memory.retrieve("news_titles")
        
        if stored_titles:
            new_titles = set(titles) - set(stored_titles)
            if new_titles:
                print(f"发现 {len(new_titles)} 条新闻:")
                for title in new_titles:
                    print(f"  - {title}")
        
        # 存储当前标题
        await memory.store(
            key="news_titles",
            value=titles,
            memory_type=MemoryType.LONG_TERM
        )
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## 完整项目示例

### 示例 8: 完整的数据分析系统

**文件**: `examples/08_complete_analytics_system.py`

```python
import asyncio
from datetime import datetime
from backend.app.core.agent import Agent
from backend.app.core.workflows import Workflow, WorkflowNode, NodeType
from backend.app.core.memory import MemoryManager, MemoryType
from backend.app.core.llm import LLMRouter

class AnalyticsSystem:
    def __init__(self):
        self.llm_router = LLMRouter(default_model="gpt-4")
        self.memory = MemoryManager()
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        workflow = Workflow(
            name="AnalyticsWorkflow",
            description="完整的数据分析工作流"
        )
        
        # 定义工作流节点
        nodes = [
            WorkflowNode(
                id="fetch_data",
                name="获取数据",
                type=NodeType.TASK,
                action="fetch_data"
            ),
            WorkflowNode(
                id="validate_data",
                name="验证数据",
                type=NodeType.TASK,
                action="validate_data"
            ),
            WorkflowNode(
                id="check_quality",
                name="检查数据质量",
                type=NodeType.DECISION,
                condition="data_quality > 0.8"
            ),
            WorkflowNode(
                id="analyze_data",
                name="分析数据",
                type=NodeType.TASK,
                action="analyze_data"
            ),
            WorkflowNode(
                id="generate_insights",
                name="生成洞察",
                type=NodeType.TASK,
                action="generate_insights"
            ),
            WorkflowNode(
                id="create_report",
                name="创建报告",
                type=NodeType.TASK,
                action="create_report"
            )
        ]
        
        # 添加节点
        for node in nodes:
            workflow.add_node(node)
        
        # 定义依赖关系
        workflow.add_edge("fetch_data", "validate_data")
        workflow.add_edge("validate_data", "check_quality")
        workflow.add_edge("check_quality", "analyze_data", condition="true")
        workflow.add_edge("analyze_data", "generate_insights")
        workflow.add_edge("generate_insights", "create_report")
        
        return workflow
    
    async def run_analysis(self, data_source):
        # 执行工作流
        run = await self.workflow.execute(
            input_data={"source": data_source}
        )
        
        # 存储结果
        await self.memory.store(
            key=f"analysis_{datetime.now().isoformat()}",
            value=run.output,
            memory_type=MemoryType.LONG_TERM
        )
        
        return run.output

async def main():
    system = AnalyticsSystem()
    
    # 运行分析
    result = await system.run_analysis("sales_database")
    
    print(f"分析完成: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 运行示例

```bash
# 运行基础示例
python examples/01_basic_agent.py

# 运行工作流示例
python examples/02_basic_workflow.py

# 运行记忆系统示例
python examples/03_memory_system.py

# 运行多 Agent 协作示例
python examples/04_multi_agent_collaboration.py

# 运行浏览器自动化示例
python examples/05_browser_automation.py

# 运行数据处理示例
python examples/06_data_processing.py

# 运行网页监控示例
python examples/07_web_monitoring.py

# 运行完整系统示例
python examples/08_complete_analytics_system.py
```

## 下一步

- 阅读 [最佳实践](../best-practices/README.md)
- 阅读 [故障排除](../troubleshooting/COMMON_ISSUES.md)
- 阅读 [FAQ](../faq/README.md)
