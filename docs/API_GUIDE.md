# X-Agent API 使用指南

## 目录
1. [快速开始](#快速开始)
2. [认证](#认证)
3. [常见用例](#常见用例)
4. [错误处理](#错误处理)
5. [速率限制](#速率限制)
6. [最佳实践](#最佳实践)

## 快速开始

### 基础 URL
```
http://localhost:8000/api/v1
```

### 健康检查
```bash
curl http://localhost:8000/health
```

## 认证

X-Agent API 支持两种认证方式：

### 1. API Key 认证
在请求头中添加 `X-API-Key`：

```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/agents
```

### 2. JWT Token 认证
在请求头中添加 `Authorization: Bearer`：

```bash
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:8000/api/v1/agents
```

### 登录获取 Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password"
  }'
```

响应示例：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## 常见用例

### 用例 1: 创建并运行 Agent

```bash
# 1. 创建 Agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Analyzer",
    "capabilities": ["run", "trace", "memory", "tools"]
  }'

# 2. 启动 Agent 运行
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze the sales data for Q1 2025",
    "extra_context": {
      "data_source": "sales_db",
      "format": "json"
    },
    "async_run": false
  }'

# 3. 查看运行结果
curl http://localhost:8000/api/v1/runs \
  -H "X-API-Key: your-api-key"
```

### 用例 2: 创建并执行 Workflow

```bash
# 1. 创建 Workflow
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Pipeline",
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
        "label": "Process Data"
      }
    ],
    "edges": [
      {
        "source": "node1",
        "target": "node2"
      }
    ]
  }'

# 2. 执行 Workflow
curl -X POST http://localhost:8000/api/v1/workflows/{workflow_id}/run \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input_data": {
      "source": "database",
      "table": "sales"
    }
  }'
```

### 用例 3: 存储和检索记忆

```bash
# 1. 存储记忆
curl -X POST http://localhost:8000/api/v1/memory \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers JSON format for data exports",
    "layer": 2,
    "importance": 0.8,
    "tags": ["user_preference", "data_format"],
    "metadata": {
      "user_id": "user123",
      "context": "data_export"
    }
  }'

# 2. 搜索记忆
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user preferences",
    "top_k": 5,
    "layers": [1, 2, 3]
  }'

# 3. 导出记忆
curl http://localhost:8000/api/v1/memory/export \
  -H "X-API-Key: your-api-key"
```

### 用例 4: 工具执行和追踪

```bash
# 1. 列出可用工具
curl http://localhost:8000/api/v1/tools \
  -H "X-API-Key: your-api-key"

# 2. 获取工具执行记录
curl http://localhost:8000/api/v1/tools/executions/{execution_id} \
  -H "X-API-Key: your-api-key"

# 3. 获取工具执行关联信息
curl http://localhost:8000/api/v1/tools/executions/{execution_id}/correlation \
  -H "X-API-Key: your-api-key"
```

## 错误处理

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "detail": "Resource not found",
  "error_code": "RESOURCE_NOT_FOUND",
  "status_code": 404,
  "trace_id": "trace_123456",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

### 常见错误码

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 401 | UNAUTHORIZED | 未授权或 API Key 无效 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | RESOURCE_NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突 |
| 429 | RATE_LIMIT_EXCEEDED | 超过速率限制 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

### 错误处理示例

```python
import requests
import json

def call_api(endpoint, method="GET", data=None):
    headers = {"X-API-Key": "your-api-key"}
    url = f"http://localhost:8000/api/v1{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.HTTPError as e:
        error_data = e.response.json()
        print(f"Error: {error_data['detail']}")
        print(f"Code: {error_data['error_code']}")
        print(f"Trace ID: {error_data.get('trace_id')}")
        raise
    
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        raise

# 使用示例
try:
    result = call_api("/agents")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Failed to fetch agents: {e}")
```

## 速率限制

X-Agent API 实施以下速率限制：

| 端点 | 限制 | 时间窗口 |
|------|------|---------|
| `/auth/login` | 10 请求 | 60 秒 |
| `/auth/register` | 5 请求 | 60 秒 |
| 其他 API | 100 请求 | 60 秒 |

### 处理速率限制

当超过限制时，API 返回 429 状态码：

```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "status_code": 429
}
```

### 重试策略

```python
import time
import requests

def call_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:
            wait_time = 2 ** attempt  # 指数退避
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

## 最佳实践

### 1. 使用异步运行处理长任务

```bash
# 异步启动 Agent 运行
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Process large dataset",
    "async_run": true
  }'

# 定期检查运行状态
curl http://localhost:8000/api/v1/runs/{run_id} \
  -H "X-API-Key: your-api-key"
```

### 2. 实现请求 ID 追踪

```bash
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "X-API-Key: your-api-key" \
  -H "X-Request-Id: req_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze data"
  }'
```

### 3. 使用分页处理大量数据

```bash
# 列出 Agents，每页 20 条
curl "http://localhost:8000/api/v1/agents?limit=20&offset=0" \
  -H "X-API-Key: your-api-key"

# 获取下一页
curl "http://localhost:8000/api/v1/agents?limit=20&offset=20" \
  -H "X-API-Key: your-api-key"
```

### 4. 缓存静态数据

```python
import requests
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_tools_cached():
    """缓存工具列表，避免重复请求"""
    response = requests.get(
        "http://localhost:8000/api/v1/tools",
        headers={"X-API-Key": "your-api-key"}
    )
    return response.json()

# 使用缓存
tools = get_tools_cached()
```

### 5. 监控和日志记录

```python
import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def call_api_with_logging(endpoint, method="GET", data=None):
    headers = {"X-API-Key": "your-api-key"}
    url = f"http://localhost:8000/api/v1{endpoint}"
    
    logger.info(f"Calling {method} {endpoint}")
    
    response = requests.request(method, url, headers=headers, json=data)
    
    logger.info(f"Response: {response.status_code}")
    if response.headers.get("x-request-id"):
        logger.info(f"Request ID: {response.headers['x-request-id']}")
    
    return response.json()
```

### 6. 安全建议

- 不要在代码中硬编码 API Key，使用环境变量
- 定期轮换 API Key
- 使用 HTTPS 在生产环境
- 限制 API Key 的权限范围
- 监控异常的 API 使用模式

```python
import os

API_KEY = os.getenv("XAGENT_API_KEY")
if not API_KEY:
    raise ValueError("XAGENT_API_KEY environment variable not set")

headers = {"X-API-Key": API_KEY}
```

## 更多资源

- [API 参考文档](./API_REFERENCE.md)
- [Postman 集合](./X-Agent.postman_collection.json)
- [架构文档](./ARCHITECTURE.md)
- [快速开始指南](./QUICKSTART.md)
