# X-Agent API 文档索引

## 概述

本目录包含 X-Agent 完整的 API 文档和集成指南。X-Agent 是一个功能强大的自主 Agent 框架，支持工作流编排、记忆管理和工具集成。

## 文档结构

### 核心文档

| 文档 | 描述 | 适用场景 |
|------|------|---------|
| [API_GUIDE.md](./API_GUIDE.md) | 详细的 API 使用指南 | 学习如何使用 API，了解认证、常见用例、错误处理 |
| [API_REFERENCE.md](./API_REFERENCE.md) | 完整的 API 参考 | 查找具体端点的详细信息、参数说明、响应格式 |
| [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE_V2.md) | 快速参考卡片 | 快速查找常用端点、错误码、代码示例 |
| [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md) | 集成开发指南 | 集成 API 到应用程序、错误处理、性能优化 |
| [API.md](./API.md) | API 概览 | API 基本信息和端点列表 |

### 机器可读格式

| 文件 | 格式 | 用途 |
|------|------|------|
| [openapi.json](./openapi.json) | OpenAPI 3.0 | 用于 Swagger UI、代码生成、API 文档工具 |
| [X-Agent.postman_collection.json](./X-Agent.postman_collection.json) | Postman Collection | 在 Postman 中导入和测试 API |

## 快速开始

### 1. 第一次使用？

从这里开始：
1. 阅读 [API_GUIDE.md](./API_GUIDE.md) 的"快速开始"部分
2. 查看 [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE_V2.md) 的常用示例
3. 在 Postman 中导入 [X-Agent.postman_collection.json](./X-Agent.postman_collection.json)

### 2. 需要具体端点信息？

查看 [API_REFERENCE.md](./API_REFERENCE.md)，按模块组织：
- Agents API
- Workflows API
- Runs API
- Memory API
- Tools API
- Auth API
- Traces API
- Audit API

### 3. 集成到应用程序？

按照 [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md)：
1. 环境设置
2. 初始化客户端
3. 常见集成场景
4. 错误处理和重试
5. 性能优化

### 4. 使用代码生成工具？

使用 [openapi.json](./openapi.json)：
```bash
# 使用 OpenAPI Generator
openapi-generator-cli generate -i docs/openapi.json -g python -o generated/

# 使用 Swagger Codegen
swagger-codegen generate -i docs/openapi.json -l python -o generated/
```

## API 端点速查

### Agents 管理
```
POST   /api/v1/agents              创建 Agent
GET    /api/v1/agents              列出 Agents
GET    /api/v1/agents/{id}         获取 Agent 详情
PUT    /api/v1/agents/{id}         更新 Agent
DELETE /api/v1/agents/{id}         删除 Agent
POST   /api/v1/agents/{id}/pause   暂停 Agent
```

### Workflows 管理
```
POST   /api/v1/workflows           创建 Workflow
GET    /api/v1/workflows           列出 Workflows
GET    /api/v1/workflows/status    获取 Workflow 状态
GET    /api/v1/workflows/templates 获取 Workflow 模板
```

### 运行管理
```
POST   /api/v1/runs/start          启动运行
GET    /api/v1/runs                列出运行
```

### 记忆管理
```
POST   /api/v1/memory              存储记忆
POST   /api/v1/memory/search       搜索记忆
GET    /api/v1/memory/export       导出记忆
POST   /api/v1/memory/import       导入记忆
POST   /api/v1/memory/consolidate  合并记忆
```

### 工具管理
```
GET    /api/v1/tools               列出工具
GET    /api/v1/tools/executions/{id}           获取工具执行
GET    /api/v1/tools/executions/{id}/correlation 获取关联信息
```

### 追踪和审计
```
GET    /api/v1/traces              列出追踪
GET    /api/v1/traces/{id}         获取追踪详情
GET    /api/v1/audit               列出审计日志
```

### 认证
```
POST   /api/v1/auth/login          用户登录
POST   /api/v1/auth/register       用户注册
```

## 认证方式

### API Key 认证
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/agents
```

### JWT Token 认证
```bash
curl -H "Authorization: Bearer your-jwt-token" http://localhost:8000/api/v1/agents
```

## 常见任务

### 启动 Agent 运行
```bash
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze sales data",
    "extra_context": {"period": "Q1 2025"}
  }'
```

### 搜索记忆
```bash
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user preferences",
    "top_k": 5
  }'
