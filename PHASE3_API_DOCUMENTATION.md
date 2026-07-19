# Claude Code能力对齐 - 第三阶段 API文档

## 目录

1. [MCP API](#mcp-api)
2. [工件API](#工件api)
3. [搜索API](#搜索api)
4. [认证和授权](#认证和授权)
5. [错误处理](#错误处理)
6. [速率限制](#速率限制)

---

## MCP API

### 基础URL

```
http://localhost:8000/api/v1/mcp
```

### 端点

#### 1. 处理MCP请求

**POST** `/request`

处理MCP协议请求。

**请求体**:
```json
{
  "type": "request",
  "id": "unique-id",
  "method": "tools/list",
  "params": {}
}
```

**响应**:
```json
{
  "type": "result",
  "id": "unique-id",
  "result": {
    "tools": [
      {
        "name": "file_read",
        "description": "Read file content",
        "input_schema": {"path": "string"},
        "tags": ["file"]
      }
    ]
  }
}
```

**错误响应**:
```json
{
  "type": "error",
  "id": "unique-id",
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Error description"
  }
}
```

#### 2. 列出可用工具

**GET** `/tools`

获取所有可用的MCP工具列表。

**查询参数**: 无

**响应**:
```json
{
  "tools": [
    {
      "name": "file_read",
      "description": "Read file content",
      "input_schema": {"path": "string", "encoding": "string"},
      "output_schema": {"content": "string"},
      "tags": ["file", "read"]
    },
    {
      "name": "search_web",
      "description": "Search the web",
      "input_schema": {"query": "string", "num_results": "integer"},
      "tags": ["search"]
    }
  ],
  "count": 2
}
```

#### 3. 获取工具定义

**GET** `/tools/{tool_name}`

获取特定工具的定义。

**路径参数**:
- `tool_name` (string, required): 工具名称

**响应**:
```json
{
  "name": "file_read",
  "description": "Read file content",
  "input_schema": {
    "path": "string",
    "encoding": "string"
  },
  "output_schema": {
    "content": "string"
  },
  "tags": ["file", "read"]
}
```

#### 4. 直接调用工具

**POST** `/tools/{tool_name}/call`

直接调用指定的工具。

**路径参数**:
- `tool_name` (string, required): 工具名称

**请求体**:
```json
{
  "path": "example.txt",
  "encoding": "utf-8"
}
```

**响应**:
```json
{
  "output": "File content here..."
}
```

#### 5. 获取MCP服务器状态

**GET** `/status`

获取MCP服务器的运行状态。

**响应**:
```json
{
  "status": "running",
  "host": "localhost",
  "port": 8001,
  "tools_count": 5,
  "tools": ["file_read", "file_write", "search_web", "extract_content", "database_query"]
}
```

---

## 工件API

### 基础URL

```
http://localhost:8000/api/v1/artifacts
```

### 端点

#### 1. 创建工件

**POST** `/`

创建新的工件。

**请求体**:
```json
{
  "name": "My Dashboard",
  "type": "html",
  "content": "<h1>Welcome</h1>",
  "tags": ["dashboard", "important"],
  "description": "My personal dashboard",
  "metadata": {
    "version": "1.0"
  }
}
```

**响应** (201):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "created"
}
```

#### 2. 列出工件

**GET** `/`

列出所有工件，支持过滤和分页。

**查询参数**:
- `artifact_type` (string, optional): 工件类型 (html, chart, dashboard, table)
- `tags` (string, optional): 标签，逗号分隔
- `limit` (integer, optional, default: 100): 返回结果数量上限
- `offset` (integer, optional, default: 0): 分页偏移

**示例**:
```
GET /artifacts?artifact_type=html&tags=dashboard&limit=10&offset=0
```

**响应**:
```json
{
  "artifacts": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "My Dashboard",
      "type": "html",
      "content": "<h1>Welcome</h1>",
      "tags": ["dashboard"],
      "description": "My personal dashboard",
      "created_at": "2026-05-26T10:00:00Z",
      "updated_at": "2026-05-26T10:00:00Z"
    }
  ],
  "count": 1,
  "limit": 10,
  "offset": 0
}
```

#### 3. 获取工件

**GET** `/{artifact_id}`

获取特定工件的详细信息。

**路径参数**:
- `artifact_id` (string, required): 工件ID

**响应**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Dashboard",
  "type": "html",
  "content": "<h1>Welcome</h1>",
  "tags": ["dashboard"],
  "description": "My personal dashboard",
  "metadata": {},
  "created_at": "2026-05-26T10:00:00Z",
  "updated_at": "2026-05-26T10:00:00Z"
}
```

#### 4. 更新工件

**PUT** `/{artifact_id}`

更新工件的信息。

**路径参数**:
- `artifact_id` (string, required): 工件ID

**请求体**:
```json
{
  "name": "Updated Dashboard",
  "content": "<h1>Updated</h1>",
  "tags": ["dashboard", "updated"],
  "description": "Updated description"
}
```

**响应**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Updated Dashboard",
  "type": "html",
  "content": "<h1>Updated</h1>",
  "tags": ["dashboard", "updated"],
  "description": "Updated description",
  "updated_at": "2026-05-26T11:00:00Z"
}
```

#### 5. 删除工件

**DELETE** `/{artifact_id}`

删除指定的工件。

**路径参数**:
- `artifact_id` (string, required): 工件ID

**响应**:
```json
{
  "status": "deleted",
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### 6. 渲染工件

**GET** `/{artifact_id}/render`

将工件渲染为HTML。

**路径参数**:
- `artifact_id` (string, required): 工件ID

**响应**:
```json
{
  "html": "<html>...</html>",
  "artifact_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### 7. 搜索工件

**GET** `/search`

搜索工件。

**查询参数**:
- `query` (string, required): 搜索查询
- `limit` (integer, optional, default: 50): 返回结果数量上限

**示例**:
```
GET /artifacts/search?query=dashboard&limit=20
```

**响应**:
```json
{
  "query": "dashboard",
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "My Dashboard",
      "type": "html",
      "description": "My personal dashboard"
    }
  ],
  "count": 1
}
```

#### 8. 获取统计信息

**GET** `/stats`

获取工件存储的统计信息。

**响应**:
```json
{
  "total_artifacts": 42,
  "by_type": {
    "html": 15,
    "chart": 12,
    "table": 10,
    "dashboard": 5
  },
  "storage_path": "./data/artifacts"
}
```

---

## 搜索API

### 基础URL

```
http://localhost:8000/api/v1/search
```

### 端点

#### 1. 执行搜索

**GET** `/`

执行搜索查询。

**查询参数**:
- `query` (string, required): 搜索查询
- `num_results` (integer, optional, default: 10): 返回结果数量
- `search_type` (string, optional, default: "web"): 搜索类型 (web, news, images)
- `use_cache` (boolean, optional, default: true): 是否使用缓存

**示例**:
```
GET /search?query=python+tutorial&num_results=10&search_type=web
```

**响应**:
```json
{
  "query": "python tutorial",
  "search_type": "web",
  "results": [
    {
      "title": "Python Tutorial - W3Schools",
      "url": "https://www.w3schools.com/python/",
      "snippet": "Well organized and easy to understand Web building tutorials..."
    }
  ],
  "count": 1,
  "from_cache": false
}
```

#### 2. 提取网页内容

**GET** `/extract`

从URL提取网页内容。

**查询参数**:
- `url` (string, required): 要提取的URL

**示例**:
```
GET /search/extract?url=https://example.com
```

**响应**:
```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "content": "This domain is for use in examples...",
  "metadata": {
    "description": "Example Domain",
    "og_title": "Example Domain"
  },
  "status": "success"
}
```

#### 3. 获取搜索历史

**GET** `/history`

获取搜索历史。

**查询参数**:
- `limit` (integer, optional, default: 50): 返回结果数量上限

**响应**:
```json
{
  "history": [
    {
      "query": "python tutorial",
      "timestamp": "2026-05-26T10:00:00Z",
      "results_count": 10
    }
  ],
  "count": 1,
  "limit": 50
}
```

#### 4. 获取缓存统计

**GET** `/cache/stats`

获取搜索缓存的统计信息。

**响应**:
```json
{
  "total_entries": 42,
  "ttl": 3600,
  "cache_size_bytes": 102400
}
```

#### 5. 清空缓存

**POST** `/cache/clear`

清空所有搜索缓存。

**响应**:
```json
{
  "status": "cleared"
}
```

#### 6. 获取搜索建议

**GET** `/suggestions`

获取搜索建议。

**查询参数**:
- `query` (string, required): 部分搜索查询
- `limit` (integer, optional, default: 10): 返回建议数量上限

**示例**:
```
GET /search/suggestions?query=pyt&limit=5
```

**响应**:
```json
{
  "query": "pyt",
  "suggestions": [
    "python",
    "python tutorial",
    "python documentation",
    "python download",
    "python ide"
  ],
  "count": 5
}
```

---

## 认证和授权

### 认证

所有API请求都需要提供有效的认证令牌。

**请求头**:
```
Authorization: Bearer <token>
```

### 授权范围

不同的API端点需要不同的权限范围：

| 端点 | 所需范围 |
|------|---------|
| MCP - 列出工具 | `mcp:read` |
| MCP - 调用工具 | `mcp:execute` |
| 工件 - 读取 | `artifacts:read` |
| 工件 - 写入 | `artifacts:write` |
| 搜索 - 读取 | `search:read` |
| 搜索 - 写入 | `search:write` |

### 权限检查

```python
from backend.app.dependencies import enforce_scope

