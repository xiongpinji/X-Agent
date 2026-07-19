# X-Agent API 完整参考文档

**版本**: 1.0.0  
**最后更新**: 2026-05-27  
**基础URL**: `http://localhost:8000/api/v1`

## 目录

1. [认证与授权](#认证与授权)
2. [Agents API](#agents-api)
3. [Runs API](#runs-api)
4. [Workflows API](#workflows-api)
5. [Memory API](#memory-api)
6. [Tools API](#tools-api)
7. [Traces API](#traces-api)
8. [Audit API](#audit-api)
9. [错误处理](#错误处理)
10. [速率限制](#速率限制)

---

## 认证与授权

### 认证方式

X-Agent 支持以下认证方式：

#### 1. API Key 认证
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/agents
```

#### 2. Bearer Token 认证
```bash
curl -H "Authorization: Bearer your-jwt-token" http://localhost:8000/api/v1/agents
```

#### 3. 登录获取 Token

**端点**: `POST /auth/login`

**请求体**:
```json
{
  "username": "user@example.com",
  "password": "secure_password"
}
```

**响应** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "user_123",
    "username": "user@example.com",
    "email": "user@example.com",
    "roles": ["user"],
    "scopes": ["agent:read", "agent:run"]
  }
}
```

### 权限范围 (Scopes)

| 范围 | 描述 |
|------|------|
| `agent:read` | 读取 Agent 信息 |
| `agent:run` | 执行 Agent 任务 |
| `agent:manage` | 管理 Agent 配置 |
| `workflow:read` | 读取工作流 |
| `workflow:create` | 创建工作流 |
| `workflow:execute` | 执行工作流 |
| `memory:read` | 读取记忆 |
| `memory:write` | 写入记忆 |
| `tools:read` | 读取工具 |
| `tools:manage` | 管理工具 |
| `audit:read` | 读取审计日志 |
| `security:manage` | 管理安全设置 |

---

## Agents API

Agent 是 X-Agent 系统中的执行单元，负责任务执行和决策。

### 创建 Agent

**端点**: `POST /agents`

**权限**: `security:manage`

**请求体**:
```json
{
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"],
  "config": {
    "max_iterations": 100,
    "timeout_seconds": 300,
    "memory_limit_mb": 512
  }
}
```

**响应** (201 Created):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"],
  "config": {
    "max_iterations": 100,
    "timeout_seconds": 300,
    "memory_limit_mb": 512
  },
  "created_at": "2026-05-27T10:30:00Z",
  "updated_at": "2026-05-27T10:30:00Z",
  "created_by": "user_123"
}
```

**错误码**:
- `400`: 请求参数无效
- `403`: 权限不足
- `409`: Agent 名称已存在

**示例**:
```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Analyzer",
    "status": "active",
    "capabilities": ["run", "trace", "memory", "tools"]
  }'
```

---

### 列出所有 Agents

**端点**: `GET /agents`

**权限**: `agent:read`

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `limit` | integer | 返回结果数量，默认 20，最大 100 |
| `offset` | integer | 分页偏移量，默认 0 |
| `status` | string | 过滤状态：active, inactive, paused |
| `search` | string | 按名称搜索 |

**响应** (200 OK):
```json
{
  "data": [
    {
      "id": "default-agent",
      "name": "Default X-Agent",
      "status": "active",
      "capabilities": ["run", "trace", "memory", "tools"],
      "max_iterations": 100,
      "created_at": "2026-05-27T10:30:00Z",
      "updated_at": "2026-05-27T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**示例**:
```bash
curl http://localhost:8000/api/v1/agents?limit=10&status=active \
  -H "Authorization: Bearer $TOKEN"
```

---

### 获取 Agent 详情

**端点**: `GET /agents/{agent_id}`

**权限**: `agent:read`

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `agent_id` | string | Agent ID |

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"],
  "config": {
    "max_iterations": 100,
    "timeout_seconds": 300,
    "memory_limit_mb": 512
  },
  "stats": {
    "total_runs": 42,
    "successful_runs": 38,
    "failed_runs": 4,
    "avg_execution_time_ms": 2500
  },
  "created_at": "2026-05-27T10:30:00Z",
  "updated_at": "2026-05-27T10:30:00Z"
}
```

**错误码**:
- `404`: Agent 不存在

**示例**:
```bash
curl http://localhost:8000/api/v1/agents/agent_a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

### 更新 Agent

**端点**: `PUT /agents/{agent_id}`

**权限**: `security:manage`

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `agent_id` | string | Agent ID |

**请求体**:
```json
{
  "name": "Updated Agent Name",
  "status": "inactive",
  "capabilities": ["run", "memory"],
  "config": {
    "max_iterations": 50
  }
}
```

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Updated Agent Name",
  "status": "inactive",
  "capabilities": ["run", "memory"],
  "config": {
    "max_iterations": 50,
    "timeout_seconds": 300,
    "memory_limit_mb": 512
  },
  "updated_at": "2026-05-27T10:35:00Z"
}
```

**示例**:
```bash
curl -X PUT http://localhost:8000/api/v1/agents/agent_a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Agent Name",
    "status": "inactive"
  }'
```

---

### 删除 Agent

**端点**: `DELETE /agents/{agent_id}`

**权限**: `security:manage`

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `agent_id` | string | Agent ID |

**响应** (204 No Content)

**错误码**:
- `404`: Agent 不存在
- `409`: 无法删除默认 Agent

**示例**:
```bash
curl -X DELETE http://localhost:8000/api/v1/agents/agent_a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

### 暂停 Agent

**端点**: `POST /agents/{agent_id}/pause`

**权限**: `security:manage`

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "status": "paused",
  "paused_at": "2026-05-27T10:40:00Z"
}
```

---

### 恢复 Agent

**端点**: `POST /agents/{agent_id}/resume`

**权限**: `security:manage`

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "status": "active",
  "resumed_at": "2026-05-27T10:45:00Z"
}
```

---

## Runs API

Run 代表一次 Agent 执行的记录。

### 启动 Run

**端点**: `POST /runs/start`

**权限**: `agent:run`

**请求体**:
```json
{
  "task": "分析这个数据集并生成报告",
  "extra_context": {
    "dataset_url": "https://example.com/data.csv",
    "format": "json"
  },
  "async_run": false
}
```

**响应** (200 OK):
```json
{
  "trace_id": "trace_xyz789",
  "status": "completed",
  "resource_type": "run",
  "run": {
    "id": "run_123",
    "task": "分析这个数据集并生成报告",
    "status": "completed",
    "started_at": "2026-05-27T10:50:00Z",
    "completed_at": "2026-05-27T10:52:30Z",
    "duration_ms": 150000,
    "result": {
      "summary": "数据分析完成",
      "insights": ["趋势1", "趋势2"],
      "confidence": 0.95
    }
  },
  "timeline": [
    {
      "timestamp": "2026-05-27T10:50:00Z",
      "event": "run_started",
      "details": {}
    },
    {
      "timestamp": "2026-05-27T10:52:30Z",
      "event": "run_completed",
      "details": {"status": "success"}
    }
  ]
}
```

**错误码**:
- `400`: 任务描述无效
- `403`: 权限不足
- `429`: 速率限制

**示例**:
```bash
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "分析这个数据集并生成报告",
    "async_run": false
  }'
```

---

### 列出 Runs

**端点**: `GET /runs`

**权限**: `agent:read`

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `limit` | integer | 返回结果数量，默认 20 |
| `status` | string | 过滤状态：running, completed, failed |
| `user_id` | string | 按用户过滤 |
| `trace_id` | string | 按 trace ID 过滤 |

**响应** (200 OK):
```json
{
  "data": [
    {
      "id": "run_123",
      "trace_id": "trace_xyz789",
      "task": "分析数据集",
      "status": "completed",
      "started_at": "2026-05-27T10:50:00Z",
      "completed_at": "2026-05-27T10:52:30Z",
      "duration_ms": 150000
    }
  ],
  "total": 1
}
```

---

### 获取 Run 详情

**端点**: `GET /runs/{trace_id}`

**权限**: `agent:read`

**响应** (200 OK):
```json
{
  "id": "run_123",
  "trace_id": "trace_xyz789",
  "task": "分析数据集",
  "status": "completed",
  "started_at": "2026-05-27T10:50:00Z",
  "completed_at": "2026-05-27T10:52:30Z",
  "duration_ms": 150000,
  "result": {
    "summary": "分析完成",
    "output": "..."
  },
  "timeline": [
    {
      "timestamp": "2026-05-27T10:50:00Z",
      "event": "run_started"
    }
  ]
}
```

---

## Memory API

管理 Agent 的记忆系统。

### 查询记忆

**端点**: `GET /memory/search`

**权限**: `memory:read`

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `query` | string | 搜索查询 |
| `limit` | integer | 返回结果数量 |
| `threshold` | float | 相似度阈值 (0-1) |

**响应** (200 OK):
```json
{
  "results": [
    {
      "id": "mem_123",
      "content": "之前分析的结果...",
      "similarity": 0.92,
      "created_at": "2026-05-26T10:00:00Z",
      "tags": ["analysis", "data"]
    }
  ],
  "total": 1
}
```

---

### 添加记忆

**端点**: `POST /memory`

**权限**: `memory:write`

**请求体**:
```json
{
  "content": "重要的分析结果",
  "tags": ["analysis", "important"],
  "metadata": {
    "source": "run_123",
    "confidence": 0.95
  }
}
```

**响应** (201 Created):
```json
{
  "id": "mem_456",
  "content": "重要的分析结果",
  "tags": ["analysis", "important"],
  "created_at": "2026-05-27T10:55:00Z"
}
```

---

## Tools API

管理可用的工具。

### 列出工具

**端点**: `GET /tools`

**权限**: `tools:read`

**响应** (200 OK):
```json
{
  "data": [
    {
      "id": "tool_web_search",
      "name": "Web Search",
      "description": "搜索网络信息",
      "category": "search",
      "parameters": {
        "query": {
          "type": "string",
          "description": "搜索查询"
        }
      },
      "enabled": true
    }
  ],
  "total": 1
}
```

---

### 获取工具详情

**端点**: `GET /tools/{tool_id}`

**权限**: `tools:read`

**响应** (200 OK):
```json
{
  "id": "tool_web_search",
  "name": "Web Search",
  "description": "搜索网络信息",
  "category": "search",
  "parameters": {
    "query": {
      "type": "string",
      "description": "搜索查询",
      "required": true
    },
    "limit": {
      "type": "integer",
      "description": "返回结果数量",
      "default": 10
    }
  },
  "enabled": true,
  "usage_count": 1234,
  "last_used": "2026-05-27T10:50:00Z"
}
```

---

## Traces API

查询执行跟踪信息。

### 获取 Trace

**端点**: `GET /traces/{trace_id}`

**权限**: `agent:read`

**响应** (200 OK):
```json
{
  "id": "trace_xyz789",
  "run_id": "run_123",
  "status": "completed",
  "started_at": "2026-05-27T10:50:00Z",
  "completed_at": "2026-05-27T10:52:30Z",
  "events": [
    {
      "timestamp": "2026-05-27T10:50:00Z",
      "type": "agent_started",
      "details": {}
    },
    {
      "timestamp": "2026-05-27T10:50:05Z",
      "type": "tool_called",
      "details": {
        "tool": "web_search",
        "input": {"query": "..."}
      }
    }
  ]
}
```

---

## Audit API

查询审计日志。

### 列出审计日志

**端点**: `GET /audit/logs`

**权限**: `audit:read`

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| `limit` | integer | 返回结果数量 |
| `action` | string | 过滤操作类型 |
| `user_id` | string | 按用户过滤 |
| `start_time` | string | 开始时间 (ISO 8601) |
| `end_time` | string | 结束时间 (ISO 8601) |

**响应** (200 OK):
```json
{
  "data": [
    {
      "id": "audit_123",
      "timestamp": "2026-05-27T10:50:00Z",
      "action": "agent_created",
      "user_id": "user_123",
      "resource_type": "agent",
      "resource_id": "agent_a1b2c3d4",
      "details": {
        "name": "Data Analyzer"
      },
      "status": "success"
    }
  ],
  "total": 1
}
```

---

## 错误处理

### 错误响应格式

所有错误响应遵循以下格式：

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "请求参数无效",
    "details": {
      "field": "task",
      "reason": "任务描述不能为空"
    },
    "request_id": "req_123abc"
  }
}
```

### 常见错误码

| 状态码 | 错误码 | 描述 |
|--------|--------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 401 | UNAUTHORIZED | 未授权 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突 |
| 429 | RATE_LIMITED | 速率限制 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

---

## 速率限制

X-Agent API 实施以下速率限制：

| 端点 | 限制 | 窗口 |
|------|------|------|
| `/auth/login` | 10 请求 | 60 秒 |
| `/auth/register` | 5 请求 | 60 秒 |
| `/api/*` | 100 请求 | 60 秒 |

超过限制时，API 返回 429 状态码：

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again later."
  }
}
```

---

## 最佳实践

### 1. 错误处理
```python
try:
    response = requests.post(
        "http://localhost:8000/api/v1/runs/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"task": "..."}
    )
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    error = e.response.json()
    print(f"Error: {error['error']['message']}")
```

### 2. 重试逻辑
```python
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
```

### 3. 异步执行
```python
# 启动异步任务
response = requests.post(
    "http://localhost:8000/api/v1/runs/start",
    headers={"Authorization": f"Bearer {token}"},
    json={"task": "...", "async_run": True}
)
trace_id = response.json()["trace_id"]

# 轮询检查状态
while True:
    status = requests.get(
        f"http://localhost:8000/api/v1/runs/{trace_id}",
        headers={"Authorization": f"Bearer {token}"}
    ).json()
    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(1)
```

---

## 更新日志

### v1.0.0 (2026-05-27)
- 初始版本发布
- 支持 Agents、Runs、Memory、Tools、Traces、Audit API
- 完整的认证和授权系统
- 速率限制和错误处理
