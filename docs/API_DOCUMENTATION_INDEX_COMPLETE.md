# X-Agent API 文档索引

本文档是 X-Agent API 文档的中心索引，帮助你快速找到所需的信息。

## 快速导航

### 新手入门
- **[快速开始指南](API_QUICKSTART.md)** - 5 分钟快速开始
- **[完整 API 参考](API_COMPLETE_REFERENCE.md)** - 所有 API 端点详细说明
- **[使用示例](API_EXAMPLES.md)** - Python、cURL、JavaScript 示例

### 开发者指南
- **[SDK 使用指南](SDK_GUIDE.md)** - Python SDK 完整使用说明
- **[集成指南](API_INTEGRATION_GUIDE_NEW.md)** - 与第三方系统集成
- **[变更日志](API_CHANGELOG.md)** - 版本历史和迁移指南

### 参考资料
- **[OpenAPI 规范](openapi.json)** - 机器可读的 API 规范
- **[Postman 集合](X-Agent.postman_collection.json)** - 可导入 Postman 的集合

---

## 文档结构

```
docs/
├── API_QUICKSTART.md              # 快速开始（5分钟）
├── API_COMPLETE_REFERENCE.md      # 完整参考（所有端点）
├── API_EXAMPLES.md                # 使用示例（多语言）
├── SDK_GUIDE.md                   # SDK 使用指南
├── API_INTEGRATION_GUIDE_NEW.md   # 集成指南
├── API_CHANGELOG.md               # 变更日志
├── API_DOCUMENTATION_INDEX.md     # 本文件
├── openapi.json                   # OpenAPI 规范
└── X-Agent.postman_collection.json # Postman 集合
```

---

## 按用途查找文档

### 我想快速开始使用 API

1. 阅读 [快速开始指南](API_QUICKSTART.md)
2. 查看 [使用示例](API_EXAMPLES.md) 中的相关示例
3. 参考 [完整 API 参考](API_COMPLETE_REFERENCE.md) 了解详细信息

### 我想了解所有可用的 API 端点

阅读 [完整 API 参考](API_COMPLETE_REFERENCE.md)，其中包含：
- 所有端点的详细说明
- 请求和响应格式
- 错误码和处理方式
- 认证和授权信息

### 我想使用 Python SDK

阅读 [SDK 使用指南](SDK_GUIDE.md)，其中包含：
- SDK 安装和初始化
- 所有主要功能的使用方法
- 错误处理和重试机制
- 高级功能和最佳实践

### 我想将 X-Agent 集成到我的应用

阅读 [集成指南](API_INTEGRATION_GUIDE_NEW.md)，其中包含：
- 常见集成场景
- 第三方系统集成
- 最佳实践
- 故障排除

### 我想查看代码示例

查看 [使用示例](API_EXAMPLES.md)，其中包含：
- Python 示例
- cURL 示例
- JavaScript 示例
- 高级场景示例

### 我想了解 API 的变更历史

阅读 [变更日志](API_CHANGELOG.md)，其中包含：
- 版本历史
- 新增功能
- 破坏性变更
- 迁移指南

### 我想在 Postman 中测试 API

1. 下载 [Postman 集合](X-Agent.postman_collection.json)
2. 在 Postman 中导入集合
3. 配置环境变量（base_url、token）
4. 开始测试 API

### 我想自动生成 API 客户端

使用 [OpenAPI 规范](openapi.json)：
- 使用 OpenAPI Generator 生成客户端代码
- 支持多种编程语言
- 自动生成文档

---

## API 端点概览

### Agents API
管理 Agent 实例

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/agents` | 创建 Agent |
| GET | `/agents` | 列出 Agents |
| GET | `/agents/{agent_id}` | 获取 Agent 详情 |
| PUT | `/agents/{agent_id}` | 更新 Agent |
| DELETE | `/agents/{agent_id}` | 删除 Agent |
| POST | `/agents/{agent_id}/pause` | 暂停 Agent |
| POST | `/agents/{agent_id}/resume` | 恢复 Agent |

### Runs API
管理任务执行

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/runs/start` | 启动 Run |
| GET | `/runs` | 列出 Runs |
| GET | `/runs/{trace_id}` | 获取 Run 详情 |

### Memory API
管理记忆系统

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/memory/search` | 搜索记忆 |
| POST | `/memory` | 添加记忆 |
| GET | `/memory/{memory_id}` | 获取记忆详情 |
| DELETE | `/memory/{memory_id}` | 删除记忆 |

### Tools API
管理工具

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/tools` | 列出工具 |
| GET | `/tools/{tool_id}` | 获取工具详情 |

