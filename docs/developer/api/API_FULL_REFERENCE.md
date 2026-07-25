# X-Agent API 完整参考文档

**版本**: 1.0.0  
**最后更新**: 2026-05-27  
**基础 URL**: `https://api.x-agent.dev/api/v1`

---

## 目录

1. [认证授权](#认证授权)
2. [API 概述](#api-概述)
3. [Agent API](#agent-api)
4. [Workflow API](#workflow-api)
5. [Tool API](#tool-api)
6. [Memory API](#memory-api)
7. [Approval API](#approval-api)
8. [Audit API](#audit-api)
9. [WebSocket API](#websocket-api)
10. [错误处理](#错误处理)
11. [速率限制](#速率限制)
12. [最佳实践](#最佳实践)

---

## 认证授权

### 认证方式

X-Agent API 支持以下认证方式：

#### 1. API Key 认证

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.x-agent.dev/api/v1/agents
```

#### 2. OAuth 2.0

```bash
# 获取访问令牌
curl -X POST https://api.x-agent.dev/oauth/token \
  -d "grant_type=client_credentials" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"

# 使用访问令牌
curl -H "Authorization: Bearer ACCESS_TOKEN" \
  https://api.x-agent.dev/api/v1/agents
```

#### 3. JWT 令牌

```bash
curl -H "Authorization: Bearer JWT_TOKEN" \
  https://api.x-agent.dev/api/v1/agents
```

### 权限模型

权限采用基于角色的访问控制（RBAC）：

| 权限 | 描述 | 角色 |
|------|------|------|
| `agent:create` | 创建 Agent | admin, developer |
| `agent:read` | 读取 Agent | admin, developer, viewer |
| `agent:update` | 更新 Agent | admin, developer |
| `agent:delete` | 删除 Agent | admin |
| `workflow:execute` | 执行工作流 | admin, developer |
| `approval:manage` | 管理审批 | admin |
| `audit:read` | 读取审计日志 | admin |

---

## API 概述

### 请求格式

所有请求必须使用 JSON 格式：

```bash
curl -X POST https://api.x-agent.dev/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "name": "MyAgent",
    "capabilities": ["run", "memory"]
  }'
```

### 响应格式

所有响应都遵循统一的格式：

```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "id": "agent_123",
    "name": "MyAgent"
  },
  "timestamp": "2026-05-27T10:30:00Z"
}
```

### 分页

支持分页的端点使用以下参数：

```bash
curl "https://api.x-agent.dev/api/v1/agents?page=1&page_size=20&sort=-created_at"
```

**参数**:
- `page`: 页码（从 1 开始）
- `page_size`: 每页数量（默认 20，最大 100）
- `sort`: 排序字段（使用 `-` 表示降序）

---

## Agent API

### 创建 Agent

**端点**: `POST /agents`

**权限**: `agent:create`

**请求体**:
```json
{
  "name": "DataAnalyzer",
  "description": "用于数据分析的 Agent",
  "status": "active",
  "capabilities": ["run", "memory", "tools", "trace"],
  "max_iterations": 100,
  "config": {
    "timeout": 300,
    "retry_policy": {
      "max_retries": 3,
      "backoff": "exponential"
    }
  }
}
```

**响应** (201 Created):
```json
{
  "code": 201,
  "message": "Agent created successfully",
  "data": {
    "id": "agent_a1b2c3d4",
    "name": "DataAnalyzer",
    "description": "用于数据分析的 Agent",
    "status": "active",
    "capabilities": ["run", "memory", "tools", "trace"],
    "max_iterations": 100,
    "created_at": "2026-05-27T10:30:00Z",
    "updated_at": "2026-05-27T10:30:00Z"
  }
}
```

**错误码**:
- `400`: 请求参数无效
- `403`: 权限不足
- `409`: Agent 名称已存在

### 列出所有 Agent

**端点**: `GET /agents`

**权限**: `agent:read`

**查询参数**:
- `page`: 页码
- `page_size`: 每页数量
- `status`: 过滤状态（active, inactive）
- `sort`: 排序字段

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "items": [
      {
        "id": "agent_a1b2c3d4",
        "name": "DataAnalyzer",
        "status": "active",
        "capabilities": ["run", "memory", "tools", "trace"],
        "created_at": "2026-05-27T10:30:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 获取 Agent 详情

**端点**: `GET /agents/{agent_id}`

**权限**: `agent:read`

**路径参数**:
- `agent_id`: Agent ID

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "id": "agent_a1b2c3d4",
    "name": "DataAnalyzer",
    "status": "active",
    "capabilities": ["run", "memory", "tools", "trace"],
    "max_iterations": 100,
    "stats": {
      "total_runs": 42,
      "successful_runs": 40,
      "failed_runs": 2,
      "avg_duration": 125.5
    },
    "created_at": "2026-05-27T10:30:00Z",
    "updated_at": "2026-05-27T10:30:00Z"
  }
}
```

### 更新 Agent

**端点**: `PUT /agents/{agent_id}`

**权限**: `agent:update`

**请求体**:
```json
{
  "name": "UpdatedAnalyzer",
  "status": "inactive",
  "capabilities": ["run", "memory"]
}
```

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Agent updated successfully",
  "data": {
    "id": "agent_a1b2c3d4",
    "name": "UpdatedAnalyzer",
    "status": "inactive",
    "updated_at": "2026-05-27T10:35:00Z"
  }
}
```

### 删除 Agent

**端点**: `DELETE /agents/{agent_id}`

**权限**: `agent:delete`

**响应** (204 No Content):
```
(无响应体)
```

### 执行 Agent 任务

**端点**: `POST /agents/{agent_id}/run`

**权限**: `agent:execute`

**请求体**:
```json
{
  "task": "分析销售数据并生成报告",
  "context": {
    "data_source": "https://api.example.com/sales",
    "date_range": "2026-01-01 to 2026-05-27"
  },
  "timeout": 300
}
```

**响应** (202 Accepted):
```json
{
  "code": 202,
  "message": "Task accepted",
  "data": {
    "run_id": "run_xyz789",
    "agent_id": "agent_a1b2c3d4",
    "status": "running",
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

### 获取 Agent 运行状态

**端点**: `GET /agents/{agent_id}/runs/{run_id}`

**权限**: `agent:read`

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "run_id": "run_xyz789",
    "agent_id": "agent_a1b2c3d4",
    "status": "completed",
    "result": {
      "summary": "销售数据分析完成",
      "metrics": {
        "total_sales": 1000000,
        "growth_rate": 0.15
      }
    },
    "duration": 125.5,
    "created_at": "2026-05-27T10:30:00Z",
    "completed_at": "2026-05-27T10:32:05Z"
  }
}
```

---

## Workflow API

### 创建工作流

**端点**: `POST /workflows`

**权限**: `workflow:create`

**请求体**:
```json
{
  "name": "DataPipeline",
  "description": "数据处理管道",
  "nodes": [
    {
      "id": "fetch",
      "name": "获取数据",
      "action": "fetch_data",
      "params": {"source": "api"}
    },
    {
      "id": "process",
      "name": "处理数据",
      "action": "process",
      "depends_on": ["fetch"]
    }
  ],
  "edges": [
    {"from": "fetch", "to": "process"}
  ]
}
```

**响应** (201 Created):
```json
{
  "code": 201,
  "message": "Workflow created successfully",
  "data": {
    "id": "wf_abc123",
    "name": "DataPipeline",
    "status": "draft",
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

### 执行工作流

**端点**: `POST /workflows/{workflow_id}/execute`

**权限**: `workflow:execute`

**请求体**:
```json
{
  "context": {
    "user_id": "user_123",
    "parameters": {}
  },
  "timeout": 600
}
```

**响应** (202 Accepted):
```json
{
  "code": 202,
  "message": "Workflow execution started",
  "data": {
    "run_id": "run_wf_123",
    "workflow_id": "wf_abc123",
    "status": "running",
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

### 获取工作流执行结果

**端点**: `GET /workflows/{workflow_id}/runs/{run_id}`

**权限**: `workflow:read`

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "run_id": "run_wf_123",
    "workflow_id": "wf_abc123",
    "status": "completed",
    "nodes": [
      {
        "id": "fetch",
        "status": "completed",
        "output": {"data": [...]},
        "duration": 10.5
      },
      {
        "id": "process",
        "status": "completed",
        "output": {"processed": [...]},
        "duration": 20.3
      }
    ],
    "timeline": [...],
    "metrics": {
      "total_duration": 30.8,
      "success_rate": 1.0
    }
  }
}
```

---

## Tool API

### 列出可用工具

**端点**: `GET /tools`

**权限**: `tool:read`

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "items": [
      {
        "id": "browser",
        "name": "Browser Automation",
        "description": "浏览器自动化工具",
        "parameters": {
          "url": {"type": "string", "required": true},
          "action": {"type": "string", "enum": ["click", "fill", "navigate"]}
        }
      },
      {
        "id": "file",
        "name": "File Operations",
        "description": "文件操作工具",
        "parameters": {
          "path": {"type": "string", "required": true},
          "operation": {"type": "string", "enum": ["read", "write", "delete"]}
        }
      }
    ],
    "total": 2
  }
}
```

### 执行工具

**端点**: `POST /tools/{tool_id}/execute`

**权限**: `tool:execute`

**请求体**:
```json
{
  "parameters": {
    "url": "https://example.com",
    "action": "navigate"
  }
}
```

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Tool executed successfully",
  "data": {
    "result": {
      "status": "success",
      "output": "Page loaded"
    },
    "duration": 2.5
  }
}
```

---

## Memory API

### 存储数据

**端点**: `POST /memory/store`

**权限**: `memory:write`

**请求体**:
```json
{
  "key": "user_profile",
  "value": {
    "name": "Alice",
    "email": "alice@example.com"
  },
  "metadata": {
    "type": "user",
    "source": "api"
  }
}
```

**响应** (201 Created):
```json
{
  "code": 201,
  "message": "Data stored successfully",
  "data": {
    "key": "user_profile",
    "stored_at": "2026-05-27T10:30:00Z"
  }
}
```

### 检索数据

**端点**: `GET /memory/retrieve/{key}`

**权限**: `memory:read`

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "key": "user_profile",
    "value": {
      "name": "Alice",
      "email": "alice@example.com"
    },
    "metadata": {
      "type": "user",
      "source": "api"
    },
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

### 语义搜索

**端点**: `POST /memory/search`

**权限**: `memory:read`

**请求体**:
```json
{
  "query": "用户信息",
  "top_k": 10,
  "threshold": 0.7
}
```

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "results": [
      {
        "key": "user_profile",
        "value": {...},
        "score": 0.95
      }
    ],
    "total": 1
  }
}
```

---

## Approval API

### 创建审批请求

**端点**: `POST /approvals`

**权限**: `approval:create`

**请求体**:
```json
{
  "action": "delete_agent",
  "resource_id": "agent_a1b2c3d4",
  "reason": "Agent 不再使用",
  "required_approvers": 2
}
```

**响应** (201 Created):
```json
{
  "code": 201,
  "message": "Approval request created",
  "data": {
    "id": "approval_123",
    "status": "pending",
    "created_at": "2026-05-27T10:30:00Z"
  }
}
```

### 批准请求

**端点**: `POST /approvals/{approval_id}/approve`

**权限**: `approval:manage`

**请求体**:
```json
{
  "comment": "已审查，同意删除"
}
```

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Approval request approved",
  "data": {
    "id": "approval_123",
    "status": "approved",
    "approved_at": "2026-05-27T10:35:00Z"
  }
}
```

---

## Audit API

### 获取审计日志

**端点**: `GET /audit/logs`

**权限**: `audit:read`

**查询参数**:
- `resource_type`: 资源类型
- `action`: 操作类型
- `actor`: 操作者
- `start_time`: 开始时间
- `end_time`: 结束时间

**响应** (200 OK):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "items": [
      {
        "id": "audit_123",
        "timestamp": "2026-05-27T10:30:00Z",
        "actor": "user_123",
        "action": "create",
        "resource_type": "agent",
        "resource_id": "agent_a1b2c3d4",
        "changes": {
          "name": "DataAnalyzer"
        },
        "status": "success"
      }
    ],
    "total": 1
  }
}
```

---

## WebSocket API

### 连接

```javascript
const ws = new WebSocket('wss://api.x-agent.dev/ws?token=YOUR_API_KEY');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};

ws.onerror = (error) => {
  console.error('Error:', error);
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

### 订阅事件

```javascript
// 订阅 Agent 运行事件
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'agent_runs',
  agent_id: 'agent_a1b2c3d4'
}));

// 接收事件
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'agent_run_update') {
    console.log('Agent run status:', message.data);
  }
};
```

### 事件类型

| 事件类型 | 描述 |
|---------|------|
| `agent_run_started` | Agent 运行开始 |
| `agent_run_updated` | Agent 运行更新 |
| `agent_run_completed` | Agent 运行完成 |
| `workflow_node_started` | 工作流节点开始 |
| `workflow_node_completed` | 工作流节点完成 |
| `approval_requested` | 审批请求 |
| `approval_completed` | 审批完成 |

---

## 错误处理

### 错误响应格式

```json
{
  "code": 400,
  "message": "Bad Request",
  "error": {
    "type": "validation_error",
    "details": [
      {
        "field": "name",
        "message": "Name is required"
      }
    ]
  },
  "timestamp": "2026-05-27T10:30:00Z"
}
```

### 常见错误码

| 错误码 | 含义 | 解决方案 |
|-------|------|---------|
| 400 | 请求参数无效 | 检查请求体和参数 |
| 401 | 未授权 | 检查认证令牌 |
| 403 | 权限不足 | 检查用户权限 |
| 404 | 资源不存在 | 检查资源 ID |
| 409 | 冲突 | 资源已存在或状态冲突 |
| 429 | 请求过于频繁 | 等待后重试 |
| 500 | 服务器错误 | 联系支持 |

---

## 速率限制

### 限制规则

- **免费计划**: 100 请求/分钟
- **专业计划**: 1000 请求/分钟
- **企业计划**: 无限制

### 响应头

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1622160000
```

### 处理限制

```python
import time
import requests

def make_request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)
        
        if response.status_code == 429:
            reset_time = int(response.headers['X-RateLimit-Reset'])
            wait_time = reset_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

---

## 最佳实践

### 1. 错误处理

```python
import requests
from requests.exceptions import RequestException

def call_api(endpoint, method='GET', **kwargs):
    try:
        response = requests.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            # 处理速率限制
            pass
        elif e.response.status_code == 401:
            # 处理认证错误
            pass
        raise
    except RequestException as e:
        # 处理网络错误
        raise
```

### 2. 重试策略

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_api_with_retry(endpoint):
    return requests.get(endpoint)
```

### 3. 异步调用

```python
import asyncio
import aiohttp

async def call_api_async(endpoint):
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as response:
            return await response.json()

# 并发调用
async def call_multiple_apis(endpoints):
    tasks = [call_api_async(ep) for ep in endpoints]
    return await asyncio.gather(*tasks)
```

### 4. 缓存策略

```python
from functools import lru_cache
import time

class APICache:
    def __init__(self, ttl=300):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())
```

---

**X-Agent API 完整参考** - 构建集成应用
