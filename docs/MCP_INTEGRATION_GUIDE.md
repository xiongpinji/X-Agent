# MCP (Model Context Protocol) 集成指南

## 概述

X-Agent MCP集成提供了一个完整的工具执行框架，支持文件操作、Web搜索和浏览器控制。该系统包括：

- **MCP Client**: 支持重试、连接池、缓存和批量调用
- **工具层**: 文件、搜索、浏览器工具，均支持权限控制和审计日志
- **适配器**: 将MCP工具与X-Agent系统集成
- **配置管理**: 灵活的配置系统
- **API端点**: RESTful接口用于工具执行和管理

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    X-Agent API                          │
├─────────────────────────────────────────────────────────┤
│                  MCP API Endpoints                      │
│  (/api/v1/mcp/tools/execute, /health, /audit-logs)    │
├─────────────────────────────────────────────────────────┤
│                   MCP Adapter                           │
│  (工具注册、执行、权限检查、审计)                        │
├─────────────────────────────────────────────────────────┤
│  File Tool  │  Search Tool  │  Browser Tool  │ MCP Client
│  (权限+审计) │  (权限+审计)  │  (权限+审计)   │ (重试+缓存)
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 初始化MCP系统

```python
from backend.app.api.mcp import initialize_mcp_system

# 在应用启动时调用
initialize_mcp_system(
    mcp_server_url="http://localhost:8001",
    file_base_path="./data"
)
```

### 2. 执行工具

```python
# 通过API执行工具
POST /api/v1/mcp/tools/execute
{
    "tool_name": "file_read",
    "arguments": {
        "path": "example.txt"
    }
}

# 响应
{
    "tool_name": "file_read",
    "success": true,
    "result": "file content",
    "timestamp": "2026-05-28T10:00:00"
}
```

### 3. 批量执行

```python
# 并发执行多个工具
POST /api/v1/mcp/tools/batch
[
    {
        "tool_name": "search_web",
        "arguments": {"query": "query1", "max_results": 5}
    },
    {
        "tool_name": "search_web",
        "arguments": {"query": "query2", "max_results": 5}
    }
]
```

## 工具参考

### 文件工具 (file_*)

#### file_read
读取文件内容

**参数:**
- `path` (string): 文件路径
- `encoding` (string, optional): 文件编码，默认 "utf-8"

**返回:** 文件内容

**权限:** `read`

#### file_write
写入文件

**参数:**
- `path` (string): 文件路径
- `content` (string): 要写入的内容
- `encoding` (string, optional): 文件编码，默认 "utf-8"

**返回:** `{"success": true, "path": "...", "size": 123}`

**权限:** `write`

#### file_list
列出目录中的文件

**参数:**
- `path` (string, optional): 目录路径，默认 "."

**返回:** `{"path": "...", "items": [...], "count": 5}`

**权限:** `list`

#### file_delete
删除文件

**参数:**
- `path` (string): 文件路径

**返回:** `{"success": true, "path": "..."}`

**权限:** `delete`

#### file_exists
检查文件是否存在

**参数:**
- `path` (string): 文件路径

**返回:** `{"exists": true, "path": "..."}`

**权限:** `read`

### 搜索工具 (search_*)

#### search_web
Web搜索

**参数:**
- `query` (string): 搜索查询
- `max_results` (integer, optional): 最大结果数，默认 10
- `language` (string, optional): 搜索语言，默认 "en"

**返回:** `{"query": "...", "results": [...], "count": 5}`

**权限:** `web_search`

#### search_news
新闻搜索

**参数:**
- `query` (string): 搜索查询
- `max_results` (integer, optional): 最大结果数，默认 10
- `language` (string, optional): 搜索语言，默认 "en"

**返回:** `{"query": "...", "results": [...], "count": 5}`

**权限:** `news_search`

### 浏览器工具 (browser_*)

#### browser_navigate
导航到URL

**参数:**
- `url` (string): 要导航的URL

**返回:** `{"success": true, "url": "...", "status": "navigated"}`

**权限:** `navigate`

#### browser_click
点击元素

**参数:**
- `selector` (string): CSS选择器

**返回:** `{"success": true, "selector": "...", "status": "clicked"}`

**权限:** `click`

#### browser_type
输入文本

**参数:**
- `selector` (string): CSS选择器
- `text` (string): 要输入的文本

**返回:** `{"success": true, "selector": "...", "text_length": 10}`

**权限:** `type`

#### browser_screenshot
截图

**参数:**
- `filename` (string, optional): 保存文件名

**返回:** `{"success": true, "filename": "screenshot.png"}`

**权限:** `screenshot`

#### browser_scroll
滚动页面

**参数:**
- `direction` (string, optional): 滚动方向 (up/down/left/right)，默认 "down"
- `amount` (integer, optional): 滚动量，默认 3

**返回:** `{"success": true, "direction": "down", "amount": 3}`

**权限:** `scroll`

#### browser_wait
等待

