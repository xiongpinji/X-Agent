# X-Agent API Reference

Complete REST API documentation for X-Agent Core.

## Quick Links

- [API 使用指南](./API_GUIDE.md) - 详细的使用指南和最佳实践
- [API 参考文档](./API_REFERENCE.md) - 完整的端点参考
- [API 错误码参考](./API_ERROR_CODES.md) - 所有错误码及解决方案
- [Postman 集合](./X-Agent.postman_collection.json) - 可导入的 Postman 集合
- [OpenAPI Schema](./openapi.json) - OpenAPI 3.0 规范

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

所有 API 请求都需要通过 API Key 或 JWT Token 进行认证：

```bash
# 使用 API Key
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/agents

# 使用 JWT Token
curl -H "Authorization: Bearer your-jwt-token" http://localhost:8000/api/v1/agents
```

## Response Format

所有响应都是 JSON 格式：

```json
{
  "data": {},
  "status": "success",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

## Error Handling

错误响应包含状态码和错误详情：

```json
{
  "detail": "Resource not found",
  "error_code": "RESOURCE_NOT_FOUND",
  "status_code": 404,
  "trace_id": "trace_123456",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

## API 端点概览

### Agents API
- `POST /agents` - 创建 Agent
- `GET /agents` - 列出所有 Agents
- `GET /agents/{agent_id}` - 获取 Agent 详情
- `PUT /agents/{agent_id}` - 更新 Agent
- `DELETE /agents/{agent_id}` - 删除 Agent
- `POST /agents/{agent_id}/pause` - 暂停 Agent

### Workflows API
- `POST /workflows` - 创建 Workflow
- `GET /workflows` - 列出所有 Workflows
- `GET /workflows/status` - 获取 Workflow 状态
- `GET /workflows/templates` - 获取 Workflow 模板

### Runs API
- `POST /runs/start` - 启动 Agent 运行
- `GET /runs` - 列出所有运行

### Memory API
- `POST /memory` - 存储记忆
- `POST /memory/search` - 搜索记忆
- `GET /memory/export` - 导出记忆
- `POST /memory/import` - 导入记忆
- `POST /memory/consolidate` - 合并记忆

### Tools API
- `GET /tools` - 列出可用工具
- `GET /tools/executions/{execution_id}` - 获取工具执行记录
- `GET /tools/executions/{execution_id}/correlation` - 获取工具执行关联信息

### Traces API
- `GET /traces` - 列出追踪
- `GET /traces/{trace_id}` - 获取追踪详情

### Audit API
- `GET /audit` - 列出审计日志

### Auth API
- `POST /auth/login` - 用户登录
- `POST /auth/register` - 用户注册

## 快速示例

### 创建 Workflow

```http
GET /workflows?limit=10&offset=0
```

**Response**: `200 OK`
```json
{
  "workflows": [...],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

### Update Workflow

```http
PUT /workflows/{workflow_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "steps": [...]
}
```

**Response**: `200 OK`

### Delete Workflow

```http
DELETE /workflows/{workflow_id}
```

**Response**: `204 No Content`

### Execute Workflow

```http
POST /workflows/{workflow_id}/execute
Content-Type: application/json

{
  "input": {
    "data": "sample data"
  },
  "context": {}
}
```

**Response**: `202 Accepted`
```json
{
  "run_id": "run_456",
  "workflow_id": "wf_123",
  "status": "running",
  "started_at": "2025-04-20T10:30:00Z"
}
```

### Get Workflow Run

```http
GET /workflows/{workflow_id}/runs/{run_id}
```

**Response**: `200 OK`
```json
{
  "id": "run_456",
  "workflow_id": "wf_123",
  "status": "completed",
  "result": {...},
  "started_at": "2025-04-20T10:30:00Z",
  "completed_at": "2025-04-20T10:35:00Z"
}
```

## Agents API

### Create Agent

```http
POST /agents
Content-Type: application/json

{
  "name": "Data Analyst",
  "description": "Analyzes data and generates insights",
  "model": "gpt-4",
  "tools": ["web_search", "data_analysis"]
}
```

**Response**: `201 Created`

### Get Agent

```http
GET /agents/{agent_id}
```

**Response**: `200 OK`

### Run Agent

```http
POST /agents/{agent_id}/run
Content-Type: application/json

{
  "task": "Analyze sales data for Q1 2025",
  "context": {}
}
```

**Response**: `202 Accepted`

## Memory API

### Store Memory

```http
POST /memory/store
Content-Type: application/json

{
  "content": "Important fact about the project",
  "metadata": {
    "type": "fact",
    "source": "documentation"
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "mem_789",
  "content": "Important fact about the project",
  "embedding": [...],
  "created_at": "2025-04-20T10:30:00Z"
}
```

### Search Memory

```http
GET /memory/search?query=project+facts&limit=10
```

**Response**: `200 OK`
```json
{
  "results": [
    {
      "id": "mem_789",
      "content": "Important fact about the project",
      "similarity": 0.95,
      "metadata": {...}
    }
  ],
  "total": 1
}
```

### Get Memory Item

```http
GET /memory/{memory_id}
```

**Response**: `200 OK`

### Delete Memory

```http
DELETE /memory/{memory_id}
```

**Response**: `204 No Content`

## Tools API

### Register Tool

```http
POST /tools
Content-Type: application/json

{
  "name": "web_search",
  "description": "Search the web for information",
  "parameters": {
    "query": {
      "type": "string",
      "description": "Search query"
    }
  }
}
```

**Response**: `201 Created`

### List Tools

```http
GET /tools
```

**Response**: `200 OK`
```json
{
  "tools": [
    {
      "id": "tool_001",
      "name": "web_search",
      "description": "Search the web for information"
    }
  ]
}
```

### Execute Tool

```http
POST /tools/{tool_id}/execute
Content-Type: application/json

{
  "parameters": {
    "query": "X-Agent framework"
  }
}
```

**Response**: `200 OK`
```json
{
  "result": {...},
  "execution_time_ms": 1234
}
```

## Approvals API

### List Pending Approvals

```http
GET /approvals?status=pending
```

**Response**: `200 OK`
```json
{
  "approvals": [
    {
      "id": "appr_001",
      "workflow_run_id": "run_456",
      "action": "Execute external API call",
      "status": "pending",
      "created_at": "2025-04-20T10:30:00Z"
    }
  ]
}
```

### Approve Request

```http
POST /approvals/{approval_id}/approve
Content-Type: application/json

{
  "comment": "Approved for execution"
}
```

**Response**: `200 OK`

### Reject Request

```http
POST /approvals/{approval_id}/reject
Content-Type: application/json

{
  "reason": "Requires additional review"
}
```

**Response**: `200 OK`

## Metrics API

### Get Metrics

```http
GET /metrics?start_time=2025-04-20T00:00:00Z&end_time=2025-04-20T23:59:59Z
```

**Response**: `200 OK`
```json
{
  "total_workflows": 42,
  "successful_runs": 38,
  "failed_runs": 2,
  "average_execution_time_ms": 5234,
  "total_tokens_used": 125000
}
```

## Health Check

### System Health

```http
GET /health
```

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "qdrant": "healthy",
    "cache": "healthy"
  }
}
```

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created |
| 202 | Accepted - Request accepted for processing |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Access denied |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Resource conflict |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server error |
| 503 | Service Unavailable - Service temporarily unavailable |

## Rate Limiting

API requests are rate limited:

- **Default**: 1000 requests per hour per API key
- **Headers**: 
  - `X-RateLimit-Limit`: Request limit
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Reset time (Unix timestamp)

## Pagination

List endpoints support pagination:

```http
GET /workflows?limit=20&offset=40
```

Parameters:
- `limit`: Number of items (default: 10, max: 100)
- `offset`: Number of items to skip (default: 0)

## Filtering

List endpoints support filtering:

```http
GET /workflows?status=completed&created_after=2025-04-01
```

## Sorting

List endpoints support sorting:

```http
GET /workflows?sort=created_at&order=desc
```

## Interactive API Documentation

Access interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Examples

### Complete Workflow Example

```bash
# 1. Create workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analysis Workflow",
    "steps": [...]
  }'

# 2. Execute workflow
curl -X POST http://localhost:8000/api/workflows/wf_123/execute \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"input": {}}'

# 3. Check status
curl http://localhost:8000/api/workflows/wf_123/runs/run_456 \
  -H "X-API-Key: your-key"
```

---

For more information, see [Architecture Guide](../../concepts/architecture/ARCHITECTURE.md) and [Examples](../sdk/EXAMPLES.md).
