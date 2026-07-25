# 企业协作平台集成指南

## 概述

X-Agent 企业协作平台集成模块提供了与钉钉、飞书、企业微信三大企业IM平台的无缝集成能力。通过统一的抽象层，支持多平台消息推送、通讯录同步、审批流程、用户映射等功能。

## 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                    API 层                                │
│  (enterprise_im.py - REST 端点)                         │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  管理层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Manager    │  │   Router     │  │   Mapping    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  平台层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  DingTalk    │  │   Feishu     │  │ WeChat Work  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              第三方 API                                  │
│  (钉钉/飞书/企业微信 Open API)                          │
└─────────────────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 功能 | 文件 |
|------|------|------|
| Base | 统一抽象基类 | `base.py` |
| DingTalk | 钉钉集成 | `dingtalk.py` |
| Feishu | 飞书集成 | `feishu.py` |
| WeChat Work | 企业微信集成 | `wechat_work.py` |
| Manager | 平台管理器 | `manager.py` |
| Router | 消息路由器 | `message_router.py` |
| Mapping | 用户映射 | `user_mapping.py` |
| API | REST 端点 | `enterprise_im.py` |
| Webhooks | 事件回调 | `webhooks.py` |

## 快速开始

### 1. 初始化管理器

```python
from backend.app.integrations.enterprise.manager import EnterpriseIMManager
from backend.app.integrations.enterprise.message_router import MessageRouter
from backend.app.integrations.enterprise.user_mapping import UserMapping

# 创建管理器实例
manager = EnterpriseIMManager()
router = MessageRouter(manager)
user_mapping = UserMapping()
```

### 2. 配置平台

#### 钉钉配置

```python
# 配置钉钉
success = await manager.create_dingtalk_platform(
    app_key="your_app_key",
    app_secret="your_app_secret",
    corp_id="your_corp_id"
)
```

#### 飞书配置

```python
# 配置飞书
success = await manager.create_feishu_platform(
    app_id="your_app_id",
    app_secret="your_app_secret"
)
```

#### 企业微信配置

```python
# 配置企业微信
success = await manager.create_wechat_work_platform(
    corp_id="your_corp_id",
    corp_secret="your_corp_secret",
    agent_id="your_agent_id"
)
```

### 3. 发送消息

#### 发送文本消息

```python
# 发送到单个平台
success = await manager.send_message_to_platform(
    platform_name="dingtalk",
    user_id="user123",
    message="Hello, World!",
    msg_type=MessageType.TEXT
)

# 发送到多个平台
user_mappings = {
    "dingtalk": "user123",
    "feishu": "user456",
    "wechat_work": "user789"
}
results = await manager.send_message_to_all(user_mappings, "Hello, World!")
```

#### 发送卡片消息

```python
card = {
    "title": "Card Title",
    "text": "Card content",
    "buttons": [
        {"text": "Button 1", "url": "https://example.com"}
    ]
}

success = await manager.send_card_to_platform(
    platform_name="dingtalk",
    user_id="user123",
    card=card
)
```

#### 发送Markdown消息

```python
success = await manager.send_markdown_to_platform(
    platform_name="feishu",
    user_id="user123",
    title="Markdown Title",
    text="# Heading\n\nContent here"
)
```

### 4. 同步通讯录

```python
# 同步所有平台的通讯录
contacts = await manager.sync_contacts_from_all()

# 同步特定平台
platform = manager.get_platform("dingtalk")
contacts = await platform.sync_contacts()
departments = await platform.sync_departments()

# 批量同步用户映射
for platform_name, platform in manager.platforms.items():
    contacts = await platform.sync_contacts()
    await user_mapping.bulk_sync_users(platform_name, contacts)
```

### 5. 创建审批

```python
# 创建审批流程
approval_id = await manager.create_approval_on_platform(
    platform_name="dingtalk",
    template_id="approval_template_001",
    data={
        "originator_user_id": "user123",
        "form_data": [
            {"key": "field1", "value": "value1"}
        ],
        "approvers": ["approver1", "approver2"]
    }
)

# 查询审批状态
status = await manager.get_approval_status_from_platform(
    platform_name="dingtalk",
    approval_id=approval_id
)
```