@router.get("/artifacts")
async def list_artifacts(principal: PrincipalDependency):
    enforce_scope(principal, "artifacts:read")
    # ... 实现
```

---

## 错误处理

### 错误响应格式

所有错误响应都遵循以下格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      "field": "Additional error details"
    }
  },
  "trace_id": "unique-trace-id"
}
```

### 常见错误代码

| 代码 | HTTP状态 | 描述 |
|------|---------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `UNAUTHORIZED` | 401 | 未授权 |
| `FORBIDDEN` | 403 | 禁止访问 |
| `RUN_NOT_FOUND` | 404 | 资源不存在 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `TOOL_NOT_FOUND` | 404 | 工具不存在 |
| `TOOL_ERROR` | 400 | 工具执行失败 |

### 错误示例

**404 - 工件不存在**:
```json
{
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "Artifact not found"
  },
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**400 - 无效请求**:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid artifact type",
    "details": {
      "type": "Must be one of: html, chart, dashboard, table"
    }
  },
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 速率限制

### 限制规则

- 每个用户每分钟最多1000个请求
- 每个IP地址每小时最多10000个请求

### 响应头

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1622505600
```

### 超出限制

当超出速率限制时，返回429状态码：

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "retry_after": 60
  }
}
```

---

## 示例代码

### Python

```python
import httpx

async def create_artifact():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/artifacts",
            json={
                "name": "My Artifact",
                "type": "html",
                "content": "<h1>Hello</h1>",
                "tags": ["test"]
            },
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

### JavaScript

```javascript
async function createArtifact() {
    const response = await fetch('http://localhost:8000/api/v1/artifacts', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer <token>'
        },
        body: JSON.stringify({
            name: 'My Artifact',
            type: 'html',
            content: '<h1>Hello</h1>',
            tags: ['test']
        })
    });
    return response.json();
}
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/artifacts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "My Artifact",
    "type": "html",
    "content": "<h1>Hello</h1>",
    "tags": ["test"]
  }'
```

---

**API版本**: 1.0  
**最后更新**: 2026-05-26
