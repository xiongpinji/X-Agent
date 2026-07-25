# 企业协作平台集成 - 快速参考

## 快速开始 (5分钟)

### 1. 安装依赖
```bash
pip install fastapi aiohttp pydantic pytest pytest-asyncio
```

### 2. 初始化管理器
```python
from backend.app.integrations.enterprise.manager import EnterpriseIMManager
from backend.app.integrations.enterprise.message_router import MessageRouter
from backend.app.integrations.enterprise.user_mapping import UserMapping

manager = EnterpriseIMManager()
router = MessageRouter(manager)
user_mapping = UserMapping()
```

### 3. 配置平台
```python
# 钉钉
await manager.create_dingtalk_platform(
    app_key="xxx",
    app_secret="xxx",
    corp_id="xxx"
)

# 飞书
await manager.create_feishu_platform(
    app_id="xxx",
    app_secret="xxx"
)

# 企业微信
await manager.create_wechat_work_platform(
    corp_id="xxx",
    corp_secret="xxx",
    agent_id="xxx"
)
```

### 4. 发送消息
```python
# 单平台
await manager.send_message_to_platform(
    "dingtalk", "user123", "Hello!"
)

# 多平台
results = await manager.send_message_to_all({
    "dingtalk": "user1",
    "feishu": "user2",
    "wechat_work": "user3"
}, "Hello!")
```

### 5. 同步通讯录
```python
# 同步所有平台
contacts = await manager.sync_contacts_from_all()

# 同步特定平台
platform = manager.get_platform("dingtalk")
users = await platform.sync_contacts()
```

---

## 常见任务

### 发送不同类型的消息

```python
from backend.app.integrations.enterprise.base import MessageType

# 文本消息
await manager.send_message_to_platform(
    "dingtalk", "user123", "Hello", MessageType.TEXT
)

# Markdown消息
await manager.send_markdown_to_platform(
    "feishu", "user123", "Title", "# Content"
)

# 卡片消息
card = {"title": "Card", "text": "Content"}
await manager.send_card_to_platform(
    "wechat_work", "user123", card
)
```

### 广播消息

```python
# 发送到所有用户
results = await router.broadcast_message(
    "Important announcement!",
    platforms=["dingtalk", "feishu"]
)

# 带过滤条件
results = await router.broadcast_message(
    "Team message",
    filter_func=lambda user: user.get("department") == "Engineering"
)
```

### 创建审批

```python
approval_id = await manager.create_approval_on_platform(
    "dingtalk",
    "approval_template_001",
    {
        "originator_user_id": "user123",
        "form_data": [{"key": "reason", "value": "Leave request"}],
        "approvers": ["manager1", "manager2"]
    }
)

# 查询状态
status = await manager.get_approval_status_from_platform(
    "dingtalk", approval_id
)
```

### 用户映射

```python
# 映射用户
await user_mapping.map_user(
    "internal_user_1",
    "dingtalk",
    "dingtalk_user_123"
)

# 获取映射
mappings = await user_mapping.get_user_mappings("internal_user_1")

# 批量同步
results = await user_mapping.bulk_sync_users(
    "dingtalk",
    [{"userid": "u1", "name": "User 1"}]
)
```

### 事件处理

```python
from backend.app.integrations.enterprise.message_router import EventType

async def on_user_joined(data):
    print(f"User joined: {data['user_name']}")

router.register_event_handler(EventType.USER_JOINED, on_user_joined)

# 触发事件
await router.trigger_event(EventType.USER_JOINED, {
    "user_id": "user123",
    "user_name": "John Doe"
})
```

---

## API 速查表

### 平台管理
| 方法 | 说明 |
|------|------|
| `create_dingtalk_platform()` | 创建钉钉平台 |
| `create_feishu_platform()` | 创建飞书平台 |
| `create_wechat_work_platform()` | 创建企业微信平台 |
| `get_platform(name)` | 获取平台实例 |
| `list_platforms()` | 列出所有平台 |
| `health_check_all()` | 检查所有平台健康状态 |

### 消息发送
| 方法 | 说明 |
|------|------|
| `send_message_to_platform()` | 发送文本消息 |
| `send_card_to_platform()` | 发送卡片消息 |
| `send_markdown_to_platform()` | 发送Markdown消息 |
| `send_message_to_all()` | 发送到多个平台 |

### 通讯录同步
| 方法 | 说明 |
|------|------|
| `sync_contacts_from_all()` | 同步所有平台通讯录 |
| `sync_departments_from_all()` | 同步所有平台部门 |
| `get_user_info_from_platform()` | 获取用户信息 |

