# X-Agent API 错误码参考

**版本：** v1.0  
**更新时间：** 2026-05-27  
**适用范围：** X-Agent 所有 API 端点的错误响应规范

---

## 文档概述

本文档定义了 X-Agent API 的完整错误码体系，包括 HTTP 状态码、错误码、错误消息、根本原因和解决方案。所有 API 端点都应遵循本规范返回错误信息。

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "status": 400,
    "timestamp": "2026-05-27T10:30:00Z",
    "request_id": "req_abc123def456",
    "trace_id": "trace_xyz789",
    "details": {
      "field": "additional context",
      "reason": "specific reason"
    }
  }
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 错误码，用于程序化处理 |
| `message` | string | 人类可读的错误消息 |
| `status` | integer | HTTP 状态码 |
| `timestamp` | string | 错误发生时间（ISO 8601） |
| `request_id` | string | 请求追踪 ID |
| `trace_id` | string | 分布式追踪 ID |
| `details` | object | 错误详情（可选） |

---

## 错误码分类

### 1. 认证与授权错误 (4xx)

#### 401 Unauthorized

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `AUTH_MISSING_CREDENTIALS` | 401 | Missing authentication credentials | 请求未提供认证信息 | 在请求头中添加 `Authorization: Bearer <token>` |
| `AUTH_INVALID_TOKEN` | 401 | Invalid or expired authentication token | Token 无效或已过期 | 重新获取有效的 Token |
| `AUTH_TOKEN_EXPIRED` | 401 | Authentication token has expired | Token 已过期 | 使用刷新令牌获取新 Token，或重新登录 |
| `AUTH_MALFORMED_TOKEN` | 401 | Malformed authentication token | Token 格式错误 | 检查 Token 格式是否正确 |
| `AUTH_INVALID_CREDENTIALS` | 401 | Invalid username or password | 用户名或密码错误 | 检查凭证并重试 |
| `AUTH_ACCOUNT_LOCKED` | 401 | Account is locked due to multiple failed attempts | 账户因多次失败登录被锁定 | 等待锁定期过期或联系管理员 |
| `AUTH_ACCOUNT_DISABLED` | 401 | Account has been disabled | 账户已被禁用 | 联系管理员启用账户 |

#### 403 Forbidden

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `AUTHZ_INSUFFICIENT_PERMISSIONS` | 403 | Insufficient permissions for this operation | 权限不足 | 请求具有所需权限的用户或角色 |
| `AUTHZ_SCOPE_MISMATCH` | 403 | Token scope does not include required permissions | Token 作用域不匹配 | 使用具有正确作用域的 Token |
| `AUTHZ_TENANT_MISMATCH` | 403 | Operation not allowed for this tenant | 租户不匹配 | 确保在正确的租户上下文中操作 |
| `AUTHZ_RESOURCE_ACCESS_DENIED` | 403 | Access to this resource is denied | 资源访问被拒绝 | 检查资源权限配置 |
| `AUTHZ_API_KEY_INVALID` | 403 | API key is invalid or revoked | API 密钥无效或已撤销 | 生成新的 API 密钥 |
| `AUTHZ_API_KEY_EXPIRED` | 403 | API key has expired | API 密钥已过期 | 生成新的 API 密钥 |

---

### 2. 请求验证错误 (4xx)