### 6. 用户映射

```python
# 映射用户
await user_mapping.map_user(
    internal_user_id="internal_user_1",
    platform="dingtalk",
    platform_user_id="dingtalk_user_123",
    metadata={"name": "John Doe", "email": "john@example.com"}
)

# 获取平台用户ID
platform_user_id = await user_mapping.get_platform_user_id(
    internal_user_id="internal_user_1",
    platform="dingtalk"
)

# 反向查询
internal_user_id = await user_mapping.get_internal_user_id(
    platform="dingtalk",
    platform_user_id="dingtalk_user_123"
)

# 批量同步
results = await user_mapping.bulk_sync_users(
    platform="dingtalk",
    users=[
        {"userid": "user1", "name": "User 1"},
        {"userid": "user2", "name": "User 2"}
    ]
)
```

## API 端点

### 平台配置

#### 配置平台
```
POST /api/v1/enterprise-im/platforms/configure
Content-Type: application/json

{
  "platform": "dingtalk",
  "credentials": {
    "app_key": "your_app_key",
    "app_secret": "your_app_secret",
    "corp_id": "your_corp_id"
  },
  "enabled": true
}
```

#### 列出平台
```
GET /api/v1/enterprise-im/platforms
```

#### 获取平台状态
```
GET /api/v1/enterprise-im/platforms/{platform}/status
```

#### 健康检查
```
POST /api/v1/enterprise-im/platforms/{platform}/health-check
```

### 消息发送

#### 发送消息
```
POST /api/v1/enterprise-im/messages/send
Content-Type: application/json

{
  "platform": "dingtalk",
  "user_id": "user123",
  "message": "Hello, World!",
  "msg_type": "text"
}
```

#### 广播消息
```
POST /api/v1/enterprise-im/messages/broadcast
Content-Type: application/json

{
  "platforms": ["dingtalk", "feishu"],
  "message": "Hello, Everyone!",
  "msg_type": "text"
}
```

#### 发送卡片
```
POST /api/v1/enterprise-im/messages/card
Content-Type: application/json

{
  "platform": "dingtalk",
  "user_id": "user123",
  "card": {
    "title": "Card Title",
    "text": "Card content"
  }
}
```

### 通讯录管理

#### 同步通讯录
```
POST /api/v1/enterprise-im/contacts/sync?platform=dingtalk
```

#### 列出用户
```
GET /api/v1/enterprise-im/contacts/users?platform=dingtalk
```

#### 列出部门
```
GET /api/v1/enterprise-im/contacts/departments?platform=dingtalk
```

### 审批流程

#### 创建审批
```
POST /api/v1/enterprise-im/approvals
Content-Type: application/json

{
  "platform": "dingtalk",
  "template_id": "approval_template_001",
  "data": {
    "originator_user_id": "user123",
    "form_data": []
  }
}
```

#### 获取审批状态
```
GET /api/v1/enterprise-im/approvals/{approval_id}?platform=dingtalk
```

### 用户映射

#### 映射用户
```
POST /api/v1/enterprise-im/users/map
Content-Type: application/json

{
  "internal_user_id": "internal_user_1",
  "platform": "dingtalk",
  "platform_user_id": "dingtalk_user_123",
  "metadata": {}
}
```

#### 获取用户映射
```
GET /api/v1/enterprise-im/users/{internal_user_id}/mappings
```

### 统计信息

#### 消息投递统计
```
GET /api/v1/enterprise-im/stats/delivery
```

#### 用户映射统计
```
GET /api/v1/enterprise-im/stats/mapping
```

#### 同步统计
```
GET /api/v1/enterprise-im/stats/sync
```

## 事件处理

### 注册事件处理器

```python
from backend.app.integrations.enterprise.message_router import EventType

async def on_user_joined(data):
    print(f"User joined: {data}")

# 注册处理器
router.register_event_handler(EventType.USER_JOINED, on_user_joined)

# 触发事件
await router.trigger_event(EventType.USER_JOINED, {
    "user_id": "user123",
    "user_name": "John Doe"
})
```

### 支持的事件类型

