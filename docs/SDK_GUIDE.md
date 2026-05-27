# X-Agent Python SDK 使用指南

本指南介绍如何使用 X-Agent Python SDK 与 API 交互。

## 安装

### 从 PyPI 安装

```bash
pip install xagent-sdk
```

### 从源代码安装

```bash
git clone https://github.com/xagent/xagent-sdk-python.git
cd xagent-sdk-python
pip install -e .
```

---

## 基本使用

### 初始化客户端

```python
from xagent import XAgentClient

# 使用 token 初始化
client = XAgentClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)

# 或使用用户名和密码
client = XAgentClient(
    base_url="http://localhost:8000",
    username="user@example.com",
    password="your_password"
)
```

### 执行任务

```python
# 同步执行
result = client.runs.start(
    task="分析这个数据集",
    extra_context={"dataset_url": "https://example.com/data.csv"}
)

print(f"Status: {result.status}")
print(f"Result: {result.run.result}")

# 异步执行
run = client.runs.start_async(
    task="分析大型数据集"
)

# 等待完成
result = run.wait_for_completion(timeout=300)
```

---

## Agent 管理

### 创建 Agent

```python
agent = client.agents.create(
    name="Data Analyzer",
    status="active",
    capabilities=["run", "trace", "memory", "tools"],
    config={
        "max_iterations": 100,
        "timeout_seconds": 300,
        "memory_limit_mb": 512
    }
)

print(f"Agent created: {agent.id}")
```

### 列出 Agents

```python
agents = client.agents.list(
    limit=10,
    status="active"
)

for agent in agents:
    print(f"- {agent.name} ({agent.id})")
    print(f"  Status: {agent.status}")
    print(f"  Capabilities: {', '.join(agent.capabilities)}")
```

### 获取 Agent 详情

```python
agent = client.agents.get("agent_a1b2c3d4")

print(f"Name: {agent.name}")
print(f"Status: {agent.status}")
print(f"Total runs: {agent.stats.total_runs}")
print(f"Success rate: {agent.stats.success_rate:.1%}")
```

### 更新 Agent

```python
agent = client.agents.update(
    "agent_a1b2c3d4",
    name="Updated Agent Name",
    status="inactive",
    config={"max_iterations": 50}
)

print(f"Agent updated: {agent.name}")
```

### 删除 Agent

```python
client.agents.delete("agent_a1b2c3d4")
print("Agent deleted")
```

### 暂停/恢复 Agent

```python
# 暂停
client.agents.pause("agent_a1b2c3d4")

# 恢复
client.agents.resume("agent_a1b2c3d4")
```

---

## Run 管理

### 启动 Run

```python
# 同步执行
result = client.runs.start(
    task="分析数据",
    extra_context={"format": "json"},
    async_run=False
)

print(f"Trace ID: {result.trace_id}")
print(f"Status: {result.status}")
print(f"Result: {result.run.result}")

# 异步执行
run = client.runs.start_async(
    task="分析大型数据集"
)

print(f"Run started: {run.trace_id}")
```

### 列出 Runs

```python
runs = client.runs.list(
    limit=20,
    status="completed"
)

for run in runs:
    print(f"- {run.task[:50]}... ({run.status})")
    print(f"  Duration: {run.duration_ms}ms")
```

### 获取 Run 详情

```python
run = client.runs.get("trace_xyz789")

print(f"Task: {run.task}")
print(f"Status: {run.status}")
print(f"Duration: {run.duration_ms}ms")
print(f"Result: {run.result}")

# 查看时间线
for event in run.timeline:
    print(f"  {event.timestamp}: {event.event}")
```

### 等待 Run 完成

```python
run = client.runs.start_async(task="分析数据")

# 等待完成（最多 5 分钟）
result = run.wait_for_completion(timeout=300)

if result.status == "completed":
    print(f"Success: {result.run.result}")
else:
    print(f"Failed: {result.status}")
```

---

## Memory 管理

### 搜索记忆

```python
results = client.memory.search(
    query="之前的分析结果",
    limit=10,
    threshold=0.8
)

for memory in results:
    print(f"- {memory.content[:50]}...")
    print(f"  Similarity: {memory.similarity:.2f}")
    print(f"  Tags: {', '.join(memory.tags)}")
```

### 添加记忆

```python
memory = client.memory.add(
    content="重要的分析结果",
    tags=["analysis", "important"],
    metadata={
        "source": "run_123",
        "confidence": 0.95
    }
)

print(f"Memory added: {memory.id}")
```

### 获取记忆详情

```python
memory = client.memory.get("mem_123")

print(f"Content: {memory.content}")
print(f"Tags: {', '.join(memory.tags)}")
print(f"Created: {memory.created_at}")
```

### 删除记忆

```python
client.memory.delete("mem_123")
print("Memory deleted")
```

---

## Tools 管理

### 列出工具

```python
tools = client.tools.list()

for tool in tools:
    print(f"- {tool.name} ({tool.id})")
    print(f"  Category: {tool.category}")
    print(f"  Description: {tool.description}")
```

### 获取工具详情

```python
tool = client.tools.get("tool_web_search")

print(f"Name: {tool.name}")
print(f"Description: {tool.description}")
print(f"Parameters:")
for param_name, param_info in tool.parameters.items():
    print(f"  - {param_name}: {param_info.type}")
```

---

## Traces 查询

### 获取 Trace

```python
trace = client.traces.get("trace_xyz789")

print(f"Status: {trace.status}")
print(f"Duration: {trace.duration}s")
print(f"Events: {len(trace.events)}")

for event in trace.events:
    print(f"  {event.timestamp}: {event.type}")
```

---

## Audit 日志

### 列出审计日志