#### 400 Bad Request

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `VALIDATION_INVALID_JSON` | 400 | Invalid JSON in request body | 请求体 JSON 格式错误 | 检查 JSON 格式是否正确 |
| `VALIDATION_MISSING_FIELD` | 400 | Required field '{field}' is missing | 缺少必需字段 | 添加缺失的必需字段 |
| `VALIDATION_INVALID_TYPE` | 400 | Field '{field}' has invalid type, expected {type} | 字段类型错误 | 使用正确的数据类型 |
| `VALIDATION_INVALID_FORMAT` | 400 | Field '{field}' has invalid format | 字段格式错误 | 检查字段格式（如邮箱、URL、日期等） |
| `VALIDATION_VALUE_OUT_OF_RANGE` | 400 | Field '{field}' value is out of range | 字段值超出范围 | 使用有效范围内的值 |
| `VALIDATION_INVALID_ENUM` | 400 | Field '{field}' has invalid enum value | 枚举值无效 | 使用允许的枚举值之一 |
| `VALIDATION_STRING_TOO_LONG` | 400 | Field '{field}' exceeds maximum length of {max} | 字符串过长 | 缩短字符串长度 |
| `VALIDATION_STRING_TOO_SHORT` | 400 | Field '{field}' is shorter than minimum length of {min} | 字符串过短 | 增加字符串长度 |
| `VALIDATION_ARRAY_EMPTY` | 400 | Array field '{field}' cannot be empty | 数组为空 | 提供至少一个数组元素 |
| `VALIDATION_ARRAY_TOO_LARGE` | 400 | Array field '{field}' exceeds maximum size of {max} | 数组过大 | 减少数组元素数量 |
| `VALIDATION_DUPLICATE_VALUE` | 400 | Duplicate value for field '{field}' | 字段值重复 | 使用唯一值 |

#### 422 Unprocessable Entity

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `VALIDATION_BUSINESS_RULE_VIOLATION` | 422 | Business rule violation: {reason} | 违反业务规则 | 根据具体业务规则调整请求 |
| `VALIDATION_CONFLICTING_FIELDS` | 422 | Conflicting values in fields {fields} | 字段值冲突 | 调整字段值使其一致 |
| `VALIDATION_INVALID_STATE_TRANSITION` | 422 | Invalid state transition from {current} to {target} | 无效的状态转换 | 检查允许的状态转换 |

---

### 3. 资源错误 (4xx)

#### 404 Not Found

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `RESOURCE_NOT_FOUND` | 404 | Resource '{resource_type}' with id '{id}' not found | 资源不存在 | 检查资源 ID 是否正确 |
| `AGENT_NOT_FOUND` | 404 | Agent with id '{id}' not found | Agent 不存在 | 检查 Agent ID 或创建新 Agent |
| `WORKFLOW_NOT_FOUND` | 404 | Workflow with id '{id}' not found | 工作流不存在 | 检查工作流 ID 或创建新工作流 |
| `RUN_NOT_FOUND` | 404 | Run with id '{id}' not found | 运行记录不存在 | 检查运行 ID 或创建新运行 |
| `MEMORY_NOT_FOUND` | 404 | Memory item with id '{id}' not found | 记忆项不存在 | 检查记忆 ID 或创建新记忆 |
| `SESSION_NOT_FOUND` | 404 | Session with id '{id}' not found | 会话不存在 | 检查会话 ID 或创建新会话 |
| `TOOL_NOT_FOUND` | 404 | Tool '{tool_name}' not found | 工具不存在 | 检查工具名称或安装工具 |
| `USER_NOT_FOUND` | 404 | User with id '{id}' not found | 用户不存在 | 检查用户 ID |
| `TENANT_NOT_FOUND` | 404 | Tenant with id '{id}' not found | 租户不存在 | 检查租户 ID |

#### 409 Conflict

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `RESOURCE_ALREADY_EXISTS` | 409 | Resource '{resource_type}' with identifier '{identifier}' already exists | 资源已存在 | 使用不同的标识符或更新现有资源 |
| `RESOURCE_VERSION_CONFLICT` | 409 | Resource version mismatch, expected {expected} but got {actual} | 资源版本冲突 | 刷新资源并重试 |
| `RESOURCE_STATE_CONFLICT` | 409 | Cannot perform operation in current resource state | 资源状态冲突 | 等待资源状态变化或更改资源状态 |
| `CONCURRENT_MODIFICATION` | 409 | Resource was modified by another request | 并发修改冲突 | 重新获取资源并重试 |

---

### 4. 限流与配额错误 (4xx)