| 事件类型 | 说明 |
|---------|------|
| MESSAGE_RECEIVED | 收到消息 |
| APPROVAL_CREATED | 审批创建 |
| APPROVAL_APPROVED | 审批通过 |
| APPROVAL_REJECTED | 审批拒绝 |
| USER_JOINED | 用户加入 |
| USER_LEFT | 用户离开 |
| CONTACT_UPDATED | 通讯录更新 |

## Webhook 配置

### 钉钉 Webhook

配置钉钉应用的事件订阅，指向：
```
https://your-domain/api/v1/webhooks/dingtalk/callback
```

### 飞书 Webhook

配置飞书应用的事件订阅，指向：
```
https://your-domain/api/v1/webhooks/feishu/callback
```

### 企业微信 Webhook

配置企业微信应用的事件接收，指向：
```
https://your-domain/api/v1/webhooks/wechat_work/callback
```

## 错误处理

```python
try:
    success = await manager.send_message_to_platform(
        "dingtalk",
        "user123",
        "Hello"
    )
    if not success:
        print("Message delivery failed")
except Exception as e:
    print(f"Error: {e}")
```

## 性能优化

### 批量操作

```python
# 批量发送消息
user_mappings = {
    "dingtalk": "user1",
    "feishu": "user2",
    "wechat_work": "user3"
}
results = await manager.send_message_to_all(user_mappings, "Hello")

# 批量同步用户
results = await user_mapping.bulk_sync_users("dingtalk", users)
```

### 缓存策略

- Access Token 自动缓存和刷新
- 通讯录信息定期同步
- 用户映射本地存储

## 安全建议

1. **凭证管理**
   - 使用环境变量存储 API 密钥
   - 定期轮换密钥
   - 不要在代码中硬编码凭证

2. **签名验证**
   - 验证所有 Webhook 请求的签名
   - 使用 HTTPS 传输

3. **权限控制**
   - 使用 `enforce_scope` 检查权限
   - 限制 API 访问范围

4. **日志审计**
   - 记录所有消息发送
   - 记录用户映射变更
   - 定期审查日志

## 故障排查

### 认证失败

```python
# 检查凭证
platform = manager.get_platform("dingtalk")
if platform:
    healthy = await platform.health_check()
    print(f"Platform healthy: {healthy}")
```

### 消息发送失败

```python
# 检查投递日志
delivery_log = router.get_delivery_log(limit=10)
for log in delivery_log:
    if not log["success"]:
        print(f"Failed: {log['error']}")
```

### 用户映射问题

```python
# 搜索用户
results = await user_mapping.search_user("user123")
print(f"Found: {results}")

# 获取映射统计
stats = user_mapping.get_mapping_stats()
print(f"Stats: {stats}")
```

## 最佳实践

1. **初始化时配置所有平台**
   ```python
   for platform_config in config.platforms:
       await manager.create_platform(platform_config)
   ```

2. **定期同步通讯录**
   ```python
   # 每小时同步一次
   async def sync_contacts_periodically():
       while True:
           await manager.sync_contacts_from_all()
           await asyncio.sleep(3600)
   ```

3. **监控投递成功率**
   ```python
   stats = router.get_delivery_stats()
   if stats["success_rate"] < 0.95:
       alert("Low delivery success rate")
   ```

4. **使用消息路由**
   ```python
   # 自动路由到用户所在的所有平台
   await router.route_message(
       user_id="internal_user_1",
       message="Hello"
   )
   ```

## 扩展开发

### 添加新平台

1. 继承 `EnterpriseIMPlatform` 基类
2. 实现所有抽象方法
3. 在 `EnterpriseIMManager` 中添加创建方法
4. 添加相应的 API 端点

```python
class NewPlatformIntegration(EnterpriseIMPlatform):
    async def authenticate(self) -> bool:
        # 实现认证逻辑
        pass
    
    async def send_message(self, user_id: str, message: str, msg_type: MessageType = MessageType.TEXT) -> bool:
        # 实现发送消息逻辑
        pass
    
    # 实现其他抽象方法...
```

## 许可证

MIT License

## 支持

如有问题，请提交 Issue 或联系技术支持。