### 审批流程
| 方法 | 说明 |
|------|------|
| `create_approval_on_platform()` | 创建审批 |
| `get_approval_status_from_platform()` | 查询审批状态 |

### 用户映射
| 方法 | 说明 |
|------|------|
| `map_user()` | 映射用户 |
| `get_platform_user_id()` | 获取平台用户ID |
| `get_internal_user_id()` | 获取内部用户ID |
| `bulk_sync_users()` | 批量同步用户 |

### 消息路由
| 方法 | 说明 |
|------|------|
| `route_message()` | 路由消息 |
| `broadcast_message()` | 广播消息 |
| `send_notification()` | 发送通知 |
| `trigger_event()` | 触发事件 |

---

## 错误处理

```python
try:
    success = await manager.send_message_to_platform(
        "dingtalk", "user123", "Hello"
    )
    if not success:
        print("Message delivery failed")
except Exception as e:
    print(f"Error: {e}")
    # 检查日志
    logs = router.get_delivery_log(limit=10)
    for log in logs:
        if not log["success"]:
            print(f"Failed: {log['error']}")
```

---

## 性能优化

### 批量操作
```python
# 批量发送 (推荐)
user_mappings = {
    "dingtalk": "user1",
    "feishu": "user2",
    "wechat_work": "user3"
}
results = await manager.send_message_to_all(user_mappings, "Hello")

# 而不是逐个发送
for platform, user_id in user_mappings.items():
    await manager.send_message_to_platform(platform, user_id, "Hello")
```

### 缓存策略
```python
# Access Token 自动缓存
platform = manager.get_platform("dingtalk")
# 第一次调用会获取token
await platform.send_message("user123", "Hello")
# 后续调用会使用缓存的token
await platform.send_message("user456", "Hello")
```

### 异步处理
```python
import asyncio

# 并发发送
tasks = [
    manager.send_message_to_platform("dingtalk", "user1", "Hello"),
    manager.send_message_to_platform("feishu", "user2", "Hello"),
    manager.send_message_to_platform("wechat_work", "user3", "Hello"),
]
results = await asyncio.gather(*tasks)
```

---

## 监控和统计

```python
# 消息投递统计
stats = router.get_delivery_stats()
print(f"Success rate: {stats['success_rate']:.2%}")

# 平台统计
platform_stats = router.get_platform_stats()
for platform, stat in platform_stats.items():
    print(f"{platform}: {stat['success']}/{stat['total']}")

# 用户映射统计
mapping_stats = user_mapping.get_mapping_stats()
print(f"Total users: {mapping_stats['total_users']}")
print(f"Platforms: {mapping_stats['platforms']}")

# 同步统计
sync_stats = user_mapping.get_sync_stats()
print(f"Sync success rate: {sync_stats['success_rate']:.2%}")
```

---

## 常见问题

### Q: 如何处理认证失败？
A: 检查凭证是否正确，使用 `health_check()` 验证连接：
```python
platform = manager.get_platform("dingtalk")
healthy = await platform.health_check()
if not healthy:
    print("Authentication failed")
```

### Q: 消息发送失败怎么办？
A: 检查投递日志找出失败原因：
```python
logs = router.get_delivery_log(limit=10)
for log in logs:
    if not log["success"]:
        print(f"Error: {log['error']}")
```

### Q: 如何同步大量用户？
A: 使用批量同步API：
```python
results = await user_mapping.bulk_sync_users(
    "dingtalk",
    users  # 列表，可包含1000+用户
)
print(f"Synced: {results['success']}/{results['total']}")
```

### Q: 支持哪些消息类型？
A: 支持 TEXT, MARKDOWN, CARD, IMAGE, FILE, LINK 六种类型。

### Q: 如何添加新平台？
A: 继承 `EnterpriseIMPlatform` 并实现所有抽象方法。

---

## 文件位置

```
backend/app/integrations/enterprise/
├── base.py                 # 基类
├── dingtalk.py             # 钉钉
├── feishu.py               # 飞书
├── wechat_work.py          # 企业微信
├── manager.py              # 管理器
├── message_router.py       # 路由器
└── user_mapping.py         # 用户映射

backend/app/api/
├── enterprise_im.py        # REST API
└── webhooks.py             # Webhook

tests/
└── test_enterprise_im.py   # 测试

docs/
└── ENTERPRISE_IM_INTEGRATION.md  # 完整文档
```

---

## 有用的链接

- 完整文档: `docs/ENTERPRISE_IM_INTEGRATION.md`
- 测试用例: `tests/test_enterprise_im.py`
- 集成报告: `企业协作平台集成报告.md`

---

**最后更新**: 2026-05-28
