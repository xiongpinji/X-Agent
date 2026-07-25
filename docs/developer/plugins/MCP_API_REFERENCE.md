# MCP API 参考

本文档详细介绍 X-Agent 中 MCP（Model Context Protocol）相关的 API 端点、参数和响应格式。

## 目录

- [概述](#概述)
- [认证](#认证)
- [健康检查 API](#健康检查-api)
- [统计信息 API](#统计信息-api)
- [工具管理 API](#工具管理-api)
- [工具执行 API](#工具执行-api)
- [服务器管理 API](#服务器管理-api)
- [缓存管理 API](#缓存管理-api)
- [错误处理](#错误处理)
- [使用示例](#使用示例)

---

## 概述

MCP API 提供以下功能：

- **健康检查**：检查 MCP 系统和服务器状态
- **统计信息**：获取 MCP 系统的详细统计数据
- **工具管理**：列出、查询和管理 MCP 工具
- **工具执行**：执行 MCP 工具并获取结果
- **服务器管理**：管理 MCP 服务器连接
- **缓存管理**：管理工具结果缓存

### API 基础 URL

```
http://localhost:8000/api/v1
```

### API 版本

当前版本：`v1`

---

## 认证

所有 API 请求都需要包含认证信息。

### 认证方式

支持以下认证方式：

1. **Bearer Token**（推荐）

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/mcp/health
```

2. **API Key**

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
  http://localhost:8000/api/v1/mcp/health
```

3. **Basic Auth**

```bash
curl -u username:password \
  http://localhost:8000/api/v1/mcp/health
```

### 获取认证令牌

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user",
    "password": "password"
  }'
```

响应：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 健康检查 API

### 获取 MCP 系统健康状态

**端点**: `GET /mcp/health`

**权限**: `mcp:read`

**描述**: 检查 MCP 系统和所有服务器的健康状态

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/health
```

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
        "last_check": "2025-05-29T10:30:00Z",
        "response_time_ms": 45
      }
    },
    "database": {
      "status": "healthy",
      "stats": {
        "tools_count": 8,
        "last_check": "2025-05-29T10:30:00Z",
        "response_time_ms": 52
      }
    },
    "browser": {
      "status": "degraded",
      "stats": {
        "tools_count": 12,
        "last_check": "2025-05-29T10:29:55Z",
        "response_time_ms": 2500
      }
    }
  }
}
```

**状态值**:

| 状态 | 含义 |
|------|------|
| `healthy` | 所有服务器正常 |
| `degraded` | 部分服务器异常 |
| `unhealthy` | 所有服务器异常 |
| `not_initialized` | MCP 系统未初始化 |

**错误响应** (503 Service Unavailable):

```json
{
  "status": "unhealthy",
  "error": "MCP system is not initialized",
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

## 统计信息 API

### 获取 MCP 系统统计信息

**端点**: `GET /mcp/stats`

**权限**: `mcp:read`

**描述**: 获取 MCP 系统的详细统计信息

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/stats
```

**响应** (200 OK):

```json
{
  "initialized": true,
  "timestamp": "2025-05-29T10:30:00Z",
  "servers": {
    "total_servers": 3,
    "servers": {
      "filesystem": {
        "status": "healthy",
        "url": "http://localhost:8001",
        "tools_count": 5,
        "active_connections": 2,
        "total_requests": 1250,
        "failed_requests": 5,
        "cache_size": 15,
        "cache_hits": 450,
        "cache_misses": 800,
        "avg_response_time_ms": 45
      },
      "database": {
        "status": "healthy",
        "url": "http://localhost:8002",
        "tools_count": 8,
        "active_connections": 1,
        "total_requests": 890,
        "failed_requests": 2,
        "cache_size": 8,
        "cache_hits": 320,
        "cache_misses": 570,
        "avg_response_time_ms": 52
      },
      "browser": {
        "status": "healthy",
        "url": "http://localhost:8005",
        "tools_count": 12,
        "active_connections": 0,
        "total_requests": 45,
        "failed_requests": 1,
        "cache_size": 0,
        "cache_hits": 0,
        "cache_misses": 45,
        "avg_response_time_ms": 2500
      }
    }
  },
  "tools": {
    "total_mcp_tools": 25,
    "by_category": {
      "file_system": 5,
      "database": 8,
      "browser": 12
    },
    "by_risk_level": {
      "low": 15,
      "medium": 8,
      "high": 2
    }
  },
  "performance": {
    "total_requests": 2185,
    "failed_requests": 8,
    "success_rate": 99.63,
    "avg_response_time_ms": 52,
    "p95_response_time_ms": 150,
    "p99_response_time_ms": 500
  }
}
```

---

## 工具管理 API

### 列出所有 MCP 工具

**端点**: `GET /tools`

**权限**: `tool:read`

**查询参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `tags` | string | 否 | 按标签过滤（逗号分隔） |
| `category` | string | 否 | 按类别过滤 |
| `risk_level` | string | 否 | 按风险级别过滤 |
| `server` | string | 否 | 按服务器过滤 |
| `limit` | integer | 否 | 返回结果数量限制（默认 100） |
| `offset` | integer | 否 | 分页偏移（默认 0） |

**请求示例**:

```bash
# 列出所有 MCP 工具
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/tools?tags=mcp"

# 按服务器过滤
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/tools?tags=mcp&server=filesystem"

# 按风险级别过滤
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/tools?tags=mcp&risk_level=low"
```

**响应** (200 OK):

```json
{
  "data": [
    {
      "id": "mcp_filesystem_read_file",
      "name": "read_file",
      "display_name": "Read File",
      "description": "Read contents of a file",
      "version": "1.0.0",
      "category": "file_system",
      "risk_level": "low",
      "status": "active",
      "server": "filesystem",
      "tags": ["mcp", "mcp:filesystem", "file_system", "read"],
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "File path"
          }
        },
        "required": ["path"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "content": {
            "type": "string",
            "description": "File content"
          }
        }
      }
    },
    {
      "id": "mcp_filesystem_write_file",
      "name": "write_file",
      "display_name": "Write File",
      "description": "Write contents to a file",
      "version": "1.0.0",
      "category": "file_system",
      "risk_level": "medium",
      "status": "active",
      "server": "filesystem",
      "tags": ["mcp", "mcp:filesystem", "file_system", "write"],
      "input_schema": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "File path"
          },
          "content": {
            "type": "string",
            "description": "File content"
          }
        },
        "required": ["path", "content"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "success": {
            "type": "boolean"
          }
        }
      }
    }
  ],
  "pagination": {
    "total": 25,
    "limit": 100,
    "offset": 0
  }
}
```

### 获取工具详情

**端点**: `GET /tools/{tool_id}`

**权限**: `tool:read`

**路径参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `tool_id` | string | 是 | 工具 ID |

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/tools/mcp_filesystem_read_file
```

