# X-Agent 插件开发指南

**版本**: 1.0.0  
**日期**: 2026-05-27  
**目标受众**: 插件开发者

---

## 目录

1. [快速开始](#快速开始)
2. [插件基础](#插件基础)
3. [开发工具](#开发工具)
4. [插件类型](#插件类型)
5. [最佳实践](#最佳实践)
6. [测试和调试](#测试和调试)
7. [发布和分发](#发布和分发)
8. [常见问题](#常见问题)

---

## 快速开始

### 1. 安装 SDK

```bash
# 使用 pip 安装
pip install xagent-sdk

# 或从源代码安装
git clone https://github.com/x-agent/xagent-sdk.git
cd xagent-sdk
pip install -e .
```

### 2. 创建第一个插件

```bash
# 使用 CLI 创建项目
xagent-cli create-plugin my-first-plugin

# 进入项目目录
cd my-first-plugin

# 查看项目结构
tree
```

### 3. 项目结构

```
my-first-plugin/
├── plugin.py              # 插件主文件
├── manifest.json          # 插件清单
├── requirements.txt       # 依赖列表
├── tests/
│   └── test_plugin.py     # 测试文件
├── examples/
│   └── usage.py           # 使用示例
└── README.md              # 文档
```

### 4. 编写插件

```python
# plugin.py
from xagent_sdk import XAgentPlugin, tool

class MyFirstPlugin(XAgentPlugin):
    """我的第一个插件"""
    
    @property
    def plugin_id(self) -> str:
        return "my-first-plugin"
    
    @property
    def plugin_name(self) -> str:
        return "My First Plugin"
    
    @property
    def plugin_version(self) -> str:
        return "1.0.0"
    
    async def initialize(self, config):
        """初始化插件"""
        print(f"Initializing {self.plugin_name}")
    
    async def shutdown(self):
        """关闭插件"""
        print(f"Shutting down {self.plugin_name}")
    
    def get_capabilities(self):
        """获取能力列表"""
        return ["tool:execute"]
    
    async def execute(self, action, params):
        """执行动作"""
        if action == "greet":
            return {"message": f"Hello, {params.get('name', 'World')}!"}
        raise ValueError(f"Unknown action: {action}")
    
    def validate_config(self, config):
        """验证配置"""
        return True
```

### 5. 测试插件

```bash
# 运行测试
pytest tests/

# 本地运行插件
xagent-cli run-plugin plugin.py

# 验证插件
xagent-cli validate-plugin plugin.py
```

---

## 插件基础

### 1. 插件生命周期

#### 初始化阶段

```python
async def initialize(self, config: Dict[str, Any]) -> None:
    """
    插件初始化
    
    Args:
        config: 插件配置字典
    
    Raises:
        PluginInitializationError: 初始化失败
    """
    # 验证配置
    if not self.validate_config(config):
        raise PluginInitializationError("Invalid configuration")
    
    # 初始化资源
    self.config = config
    self.logger = get_logger(self.plugin_id)
    
    # 连接外部服务
    await self._connect_services()
```

#### 执行阶段

```python
async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行插件动作
    
    Args:
        action: 动作名称
        params: 动作参数
    
    Returns:
        执行结果
    
    Raises:
        PluginExecutionError: 执行失败
    """
    if action not in self.get_capabilities():
        raise PluginExecutionError(f"Unknown action: {action}")
    
    try:
        result = await self._execute_action(action, params)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

#### 关闭阶段

```python
async def shutdown(self) -> None:
    """
    插件关闭
    
    清理资源、关闭连接等
    """
    # 断开连接
    await self._disconnect_services()
    
    # 清理资源
    self.logger.info(f"Plugin {self.plugin_id} shutdown")
```

### 2. 配置管理

#### 配置文件格式

```json
{
  "plugin_id": "my-plugin",
  "settings": {
    "timeout": 30,
    "retry_count": 3,
    "log_level": "INFO"
  },
  "credentials": {
    "api_key": "${PLUGIN_API_KEY}",
    "api_secret": "${PLUGIN_API_SECRET}"
  }
}
```

#### 配置验证

```python
def validate_config(self, config: Dict[str, Any]) -> bool:
    """验证配置"""
    required_fields = ["api_key", "api_secret"]
    
    for field in required_fields:
        if field not in config:
            self.logger.error(f"Missing required field: {field}")
            return False
    
    # 验证字段类型
    if not isinstance(config.get("timeout"), int):
        self.logger.error("timeout must be an integer")
        return False
    
    return True
```

### 3. 错误处理

```python
from xagent_sdk.exceptions import (
    PluginError,
    PluginInitializationError,
    PluginExecutionError,
    PluginValidationError,
)

class MyPlugin(XAgentPlugin):
    async def execute(self, action, params):
        try:
            # 执行动作
            result = await self._do_something(params)
            return result
        except ValueError as e:
            raise PluginValidationError(f"Invalid parameter: {e}")
        except ConnectionError as e:
            raise PluginExecutionError(f"Connection failed: {e}")
        except Exception as e:
            raise PluginError(f"Unexpected error: {e}")
```

---

## 开发工具

### 1. SDK 组件

#### 1.1 装饰器

```python
from xagent_sdk import tool, workflow_node, event_handler

# 工具装饰器
@tool(
    name="my_tool",
    description="My custom tool",
    category="utility",
    tags=["example"]
)
async def my_tool(param1: str, param2: int) -> str:
    """工具实现"""
    return f"Result: {param1} - {param2}"

# 工作流节点装饰器
@workflow_node(
    name="my_node",
    description="My custom node",
    node_type="custom"
)
async def my_node(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """节点实现"""
    return {"output": input_data}

# 事件处理器装饰器
@event_handler(event_type="workflow:completed")
async def on_workflow_completed(event: Dict[str, Any]) -> None:
    """处理工作流完成事件"""
    print(f"Workflow completed: {event}")
```

#### 1.2 日志记录

```python
from xagent_sdk import get_logger

logger = get_logger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

#### 1.3 配置管理

```python
from xagent_sdk import get_config

# 获取配置
config = get_config()

# 获取特定配置
api_key = config.get("api_key")
timeout = config.get("timeout", default=30)

# 设置配置
config.set("my_setting", "value")
```

### 2. CLI 工具

```bash
# 创建新插件
xagent-cli create-plugin <plugin-name>

# 验证插件
xagent-cli validate-plugin <plugin-path>

# 本地运行插件
xagent-cli run-plugin <plugin-path>

# 打包插件
xagent-cli package-plugin <plugin-path>

# 发布插件
xagent-cli publish-plugin <plugin-path>

# 测试插件
xagent-cli test-plugin <plugin-path>

# 生成文档
xagent-cli generate-docs <plugin-path>
```

### 3. 开发环境

#### 3.1 Docker 开发环境

```dockerfile
FROM python:3.11-slim

WORKDIR /workspace

# 安装依赖
RUN pip install xagent-sdk pytest pytest-asyncio

# 复制代码
COPY . .

# 运行测试
CMD ["pytest"]
```

#### 3.2 开发配置

```yaml
# .xagent-dev.yml
development:
  debug: true
  log_level: DEBUG
  hot_reload: true
  
testing:
  mock_external_services: true
  test_timeout: 30
  
plugins:
  - path: ./plugin.py
    config: ./config.dev.json
```

---

## 插件类型

### 1. 工具提供者插件

```python
from xagent_sdk import ToolProvider, tool

class MyToolProvider(ToolProvider):
    """提供自定义工具的插件"""
    
    def get_tools(self):
        """返回提供的工具列表"""
        return [
            {
                "id": "tool1",
                "name": "Tool 1",
                "description": "First tool",
                "schema": {...}
            },
            {
                "id": "tool2",
                "name": "Tool 2",
                "description": "Second tool",
                "schema": {...}
            }
        ]
    
    async def execute_tool(self, tool_id, params):
        """执行工具"""
        if tool_id == "tool1":
            return await self._execute_tool1(params)
        elif tool_id == "tool2":
            return await self._execute_tool2(params)
    
    def get_tool_schema(self, tool_id):
        """获取工具的JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "integer"}
            },
            "required": ["param1"]
        }
```

### 2. 工作流扩展插件

```python
from xagent_sdk import WorkflowExtension

class MyWorkflowExtension(WorkflowExtension):
    """扩展工作流功能的插件"""
    
    def get_node_types(self):
        """返回支持的节点类型"""
        return ["custom_node", "decision_node"]
    
    async def execute_node(self, node_type, node_config):
        """执行工作流节点"""
        if node_type == "custom_node":
            return await self._execute_custom_node(node_config)
        elif node_type == "decision_node":
            return await self._execute_decision_node(node_config)
    
    def get_node_schema(self, node_type):
        """获取节点的JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "config": {"type": "object"}
            }
        }
```

### 3. 集成插件

```python
from xagent_sdk import IntegrationPlugin

class SlackIntegration(IntegrationPlugin):
    """Slack集成插件"""
    
    async def connect(self, config):
        """连接到Slack"""
        self.token = config.get("slack_token")
        self.client = WebClient(token=self.token)
    
    async def send_event(self, event):
        """发送事件到Slack"""
        channel = event.get("channel")
        text = event.get("text")
        await self.client.chat_postMessage(
            channel=channel,
            text=text
        )
    
    async def receive_event(self):
        """从Slack接收事件"""
        # 实现事件接收逻辑
        pass
```

### 4. 中间件插件

```python
from xagent_sdk import MiddlewarePlugin

class AuthMiddleware(MiddlewarePlugin):
    """认证中间件插件"""
    
    async def process_request(self, request):
        """处理请求"""
        # 验证认证信息
        token = request.headers.get("Authorization")
        if not self._validate_token(token):
            raise UnauthorizedError("Invalid token")
        return request
    
    async def process_response(self, response):
        """处理响应"""
        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
```

---

## 最佳实践

### 1. 代码质量

#### 1.1 类型提示

```python
from typing import Dict, List, Optional, Any

async def execute(
    self,
    action: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """使用类型提示提高代码质量"""
    pass
```

#### 1.2 文档字符串

```python
def get_capabilities(self) -> List[str]:
    """
    获取插件能力列表
    
    Returns:
        能力列表，例如 ["tool:execute", "workflow:extend"]
    
    Examples:
        >>> plugin = MyPlugin()
        >>> capabilities = plugin.get_capabilities()
        >>> print(capabilities)
        ['tool:execute']
    """
    return ["tool:execute"]
```

#### 1.3 错误处理

```python
async def execute(self, action, params):
    """执行动作，包含完整的错误处理"""
    try:
        # 验证输入
        if not isinstance(params, dict):
            raise PluginValidationError("params must be a dict")
        
        # 执行动作
        result = await self._do_action(action, params)
        
        # 验证输出
        if not isinstance(result, dict):
            raise PluginExecutionError("result must be a dict")
        
        return result
    
    except PluginError:
        raise
    except Exception as e:
        self.logger.error(f"Unexpected error: {e}", exc_info=True)
        raise PluginError(f"Execution failed: {e}")
```

### 2. 性能优化

#### 2.1 异步编程

```python
import asyncio

async def execute(self, action, params):
    """使用异步编程提高性能"""
    # 并发执行多个任务
    results = await asyncio.gather(
        self._fetch_data1(),
        self._fetch_data2(),
        self._fetch_data3()
    )
    return {"results": results}
```

#### 2.2 缓存

```python
from functools import lru_cache

class MyPlugin(XAgentPlugin):
    @lru_cache(maxsize=128)
    def _get_config_value(self, key):
        """缓存配置值"""
        return self.config.get(key)
```

#### 2.3 连接池

```python
from aiohttp import ClientSession

class MyPlugin(XAgentPlugin):
    async def initialize(self, config):
        """使用连接池"""
        self.session = ClientSession()
    
    async def shutdown(self):
        """关闭连接池"""
        await self.session.close()
```

### 3. 安全性

#### 3.1 输入验证

```python
from pydantic import BaseModel, Field, validator

class ToolParams(BaseModel):
    """工具参数模型"""
    name: str = Field(..., min_length=1, max_length=100)
    count: int = Field(..., ge=1, le=1000)
    
    @validator('name')
    def name_must_be_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError('name must be alphanumeric')
        return v

async def execute(self, action, params):
    """验证输入"""
    try:
        validated_params = ToolParams(**params)
        return await self._execute_tool(validated_params)
    except ValueError as e:
        raise PluginValidationError(f"Invalid parameters: {e}")
```

#### 3.2 敏感信息处理

```python
import os
from dotenv import load_dotenv

class MyPlugin(XAgentPlugin):
    async def initialize(self, config):
        """安全地处理敏感信息"""
        # 从环境变量读取敏感信息
        api_key = os.getenv("PLUGIN_API_KEY")
        if not api_key:
            raise PluginInitializationError("API_KEY not set")
        
        # 不要在日志中输出敏感信息
        self.logger.info("Plugin initialized with API key")
        # 不要这样做: self.logger.info(f"API key: {api_key}")
```

#### 3.3 权限检查

```python
class MyPlugin(XAgentPlugin):
    async def execute(self, action, params):
        """检查权限"""
        required_permission = self._get_required_permission(action)
        
        if not self._has_permission(required_permission):
            raise PluginExecutionError(
                f"Permission denied: {required_permission}"
            )
        
        return await self._execute_action(action, params)
```

---

## 测试和调试

### 1. 单元测试

```python
# tests/test_plugin.py
import pytest
from plugin import MyPlugin

@pytest.fixture
async def plugin():
    """创建插件实例"""
    plugin = MyPlugin()
    await plugin.initialize({"timeout": 30})
    yield plugin
    await plugin.shutdown()

@pytest.mark.asyncio
async def test_execute_greet(plugin):
    """测试greet动作"""
    result = await plugin.execute("greet", {"name": "World"})
    assert result["success"] is True
    assert "Hello, World!" in result["data"]["message"]

@pytest.mark.asyncio
async def test_execute_unknown_action(plugin):
    """测试未知动作"""
    with pytest.raises(PluginExecutionError):
        await plugin.execute("unknown", {})
```

### 2. 集成测试

```python
# tests/test_integration.py
import pytest
from xagent_sdk import XAgentClient

@pytest.mark.asyncio
async def test_plugin_integration():
    """测试插件集成"""
    client = XAgentClient()
    
    # 加载插件
    plugin = await client.load_plugin("my-plugin")
    
    # 执行动作
    result = await plugin.execute("greet", {"name": "Integration"})
    
    # 验证结果
    assert result["success"] is True
```

### 3. 调试技巧

#### 3.1 日志调试

```python
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

async def execute(self, action, params):
    """使用日志调试"""
    logger.debug(f"Executing action: {action}")
    logger.debug(f"Parameters: {params}")
    
    result = await self._do_action(action, params)
    
    logger.debug(f"Result: {result}")
    return result
```

#### 3.2 断点调试

```python
# 使用 pdb 调试
import pdb

async def execute(self, action, params):
    """使用断点调试"""
    pdb.set_trace()  # 在这里设置断点
    result = await self._do_action(action, params)
    return result
```

#### 3.3 性能分析

```python
import cProfile
import pstats

def profile_execute():
    """性能分析"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 执行代码
    asyncio.run(plugin.execute("action", {}))
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

---

## 发布和分发

### 1. 准备发布

#### 1.1 检查清单

- [ ] 代码通过所有测试
- [ ] 文档完整
- [ ] 版本号已更新
- [ ] CHANGELOG 已更新
- [ ] 许可证已设置
- [ ] 依赖已列出

#### 1.2 版本号

遵循语义化版本 (Semantic Versioning):
- MAJOR: 不兼容的API变更
- MINOR: 向后兼容的功能添加
- PATCH: 向后兼容的bug修复

### 2. 打包插件

```bash
# 打包插件
xagent-cli package-plugin my-plugin

# 验证包
xagent-cli validate-package my-plugin.xpkg

# 生成校验和
sha256sum my-plugin.xpkg > my-plugin.xpkg.sha256
```

### 3. 发布到市场

```bash
# 登录市场
xagent-cli login

# 发布插件
xagent-cli publish-plugin my-plugin.xpkg

# 查看发布状态
xagent-cli plugin-status my-plugin
```

### 4. 版本更新

```bash
# 更新插件版本
xagent-cli update-plugin my-plugin --version 1.1.0

# 发布更新
xagent-cli publish-plugin my-plugin.xpkg --update
```

---

## 常见问题

### Q1: 如何调试插件中的异步问题?

A: 使用 `asyncio.run()` 和日志记录来追踪异步执行流程。

```python
import asyncio

async def debug_async():
    logger.debug("Starting async operation")
    result = await some_async_operation()
    logger.debug(f"Async operation completed: {result}")
    return result

asyncio.run(debug_async())
```

### Q2: 如何处理插件中的超时?

A: 使用 `asyncio.wait_for()` 设置超时。

```python
import asyncio

async def execute_with_timeout(self, action, params):
    try:
        result = await asyncio.wait_for(
            self._do_action(action, params),
            timeout=30
        )
        return result
    except asyncio.TimeoutError:
        raise PluginExecutionError("Operation timed out")
```

### Q3: 如何在插件中使用外部库?

A: 在 `requirements.txt` 中列出依赖，并在 `initialize()` 中导入。

```python
# requirements.txt
requests>=2.28.0
aiohttp>=3.8.0

# plugin.py
async def initialize(self, config):
    import requests
    import aiohttp
    self.requests = requests
    self.aiohttp = aiohttp
```

### Q4: 如何处理插件中的并发请求?

A: 使用 `asyncio.gather()` 或 `asyncio.create_task()`。

```python
async def execute(self, action, params):
    if action == "parallel_requests":
        results = await asyncio.gather(
            self._request1(),
            self._request2(),
            self._request3()
        )
        return {"results": results}
```

### Q5: 如何测试插件的权限检查?

A: 创建模拟的权限上下文进行测试。

```python
@pytest.mark.asyncio
async def test_permission_denied(plugin):
    """测试权限拒绝"""
    with pytest.raises(PluginExecutionError):
        await plugin.execute("restricted_action", {})
```

---

## 更多资源

- [API 参考](./API_REFERENCE.md)
- [示例代码](./examples/)
- [社区论坛](https://forum.x-agent.io)
- [GitHub 讨论](https://github.com/x-agent/x-agent-core/discussions)