#### 429 Too Many Requests

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded, retry after {retry_after} seconds | 超过速率限制 | 等待指定时间后重试 |
| `QUOTA_EXCEEDED` | 429 | Quota exceeded for resource '{resource}' | 超过配额限制 | 升级计划或等待配额重置 |
| `CONCURRENT_REQUEST_LIMIT` | 429 | Too many concurrent requests, limit is {limit} | 并发请求过多 | 减少并发请求数量 |

---

### 5. 服务器错误 (5xx)

#### 500 Internal Server Error

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `INTERNAL_SERVER_ERROR` | 500 | An unexpected error occurred | 内部服务器错误 | 查看服务器日志，联系支持团队 |
| `DATABASE_ERROR` | 500 | Database operation failed | 数据库操作失败 | 检查数据库连接，重试操作 |
| `EXTERNAL_SERVICE_ERROR` | 500 | External service call failed: {service} | 外部服务调用失败 | 检查外部服务状态，重试操作 |
| `LLM_SERVICE_ERROR` | 500 | LLM service error: {error_detail} | LLM 服务错误 | 检查 LLM 服务状态，重试操作 |
| `MEMORY_SERVICE_ERROR` | 500 | Memory service error: {error_detail} | 记忆服务错误 | 检查记忆服务状态，重试操作 |
| `WORKFLOW_EXECUTION_ERROR` | 500 | Workflow execution failed: {error_detail} | 工作流执行失败 | 检查工作流定义和日志 |
| `AGENT_EXECUTION_ERROR` | 500 | Agent execution failed: {error_detail} | Agent 执行失败 | 检查 Agent 配置和日志 |

#### 502 Bad Gateway

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `GATEWAY_ERROR` | 502 | Bad gateway, upstream service unavailable | 网关错误 | 检查上游服务状态，重试 |
| `UPSTREAM_TIMEOUT` | 502 | Upstream service timeout | 上游服务超时 | 增加超时时间或检查服务性能 |

#### 503 Service Unavailable

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `SERVICE_UNAVAILABLE` | 503 | Service is temporarily unavailable | 服务暂时不可用 | 稍后重试 |
| `MAINTENANCE_MODE` | 503 | Service is under maintenance | 服务维护中 | 等待维护完成 |
| `DEPENDENCY_UNAVAILABLE` | 503 | Required dependency is unavailable: {dependency} | 依赖服务不可用 | 检查依赖服务状态 |

#### 504 Gateway Timeout

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `REQUEST_TIMEOUT` | 504 | Request timeout after {timeout} seconds | 请求超时 | 增加超时时间或优化请求 |
| `OPERATION_TIMEOUT` | 504 | Operation timeout: {operation} | 操作超时 | 检查操作性能或增加超时时间 |

---

## 特定领域错误码

### Agent 相关错误

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `AGENT_INVALID_CONFIG` | 400 | Invalid agent configuration: {reason} | Agent 配置无效 | 检查 Agent 配置参数 |
| `AGENT_CAPABILITY_MISSING` | 400 | Agent lacks required capability: {capability} | Agent 缺少必需能力 | 为 Agent 添加所需能力 |
| `AGENT_TOOL_NOT_AVAILABLE` | 400 | Tool '{tool}' is not available for this agent | 工具对 Agent 不可用 | 检查工具权限或安装工具 |
| `AGENT_EXECUTION_FAILED` | 500 | Agent execution failed: {reason} | Agent 执行失败 | 检查 Agent 日志和配置 |
| `AGENT_APPROVAL_REQUIRED` | 403 | High-risk operation requires approval | 高风险操作需要审批 | 请求审批或降低操作风险等级 |
| `AGENT_APPROVAL_REJECTED` | 403 | Operation was rejected by approver | 操作被审批人拒绝 | 修改操作参数并重新提交 |