```python
logs = client.audit.list(
    limit=50,
    action="agent_created",
    start_time="2026-05-27T00:00:00Z",
    end_time="2026-05-27T23:59:59Z"
)

for log in logs:
    print(f"- {log.timestamp}: {log.action}")
    print(f"  User: {log.user_id}")
    print(f"  Resource: {log.resource_type}/{log.resource_id}")
```

---

## 错误处理

### 处理异常

```python
from xagent.exceptions import (
    XAgentError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError
)

try:
    result = client.runs.start(task="")
except ValidationError as e:
    print(f"Validation error: {e.message}")
    print(f"Details: {e.details}")
except AuthenticationError:
    print("Authentication failed - check your credentials")
except NotFoundError as e:
    print(f"Resource not found: {e.resource_id}")
except RateLimitError:
    print("Rate limited - wait before retrying")
except XAgentError as e:
    print(f"API error: {e.message}")
```

### 重试机制

```python
from xagent.retry import retry_with_backoff

@retry_with_backoff(max_retries=3, backoff_factor=0.5)
def fetch_run(trace_id):
    return client.runs.get(trace_id)

result = fetch_run("trace_xyz789")
```

---

## 高级功能

### 批量操作

```python
# 批量创建 Agents
agents = client.agents.create_batch([
    {"name": "Agent 1", "status": "active"},
    {"name": "Agent 2", "status": "active"},
    {"name": "Agent 3", "status": "active"}
])

print(f"Created {len(agents)} agents")

# 批量启动 Runs
runs = client.runs.start_batch([
    {"task": "Task 1"},
    {"task": "Task 2"},
    {"task": "Task 3"}
])

print(f"Started {len(runs)} runs")
```

### 流式处理

```python
# 流式获取大量数据
for run in client.runs.list_stream(limit=1000):
    print(f"Processing: {run.task}")
    # 处理每个 run
```

### 事件监听

```python
def on_run_completed(run):
    print(f"Run completed: {run.trace_id}")
    print(f"Result: {run.result}")

def on_run_failed(run, error):
    print(f"Run failed: {run.trace_id}")
    print(f"Error: {error}")

# 订阅事件
client.runs.on("completed", on_run_completed)
client.runs.on("failed", on_run_failed)

# 启动异步 Run
run = client.runs.start_async(task="分析数据")
```

### 自定义配置

```python
from xagent import XAgentClient, ClientConfig

config = ClientConfig(
    base_url="http://localhost:8000",
    token="your-token",
    timeout=30,
    max_retries=3,
    retry_backoff_factor=0.5,
    verify_ssl=True,
    proxy="http://proxy.example.com:8080"
)

client = XAgentClient(config=config)
```

---

## 上下文管理

### 使用上下文管理器

```python
from xagent import XAgentClient

with XAgentClient(
    base_url="http://localhost:8000",
    token="your-token"
) as client:
    result = client.runs.start(task="分析数据")
    print(f"Result: {result}")

# 连接自动关闭
```

---

## 日志和调试

### 启用日志

```python
import logging
from xagent import XAgentClient

# 配置日志
logging.basicConfig(level=logging.DEBUG)

client = XAgentClient(
    base_url="http://localhost:8000",
    token="your-token",
    debug=True
)

# 现在所有请求都会被记录
result = client.runs.start(task="分析数据")
```

### 获取请求详情

```python
result = client.runs.start(task="分析数据")

# 获取最后一个请求的详情
last_request = client.get_last_request()
print(f"URL: {last_request.url}")
print(f"Method: {last_request.method}")
print(f"Headers: {last_request.headers}")
print(f"Body: {last_request.body}")

# 获取最后一个响应的详情
last_response = client.get_last_response()
print(f"Status: {last_response.status_code}")
print(f"Headers: {last_response.headers}")
print(f"Body: {last_response.body}")
```

---

## 最佳实践

### 1. 使用环境变量

```python
import os
from xagent import XAgentClient

client = XAgentClient(
    base_url=os.getenv("XAGENT_BASE_URL", "http://localhost:8000"),
    token=os.getenv("XAGENT_TOKEN")
)
```

### 2. 实施重试逻辑

```python
from xagent.retry import retry_with_backoff

@retry_with_backoff(max_retries=3)
def execute_task(task):
    return client.runs.start(task=task)

result = execute_task("分析数据")
```

### 3. 使用异步执行处理长时间任务

```python
run = client.runs.start_async(task="分析大型数据集")
result = run.wait_for_completion(timeout=600)
```

### 4. 监控和日志

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = client.runs.start(task="分析数据")
    logger.info(f"Run completed: {result.trace_id}")
except Exception as e:
    logger.error(f"Run failed: {e}")
```

### 5. 资源清理

```python
# 使用上下文管理器自动清理
with XAgentClient(token="your-token") as client:
    result = client.runs.start(task="分析数据")
```

---

## 常见问题

### Q: 如何处理长时间运行的任务？
A: 使用异步执行和 `wait_for_completion()` 方法：
```python
run = client.runs.start_async(task="长时间任务")
result = run.wait_for_completion(timeout=600)
```

### Q: 如何重试失败的请求？
A: 使用 `@retry_with_backoff` 装饰器或配置客户端的重试策略。

### Q: 如何处理速率限制？
A: SDK 会自动处理速率限制，但你也可以手动实施退避策略。

### Q: 如何调试 API 问题？
A: 启用调试模式并查看日志：
```python
client = XAgentClient(token="your-token", debug=True)
```

---

## 更新日志

### v1.0.0 (2026-05-27)
- 初始版本发布
- 支持所有主要 API 端点
- 完整的错误处理和重试机制
- 详细的文档和示例