### Traces API
查询执行跟踪

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/traces/{trace_id}` | 获取 Trace |

### Audit API
查询审计日志

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/audit/logs` | 列出审计日志 |

### Auth API
认证和授权

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/auth/login` | 用户登录 |
| POST | `/auth/logout` | 用户登出 |
| POST | `/auth/refresh` | 刷新 Token |

---

## 常见任务

### 执行一个任务
```python
from xagent import XAgentClient

client = XAgentClient(token="your-token")
result = client.runs.start(task="分析这个数据集")
print(result.run.result)
```
详见: [快速开始指南](API_QUICKSTART.md#第-2-步执行你的第一个任务)

### 创建一个 Agent
```python
agent = client.agents.create(
    name="My Agent",
    status="active",
    capabilities=["run", "trace", "memory", "tools"]
)
```
详见: [SDK 使用指南](SDK_GUIDE.md#创建-agent)

### 搜索记忆
```python
results = client.memory.search(
    query="之前的分析结果",
    limit=10
)
```
详见: [SDK 使用指南](SDK_GUIDE.md#搜索记忆)

### 处理异步任务
```python
run = client.runs.start_async(task="长时间任务")
result = run.wait_for_completion(timeout=300)
```
详见: [使用示例](API_EXAMPLES.md#python---启动异步-run)

### 集成到 Web 应用
详见: [集成指南](API_INTEGRATION_GUIDE_NEW.md#场景-1-web-应用集成)

### 批量处理
详见: [集成指南](API_INTEGRATION_GUIDE_NEW.md#场景-2-批处理集成)

---

## 认证和授权

### 获取 API Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "your_password"
  }'
```

### 使用 Token
```bash
curl -H "Authorization: Bearer your-token" \
  http://localhost:8000/api/v1/agents
```

详见: [完整 API 参考](API_COMPLETE_REFERENCE.md#认证与授权)

---

## 错误处理

### 常见错误码

| 状态码 | 错误码 | 描述 |
|--------|--------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 401 | UNAUTHORIZED | 未授权 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | NOT_FOUND | 资源不存在 |
| 429 | RATE_LIMITED | 速率限制 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

详见: [完整 API 参考](API_COMPLETE_REFERENCE.md#错误处理)

---

## 速率限制

| 端点 | 限制 | 窗口 |
|------|------|------|
| `/auth/login` | 10 请求 | 60 秒 |
| `/auth/register` | 5 请求 | 60 秒 |
| `/api/*` | 100 请求 | 60 秒 |

详见: [完整 API 参考](API_COMPLETE_REFERENCE.md#速率限制)

---

## 最佳实践

1. **使用异步执行处理长时间任务**
   - 使用 `async_run: true` 启动异步任务
   - 使用 `wait_for_completion()` 等待完成

2. **实施错误处理和重试**
   - 捕获异常并处理
   - 使用指数退避重试

3. **监控和日志**
   - 记录所有 API 调用
   - 监控错误率和延迟

4. **资源管理**
   - 使用上下文管理器
   - 及时关闭连接

5. **安全性**
   - 使用环境变量存储敏感信息
   - 定期轮换 API Token
   - 使用 HTTPS 连接

详见: [SDK 使用指南](SDK_GUIDE.md#最佳实践)

---

## 获取帮助

### 文档
- [快速开始指南](API_QUICKSTART.md)
- [完整 API 参考](API_COMPLETE_REFERENCE.md)
- [使用示例](API_EXAMPLES.md)
- [SDK 使用指南](SDK_GUIDE.md)
- [集成指南](API_INTEGRATION_GUIDE_NEW.md)
- [变更日志](API_CHANGELOG.md)

### 工具
- [OpenAPI 规范](openapi.json)
- [Postman 集合](X-Agent.postman_collection.json)

### 支持
- 问题追踪: https://github.com/xagent/xagent/issues
- 讨论: https://github.com/xagent/xagent/discussions
- 邮件: support@xagent.io

---

## 版本信息

- **API 版本**: v1.0.0
- **最后更新**: 2026-05-27
- **基础 URL**: `http://localhost:8000/api/v1`

---

## 相关链接

- [X-Agent 主页](https://xagent.io)
- [GitHub 仓库](https://github.com/xagent/xagent)
- [问题追踪](https://github.com/xagent/xagent/issues)
- [讨论区](https://github.com/xagent/xagent/discussions)