### 工作流相关错误

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `WORKFLOW_INVALID_DEFINITION` | 400 | Invalid workflow definition: {reason} | 工作流定义无效 | 检查工作流 DAG 结构 |
| `WORKFLOW_EXECUTION_FAILED` | 500 | Workflow execution failed at node '{node}': {reason} | 工作流执行失败 | 检查失败节点的配置和日志 |
| `WORKFLOW_NODE_FAILED` | 500 | Workflow node '{node}' failed: {reason} | 工作流节点失败 | 检查节点配置和输入 |
| `WORKFLOW_TIMEOUT` | 504 | Workflow execution timeout after {timeout} seconds | 工作流执行超时 | 增加超时时间或优化工作流 |
| `WORKFLOW_COMPENSATION_FAILED` | 500 | Workflow compensation failed: {reason} | 工作流补偿失败 | 检查补偿逻辑和日志 |

### 记忆相关错误

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `MEMORY_INVALID_SESSION` | 400 | Invalid memory session: {reason} | 无效的记忆会话 | 检查会话 ID 或创建新会话 |
| `MEMORY_POLLUTION_DETECTED` | 422 | Memory pollution detected: {reason} | 检测到记忆污染 | 检查并清理污染的记忆 |
| `MEMORY_CONSOLIDATION_FAILED` | 500 | Memory consolidation failed: {reason} | 记忆巩固失败 | 检查记忆数据和日志 |
| `MEMORY_RETRIEVAL_FAILED` | 500 | Memory retrieval failed: {reason} | 记忆检索失败 | 检查向量数据库连接 |
| `MEMORY_EXPORT_FAILED` | 500 | Memory export failed: {reason} | 记忆导出失败 | 检查导出配置和权限 |
| `MEMORY_IMPORT_FAILED` | 400 | Memory import failed: {reason} | 记忆导入失败 | 检查导入数据格式 |

### 浏览器自动化错误

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `BROWSER_SESSION_NOT_FOUND` | 404 | Browser session '{session_id}' not found | 浏览器会话不存在 | 创建新的浏览器会话 |
| `BROWSER_NAVIGATION_FAILED` | 500 | Failed to navigate to '{url}': {reason} | 浏览器导航失败 | 检查 URL 和网络连接 |
| `BROWSER_ELEMENT_NOT_FOUND` | 404 | Element not found: {selector} | 页面元素不存在 | 检查选择器或等待元素加载 |
| `BROWSER_INTERACTION_FAILED` | 500 | Browser interaction failed: {reason} | 浏览器交互失败 | 检查元素状态和交互参数 |
| `BROWSER_TIMEOUT` | 504 | Browser operation timeout after {timeout} seconds | 浏览器操作超时 | 增加超时时间或检查页面加载 |

### 桌面自动化错误

| 错误码 | HTTP状态 | 消息 | 原因 | 解决方案 |
|--------|---------|------|------|---------|
| `DESKTOP_SESSION_NOT_FOUND` | 404 | Desktop session '{session_id}' not found | 桌面会话不存在 | 创建新的桌面会话 |
| `DESKTOP_ELEMENT_NOT_FOUND` | 404 | Desktop element not found: {description} | 桌面元素不存在 | 检查元素描述或等待元素出现 |
| `DESKTOP_INTERACTION_FAILED` | 500 | Desktop interaction failed: {reason} | 桌面交互失败 | 检查元素状态和交互参数 |
| `DESKTOP_CLIPBOARD_ERROR` | 500 | Clipboard operation failed: {reason} | 剪贴板操作失败 | 检查系统权限和剪贴板状态 |
| `DESKTOP_INPUT_METHOD_ERROR` | 500 | Input method operation failed: {reason} | 输入法操作失败 | 检查输入法配置 |

---

## 错误处理最佳实践

### 1. 客户端错误处理

