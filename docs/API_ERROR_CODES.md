# API 错误码参考

**版本**: 1.0  
**更新时间**: 2026-05-27  
**文档状态**: Published

---

## 概述

本文档列出了X-Agent API的所有错误码及其含义、HTTP状态码、错误消息和解决方案。每个错误码都包含详细的说明和建议的处理方式。

## 错误码格式

X-Agent API 使用以下格式返回错误：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": "Additional context or debugging information",
    "trace_id": "trace_123456789",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 400
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `code` | 应用级错误码，用于程序化处理 |
| `message` | 人类可读的错误描述 |
| `details` | 额外的上下文信息，帮助调试 |
| `trace_id` | 请求追踪ID，用于日志查询 |
| `timestamp` | 错误发生的时间戳 |
| `status_code` | HTTP状态码 |

---

## 错误码分类

### 认证错误 (401 Unauthorized)

认证错误表示请求缺少有效的认证凭证。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `AUTH_001` | 401 | 缺少认证令牌 | 在请求头中添加 `Authorization: Bearer <token>` 或 `X-API-Key: <key>` |
| `AUTH_002` | 401 | 令牌无效或过期 | 重新登录获取新令牌，或刷新令牌 |
| `AUTH_003` | 401 | 令牌格式错误 | 检查令牌格式，应为 `Bearer <token>` 或 `<api-key>` |
| `AUTH_004` | 401 | API密钥无效 | 验证API密钥是否正确，检查是否已过期 |
| `AUTH_005` | 401 | 会话已过期 | 重新登录以创建新会话 |

**示例错误响应**：
```json
{
  "error": {
    "code": "AUTH_001",
    "message": "Missing authentication token",
    "details": "The Authorization header is required for this endpoint",
    "trace_id": "trace_abc123",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 401
}
```

---

### 授权错误 (403 Forbidden)

授权错误表示认证成功但用户没有权限访问该资源。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `AUTHZ_001` | 403 | 权限不足 | 联系管理员获取所需权限 |
| `AUTHZ_002` | 403 | 资源访问被拒绝 | 检查资源所有权和租户隔离 |
| `AUTHZ_003` | 403 | 操作不被允许 | 检查用户角色和权限策略 |
| `AUTHZ_004` | 403 | 租户隔离违规 | 确保只访问自己租户的资源 |
| `AUTHZ_005` | 403 | 需要高级权限 | 升级用户权限级别 |

**示例错误响应**：
```json
{
  "error": {
    "code": "AUTHZ_001",
    "message": "Insufficient permissions",
    "details": "User requires 'admin' role to perform this action",
    "trace_id": "trace_def456",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 403
}
```

---

### 验证错误 (400 Bad Request)

验证错误表示请求参数无效或不符合要求。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `VAL_001` | 400 | 请求参数缺失 | 检查必需参数是否都已提供 |
| `VAL_002` | 400 | 参数格式错误 | 检查参数类型和格式（如JSON格式） |
| `VAL_003` | 400 | 参数值超出范围 | 检查参数约束（如最大长度、数值范围） |
| `VAL_004` | 400 | 参数类型不匹配 | 确保参数类型正确（字符串、数字、布尔值等） |
| `VAL_005` | 400 | 无效的枚举值 | 使用允许的枚举值之一 |
| `VAL_006` | 400 | 请求体格式错误 | 检查JSON格式是否正确 |
| `VAL_007` | 400 | 字段验证失败 | 检查字段值是否符合验证规则 |

**示例错误响应**：
```json
{
  "error": {
    "code": "VAL_001",
    "message": "Missing required parameter",
    "details": "Parameter 'workflow_id' is required but not provided",
    "trace_id": "trace_ghi789",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 400
}
```

---

### 资源错误 (404 Not Found)

资源错误表示请求的资源不存在。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `RES_001` | 404 | 资源不存在 | 检查资源ID是否正确 |
| `RES_002` | 404 | 端点不存在 | 检查API路径是否正确 |
| `RES_003` | 404 | Agent不存在 | 验证Agent ID是否有效 |
| `RES_004` | 404 | Workflow不存在 | 验证Workflow ID是否有效 |
| `RES_005` | 404 | 记忆项不存在 | 检查记忆ID是否正确 |
| `RES_006` | 404 | 运行记录不存在 | 验证运行ID是否有效 |

**示例错误响应**：
```json
{
  "error": {
    "code": "RES_001",
    "message": "Resource not found",
    "details": "Agent with ID 'agent_xyz' does not exist",
    "trace_id": "trace_jkl012",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 404
}
```

---

### 冲突错误 (409 Conflict)

