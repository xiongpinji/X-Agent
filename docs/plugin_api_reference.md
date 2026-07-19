# X-Agent 插件 API 参考文档

## 目录

1. [核心接口](#核心接口)
2. [工具接口](#工具接口)
3. [集成接口](#集成接口)
4. [配置接口](#配置接口)
5. [生命周期接口](#生命周期接口)
6. [权限接口](#权限接口)
7. [错误处理](#错误处理)
8. [示例代码](#示例代码)

## 核心接口

### BasePlugin

所有插件的基类。

```python
class BasePlugin:
    """Base class for all X-Agent plugins"""
    
    # 属性
    name: str                          # 插件名称
    version: str                       # 版本号
    description: str                   # 描述
    author: str                        # 作者
    license: str                       # 许可证
    enabled: bool                      # 是否启用
    config: Optional[PluginConfig]     # 配置对象
    logger: logging.Logger             # 日志记录器
    
    # 生命周期方法
    async def initialize(self) -> None:
        """初始化插件
        
        在插件加载时调用，用于初始化资源、加载配置等。
        """
        pass
    
    async def register(self) -> None:
        """注册插件组件
        
        在初始化后调用，用于注册工具、集成等。
        """
        pass
    
    async def enable(self) -> None:
        """启用插件
        
        在插件被启用时调用。
        """
        pass
    
    async def disable(self) -> None:
        """禁用插件
        
        在插件被禁用时调用。
        """
        pass
    
    async def cleanup(self) -> None:
        """清理资源
        
        在插件卸载时调用，用于关闭连接、释放资源等。
        """
        pass
    
    # 组件注册方法
    def register_tool(self, tool: Tool) -> None:
        """注册工具
        
        Args:
            tool: Tool 实例
        """
        pass
    
    def register_integration(self, name: str, integration: Integration) -> None:
        """注册集成
        
        Args:
            name: 集成名称
            integration: Integration 实例
        """
        pass
    
    def register_command(self, command: str, handler: Callable) -> None:
        """注册命令
        
        Args:
            command: 命令名称
            handler: 命令处理函数
        """
        pass
    
    # 配置方法
    async def load_config(self) -> Dict[str, Any]:
        """加载配置
        
        Returns:
            配置字典
        """
        pass
    
    async def save_config(self, config: Dict[str, Any]) -> None:
        """保存配置
        
        Args:
            config: 配置字典
        """
        pass
```

## 工具接口

### Tool

所有工具的基类。

```python
class Tool:
    """Base class for tools"""
    
    # 属性
    name: str                          # 工具名称
    description: str                   # 描述
    category: str                      # 分类
    parameters: Dict[str, Any]         # 参数定义
    
    # 方法
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具
        
        Args:
            **kwargs: 工具参数
        
        Returns:
            执行结果
        """
        pass
    
    def validate(self, **kwargs) -> bool:
        """验证参数
        
        Args:
            **kwargs: 工具参数
        
        Returns:
            是否有效
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具 schema
        
        Returns:
            工具 schema
        """
        pass
```

### ToolParameter

工具参数定义。

```python
@dataclass
class ToolParameter:
    """Tool parameter definition"""
    
    name: str                          # 参数名称
    type: str                          # 参数类型 (string, number, boolean, array, object)
    description: str                   # 参数描述
    required: bool = False             # 是否必需
    default: Optional[Any] = None      # 默认值
    enum: Optional[List[Any]] = None   # 枚举值
    min_value: Optional[float] = None  # 最小值
    max_value: Optional[float] = None  # 最大值
    pattern: Optional[str] = None      # 正则表达式
```

## 集成接口

### Integration

所有集成的基类。

```python
class Integration:
    """Base class for integrations"""
    
    # 属性
    name: str                          # 集成名称
    description: str                   # 描述
    config: Optional[Dict[str, Any]]   # 配置
    
    # 方法
    async def connect(self) -> None:
        """连接到服务
        
        Raises:
            ConnectionError: 连接失败
        """
        pass
    
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    async def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """执行操作
        
        Args:
            action: 操作名称
            **kwargs: 操作参数
        
        Returns:
            操作结果
        
        Raises:
            ValueError: 无效的操作
            RuntimeError: 执行失败
        """
        pass
    
    def is_connected(self) -> bool:
        """检查连接状态
        
        Returns:
            是否已连接
        """
        pass
```

## 配置接口

### PluginConfig

插件配置。

```python
@dataclass
class PluginConfig:
    """Plugin configuration"""
    
    # 基本设置
    enabled: bool = True               # 是否启用
    debug: bool = False                # 调试模式
    
    # 服务设置
    api_key: Optional[str] = None      # API 密钥
    api_url: Optional[str] = None      # API URL
    timeout: int = 30                  # 超时时间（秒）
    
    # 高级设置
    retry_count: int = 3               # 重试次数
    retry_delay: int = 1               # 重试延迟（秒）
    cache_enabled: bool = True         # 缓存启用
    cache_ttl: int = 3600              # 缓存 TTL（秒）
    
    # 自定义设置
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """验证配置"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig":
        """从字典创建配置"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        pass
```

## 生命周期接口

### PluginLifecycle

插件生命周期管理。

```python
class PluginLifecycle:
    """Plugin lifecycle management"""
    
    async def on_load(self, plugin: BasePlugin) -> None:
        """插件加载时调用"""
        pass
    
    async def on_initialize(self, plugin: BasePlugin) -> None:
        """插件初始化时调用"""
        pass
    
    async def on_register(self, plugin: BasePlugin) -> None:
        """插件注册时调用"""
        pass
    
    async def on_enable(self, plugin: BasePlugin) -> None:
        """插件启用时调用"""
        pass
    
    async def on_disable(self, plugin: BasePlugin) -> None:
        """插件禁用时调用"""
        pass
    
    async def on_unload(self, plugin: BasePlugin) -> None:
        """插件卸载时调用"""
        pass
```

## 权限接口

### Permission

权限定义。

```python
@dataclass
class Permission:
    """Permission definition"""
    
    resource: str                      # 资源名称
    action: str                        # 操作名称
    description: str                   # 描述
    
    def __str__(self) -> str:
        """返回权限字符串 (resource:action)"""
        return f"{self.resource}:{self.action}"
```

### PermissionManager

权限管理器。

```python
class PermissionManager:
    """Permission management"""
    
    @staticmethod
    def has_permission(plugin_name: str, permission: str) -> bool:
        """检查权限
        
        Args:
            plugin_name: 插件名称
            permission: 权限字符串 (resource:action)
        
        Returns:
            是否有权限
        """
        pass
    
    @staticmethod
    def require_permission(permission: str) -> Callable:
        """权限装饰器
        
        Args:
            permission: 权限字符串
        
        Returns:
            装饰器函数
        """
        pass
```

## 错误处理

### 异常类

```python
class PluginError(Exception):
    """Base plugin error"""
    pass

class PluginInitializationError(PluginError):
    """Plugin initialization error"""
    pass

class PluginLoadError(PluginError):
    """Plugin load error"""
    pass

class ToolExecutionError(PluginError):
    """Tool execution error"""
    pass

class IntegrationError(PluginError):
    """Integration error"""
    pass

class PermissionError(PluginError):
    """Permission error"""
    pass

class ConfigurationError(PluginError):
    """Configuration error"""
    pass
```

## 示例代码

### 基础插件

```python
from xagent.plugins import BasePlugin, Tool

class HelloWorldPlugin(BasePlugin):
    name = "hello-world"
    version = "0.1.0"
    description = "Hello World plugin"
    author = "Your Name"
    license = "MIT"
    
    async def initialize(self) -> None:
        self.logger.info("Initializing Hello World plugin")
    
    async def register(self) -> None:
        self.register_tool(HelloTool())
    
    async def cleanup(self) -> None:
        self.logger.info("Cleaning up Hello World plugin")

class HelloTool(Tool):
    name = "hello"
    description = "Say hello"
    
    def __init__(self):
        super().__init__()
        self.parameters = {
            "name": {
                "type": "string",
                "description": "Name to greet",
                "required": True,
            }
        }
    
    async def execute(self, name: str, **kwargs) -> dict:
        return {"message": f"Hello, {name}!"}
```

### 集成插件

```python
from xagent.plugins import BasePlugin, Integration

class SlackPlugin(BasePlugin):
    name = "slack"
    version = "0.1.0"
    
    async def register(self) -> None:
        self.register_integration("slack", SlackIntegration())

class SlackIntegration(Integration):
    name = "slack"
    
    async def connect(self) -> None:
        # Initialize Slack client
        pass
    
    async def execute(self, action: str, **kwargs) -> dict:
        if action == "send_message":
            return await self._send_message(**kwargs)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _send_message(self, channel: str, text: str) -> dict:
        # Send message to Slack
        return {"status": "sent"}
```

---

最后更新: 2026-05-29
