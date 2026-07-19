# X-Agent 快速开始指南

5 分钟快速上手 X-Agent，创建你的第一个 Agent 和工作流。

## 前置要求

- Python 3.11+
- PostgreSQL 14+
- Docker 和 Docker Compose（可选）
- 基本的 Python 和 REST API 知识

## 第 1 步：安装 X-Agent

### 1.1 克隆仓库

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
```

### 1.2 创建虚拟环境

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 1.3 安装依赖

```bash
pip install -e ".[dev]"
```

### 1.4 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置必要的环境变量：

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://xagent:xagent@localhost:5432/xagent

# LLM API
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# 记忆系统
XAGENT_MEMORY_BACKEND=jsonl
XAGENT_MEMORY_STORE_PATH=.xagent_runtime/memory.jsonl

# 追踪
XAGENT_TRACE_BACKEND=jsonl
XAGENT_TRACE_STORE_PATH=.xagent_runtime/traces.jsonl
```

## 第 2 步：启动依赖服务

### 2.1 使用 Docker Compose

```bash
docker-compose up -d postgres qdrant neo4j redis
```

### 2.2 初始化数据库

```bash
python -m backend.app.core.migration init
```

## 第 3 步：启动 X-Agent 服务

```bash
uvicorn backend.app.main:app --reload --port 8000
```

服务启动后，访问 http://localhost:8000/docs 查看 API 文档。

## 第 4 步：创建你的第一个 Agent

### 4.1 使用 Python SDK

创建文件 `my_first_agent.py`：

```python
import asyncio
from backend.app.core.agent import Agent
from backend.app.core.llm import LLMRouter

async def main():
    # 初始化 LLM 路由器
    llm_router = LLMRouter()
    
    # 创建 Agent
    agent = Agent(
        name="MyFirstAgent",
        description="我的第一个 Agent",
        llm_router=llm_router,
        tools=[]  # 稍后添加工具
    )
    
    # 执行任务
    result = await agent.execute(
        task="请告诉我今天的日期"
    )
    
    print(f"Agent 执行结果: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

运行 Agent：

```bash
python my_first_agent.py
```

### 4.2 使用 REST API

```bash
# 创建 Agent
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyFirstAgent",
    "description": "我的第一个 Agent",
    "model": "gpt-4",
    "tools": []
  }'

# 执行任务
curl -X POST http://localhost:8000/api/agents/MyFirstAgent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "请告诉我今天的日期"
  }'
```

## 第 5 步：创建你的第一个工作流

### 5.1 定义工作流

创建文件 `my_first_workflow.py`：

```python
import asyncio
from backend.app.core.workflows import Workflow, WorkflowNode, NodeType

async def main():
    # 创建工作流
    workflow = Workflow(
        name="MyFirstWorkflow",
        description="我的第一个工作流"
    )
    
    # 添加节点
    node1 = WorkflowNode(
        id="step1",
        name="获取数据",
        type=NodeType.TASK,
        action="fetch_data",
        params={"source": "api"}
    )
    
    node2 = WorkflowNode(
        id="step2",
        name="处理数据",
        type=NodeType.TASK,
        action="process_data",
        params={"format": "json"}
    )
    
    node3 = WorkflowNode(
        id="step3",
        name="保存结果",
        type=NodeType.TASK,
        action="save_result",
        params={"destination": "database"}
    )
    
    # 添加节点到工作流
    workflow.add_node(node1)
    workflow.add_node(node2)
    workflow.add_node(node3)
    
    # 定义节点之间的依赖关系
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    
    # 执行工作流
    run = await workflow.execute()
    
    print(f"工作流执行完成: {run.status}")
    print(f"执行时间: {run.duration}s")

if __name__ == "__main__":
    asyncio.run(main())