**参数:**
- `duration` (float): 等待时间（秒）

**返回:** `{"success": true, "duration": 2.0}`

**权限:** `wait`

#### browser_get_content
获取页面内容

**参数:** 无

**返回:** `{"success": true, "content": "..."}`

**权限:** `get_page_content`

## 权限管理

### 获取权限

```
GET /api/v1/mcp/permissions/{tool_category}

# 响应
{
    "read": true,
    "write": true,
    "delete": true,
    "list": true
}
```

### 更新权限

```
PUT /api/v1/mcp/permissions/{tool_category}
{
    "tool_category": "file",
    "permissions": {
        "read": true,
        "write": false,
        "delete": false,
        "list": true
    }
}
```

**工具类别:**
- `file`: 文件操作
- `search`: Web搜索
- `browser`: 浏览器控制

## 审计日志

### 获取审计日志

```
GET /api/v1/mcp/audit-logs?tool_category=file

# 响应
{
    "tool_category": "file",
    "entries": [
        {
            "timestamp": "2026-05-28T10:00:00",
            "operation": "read",
            "path": "example.txt",
            "success": true,
            "details": {"size": 100, "encoding": "utf-8"}
        }
    ],
    "count": 1
}
```

## 健康检查

```
GET /api/v1/mcp/health

# 响应
{
    "status": "healthy",
    "timestamp": "2026-05-28T10:00:00",
    "components": {
        "mcp_client": "healthy",
        "file_tool": "ready",
        "search_tool": "ready",
        "browser_tool": "ready"
    }
}
```

## 配置

### 配置文件格式

```json
{
    "mcp_client": {
        "server_url": "http://localhost:8001",
        "timeout": 30.0,
        "max_retries": 3,
        "retry_backoff_factor": 2.0,
        "max_connections": 10,
        "cache_ttl_seconds": 300,
        "enable_cache": true
    },
    "file_tool": {
        "base_path": "./data",
        "enable_audit": true,
        "max_audit_entries": 1000,
        "permissions": {
            "read": true,
            "write": true,
            "delete": true,
            "list": true
        }
    },
    "search_tool": {
        "api_key": "your-api-key",
        "search_engine_id": "your-engine-id",
        "enable_audit": true,
        "max_audit_entries": 1000,
        "permissions": {
            "web_search": true,
            "news_search": true
        }
    },
    "browser_tool": {
        "enable_audit": true,
        "max_audit_entries": 1000,
        "permissions": {
            "navigate": true,
            "click": true,
            "type": true,
            "screenshot": true,
            "scroll": true,
            "wait": true,
            "get_page_content": true,
            "execute_script": false
        }
    }
}
```

## 性能特性

### 连接池
- 最大并发连接数: 10（可配置）
- 自动连接管理
- 防止连接泄漏

### 结果缓存
- TTL: 300秒（可配置）
- 基于工具名称和参数的缓存键
- 自动过期清理

### 重试机制
- 最大重试次数: 3（可配置）
- 指数退避: 2.0倍（可配置）
- 自动故障恢复

### 批量执行
- 并发执行多个工具
- 自动错误处理
- 保持执行顺序

## 错误处理

### 错误代码

| 代码 | 含义 |
|------|------|
| TOOL_NOT_FOUND | 工具不存在 |
| PERMISSION_DENIED | 权限被拒绝 |
| EXECUTION_ERROR | 执行错误 |
| TIMEOUT | 请求超时 |
| INVALID_ARGUMENTS | 无效参数 |

### 错误响应

```json
{
    "tool_name": "file_read",
    "success": false,
    "error": "Permission denied",
    "error_code": "PERMISSION_DENIED",
    "timestamp": "2026-05-28T10:00:00"
}
```

## 最佳实践

1. **权限管理**
   - 根据需要限制权限
   - 定期审查审计日志
   - 禁用不需要的操作

2. **性能优化**
   - 使用批量执行处理多个工具
   - 启用结果缓存以减少重复查询
   - 监控连接池使用情况

3. **错误处理**
   - 实现重试逻辑
   - 记录所有错误
   - 提供有意义的错误消息

4. **安全性**
   - 验证所有输入
   - 使用HTTPS进行远程连接
   - 定期更新依赖项

## 测试

### 运行单元测试

```bash
pytest tests/test_mcp_components.py -v
```

### 运行集成测试

```bash
pytest tests/test_mcp_integration.py -v
```

### 运行性能测试

```bash
pytest tests/test_mcp_integration.py::TestMCPPerformance -v
```

## 故障排除

### 连接超时
- 检查MCP服务器是否运行
- 增加超时时间
- 检查网络连接

### 权限被拒绝
- 检查工具权限配置
- 验证用户权限范围
- 查看审计日志

### 缓存问题
- 清除缓存
- 检查TTL设置
- 验证缓存键生成

## 相关资源

- [MCP协议规范](https://spec.modelcontextprotocol.io/)
- [X-Agent文档](../README.md)
- [API参考](./api_reference.md)