```python
import requests
from typing import Optional, Dict, Any

def handle_api_error(response: requests.Response) -> None:
    """处理 API 错误响应"""
    if response.status_code >= 400:
        try:
            error_data = response.json()
            error = error_data.get('error', {})
            code = error.get('code', 'UNKNOWN_ERROR')
            message = error.get('message', 'Unknown error')
            
            # 根据错误码采取不同的处理策略
            if code == 'AUTH_TOKEN_EXPIRED':
                # 刷新 Token
                refresh_token()
            elif code == 'RATE_LIMIT_EXCEEDED':
                # 等待后重试
                retry_after = error.get('details', {}).get('retry_after', 60)
                time.sleep(retry_after)
            elif code.startswith('VALIDATION_'):
                # 记录验证错误
                log_validation_error(error)
            else:
                # 其他错误
                raise APIError(code, message)
        except ValueError:
            raise APIError('INVALID_RESPONSE', 'Invalid error response format')
```

### 2. 重试策略

```python
def retry_with_backoff(
    func,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_codes: Optional[list] = None
) -> Any:
    """带指数退避的重试"""
    if retryable_codes is None:
        retryable_codes = [
            'RATE_LIMIT_EXCEEDED',
            'SERVICE_UNAVAILABLE',
            'REQUEST_TIMEOUT',
            'UPSTREAM_TIMEOUT'
        ]
    
    for attempt in range(max_retries):
        try:
            return func()
        except APIError as e:
            if e.code not in retryable_codes or attempt == max_retries - 1:
                raise
            wait_time = backoff_factor ** attempt
            time.sleep(wait_time)
```

### 3. 错误日志记录

```python
import logging

logger = logging.getLogger(__name__)

def log_api_error(error_data: Dict[str, Any]) -> None:
    """记录 API 错误"""
    error = error_data.get('error', {})
    code = error.get('code')
    message = error.get('message')
    request_id = error.get('request_id')
    trace_id = error.get('trace_id')
    
    logger.error(
        f"API Error: {code} - {message}",
        extra={
            'request_id': request_id,
            'trace_id': trace_id,
            'error_code': code,
            'details': error.get('details')
        }
    )
```

---

## 错误码查询速查表

### 按 HTTP 状态码分类

| 状态码 | 常见错误码 | 说明 |
|--------|-----------|------|
| 400 | VALIDATION_*, AGENT_INVALID_CONFIG | 请求格式或参数错误 |
| 401 | AUTH_* | 认证失败 |
| 403 | AUTHZ_*, AGENT_APPROVAL_REQUIRED | 授权失败或权限不足 |
| 404 | RESOURCE_NOT_FOUND, *_NOT_FOUND | 资源不存在 |
| 409 | RESOURCE_ALREADY_EXISTS, CONCURRENT_MODIFICATION | 资源冲突 |
| 422 | VALIDATION_BUSINESS_RULE_VIOLATION | 业务规则违反 |
| 429 | RATE_LIMIT_EXCEEDED, QUOTA_EXCEEDED | 限流或配额超限 |
| 500 | *_ERROR, *_FAILED | 服务器内部错误 |
| 502 | GATEWAY_ERROR, UPSTREAM_TIMEOUT | 网关错误 |
| 503 | SERVICE_UNAVAILABLE, MAINTENANCE_MODE | 服务不可用 |
| 504 | REQUEST_TIMEOUT, OPERATION_TIMEOUT | 操作超时 |

### 按错误类型分类

| 错误类型 | 错误码前缀 | 说明 |
|---------|-----------|------|
| 认证 | AUTH_* | 身份验证相关 |
| 授权 | AUTHZ_* | 权限和访问控制 |
| 验证 | VALIDATION_* | 请求数据验证 |
| 资源 | RESOURCE_* | 资源操作 |
| Agent | AGENT_* | Agent 相关操作 |
| 工作流 | WORKFLOW_* | 工作流相关操作 |
| 记忆 | MEMORY_* | 记忆系统操作 |
| 浏览器 | BROWSER_* | 浏览器自动化 |
| 桌面 | DESKTOP_* | 桌面自动化 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-27 | 初始版本，包含完整错误码体系 |

---

## 相关文档

- [API 接口设计文档](./08-API接口设计文档.md)
- [安全最佳实践](../SECURITY_BEST_PRACTICES.md)
- [故障排查指南](../TROUBLESHOOTING.md)
