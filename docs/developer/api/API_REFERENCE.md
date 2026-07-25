# X-Agent API 参考文档

## 目录
- [Agents API](#agents-api)
- [Workflows API](#workflows-api)
- [Runs API](#runs-api)
- [Memory API](#memory-api)
- [Tools API](#tools-api)
- [MCP API](#mcp-api)
- [Auth API](#auth-api)
- [Traces API](#traces-api)
- [Audit API](#audit-api)

---

## Agents API

Agent 是 X-Agent 系统中的执行单元，负责任务执行和决策。

### 创建 Agent

**端点**: `POST /api/v1/agents`

**权限**: `security:manage`

**请求体**:
```json
{
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"]
}
```

**响应** (201 Created):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"],
  "created_at": "2025-05-26T10:30:00Z",
  "updated_at": "2025-05-26T10:30:00Z"
}
```

**错误码**:
- `400`: 请求参数无效
- `403`: 权限不足

---

### 列出所有 Agents

**端点**: `GET /api/v1/agents`

**权限**: `agent:run`

**查询参数**: 无

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
      "created_at": "2025-05-26T10:30:00Z",
      "updated_at": "2025-05-26T10:30:00Z"
    },
    {
      "id": "agent_a1b2c3d4",
      "name": "Data Analyzer",
      "status": "active",
      "capabilities": ["run", "trace", "memory", "tools"],
      "created_at": "2025-05-26T10:30:00Z",
      "updated_at": "2025-05-26T10:30:00Z"
    }
  ]
}
```

---

### 获取 Agent 详情

**端点**: `GET /api/v1/agents/{agent_id}`

**权限**: `agent:run`

**路径参数**:
- `agent_id` (string, required): Agent ID

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Data Analyzer",
  "status": "active",
  "capabilities": ["run", "trace", "memory", "tools"],
  "max_iterations": 100,
  "created_at": "2025-05-26T10:30:00Z",
  "updated_at": "2025-05-26T10:30:00Z"
}
```

**错误码**:
- `404`: Agent 不存在

---

### 更新 Agent

**端点**: `PUT /api/v1/agents/{agent_id}`

**权限**: `security:manage`

**路径参数**:
- `agent_id` (string, required): Agent ID

**请求体**:
```json
{
  "name": "Updated Agent Name",
  "status": "inactive",
  "capabilities": ["run", "memory"]
}
```

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "name": "Updated Agent Name",
  "status": "inactive",
  "capabilities": ["run", "memory"],
  "updated_at": "2025-05-26T10:35:00Z"
}
```

---

### 删除 Agent

**端点**: `DELETE /api/v1/agents/{agent_id}`

**权限**: `security:manage`

**路径参数**:
- `agent_id` (string, required): Agent ID

**响应** (200 OK):
```json
{
  "deleted": true
}
```

**注意**: 默认 Agent (`default-agent`) 无法删除

---

### 暂停 Agent

**端点**: `POST /api/v1/agents/{agent_id}/pause`

**权限**: `security:manage`

**路径参数**:
- `agent_id` (string, required): Agent ID

**响应** (200 OK):
```json
{
  "id": "agent_a1b2c3d4",
  "status": "paused",
  "updated_at": "2025-05-26T10:40:00Z"
}
```

---

## Workflows API

Workflow 是一系列任务的有向无环图 (DAG)，用于自动化复杂流程。

### 创建 Workflow

**端点**: `POST /api/v1/workflows`

**权限**: `workflow:create`

**请求体**:
```json
{
  "name": "Data Processing Pipeline",
  "description": "ETL workflow for data processing",
  "nodes": [
    {
      "id": "node1",
      "type": "start",
      "label": "Start"
    },
    {
      "id": "node2",
      "type": "task",
      "label": "Extract Data",
      "config": {
        "source": "database",
        "query": "SELECT * FROM sales"
      }
    },
    {
      "id": "node3",
      "type": "task",
      "label": "Transform Data"
    },
    {
      "id": "node4",
      "type": "end",
      "label": "End"
    }
  ],
  "edges": [
    {"source": "node1", "target": "node2"},
    {"source": "node2", "target": "node3"},
    {"source": "node3", "target": "node4"}
  ]
}
```

**响应** (201 Created):
```json
{
  "id": "wf_xyz789",
  "workflow_id": "wf_xyz789",
  "name": "Data Processing Pipeline",
  "description": "ETL workflow for data processing",
  "nodes": [...],
  "edges": [...],
  "resource_type": "workflow",
  "snapshot": {
    "workflow_id": "wf_xyz789",
    "node_count": 4,
    "edge_count": 3
  },
  "created_at": "2025-05-26T10:30:00Z",
  "updated_at": "2025-05-26T10:30:00Z"
}
```

---

### 列出所有 Workflows

**端点**: `GET /api/v1/workflows`

**权限**: `workflow:run`

**响应** (200 OK):
```json
[
  {
    "id": "wf_xyz789",
    "workflow_id": "wf_xyz789",
    "name": "Data Processing Pipeline",
    "description": "ETL workflow for data processing",
    "resource_type": "workflow",
    "snapshot": {
      "workflow_id": "wf_xyz789",
      "node_count": 4,
      "edge_count": 3
    }
  }
]
```

---

### 获取 Workflow 状态

**端点**: `GET /api/v1/workflows/status`

**权限**: `workflow:run`

**响应** (200 OK):
```json
[
  {
    "workflow_id": "wf_xyz789",
    "workflow_name": "Data Processing Pipeline",
    "status": "completed",
    "latest_run_id": "run_abc123",
    "latest_run_status": "completed",
    "run_count": 5,
    "updated_at": "2025-05-26T10:30:00Z",
    "snapshot": {
      "workflow_id": "wf_xyz789",
      "run_count": 5
    }
  }
]
```

---

### 获取 Workflow 模板

**端点**: `GET /api/v1/workflows/templates`

**权限**: `workflow:run`

**响应** (200 OK):
```json
[
  {
    "id": "template-wf_xyz789",
    "workflow_id": "wf_xyz789",
    "name": "Data Processing Pipeline",
    "description": "ETL workflow for data processing",
    "nodes": 4,
    "edges": 3,
    "resource_type": "workflow_template",
    "snapshot": {
      "workflow_id": "wf_xyz789",
      "template_id": "template-wf_xyz789"
    }
  }
]
```

---

## Runs API

Run 是 Agent 或 Workflow 的一次执行实例。

### 启动 Agent 运行

**端点**: `POST /api/v1/runs/start`

**权限**: `agent:run`

**请求体**:
```json
{
  "task": "Analyze the sales data for Q1 2025",
  "extra_context": {
    "data_source": "sales_db",
    "format": "json",
    "filters": {
      "region": "North America"
    }
  },
  "async_run": false
}
```

**响应** (200 OK):
```json
{
  "run_id": "run_abc123",
  "trace_id": "trace_xyz789",
  "status": "completed",
  "task": "Analyze the sales data for Q1 2025",
  "result": {
    "summary": "Q1 2025 sales analysis complete",
    "total_revenue": 1500000,
    "growth_rate": 0.15
  },
  "started_at": "2025-05-26T10:30:00Z",
  "completed_at": "2025-05-26T10:35:00Z",
  "duration_ms": 300000
}
```

**错误码**:
- `400`: 任务参数无效
- `403`: 权限不足

---

### 列出所有运行

**端点**: `GET /api/v1/runs`

**权限**: `agent:read`

**查询参数**:
- `limit` (integer, default=20, max=100): 返回结果数量
- `status` (string, optional): 筛选状态 (pending, running, completed, failed)
- `user_id` (string, optional): 筛选用户
- `trace_id` (string, optional): 筛选追踪 ID

**响应** (200 OK):
```json
[
  {
    "run_id": "run_abc123",
    "trace_id": "trace_xyz789",
    "status": "completed",
    "task": "Analyze the sales data for Q1 2025",
    "user_id": "user_123",
    "tenant_id": "tenant_456",
    "started_at": "2025-05-26T10:30:00Z",
    "completed_at": "2025-05-26T10:35:00Z"
  }
]
```

---

## Memory API

Memory 系统用于存储和检索 Agent 的知识和经验。

### 存储记忆

**端点**: `POST /api/v1/memory`

**权限**: `memory:write`

**请求体**:
```json
{
  "content": "User prefers JSON format for data exports",
  "layer": 2,
  "importance": 0.8,
  "tags": ["user_preference", "data_format"],
  "metadata": {
    "user_id": "user123",
    "context": "data_export",
    "source": "user_feedback"
  },
  "session_id": "session_abc123",
  "scope": "user"
}
```

**响应** (200 OK):
```json
{
  "id": "mem_xyz789"
}
```

**参数说明**:
- `content` (string, 1-20000 chars): 记忆内容
- `layer` (integer, 1-10, default=3): 记忆层级
- `importance` (float, 0.0-1.0, default=0.5): 重要性评分
- `tags` (array): 标签列表
- `metadata` (object): 元数据
- `scope` (enum): 作用域 (user, session, global)

---

### 搜索记忆

**端点**: `POST /api/v1/memory/search`

**权限**: `memory:read`

**请求体**:
```json
{
  "query": "user preferences for data export",
  "layers": [1, 2, 3],
  "top_k": 5,
  "include_scores": true,
  "scope": "user"
}
```

**响应** (200 OK):
```json
{
  "items": [
    {
      "id": "mem_xyz789",
      "content": "User prefers JSON format for data exports",
      "layer": 2,
      "importance": 0.8,
      "tags": ["user_preference", "data_format"],
      "created_at": "2025-05-26T10:30:00Z"
    }
  ],
  "hits": [
    {
      "memory_id": "mem_xyz789",
      "score": 0.95,
      "relevance": "high"
    }
  ]
}
```

---

### 导出记忆

**端点**: `GET /api/v1/memory/export`

**权限**: `memory:read`

**响应** (200 OK):
```json
{
  "bundle": {
    "version": "1.0",
    "exported_at": "2025-05-26T10:30:00Z",
    "memories": [
      {
        "id": "mem_xyz789",
        "content": "User prefers JSON format for data exports",
        "layer": 2,
        "importance": 0.8,
        "tags": ["user_preference", "data_format"]
      }
    ],
    "sessions": [
      {
        "session_id": "session_abc123",
        "created_at": "2025-05-26T10:00:00Z",
        "memory_count": 5
      }
    ]
  }
}
```

---

### 导入记忆

**端点**: `POST /api/v1/memory/import`

**权限**: `memory:write`

**请求体**: 与导出格式相同

**响应** (200 OK):
```json
{
  "memories": 10,
  "sessions": 2
}
```

---

### 合并记忆

**端点**: `POST /api/v1/memory/consolidate`

**权限**: `memory:write`

**请求体**:
```json
{
  "source_layers": [1, 2],
  "target_layer": 4,
  "max_items": 20,
  "min_importance": 0.5
}
```

**响应** (200 OK):
```json
{
  "consolidated_count": 15,
  "target_layer": 4,
  "timestamp": "2025-05-26T10:30:00Z"
}
```

---

## Tools API

Tools 是 Agent 可以调用的外部功能或服务。

### 列出可用工具

**端点**: `GET /api/v1/tools`

**权限**: `tools:read`

**响应** (200 OK):
```json
[
  {
    "name": "web_search",
    "description": "Search the web for information",
    "parameters": {
      "query": {
        "type": "string",
        "description": "Search query"
      },
      "max_results": {
        "type": "integer",
        "description": "Maximum number of results",
        "default": 10
      }
    },
    "returns": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "url": {"type": "string"},
          "snippet": {"type": "string"}
        }
      }
    }
  },
  {
    "name": "file_read",
    "description": "Read file contents",
    "parameters": {
      "path": {
        "type": "string",
        "description": "File path"
      }
    }
  }
]
```

---

### 获取工具执行记录

**端点**: `GET /api/v1/tools/executions/{execution_id}`

**权限**: `agent:run`

**路径参数**:
- `execution_id` (string, required): 执行 ID

**响应** (200 OK):
```json
{
  "execution_id": "exec_abc123",
  "tool_name": "web_search",
  "status": "completed",
  "input": {
    "query": "X-Agent framework",
    "max_results": 5
  },
  "output": [
    {
      "title": "X-Agent: A Framework for Building Autonomous Agents",
      "url": "https://example.com/xagent",
      "snippet": "X-Agent is a comprehensive framework..."
    }
  ],
  "created_at": "2025-05-26T10:30:00Z",
  "updated_at": "2025-05-26T10:30:05Z",
  "duration_ms": 5000
}
```

---

### 获取工具执行关联信息

**端点**: `GET /api/v1/tools/executions/{execution_id}/correlation`

**权限**: `agent:run`

**响应** (200 OK):
```json
{
  "trace_id": "trace_xyz789",
  "resource_type": "tool_execution",
  "resource_id": "exec_abc123",
  "tool_name": "web_search",
  "status": "completed",
  "trace_summary": {
    "trace_id": "trace_xyz789",
    "event_count": 1,
    "started_at": "2025-05-26T10:30:00Z",
    "ended_at": "2025-05-26T10:30:05Z",
    "last_event": "tool.execution.completed",
    "task": "web_search"
  },
  "snapshot": {
    "resource_type": "tool_execution",
    "resource_id": "exec_abc123",
    "trace_id": "trace_xyz789",
    "tool_name": "web_search",
    "success": true
  }
}
```

---

## MCP API

MCP（Model Context Protocol）API 用于管理和执行 MCP 工具。详细文档请参考 [MCP API 参考](../plugins/MCP_API_REFERENCE.md)。

### 获取 MCP 系统健康状态

**端点**: `GET /api/v1/mcp/health`

**权限**: `mcp:read`

**描述**: 检查 MCP 系统和所有服务器的健康状态

**响应** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2025-05-29T10:30:00Z",
  "servers": {
    "filesystem": {
      "status": "healthy",
      "stats": {
        "tools_count": 5,
        "last_check": "2025-05-29T10:30:00Z"
      }
    },
    "database": {
      "status": "healthy",
      "stats": {
        "tools_count": 8,
        "last_check": "2025-05-29T10:30:00Z"
      }
    }
  }
}
```

---

### 获取 MCP 系统统计信息

**端点**: `GET /api/v1/mcp/stats`

**权限**: `mcp:read`

**描述**: 获取 MCP 系统的详细统计信息

**响应** (200 OK):
```json
{
  "initialized": true,
  "servers": {
    "total_servers": 2,
    "servers": {
      "filesystem": {
        "status": "healthy",
        "tools_count": 5,
        "active_connections": 2,
        "avg_response_time_ms": 45
      },
      "database": {
        "status": "healthy",
        "tools_count": 8,
        "active_connections": 1,
        "avg_response_time_ms": 52
      }
    }
  },
  "tools": {
    "total_mcp_tools": 13,
    "by_category": {
      "file_system": 5,
      "database": 8
    }
  }
}
```

---

### 列出 MCP 工具

**端点**: `GET /api/v1/tools?tags=mcp`

**权限**: `tool:read`

**查询参数**:
- `tags` (string): 按标签过滤，使用 `mcp` 获取所有 MCP 工具
- `server` (string, optional): 按服务器过滤
- `risk_level` (string, optional): 按风险级别过滤

**响应** (200 OK):
```json
{
  "data": [
    {
      "id": "mcp_filesystem_read_file",
      "name": "read_file",
      "display_name": "Read File",
      "description": "Read contents of a file",
      "category": "file_system",
      "risk_level": "low",
      "server": "filesystem",
      "tags": ["mcp", "mcp:filesystem", "file_system"]
    },
    {
      "id": "mcp_database_query",
      "name": "query",
      "display_name": "Query Database",
      "description": "Execute database query",
      "category": "database",
      "risk_level": "medium",
      "server": "database",
      "tags": ["mcp", "mcp:database", "database"]
    }
  ],
  "pagination": {
    "total": 13,
    "limit": 100,
    "offset": 0
  }
}
```

---

### 执行 MCP 工具

**端点**: `POST /api/v1/tools/{tool_id}/execute`

**权限**: `tool:execute`

**请求体**:
```json
{
  "arguments": {
    "path": "/tmp/test.txt"
  }
}
```

**响应** (200 OK):
```json
{
  "tool_id": "mcp_filesystem_read_file",
  "tool_name": "read_file",
  "success": true,
  "result": {
    "content": "File content here",
    "size": 18
  },
  "execution_time_ms": 45,
  "cached": false,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

### 批量执行 MCP 工具

**端点**: `POST /api/v1/tools/batch/execute`

**权限**: `tool:execute`

**请求体**:
```json
{
  "requests": [
    {
      "tool_id": "mcp_filesystem_read_file",
      "arguments": {"path": "/tmp/file1.txt"}
    },
    {
      "tool_id": "mcp_filesystem_read_file",
      "arguments": {"path": "/tmp/file2.txt"}
    }
  ]
}
```

**响应** (200 OK):
```json
{
  "results": [
    {
      "tool_id": "mcp_filesystem_read_file",
      "success": true,
      "result": {"content": "File 1 content", "size": 14},
      "execution_time_ms": 45
    },
    {
      "tool_id": "mcp_filesystem_read_file",
      "success": true,
      "result": {"content": "File 2 content", "size": 14},
      "execution_time_ms": 42
    }
  ],
  "total_time_ms": 87
}
```

---

### 列出 MCP 服务器

**端点**: `GET /api/v1/mcp/servers`

**权限**: `mcp:read`

**响应** (200 OK):
```json
{
  "data": [
    {
      "name": "filesystem",
      "url": "http://localhost:8001",
      "enabled": true,
      "status": "healthy",
      "tools_count": 5,
      "active_connections": 2,
      "last_check": "2025-05-29T10:30:00Z"
    },
    {
      "name": "database",
      "url": "http://localhost:8002",
      "enabled": true,
      "status": "healthy",
      "tools_count": 8,
      "active_connections": 1,
      "last_check": "2025-05-29T10:30:00Z"
    }
  ]
}
```

---

### 刷新 MCP 服务器工具

**端点**: `POST /api/v1/mcp/servers/{server_name}/refresh`

**权限**: `mcp:manage`

**描述**: 重新发现并注册指定服务器的工具

**响应** (200 OK):
```json
{
  "server_name": "filesystem",
  "tools_discovered": 5,
  "tools_registered": 5,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

### 获取 MCP 缓存统计

**端点**: `GET /api/v1/mcp/cache/stats`

**权限**: `mcp:read`

**响应** (200 OK):
```json
{
  "enabled": true,
  "total_entries": 150,
  "total_size_bytes": 524288,
  "ttl_seconds": 300,
  "hit_rate": 0.65,
  "total_hits": 1200,
  "total_misses": 650
}
```

---

### 清除 MCP 缓存

**端点**: `POST /api/v1/mcp/cache/clear`

**权限**: `mcp:manage`

**查询参数**:
- `server` (string, optional): 只清除特定服务器的缓存

**响应** (200 OK):
```json
{
  "cleared_entries": 150,
  "freed_bytes": 524288,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

## Auth API

认证和授权管理。

### 登录

**端点**: `POST /api/v1/auth/login`

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
    "scopes": ["agent:run", "workflow:run", "memory:read"]
  }
}
```

---

### 注册

**端点**: `POST /api/v1/auth/register`

**请求体**:
```json
{
  "username": "newuser@example.com",
  "password": "secure_password",
  "email": "newuser@example.com"
}
```

**响应** (201 Created):
```json
{
  "id": "user_456",
  "username": "newuser@example.com",
  "email": "newuser@example.com",
  "created_at": "2025-05-26T10:30:00Z"
}
```

---

## Traces API

追踪系统用于记录和分析 Agent 的执行过程。

### 列出追踪

**端点**: `GET /api/v1/traces`

**权限**: `agent:read`

**查询参数**:
- `limit` (integer, default=20): 返回结果数量
- `run_id` (string, optional): 筛选运行 ID
- `status` (string, optional): 筛选状态

**响应** (200 OK):
```json
[
  {
    "trace_id": "trace_xyz789",
    "run_id": "run_abc123",
    "status": "completed",
    "event_count": 15,
    "started_at": "2025-05-26T10:30:00Z",
    "ended_at": "2025-05-26T10:35:00Z"
  }
]
```

---

### 获取追踪详情

**端点**: `GET /api/v1/traces/{trace_id}`

**权限**: `agent:read`

**响应** (200 OK):
```json
{
  "trace_id": "trace_xyz789",
  "run_id": "run_abc123",
  "status": "completed",
  "events": [
    {
      "event_id": "evt_1",
      "type": "agent.start",
      "timestamp": "2025-05-26T10:30:00Z",
      "data": {
        "task": "Analyze data"
      }
    },
    {
      "event_id": "evt_2",
      "type": "tool.call",
      "timestamp": "2025-05-26T10:30:01Z",
      "data": {
        "tool": "web_search",
        "input": {"query": "data analysis"}
      }
    }
  ]
}
```

---

## Audit API

审计日志记录所有系统操作。

### 列出审计日志

**端点**: `GET /api/v1/audit`

**权限**: `audit:read`

**查询参数**:
- `limit` (integer, default=20): 返回结果数量
- `action` (string, optional): 筛选操作类型
- `resource_type` (string, optional): 筛选资源类型
- `actor_id` (string, optional): 筛选操作者

**响应** (200 OK):
```json
[
  {
    "id": "audit_123",
    "action": "workflow.create",
    "resource_type": "workflow",
    "resource_id": "wf_xyz789",
    "actor_id": "user_123",
    "tenant_id": "tenant_456",
    "details": {
      "name": "Data Processing Pipeline"
    },
    "timestamp": "2025-05-26T10:30:00Z"
  }
]
```

---

## 通用响应格式

### 成功响应

```json
{
  "data": {},
  "status": "success",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

### 错误响应

```json
{
  "detail": "Resource not found",
  "error_code": "RESOURCE_NOT_FOUND",
  "status_code": 404,
  "trace_id": "trace_123456",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

---

## 状态码参考

| 状态码 | 说明 |
|--------|------|
| 200 | OK - 请求成功 |
| 201 | Created - 资源已创建 |
| 400 | Bad Request - 请求参数无效 |
| 401 | Unauthorized - 未授权 |
| 403 | Forbidden - 权限不足 |
| 404 | Not Found - 资源不存在 |
| 409 | Conflict - 资源冲突 |
| 429 | Too Many Requests - 超过速率限制 |
| 500 | Internal Server Error - 服务器错误 |

