# X-Agent 插件示例集合

本目录包含了多个 X-Agent 插件示例，展示了如何开发不同类型的插件。

## 示例插件列表

### 1. Hello World 插件 (`hello_world_plugin.py`)

**描述**: 最简单的插件示例，展示了基本的插件结构和生命周期。

**功能**:
- `hello`: 返回 "Hello, World!"
- `greet`: 问候指定的人

**适用场景**: 学习插件基础、快速入门

**代码示例**:
```python
from plugins.examples.hello_world_plugin import HelloWorldPlugin

plugin = HelloWorldPlugin()
await plugin.initialize()
await plugin.register()

result = await plugin.hello_tool()
# 输出: {"status": "success", "message": "Hello, World!"}
```

### 2. 数据库连接插件 (`database_plugin.py`)

**描述**: 展示了如何与数据库交互的插件。

**功能**:
- `connect`: 连接到数据库
- `disconnect`: 断开连接
- `execute_query`: 执行数据库查询
- `get_tables`: 获取表列表

**适用场景**: 数据库集成、数据查询、数据管理

**代码示例**:
```python
from plugins.examples.database_plugin import DatabaseConnectionPlugin

plugin = DatabaseConnectionPlugin()
await plugin.initialize()

result = await plugin.connect()
# 输出: {"status": "success", "message": "Connected to database"}

tables = await plugin.get_tables()
# 输出: {"status": "success", "tables": ["users", "workflows", "tasks"]}
```

### 3. API 集成插件 (`api_plugin.py`)

**描述**: 展示了如何与 REST API 交互的插件。

**功能**:
- `get`: 发送 GET 请求
- `post`: 发送 POST 请求
- `put`: 发送 PUT 请求
- `delete`: 发送 DELETE 请求

**适用场景**: REST API 集成、第三方服务调用、数据同步

**代码示例**:
```python
from plugins.examples.api_plugin import APIIntegrationPlugin

plugin = APIIntegrationPlugin()
await plugin.initialize()

result = await plugin.get("/users")
# 输出: {"status": "success", "status_code": 200, "data": {}}

result = await plugin.post("/users", data={"name": "John"})
# 输出: {"status": "success", "status_code": 201, "data": {}}
```

### 4. 自定义命令插件 (`custom_command_plugin.py`)

**描述**: 展示了如何创建自定义命令的插件。

**功能**:
- `echo`: 回显文本
- `calculate`: 计算表达式
- `transform`: 转换文本（大写、小写、反转等）

**适用场景**: 自定义命令、文本处理、计算

**代码示例**:
```python
from plugins.examples.custom_command_plugin import CustomCommandPlugin

plugin = CustomCommandPlugin()
await plugin.initialize()
await plugin.register()

result = await plugin.execute_command("echo", text="Hello")
# 输出: {"status": "success", "result": "Hello"}

result = await plugin.execute_command("calculate", expression="2+2")
# 输出: {"status": "success", "result": 4}

result = await plugin.execute_command("transform", text="hello", operation="upper")
# 输出: {"status": "success", "result": "HELLO"}
```

### 5. 数据处理插件 (`data_processing_plugin.py`)

**描述**: 展示了如何处理和转换数据的插件。

**功能**:
- `parse_json`: 解析 JSON 数据
- `parse_csv`: 解析 CSV 数据
- `filter_data`: 按条件过滤数据
- `aggregate_data`: 聚合数据
- `transform_data`: 转换数据结构

**适用场景**: 数据处理、数据转换、数据分析

**代码示例**:
```python
from plugins.examples.data_processing_plugin import DataProcessingPlugin

plugin = DataProcessingPlugin()
await plugin.initialize()

# 解析 JSON
result = await plugin.parse_json('{"name": "John", "age": 30}')
# 输出: {"status": "success", "data": {"name": "John", "age": 30}}

# 过滤数据
data = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
result = await plugin.filter_data(data, "name", "John")
# 输出: {"status": "success", "data": [...], "count": 1}
```

### 6. 通知插件 (`notification_plugin.py`)

**描述**: 展示了如何发送通知的插件。

**功能**:
- `send_email`: 发送邮件通知
- `send_slack`: 发送 Slack 消息
- `send_webhook`: 发送 Webhook
- `get_notifications`: 获取通知历史
- `clear_notifications`: 清除通知

**适用场景**: 通知系统、告警、消息推送

**代码示例**:
```python
from plugins.examples.notification_plugin import NotificationPlugin

plugin = NotificationPlugin()
await plugin.initialize()

# 发送邮件
result = await plugin.send_email(
    to="user@example.com",
    subject="Hello",
    body="This is a test email"
)
# 输出: {"status": "success", "message": "Email sent successfully", "notification_id": 0}

# 获取通知
result = await plugin.get_notifications(limit=10)
# 输出: {"status": "success", "notifications": [...], "count": 1}
```

## 快速开始

### 1. 安装依赖

```bash
pip install xagent-core
```

### 2. 导入插件

```python
from plugins.examples.hello_world_plugin import HelloWorldPlugin

plugin = HelloWorldPlugin()
```

### 3. 初始化和使用

```python
import asyncio

async def main():
    plugin = HelloWorldPlugin()
    await plugin.initialize()
    await plugin.register()
    
    result = await plugin.hello_tool()
    print(result)
    
    await plugin.cleanup()

asyncio.run(main())
```

## 插件开发指南

详见 `docs/plugin_development_guide.md`

## API 参考

详见 `docs/plugin_api_reference.md`

## 测试指南

详见 `docs/plugin_testing_guide.md`

## 常见问题

### Q: 如何创建自己的插件?

A: 使用 `plugins/templates/template_plugin.py` 作为模板，按照 `docs/plugin_development_guide.md` 中的步骤进行开发。

### Q: 如何测试插件?

A: 参考 `docs/plugin_testing_guide.md` 中的测试指南。

### Q: 如何发布插件?

A: 参考 `docs/plugin_development_guide.md` 中的发布和分发部分。

### Q: 如何调试插件?

A: 使用日志记录和 pytest 进行调试。详见 `docs/plugin_testing_guide.md`。

## 许可证

所有示例插件均采用 MIT 许可证。

---

最后更新: 2026-05-29
