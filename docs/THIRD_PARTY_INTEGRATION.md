# X-Agent 第三方集成指南

**版本**: 1.0.0  
**日期**: 2026-05-27  
**目标**: 帮助第三方工具和服务与X-Agent集成

---

## 目录

1. [集成概述](#集成概述)
2. [集成类型](#集成类型)
3. [集成接口](#集成接口)
4. [常见集成](#常见集成)
5. [集成最佳实践](#集成最佳实践)
6. [集成认证](#集成认证)
7. [故障排除](#故障排除)

---

## 集成概述

### 什么是集成?

集成是指将X-Agent与第三方工具、服务或平台连接起来，实现数据交换和功能协作。

### 集成的好处

- **扩展功能**: 利用第三方服务的能力
- **提高效率**: 自动化跨系统的工作流
- **改善体验**: 在熟悉的工具中使用X-Agent
- **降低成本**: 复用现有投资

### 集成场景

- **通知**: 将X-Agent事件发送到Slack、Email等
- **数据同步**: 在X-Agent和CRM、ERP等系统间同步数据
- **工作流**: 在X-Agent中调用第三方API
- **认证**: 使用第三方身份提供商
- **存储**: 使用第三方存储服务

---

## 集成类型

### 1. Webhook 集成

#### 概述

Webhook 是事件驱动的集成方式，当X-Agent中发生特定事件时，自动向第三方服务发送HTTP请求。

#### 支持的事件

```
工作流事件:
- workflow:created
- workflow:started
- workflow:completed
- workflow:failed

任务事件:
- task:created
- task:started
- task:completed
- task:failed

插件事件:
- plugin:installed
- plugin:enabled
- plugin:disabled
- plugin:error

用户事件:
- user:created
- user:updated
- user:deleted
```

#### 配置 Webhook

```bash
# 创建 Webhook
curl -X POST http://localhost:8000/api/v1/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Slack Notification",
    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "events": ["workflow:completed", "workflow:failed"],
    "active": true
  }'

# 列出 Webhooks
curl http://localhost:8000/api/v1/webhooks

# 更新 Webhook
curl -X PUT http://localhost:8000/api/v1/webhooks/{webhook_id} \
  -H "Content-Type: application/json" \
  -d '{"active": false}'

# 删除 Webhook
curl -X DELETE http://localhost:8000/api/v1/webhooks/{webhook_id}
```

### 2. REST API 集成

#### 基本用法

```python
import requests

# 创建工作流
response = requests.post(
    "http://localhost:8000/api/v1/workflows",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "name": "My Workflow",
        "description": "My workflow description",
        "nodes": [...]
    }
)

workflow = response.json()
print(f"Created workflow: {workflow['id']}")

# 执行工作流
response = requests.post(
    f"http://localhost:8000/api/v1/workflows/{workflow['id']}/run",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={"input": {...}}
)

run = response.json()
print(f"Started run: {run['id']}")
```

### 3. GraphQL 集成

#### 基本用法

```python
import requests

query = """
{
  workflows {
    id
    name
    description
    createdAt
  }
  runs(limit: 10) {
    id
    workflowId
    status
    startedAt
    completedAt
  }
}
"""

response = requests.post(
    "http://localhost:8000/graphql",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={"query": query}
)

data = response.json()
print(data)
```

### 4. Message Queue 集成

#### 支持的消息队列

- RabbitMQ
- Kafka
- AWS SQS
- Google Cloud Pub/Sub

#### 配置示例

```yaml
message_queue:
  type: "rabbitmq"
  host: "localhost"
  port: 5672
  username: "guest"
  password: "guest"
  
  topics:
    - name: "workflow.events"
      events: ["workflow:*"]
    - name: "task.events"
      events: ["task:*"]
```

---

## 集成接口

### 标准集成接口

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IntegrationAdapter(ABC):
    """集成适配器基类"""
    
    @property
    @abstractmethod
    def integration_id(self) -> str:
        """集成唯一标识"""
        pass
    
    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> None:
        """连接到外部系统"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    async def send_event(self, event: Dict[str, Any]) -> None:
        """发送事件"""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
```

---

## 常见集成

### 1. Slack 集成

#### 配置

```json
{
  "integration": "slack",
  "config": {
    "bot_token": "xoxb-YOUR-TOKEN",
    "signing_secret": "YOUR-SIGNING-SECRET",
    "channel": "#x-agent",
    "notifications": {
      "workflow_completed": true,
      "workflow_failed": true
    }
  }
}
```

#### 使用示例

```python
from xagent_sdk.integrations import SlackIntegration

slack = SlackIntegration()
await slack.connect(config)

# 发送消息
await slack.send_message(
    channel="#x-agent",
    text="Workflow completed successfully!"
)
```

### 2. GitHub 集成

#### 配置

```json
{
  "integration": "github",
  "config": {
    "token": "ghp_YOUR-TOKEN",
    "owner": "your-org",
    "repo": "your-repo"
  }
}
```

#### 使用示例

```python
from xagent_sdk.integrations import GitHubIntegration

github = GitHubIntegration()
await github.connect(config)

# 创建Issue
issue = await github.create_issue(
    title="Bug: Something is broken",
    body="Description of the bug",
    labels=["bug"]
)
```

### 3. Jira 集成

#### 配置

```json
{
  "integration": "jira",
  "config": {
    "url": "https://your-jira.atlassian.net",
    "username": "your-email@example.com",
    "api_token": "YOUR-API-TOKEN",
    "project_key": "PROJ"
  }
}
```

#### 使用示例

```python
from xagent_sdk.integrations import JiraIntegration

jira = JiraIntegration()
await jira.connect(config)

# 创建Issue
issue = await jira.create_issue(
    issue_type="Task",
    summary="Process data",
    description="Process the uploaded data"
)
```

---

## 集成最佳实践

### 1. 错误处理

```python
class IntegrationAdapter:
    async def send_event(self, event):
        """发送事件，包含重试逻辑"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                await self._send_event_impl(event)
                return
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
```

### 2. 速率限制

```python
from aiolimiter import AsyncLimiter

class IntegrationAdapter:
    def __init__(self):
        # 每秒最多10个请求
        self.limiter = AsyncLimiter(max_rate=10, time_period=1)
    
    async def send_event(self, event):
        """发送事件，遵守速率限制"""
        async with self.limiter:
            await self._send_event_impl(event)
```

### 3. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

class IntegrationAdapter:
    async def send_event(self, event):
        """发送事件，包含日志"""
        logger.info(f"Sending event: {event['event_type']}")
        try:
            result = await self._send_event_impl(event)
            logger.info(f"Event sent successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to send event: {e}")
            raise
```

---

## 集成认证

### 1. API Key 认证

```python
class IntegrationAdapter:
    async def connect(self, config):
        """使用API Key连接"""
        api_key = config.get("api_key")
        if not api_key:
            raise ValueError("API key is required")
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
```

### 2. OAuth 2.0 认证

```python
from authlib.integrations.httpx_client import AsyncOAuth2Client

class IntegrationAdapter:
    async def connect(self, config):
        """使用OAuth 2.0连接"""
        self.client = AsyncOAuth2Client(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            token_endpoint=config["token_endpoint"]
        )
```

### 3. 基本认证

```python
import base64

class IntegrationAdapter:
    async def connect(self, config):
        """使用基本认证连接"""
        username = config.get("username")
        password = config.get("password")
        
        credentials = base64.b64encode(
            f"{username}:{password}".encode()
        ).decode()
        
        self.headers = {
            "Authorization": f"Basic {credentials}"
        }
```

---

## 故障排除

### 常见问题

#### Q1: 连接超时

**症状**: 集成无法连接到外部服务

**解决方案**:
1. 检查网络连接
2. 验证服务URL
3. 检查防火墙规则
4. 增加超时时间

#### Q2: 认证失败

**症状**: 收到401或403错误

**解决方案**:
1. 验证API Key或Token
2. 检查权限
3. 检查Token过期时间
4. 重新生成凭证

#### Q3: 速率限制

**症状**: 收到429错误

**解决方案**:
1. 实现指数退避重试
2. 使用速率限制器
3. 批量处理请求
4. 联系服务提供商增加配额

#### Q4: 数据格式不匹配

**症状**: 集成无法解析响应

**解决方案**:
1. 检查API文档
2. 验证响应格式
3. 添加数据转换
4. 使用Schema验证

---

## 更多资源

- [API 参考](./API_REFERENCE.md)
- [插件开发指南](./PLUGIN_DEVELOPMENT_GUIDE.md)
- [社区论坛](https://forum.x-agent.io)
- [GitHub 讨论](https://github.com/x-agent/x-agent-core/discussions)