冲突错误表示请求与当前资源状态冲突。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `CONF_001` | 409 | 资源已存在 | 使用不同的名称或ID |
| `CONF_002` | 409 | 资源状态冲突 | 检查资源当前状态，可能需要先完成其他操作 |
| `CONF_003` | 409 | 并发修改冲突 | 重新获取资源并重试操作 |
| `CONF_004` | 409 | 版本冲突 | 更新到最新版本后重试 |
| `CONF_005` | 409 | 工作流已运行 | 等待当前运行完成或取消后重试 |

**示例错误响应**：
```json
{
  "error": {
    "code": "CONF_001",
    "message": "Resource already exists",
    "details": "An agent with name 'DataAnalyzer' already exists in this tenant",
    "trace_id": "trace_mno345",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 409
}
```

---

### 速率限制错误 (429 Too Many Requests)

速率限制错误表示请求超过了允许的速率。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `RATE_001` | 429 | 请求过于频繁 | 减少请求频率，等待速率限制重置 |
| `RATE_002` | 429 | API配额已用尽 | 升级订阅计划或等待配额重置 |
| `RATE_003` | 429 | 并发请求过多 | 减少并发请求数量 |

**响应头**：
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1653657600
Retry-After: 60
```

**示例错误响应**：
```json
{
  "error": {
    "code": "RATE_001",
    "message": "Rate limit exceeded",
    "details": "You have exceeded the rate limit of 1000 requests per hour",
    "trace_id": "trace_pqr678",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 429
}
```

---

### 服务器错误 (500 Internal Server Error)

服务器错误表示服务器内部发生了错误。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `SRV_001` | 500 | 内部服务器错误 | 联系技术支持，提供trace_id |
| `SRV_002` | 500 | 数据库连接失败 | 检查数据库状态，稍后重试 |
| `SRV_003` | 500 | 外部服务不可用 | 检查外部服务状态，稍后重试 |
| `SRV_004` | 500 | 配置错误 | 检查服务器配置 |
| `SRV_005` | 500 | 资源耗尽 | 等待资源释放或升级服务器 |

**示例错误响应**：
```json
{
  "error": {
    "code": "SRV_001",
    "message": "Internal server error",
    "details": "An unexpected error occurred while processing your request",
    "trace_id": "trace_stu901",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 500
}
```

---

### 服务不可用错误 (503 Service Unavailable)

服务不可用错误表示服务暂时无法使用。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `UNAVAIL_001` | 503 | 服务维护中 | 稍后重试 |
| `UNAVAIL_002` | 503 | 服务过载 | 等待一段时间后重试 |
| `UNAVAIL_003` | 503 | 依赖服务不可用 | 检查依赖服务状态 |

**示例错误响应**：
```json
{
  "error": {
    "code": "UNAVAIL_001",
    "message": "Service unavailable",
    "details": "The service is currently under maintenance. Please try again later.",
    "trace_id": "trace_vwx234",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 503
}
```

---

## 业务逻辑错误 (400/422)

业务逻辑错误表示请求在语法上有效但在业务逻辑上无法处理。

| 错误码 | HTTP状态 | 说明 | 解决方案 |
|--------|---------|------|---------|
| `BIZ_001` | 422 | Agent不能为空 | 提供有效的Agent配置 |
| `BIZ_002` | 422 | Workflow步骤无效 | 检查工作流步骤配置 |
| `BIZ_003` | 422 | 记忆冲突 | 解决记忆冲突或使用冲突解决策略 |
| `BIZ_004` | 422 | 工具不可用 | 检查工具是否已注册和启用 |
| `BIZ_005` | 422 | 审批被拒绝 | 根据拒绝原因修改请求 |
| `BIZ_006` | 422 | 配额不足 | 升级订阅或释放资源 |
| `BIZ_007` | 422 | 操作不支持 | 检查当前资源状态是否支持该操作 |

**示例错误响应**：
```json
{
  "error": {
    "code": "BIZ_003",
    "message": "Memory conflict detected",
    "details": "Conflicting memory entries found. Use conflict resolution strategy to proceed.",
    "trace_id": "trace_yz1234",
    "timestamp": "2026-05-27T10:30:00Z"
  },
  "status_code": 422
}
```

---

## 错误处理最佳实践

### 1. 始终检查HTTP状态码

```python
import requests

response = requests.get('http://localhost:8000/api/v1/agents/agent_123')

if response.status_code == 200:
    data = response.json()
    print(f"Agent: {data['name']}")
elif response.status_code == 404:
    error = response.json()['error']
    print(f"Agent not found: {error['message']}")
elif response.status_code == 401:
    print("Authentication required")
else:
    print(f"Error: {response.status_code}")
```

### 2. 解析错误码进行精确处理

```python
def handle_api_error(response):
    if response.status_code >= 500:
        # 服务器错误，重试
        return retry_request()
    
    error = response.json().get('error', {})
    error_code = error.get('code')
    
    if error_code == 'AUTH_002':
        # 令牌过期，刷新令牌
        refresh_token()
    elif error_code == 'RATE_001':
        # 速率限制，等待后重试
        wait_and_retry()
    elif error_code == 'RES_001':
        # 资源不存在，记录并继续
        log_missing_resource(error)
    else:
        # 其他错误
        raise APIError(error)
```

### 3. 向用户显示友好的错误消息

```python
def get_user_friendly_message(error_code):
    messages = {
        'AUTH_001': '请登录后继续',
        'AUTH_002': '登录已过期，请重新登录',
        'AUTHZ_001': '您没有权限执行此操作',
        'VAL_001': '请检查输入参数',
        'RES_001': '请求的资源不存在',
        'RATE_001': '请求过于频繁，请稍后再试',
        'SRV_001': '服务器出错，请稍后重试',
    }
    return messages.get(error_code, '发生未知错误')
```

### 4. 记录详细错误信息用于调试

```python
import logging

logger = logging.getLogger(__name__)

def log_api_error(response):
    error = response.json().get('error', {})
    logger.error(
        f"API Error: {error.get('code')} - {error.get('message')}",
        extra={
            'trace_id': error.get('trace_id'),
            'status_code': response.status_code,
            'details': error.get('details'),
            'timestamp': error.get('timestamp'),
        }
    )
```

### 5. 实现重试逻辑

```python
import time
from typing import Optional

def call_api_with_retry(
    url: str,
    max_retries: int = 3,
    backoff_factor: float = 1.0
) -> Optional[dict]:
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            
            # 可重试的错误
            if response.status_code in [429, 503]:
                wait_time = backoff_factor * (2 ** attempt)
                logger.warning(f"Retrying after {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            # 不可重试的错误
            if response.status_code >= 400:
                error = response.json().get('error', {})
                logger.error(f"API Error: {error.get('code')}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
    
    return None
```

---

## 错误响应示例

### 完整的错误响应示例

```json
{
  "error": {
    "code": "VAL_003",
    "message": "Parameter value out of range",
    "details": "The 'limit' parameter must be between 1 and 100, but got 150",
    "trace_id": "trace_abc123def456",
    "timestamp": "2026-05-27T10:30:45.123Z",
    "request_id": "req_789xyz",
    "path": "/api/v1/workflows",
    "method": "GET"
  },
  "status_code": 400
}
```

### 多个验证错误

```json
{
  "error": {
    "code": "VAL_MULTIPLE",
    "message": "Multiple validation errors",
    "details": {
      "name": "Field is required",
      "description": "Field must be at least 10 characters",
      "model": "Invalid model name"
    },
    "trace_id": "trace_abc123def456",
    "timestamp": "2026-05-27T10:30:45.123Z"
  },
  "status_code": 400
}
```

---

## 常见错误场景

### 场景1：认证失败

**请求**：
```bash
curl http://localhost:8000/api/v1/agents
```

**响应**：
```json
{
  "error": {
    "code": "AUTH_001",
    "message": "Missing authentication token",
    "details": "The Authorization header is required for this endpoint"
  },
  "status_code": 401
}
```

**解决方案**：添加认证令牌
```bash
curl -H "Authorization: Bearer your-token" http://localhost:8000/api/v1/agents
```

### 场景2：参数验证失败

**请求**：
```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{"name": ""}'
```

**响应**：
```json
{
  "error": {
    "code": "VAL_001",
    "message": "Missing required parameter",
    "details": "Field 'name' is required and cannot be empty"
  },
  "status_code": 400
}
```

### 场景3：资源不存在

**请求**：
```bash
curl http://localhost:8000/api/v1/agents/invalid_id \
  -H "Authorization: Bearer token"
```

**响应**：
```json
{
  "error": {
    "code": "RES_001",
    "message": "Resource not found",
    "details": "Agent with ID 'invalid_id' does not exist"
  },
  "status_code": 404
}
```

---

## 相关文档

- [API参考](./API_REFERENCE.md) - 完整API端点列表
- [API集成指南](./API_INTEGRATION_GUIDE.md) - API使用示例
- [故障排查](./TROUBLESHOOTING_GUIDE.md) - 常见问题解决
- [安全指南](./SECURITY_GUIDE.md) - 安全最佳实践

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 文档团队  
**许可证**: MIT