**响应** (200 OK):

```json
{
  "id": "mcp_filesystem_read_file",
  "name": "read_file",
  "display_name": "Read File",
  "description": "Read contents of a file",
  "version": "1.0.0",
  "category": "file_system",
  "risk_level": "low",
  "status": "active",
  "server": "filesystem",
  "tags": ["mcp", "mcp:filesystem", "file_system", "read"],
  "input_schema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "File path to read"
      },
      "encoding": {
        "type": "string",
        "description": "File encoding (default: utf-8)",
        "default": "utf-8"
      }
    },
    "required": ["path"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "content": {
        "type": "string",
        "description": "File content"
      },
      "size": {
        "type": "integer",
        "description": "File size in bytes"
      }
    }
  },
  "metadata": {
    "mcp_server": "filesystem",
    "mcp_tool_name": "read_file",
    "source": "mcp_discovery"
  }
}
```

---

## 工具执行 API

### 执行 MCP 工具

**端点**: `POST /tools/{tool_id}/execute`

**权限**: `tool:execute`

**路径参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `tool_id` | string | 是 | 工具 ID |

**请求体**:

```json
{
  "arguments": {
    "path": "/tmp/test.txt"
  },
  "timeout": 30,
  "use_cache": true
}
```

**请求示例**:

```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "path": "/tmp/test.txt"
    }
  }' \
  http://localhost:8000/api/v1/tools/mcp_filesystem_read_file/execute
```

**响应** (200 OK):