```

### 创建 Workflow
```bash
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Pipeline",
    "nodes": [...],
    "edges": [...]
  }'
```

## 错误处理

所有错误响应遵循统一格式：

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "status_code": 400,
  "trace_id": "trace_123456",
  "timestamp": "2025-05-26T10:30:00Z"
}
```

常见错误码：
- `400` - INVALID_REQUEST: 请求参数无效
- `401` - UNAUTHORIZED: 未授权
- `403` - FORBIDDEN: 权限不足
- `404` - RESOURCE_NOT_FOUND: 资源不存在
- `429` - RATE_LIMIT_EXCEEDED: 超过速率限制
- `500` - INTERNAL_ERROR: 服务器错误

详见 [API_REFERENCE.md](./API_REFERENCE.md#错误响应格式)

## 速率限制

| 端点 | 限制 | 时间窗口 |
|------|------|---------|
| `/auth/login` | 10 请求 | 60 秒 |
| `/auth/register` | 5 请求 | 60 秒 |
| 其他 API | 100 请求 | 60 秒 |

## 客户端库

### Python
```python
import requests

class XAgentClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    def start_run(self, task):
        response = requests.post(
            f"{self.base_url}/api/v1/runs/start",
            headers=self.headers,
            json={"task": task}
        )
        return response.json()

client = XAgentClient("http://localhost:8000", "your-api-key")
result = client.start_run("Analyze data")
```

### JavaScript/Node.js
```javascript
class XAgentClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async startRun(task) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/runs/start`,
      {
        method: "POST",
        headers: {
          "X-API-Key": this.apiKey,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ task })
      }
    );
    return response.json();
  }
}

const client = new XAgentClient("http://localhost:8000", "your-api-key");
const result = await client.startRun("Analyze data");
```

详见 [API_QUICK_REFERENCE.md](./API_QUICK_REFERENCE_V2.md#python-客户端示例)

## 工具和资源

### Postman
1. 下载 [X-Agent.postman_collection.json](./X-Agent.postman_collection.json)
2. 在 Postman 中导入集合
3. 配置环境变量：`base_url` 和 `api_key`
4. 开始测试 API

### Swagger UI
访问 `http://localhost:8000/docs` 查看交互式 API 文档

### OpenAPI 生成工具
使用 [openapi.json](./openapi.json) 生成代码：
```bash
# Python
openapi-generator-cli generate -i docs/openapi.json -g python -o generated/

# Go
openapi-generator-cli generate -i docs/openapi.json -g go -o generated/

# TypeScript
openapi-generator-cli generate -i docs/openapi.json -g typescript-fetch -o generated/
```

## 最佳实践

### 安全
- 不要在代码中硬编码 API Key
- 使用环境变量存储敏感信息
- 定期轮换 API Key
- 使用 HTTPS 在生产环境

### 性能
- 使用连接池和会话复用
- 实现请求缓存
- 使用异步运行处理长任务
- 批量操作而不是逐个请求

### 可靠性
- 实现重试机制
- 使用指数退避策略
- 监控 API 使用情况
- 记录所有请求和响应

详见 [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md)

## 故障排除

### 常见问题

**Q: 收到 401 Unauthorized 错误**
A: 检查 API Key 是否正确，是否在请求头中包含 `X-API-Key`

**Q: 收到 429 Rate Limit Exceeded 错误**
A: 等待一段时间后重试，或实现指数退避重试策略

**Q: API 响应缓慢**
A: 检查网络连接，考虑使用异步运行，或联系管理员

**Q: 如何调试 API 请求**
A: 使用 `curl -v` 查看详细信息，或在 Postman 中启用日志

详见 [API_GUIDE.md](./API_GUIDE.md#错误处理)

## 支持和反馈

- 查看 [TROUBLESHOOTING.md](../../operations/support/TROUBLESHOOTING.md) 获取更多帮助
- 查看 [FAQ.md](../../operations/support/FAQ.md) 了解常见问题
- 提交 Issue 或 Pull Request

## 版本历史

### v1.0.0 (2025-05-26)
- 初始版本
- 完整的 API 参考文档
- Postman 集合
- OpenAPI Schema
- 集成指南

## 许可证

MIT License - 详见项目根目录的 LICENSE 文件

---

**最后更新**: 2025-05-26
**维护者**: X-Agent Team
**文档版本**: 1.0.0
