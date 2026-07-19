# X-Agent 插件模板

本目录包含了 X-Agent 插件开发的模板和最佳实践示例。

## 文件说明

### `template_plugin.py`

这是一个完整的插件模板，包含了所有必要的方法和注释。

**使用步骤**:

1. 复制 `template_plugin.py` 到你的项目目录
2. 重命名为你的插件名称（例如 `my_plugin.py`）
3. 修改类名和元数据
4. 实现你的插件逻辑

**模板结构**:

```python
class TemplatePlugin:
    # 元数据
    name = "template-plugin"
    version = "0.1.0"
    description = "A template plugin for X-Agent"
    author = "Your Name"
    license = "MIT"
    
    # 生命周期方法
    async def initialize(self) -> None:
        """初始化插件"""
        pass
    
    async def register(self) -> None:
        """注册组件"""
        pass
    
    async def cleanup(self) -> None:
        """清理资源"""
        pass
    
    # 工具方法
    async def my_tool(self, **kwargs) -> Dict[str, Any]:
        """你的工具实现"""
        pass
    
    # 集成方法
    async def my_service(self, action: str, **kwargs) -> Dict[str, Any]:
        """你的集成实现"""
        pass
```

## 最佳实践

### 1. 命名约定

- 插件名称: 使用小写字母和连字符 (例如 `my-plugin`)
- 类名: 使用 PascalCase (例如 `MyPlugin`)
- 方法名: 使用 snake_case (例如 `my_method`)
- 文件名: 使用 snake_case (例如 `my_plugin.py`)

### 2. 元数据

始终提供完整的元数据:

```python
class MyPlugin:
    name = "my-plugin"              # 必需
    version = "0.1.0"               # 必需
    description = "..."             # 必需
    author = "Your Name"            # 推荐
    license = "MIT"                 # 推荐
```

### 3. 生命周期管理

实现所有生命周期方法:

```python
async def initialize(self) -> None:
    """加载配置、初始化资源"""
    pass

async def register(self) -> None:
    """注册工具、集成等"""
    pass

async def cleanup(self) -> None:
    """关闭连接、释放资源"""
    pass
```

### 4. 错误处理

始终处理异常并返回结构化的错误响应:

```python
try:
    # 你的逻辑
    return {"status": "success", "result": result}
except Exception as e:
    logger.error(f"Error: {e}")
    return {"status": "error", "message": str(e)}
```

### 5. 日志记录

使用日志记录而不是 print:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Plugin initialized")
logger.error("An error occurred")
```

### 6. 类型提示

使用类型提示提高代码质量:

```python
async def my_method(self, param: str) -> Dict[str, Any]:
    """Method with type hints"""
    pass
```

### 7. 文档字符串

为所有公共方法编写文档字符串:

```python
async def my_method(self, param: str) -> Dict[str, Any]:
    """Short description
    
    Longer description if needed.
    
    Args:
        param: Parameter description
    
    Returns:
        Return value description
    """
    pass
```

## 创建新插件

### 步骤 1: 复制模板

```bash
cp template_plugin.py my_plugin.py
```

### 步骤 2: 修改元数据

```python
class MyPlugin:
    name = "my-plugin"
    version = "0.1.0"
    description = "My custom plugin"
    author = "Your Name"
    license = "MIT"
```

### 步骤 3: 实现初始化

```python
async def initialize(self) -> None:
    logger.info(f"Initializing {self.name}")
    
    # 加载配置
    self.config = {
        "key": "value"
    }
    
    # 初始化资源
    # await self._init_resources()
    
    self.enabled = True
```

### 步骤 4: 注册组件

```python
async def register(self) -> None:
    logger.info("Registering components")
    
    # 注册工具
    self.tools["my_tool"] = self.my_tool
    
    # 注册集成
    self.integrations["my_service"] = self.my_service
```

### 步骤 5: 实现工具和集成

```python
async def my_tool(self, **kwargs) -> Dict[str, Any]:
    """My tool implementation"""
    try:
        # 你的逻辑
        return {"status": "success", "result": "..."}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error", "message": str(e)}
```

### 步骤 6: 实现清理

```python
async def cleanup(self) -> None:
    logger.info(f"Cleaning up {self.name}")
    
    # 关闭连接
    # await self._cleanup_resources()
    
    self.enabled = False
```

## 测试你的插件

### 创建测试文件

```python
import pytest
from my_plugin import MyPlugin

@pytest.fixture
def plugin():
    return MyPlugin()

@pytest.mark.asyncio
async def test_initialization(plugin):
    await plugin.initialize()
    assert plugin.enabled is True

@pytest.mark.asyncio
async def test_my_tool(plugin):
    await plugin.initialize()
    result = await plugin.my_tool()
    assert result["status"] == "success"
```

### 运行测试

```bash
pytest tests/test_my_plugin.py
```

## 发布你的插件

1. 创建 GitHub 仓库
2. 添加 `xagent-plugin` 标签
3. 在 `plugin.manifest.json` 中填写完整信息
4. 提交到 X-Agent 插件市场

## 常见问题

### Q: 如何访问配置?

A: 在 `initialize` 方法中加载配置:

```python
async def initialize(self) -> None:
    self.config = {
        "api_key": os.getenv("API_KEY"),
        "api_url": "https://api.example.com"
    }
```

### Q: 如何处理异步操作?

A: 使用 async/await:

```python
async def my_tool(self, **kwargs) -> Dict[str, Any]:
    result = await some_async_function()
    return {"status": "success", "result": result}
```

### Q: 如何记录日志?

A: 使用 logging 模块:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error")
```

### Q: 如何处理错误?

A: 使用 try-except 并返回错误响应:

```python
try:
    # 你的逻辑
    return {"status": "success"}
except Exception as e:
    logger.error(f"Error: {e}")
    return {"status": "error", "message": str(e)}
```

## 资源

- [插件开发指南](../docs/plugin_development_guide.md)
- [API 参考](../docs/plugin_api_reference.md)
- [测试指南](../docs/plugin_testing_guide.md)
- [示例插件](../examples/)

---

最后更新: 2026-05-29
