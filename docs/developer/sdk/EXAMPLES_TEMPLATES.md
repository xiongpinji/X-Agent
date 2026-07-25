# X-Agent 示例和模板集合

包含常见使用场景的代码示例和可复用模板。

## 目录

- [Agent 示例](#agent-示例)
- [工作流示例](#工作流示例)
- [记忆系统示例](#记忆系统示例)
- [工具集成示例](#工具集成示例)
- [API 调用示例](#api-调用示例)
- [配置模板](#配置模板)

---

## Agent 示例

### 示例 1：基础 Agent 创建

```python
import requests

agent_config = {
    "name": "BasicAgent",
    "description": "A basic agent for simple tasks",
    "capabilities": ["reasoning", "planning"],
    "model": "gpt-4",
    "temperature": 0.7
}

response = requests.post(
    "http://localhost:8000/api/v1/agents",
    json=agent_config
)

agent = response.json()
print(f"Agent created: {agent['id']}")
```

### 示例 2：具有工具的 Agent

```python
agent_config = {
    "name": "ToolAgent",
    "description": "Agent with browser and file tools",
    "capabilities": ["reasoning", "planning", "tool_use"],
    "tools": [
        {
            "name": "browser",
            "enabled": True,
            "config": {"headless": True}
        },
        {
            "name": "file_system",
            "enabled": True
        }
    ],
    "model": "gpt-4"
}

response = requests.post(
    "http://localhost:8000/api/v1/agents",
    json=agent_config
)

agent = response.json()
print(f"Agent with tools created: {agent['id']}")
```

### 示例 3：执行任务

```python
task_config = {
    "description": "Analyze customer reviews",
    "priority": "high",
    "context": {
        "reviews": [
            "Great product!",
            "Poor quality",
            "Average"
        ]
    }
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/tasks",
    json=task_config
)

task = response.json()
print(f"Task created: {task['id']}")
```

---

## 工作流示例

### 示例 4：基础工作流

```python
workflow_config = {
    "name": "DataProcessingWorkflow",
    "steps": [
        {
            "id": "extract",
            "type": "agent_task",
            "agent_id": "agent1",
            "task": "Extract data"
        },
        {
            "id": "transform",
            "type": "agent_task",
            "agent_id": "agent2",
            "task": "Transform data",
            "depends_on": ["extract"]
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/workflows",
    json=workflow_config
)

workflow = response.json()
print(f"Workflow created: {workflow['id']}")
```

### 示例 5：条件分支工作流

```python
workflow_config = {
    "name": "ConditionalWorkflow",
    "steps": [
        {
            "id": "check",
            "type": "agent_task",
            "agent_id": "agent1",
            "task": "Check data quality"
        },
        {
            "id": "branch",
            "type": "condition",
            "depends_on": ["check"],
            "condition": "${check.output.quality > 0.8}",
            "true_branch": "process",
            "false_branch": "fix"
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/workflows",
    json=workflow_config
)
```

---

## 记忆系统示例

### 示例 6：存储记忆

```python
memory_data = {
    "content": "User prefers JSON format",
    "type": "preference",
    "tags": ["user_preference"],
    "metadata": {"user_id": "user123"}
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/memory",
    json=memory_data
)

memory = response.json()
print(f"Memory stored: {memory['id']}")
```

### 示例 7：检索记忆

```python
response = requests.get(
    f"http://localhost:8000/api/v1/agents/{agent_id}/memory/search",
    params={"query": "user preferences", "limit": 5}
)

memories = response.json()
for memory in memories['items']:
    print(f"- {memory['content']}")
```

---

## 工具集成示例

### 示例 8：浏览器自动化

```python
browser_task = {
    "description": "Extract data from website",
    "tool": "browser",
    "actions": [
        {"type": "navigate", "url": "https://example.com"},
        {"type": "wait", "selector": ".data-table"},
        {"type": "extract", "selector": ".data-table"}
    ]
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/tasks",
    json=browser_task
)
```

### 示例 9：文件系统操作

```python
file_task = {
    "description": "Process files",
    "tool": "file_system",
    "actions": [
        {"type": "read", "path": "/data/input.txt"},
        {"type": "write", "path": "/data/output.txt", "content": "Result"}
    ]
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/tasks",
    json=file_task
)
```

---

## API 调用示例

### 示例 10：cURL 命令

```bash
# 创建 Agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyAgent",
    "capabilities": ["reasoning"],
    "model": "gpt-4"
  }'

# 创建任务
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Do something"}'

# 获取任务状态
curl http://localhost:8000/api/v1/agents/{agent_id}/tasks/{task_id}

# 列出所有 Agent
curl http://localhost:8000/api/v1/agents?limit=10
```

---

## 配置模板

### 模板 1：开发环境

```bash
# .env.development
DATABASE_URL=postgresql://xagent:xagent@localhost:5432/xagent_dev
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379

OPENAI_API_KEY=sk-...
DEBUG=true
LOG_LEVEL=DEBUG
SERVER_PORT=8000
```

### 模板 2：生产环境

```bash
# .env.production
DATABASE_URL=postgresql://xagent:${DB_PASSWORD}@db.example.com:5432/xagent
QDRANT_URL=https://qdrant.example.com
REDIS_URL=redis://:${REDIS_PASSWORD}@redis.example.com:6379

OPENAI_API_KEY=${OPENAI_API_KEY}
DEBUG=false
LOG_LEVEL=INFO
SSL_ENABLED=true
```

---

**最后更新**：2026年5月29日