```json
{
  "tool_id": "mcp_filesystem_read_file",
  "tool_name": "read_file",
  "success": true,
  "result": {
    "content": "Hello, World!",
    "size": 13
  },
  "execution_time_ms": 45,
  "cached": false,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

**错误响应** (400 Bad Request):

```json
{
  "tool_id": "mcp_filesystem_read_file",
  "tool_name": "read_file",
  "success": false,
  "error": "File not found",
  "error_code": "FILE_NOT_FOUND",
  "execution_time_ms": 12,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

**错误响应** (403 Forbidden):

```json
{
  "tool_id": "mcp_filesystem_write_file",
  "tool_name": "write_file",
  "success": false,
  "error": "Permission denied: high-risk tool requires approval",
  "error_code": "PERMISSION_DENIED",
  "execution_time_ms": 5,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

### 批量执行工具

**端点**: `POST /tools/batch/execute`

**权限**: `tool:execute`

**请求体**:

```json
{
  "requests": [
    {
      "tool_id": "mcp_filesystem_read_file",
      "arguments": {
        "path": "/tmp/file1.txt"
      }
    },
    {
      "tool_id": "mcp_filesystem_read_file",
      "arguments": {
        "path": "/tmp/file2.txt"
      }
    }
  ]
}
```

**请求示例**:

```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }' \
  http://localhost:8000/api/v1/tools/batch/execute
```

**响应** (200 OK):

```json
{
  "results": [
    {
      "tool_id": "mcp_filesystem_read_file",
      "success": true,
      "result": {
        "content": "File 1 content",
        "size": 14
      },
      "execution_time_ms": 45
    },
    {
      "tool_id": "mcp_filesystem_read_file",
      "success": true,
      "result": {
        "content": "File 2 content",
        "size": 14
      },
      "execution_time_ms": 42
    }
  ],
  "total_time_ms": 87
}
```

---

## 服务器管理 API

### 列出所有 MCP 服务器

**端点**: `GET /mcp/servers`

**权限**: `mcp:read`

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/servers
```

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

### 获取服务器详情

**端点**: `GET /mcp/servers/{server_name}`