```

运行工作流：

```bash
python my_first_workflow.py
```

### 5.2 使用 REST API

```bash
# 创建工作流
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyFirstWorkflow",
    "description": "我的第一个工作流",
    "nodes": [
      {
        "id": "step1",
        "name": "获取数据",
        "type": "task",
        "action": "fetch_data"
      },
      {
        "id": "step2",
        "name": "处理数据",
        "type": "task",
        "action": "process_data"
      }
    ],
    "edges": [
      {"from": "step1", "to": "step2"}
    ]
  }'

# 执行工作流
curl -X POST http://localhost:8000/api/workflows/MyFirstWorkflow/execute \
  -H "Content-Type: application/json" \
  -d '{}'
```

## 第 6 步：创建你的第一个技能

### 6.1 定义技能

创建文件 `my_first_skill.py`：

```python
from backend.app.core.tool_schema import Tool, ToolParameter

class MyFirstSkill:
    """我的第一个技能"""
    
    @staticmethod
    def get_tool_definition() -> Tool:
        return Tool(
            name="my_first_skill",
            description="这是我的第一个技能",
            parameters=[
                ToolParameter(
                    name="input_text",
                    type="string",
                    description="输入文本",
                    required=True
                )
            ]
        )
    
    @staticmethod
    async def execute(input_text: str) -> str:
        """执行技能"""
        return f"处理结果: {input_text.upper()}"
```

### 6.2 注册技能

```python
from backend.app.core.tool_registry import ToolRegistry
from my_first_skill import MyFirstSkill

# 注册技能
registry = ToolRegistry()
registry.register(MyFirstSkill)
```

## 第 7 步：监控和调试

### 7.1 查看执行日志

```bash
# 查看 Agent 执行日志
curl http://localhost:8000/api/agents/MyFirstAgent/logs

# 查看工作流执行日志
curl http://localhost:8000/api/workflows/MyFirstWorkflow/runs/run-id/logs
```

### 7.2 查看追踪信息

```bash
# 查看执行追踪
curl http://localhost:8000/api/traces/run-id
```

### 7.3 查看性能指标

```bash
# 查看性能指标
curl http://localhost:8000/api/metrics/run-id
```

## 常见问题

### Q1: 如何添加工具到 Agent？

```python
from backend.app.core.tool_registry import ToolRegistry

# 获取工具注册表
registry = ToolRegistry()

# 获取可用工具
tools = registry.get_all_tools()

# 创建 Agent 时指定工具
agent = Agent(
    name="MyAgent",
    tools=tools
)
```

### Q2: 如何处理工作流中的错误？

```python
# 添加错误处理节点
error_handler = WorkflowNode(
    id="error_handler",
    name="错误处理",
    type=NodeType.ERROR_HANDLER,
    action="handle_error"
)

workflow.add_node(error_handler)

# 为所有节点添加错误处理
for node in workflow.nodes:
    workflow.add_edge(node.id, "error_handler", condition="on_error")
```

### Q3: 如何使用记忆系统？

```python
from backend.app.core.memory import MemoryManager

# 创建记忆管理器
memory = MemoryManager()

# 存储信息
await memory.store(
    key="user_preference",
    value={"theme": "dark", "language": "zh"}
)

# 检索信息
preference = await memory.retrieve("user_preference")

# 搜索相似信息
results = await memory.search("用户偏好")
```

## 下一步

1. 阅读 [Agent 使用教程](01-agent-basics.md)
2. 阅读 [工作流编排教程](02-workflow-orchestration.md)
3. 阅读 [记忆系统教程](03-memory-system.md)
4. 探索 [示例代码库](../../examples/)
5. 阅读 [最佳实践](../best-practices/README.md)

## 获取帮助

- 📖 查看 [API 文档](http://localhost:8000/docs)
- 🐛 报告问题：https://github.com/x-agent/x-agent-core/issues
- 💬 社区讨论：https://github.com/x-agent/x-agent-core/discussions
- 📧 联系支持：support@x-agent.dev

---

**恭喜！** 你已经完成了 X-Agent 的快速开始。现在可以开始构建更复杂的应用了！