**权限**: `mcp:read`

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/servers/filesystem
```

**响应** (200 OK):

```json
{
  "name": "filesystem",
  "url": "http://localhost:8001",
  "enabled": true,
  "status": "healthy",
  "tools_count": 5,
  "active_connections": 2,
  "total_requests": 1250,
  "failed_requests": 5,
  "avg_response_time_ms": 45,
  "last_check": "2025-05-29T10:30:00Z",
  "tools": [
    {
      "id": "mcp_filesystem_read_file",
      "name": "read_file",
      "description": "Read contents of a file"
    },
    {
      "id": "mcp_filesystem_write_file",
      "name": "write_file",
      "description": "Write contents to a file"
    }
  ]
}
```

### 刷新服务器工具

**端点**: `POST /mcp/servers/{server_name}/refresh`

**权限**: `mcp:manage`

**描述**: 重新发现并注册指定服务器的工具

**请求示例**:

```bash
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/servers/filesystem/refresh
```

**响应** (200 OK):

```json
{
  "server_name": "filesystem",
  "tools_discovered": 5,
  "tools_registered": 5,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

### 启用/禁用服务器

**端点**: `PATCH /mcp/servers/{server_name}`

**权限**: `mcp:manage`

**请求体**:

```json
{
  "enabled": false
}
```

**请求示例**:

```bash
curl -X PATCH \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  http://localhost:8000/api/v1/mcp/servers/filesystem
```

**响应** (200 OK):

```json
{
  "name": "filesystem",
  "enabled": false,
  "status": "disabled",
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

## 缓存管理 API

### 获取缓存统计

**端点**: `GET /mcp/cache/stats`

**权限**: `mcp:read`

**请求示例**:

```bash
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/cache/stats
```

**响应** (200 OK):

```json
{
  "enabled": true,
  "total_entries": 150,
  "total_size_bytes": 524288,
  "ttl_seconds": 300,
  "hit_rate": 0.65,
  "total_hits": 1200,
  "total_misses": 650,
  "by_server": {
    "filesystem": {
      "entries": 50,
      "size_bytes": 102400,
      "hit_rate": 0.70
    },
    "database": {
      "entries": 100,
      "size_bytes": 421888,
      "hit_rate": 0.62
    }
  }
}
```

### 清除缓存

**端点**: `POST /mcp/cache/clear`

**权限**: `mcp:manage`

**查询参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `server` | string | 否 | 只清除特定服务器的缓存 |
| `tool` | string | 否 | 只清除特定工具的缓存 |

**请求示例**:

```bash
# 清除所有缓存
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/cache/clear

# 清除特定服务器的缓存
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/mcp/cache/clear?server=filesystem"
```

**响应** (200 OK):

```json
{
  "cleared_entries": 150,
  "freed_bytes": 524288,
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

## 错误处理

### 错误响应格式

所有错误响应都遵循以下格式：

```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  },
  "timestamp": "2025-05-29T10:30:00Z"
}
```

### 常见错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| `INVALID_REQUEST` | 400 | 请求参数无效 |
| `UNAUTHORIZED` | 401 | 未授权 |
| `FORBIDDEN` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `TOOL_NOT_FOUND` | 404 | 工具不存在 |
| `SERVER_NOT_FOUND` | 404 | 服务器不存在 |
| `TIMEOUT` | 408 | 请求超时 |
| `PERMISSION_DENIED` | 403 | 权限被拒绝 |
| `TOOL_EXECUTION_FAILED` | 500 | 工具执行失败 |
| `SERVER_ERROR` | 500 | 服务器错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

### 错误响应示例

**400 Bad Request**:

```json
{
  "error": "Invalid request parameters",
  "error_code": "INVALID_REQUEST",
  "details": {
    "path": "Required parameter 'path' is missing"
  },
  "timestamp": "2025-05-29T10:30:00Z"
}
```

**404 Not Found**:

```json
{
  "error": "Tool not found",
  "error_code": "TOOL_NOT_FOUND",
  "details": {
    "tool_id": "mcp_filesystem_unknown_tool"
  },
  "timestamp": "2025-05-29T10:30:00Z"
}
```

**503 Service Unavailable**:

```json
{
  "error": "MCP service is not available",
  "error_code": "SERVICE_UNAVAILABLE",
  "details": {
    "reason": "All MCP servers are offline"
  },
  "timestamp": "2025-05-29T10:30:00Z"
}
```

---

## 使用示例

### 示例 1：读取文件

```bash
# 1. 获取工具详情
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/tools/mcp_filesystem_read_file

# 2. 执行工具
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "path": "/tmp/test.txt"
    }
  }' \
  http://localhost:8000/api/v1/tools/mcp_filesystem_read_file/execute
```

### 示例 2：查询数据库

```bash
# 1. 列出数据库工具
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/v1/tools?server=database"

# 2. 执行查询
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "arguments": {
      "query": "SELECT * FROM users LIMIT 10"
    }
  }' \
  http://localhost:8000/api/v1/tools/mcp_database_query/execute
```

### 示例 3：批量操作

```bash
# 批量读取多个文件
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "tool_id": "mcp_filesystem_read_file",
        "arguments": {"path": "/tmp/file1.txt"}
      },
      {
        "tool_id": "mcp_filesystem_read_file",
        "arguments": {"path": "/tmp/file2.txt"}
      },
      {
        "tool_id": "mcp_filesystem_read_file",
        "arguments": {"path": "/tmp/file3.txt"}
      }
    ]
  }' \
  http://localhost:8000/api/v1/tools/batch/execute
```

### 示例 4：监控系统

```bash
# 1. 检查健康状态
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/health

# 2. 获取统计信息
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/stats

# 3. 查看缓存统计
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/mcp/cache/stats
```

### 示例 5：Python 客户端

```python
import requests
import json

class MCPClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_health(self):
        """获取健康状态"""
        response = requests.get(
            f"{self.base_url}/mcp/health",
            headers=self.headers
        )
        return response.json()
    
    def list_tools(self, tags: str = "mcp"):
        """列出工具"""
        response = requests.get(
            f"{self.base_url}/tools",
            params={"tags": tags},
            headers=self.headers
        )
        return response.json()
    
    def execute_tool(self, tool_id: str, arguments: dict):
        """执行工具"""
        response = requests.post(
            f"{self.base_url}/tools/{tool_id}/execute",
            json={"arguments": arguments},
            headers=self.headers
        )
        return response.json()

# 使用示例
client = MCPClient("http://localhost:8000/api/v1", "YOUR_TOKEN")

# 检查健康状态
health = client.get_health()
print(f"Status: {health['status']}")

# 列出工具
tools = client.list_tools()
print(f"Total tools: {len(tools['data'])}")

# 执行工具
result = client.execute_tool(
    "mcp_filesystem_read_file",
    {"path": "/tmp/test.txt"}
)
print(f"Result: {result['result']}")
```

---

## 相关文档

- [MCP 配置指南](./MCP_CONFIGURATION_GUIDE.md)
- [MCP 故障排除指南](./MCP_TROUBLESHOOTING.md)
- [X-Agent API 参考](../api/API_REFERENCE.md)
