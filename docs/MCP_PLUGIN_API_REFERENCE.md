# MCP插件API参考 v1.0

## 概述

本文档提供了X-Agent MCP插件系统的完整API参考。

## 目录

1. [MCPPluginAdapter](#mcppluginadapter)
2. [MCPManifest](#mcpmanifest)
3. [MCPPlugin](#mcpplugin)
4. [错误处理](#错误处理)
5. [工具调用](#工具调用)
6. [资源访问](#资源访问)

## MCPPluginAdapter

### 概述

`MCPPluginAdapter`是MCP插件系统的核心类，负责加载、验证、管理和执行MCP插件。

### 类定义

```python
class MCPPluginAdapter:
    def __init__(self, plugins_dir: str | Path | None = None)
    def load_manifest(self, plugin_path: str | Path) -> MCPManifest
    def validate_manifest(self, manifest: MCPManifest) -> tuple[bool, list[str]]
    def check_compatibility(self, manifest: MCPManifest, xagent_version: str = "0.1.0") -> tuple[bool, list[str]]
    def load_plugin(self, plugin_path: str | Path) -> MCPPlugin
    def start_server(self, plugin: MCPPlugin) -> bool
    def stop_server(self, plugin: MCPPlugin) -> bool
    def call_tool(self, plugin: MCPPlugin, tool_name: str, args: dict[str, Any]) -> Any
    def get_resources(self, plugin: MCPPlugin) -> list[dict[str, Any]]
    def get_tools(self, plugin: MCPPlugin) -> list[dict[str, Any]]
    def update_config(self, plugin: MCPPlugin, config: dict[str, Any]) -> bool
    def get_plugin(self, plugin_id: str) -> Optional[MCPPlugin]
    def list_plugins(self) -> list[MCPPlugin]
    def unload_plugin(self, plugin_id: str) -> bool
```

### 方法详解

#### `__init__(plugins_dir: str | Path | None = None)`

初始化MCP插件适配器。

**参数**：
- `plugins_dir` (str | Path | None)：插件目录路径。如果为None，使用默认路径 `./plugins`

**示例**：
```python
adapter = MCPPluginAdapter("/path/to/plugins")
```

#### `load_manifest(plugin_path: str | Path) -> MCPManifest`

加载并解析插件的manifest.json文件。

**参数**：
- `plugin_path` (str | Path)：插件目录路径

**返回**：
- `MCPManifest`：解析后的manifest对象

**异常**：
- `FileNotFoundError`：manifest文件不存在
- `ValueError`：manifest格式无效

**示例**：
```python
manifest = adapter.load_manifest("/path/to/plugin")
print(manifest.name)  # 输出插件名称
```

#### `validate_manifest(manifest: MCPManifest) -> tuple[bool, list[str]]`

验证manifest是否符合规范。

**参数**：
- `manifest` (MCPManifest)：要验证的manifest对象

**返回**：
- `tuple[bool, list[str]]`：(是否有效, 错误列表)

**示例**：
```python
is_valid, errors = adapter.validate_manifest(manifest)
if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
```

#### `check_compatibility(manifest: MCPManifest, xagent_version: str = "0.1.0") -> tuple[bool, list[str]]`

检查插件与X-Agent版本的兼容性。

**参数**：
- `manifest` (MCPManifest)：插件manifest
- `xagent_version` (str)：X-Agent版本号

**返回**：
- `tuple[bool, list[str]]`：(是否兼容, 警告列表)

**示例**：
```python
is_compatible, warnings = adapter.check_compatibility(manifest, "0.1.0")
if not is_compatible:
    print("Plugin is not compatible with this X-Agent version")
```

#### `load_plugin(plugin_path: str | Path) -> MCPPlugin`

加载插件。

**参数**：
- `plugin_path` (str | Path)：插件目录路径

**返回**：
- `MCPPlugin`：加载的插件实例

**异常**：
- `ValueError`：插件无效或不兼容

**示例**：
```python
plugin = adapter.load_plugin("/path/to/plugin")
print(f"Loaded plugin: {plugin.manifest.name}")
```

#### `start_server(plugin: MCPPlugin) -> bool`

启动插件的MCP服务器。

**参数**：
- `plugin` (MCPPlugin)：要启动的插件

**返回**：
- `bool`：是否成功启动

**示例**：
```python
success = adapter.start_server(plugin)
if success:
    print("Plugin server started")
```

#### `stop_server(plugin: MCPPlugin) -> bool`

停止插件的MCP服务器。

**参数**：
- `plugin` (MCPPlugin)：要停止的插件

**返回**：
- `bool`：是否成功停止

**示例**：
```python
success = adapter.stop_server(plugin)
if success:
    print("Plugin server stopped")
```

#### `call_tool(plugin: MCPPlugin, tool_name: str, args: dict[str, Any]) -> Any`

调用插件提供的工具。

**参数**：
- `plugin` (MCPPlugin)：插件实例
- `tool_name` (str)：工具名称
- `args` (dict[str, Any])：工具参数

**返回**：
- `Any`：工具执行结果

**异常**：
- `RuntimeError`：插件未运行
- `ValueError`：工具不存在

**示例**：
```python
result = adapter.call_tool(plugin, "list_repositories", {"username": "torvalds"})
print(result)
```

#### `get_resources(plugin: MCPPlugin) -> list[dict[str, Any]]`

获取插件提供的资源列表。

**参数**：
- `plugin` (MCPPlugin)：插件实例

**返回**：
- `list[dict[str, Any]]`：资源列表

**示例**：
```python
resources = adapter.get_resources(plugin)
for resource in resources:
    print(f"Resource: {resource['uri']}")
```

#### `get_tools(plugin: MCPPlugin) -> list[dict[str, Any]]`

获取插件提供的工具列表。

**参数**：
- `plugin` (MCPPlugin)：插件实例

**返回**：
- `list[dict[str, Any]]`：工具列表

**示例**：
```python
tools = adapter.get_tools(plugin)
for tool in tools:
    print(f"Tool: {tool['name']}")
```

#### `update_config(plugin: MCPPlugin, config: dict[str, Any]) -> bool`

更新插件配置。

**参数**：
- `plugin` (MCPPlugin)：插件实例
- `config` (dict[str, Any])：新配置

**返回**：
- `bool`：是否成功更新

**示例**：
```python
success = adapter.update_config(plugin, {"timeout": 60})
if success:
    print("Config updated")
```

#### `get_plugin(plugin_id: str) -> Optional[MCPPlugin]`

根据ID获取插件。

**参数**：
- `plugin_id` (str)：插件ID

**返回**：
- `Optional[MCPPlugin]`：插件实例或None

**示例**：
```python
plugin = adapter.get_plugin("plugin-id-123")
if plugin:
    print(f"Found plugin: {plugin.manifest.name}")
```

#### `list_plugins() -> list[MCPPlugin]`

列出所有已加载的插件。

**返回**：
- `list[MCPPlugin]`：插件列表

**示例**：
```python
plugins = adapter.list_plugins()
for plugin in plugins:
    print(f"Plugin: {plugin.manifest.name} ({plugin.status})")
```

#### `unload_plugin(plugin_id: str) -> bool`

卸载插件。

**参数**：
- `plugin_id` (str)：插件ID

**返回**：
- `bool`：是否成功卸载

**示例**：
```python
success = adapter.unload_plugin("plugin-id-123")
if success:
    print("Plugin unloaded")
```

## MCPManifest

### 概述

`MCPManifest`是插件清单的数据模型，包含插件的所有元数据。

### 类定义

```python
class MCPManifest(BaseModel):
    schema_version: str
    name: str
    version: str
    type: str = "mcp-plugin"
    xagent_compatibility: dict[str, str]
    metadata: dict[str, Any]
    chinese: dict[str, Any]
    capabilities: MCPCapability
    permissions: MCPPermission
    entry_point: MCPEntryPoint
    dependencies: dict[str, Any]
    configuration: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    security: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
```

### 属性详解

#### `schema_version: str`

Manifest规范版本。必须为 "1.0"。

#### `name: str`

插件唯一标识符。必须匹配正则表达式 `^[a-z0-9-]+$`。

#### `version: str`

插件版本号。必须遵循语义版本号规范（如 1.0.0）。

#### `type: str`

插件类型。必须为 "mcp-plugin"。

#### `xagent_compatibility: dict[str, str]`

X-Agent兼容性版本范围。

```python
{
    "min_version": "0.1.0",
    "max_version": "1.0.0"
}
```

#### `metadata: dict[str, Any]`

插件元数据。

```python
{
    "display_name": "插件显示名称",
    "description": "插件描述",
    "author": "作者名称",
    "license": "MIT"
}
```

#### `chinese: dict[str, Any]`

中文化内容。

```python
{
    "name": "插件中文名",
    "description": "中文描述",
    "usage": "使用说明"
}
```

#### `capabilities: MCPCapability`

插件能力声明。

```python
{
    "tools": True,
    "resources": True,
    "prompts": False
}
```

#### `permissions: MCPPermission`

权限声明。

```python
{
    "network": {"required": True, "domains": ["api.example.com"]},
    "filesystem": {"required": False, "paths": []},
    "environment": {"required": False, "variables": []}
}
```

#### `entry_point: MCPEntryPoint`

插件入口点。

```python
{
    "type": "python",
    "module": "main",
    "class": "PluginServer"
}
```

#### `dependencies: dict[str, Any]`

依赖声明。

```python
{
    "python": ">=3.11",
    "packages": {
        "requests": ">=2.31.0"
    }
}
```

#### `configuration: dict[str, Any]`

配置参数定义。

```python
{
    "api_key": {
        "type": "string",
        "required": True,
        "secret": True
    }
}
```

#### `tools: list[dict[str, Any]]`

工具定义列表。

#### `resources: list[dict[str, Any]]`

资源定义列表。

#### `security: dict[str, Any]`

安全配置。

```python
{
    "sandbox": True,
    "max_memory_mb": 512,
    "timeout_seconds": 300
}
```

#### `quality_metrics: dict[str, Any]`

质量指标。

```python
{
    "code_quality_score": 8.5,
    "test_coverage": 85
}
```

## MCPPlugin

### 概述

`MCPPlugin`是插件实例的数据模型。

### 类定义

```python
@dataclass
class MCPPlugin:
    plugin_id: str
    manifest: MCPManifest
    plugin_path: Path
    status: MCPPluginStatus
    process: Optional[subprocess.Popen]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str]
```

### 属性详解

#### `plugin_id: str`

插件的唯一标识符（UUID）。

#### `manifest: MCPManifest`

插件的manifest对象。

#### `plugin_path: Path`

插件的文件系统路径。

#### `status: MCPPluginStatus`

插件的当前状态。可能的值：
- `UNLOADED`：未加载
- `LOADING`：加载中
- `LOADED`：已加载
- `RUNNING`：运行中
- `STOPPED`：已停止
- `ERROR`：错误
- `UNLOADING`：卸载中

#### `process: Optional[subprocess.Popen]`

插件进程对象（如果是子进程）。

#### `config: dict[str, Any]`

插件的当前配置。

#### `created_at: datetime`

插件创建时间。

#### `updated_at: datetime`

插件最后更新时间。

#### `error_message: Optional[str]`

错误消息（如果有错误）。

### 方法

#### `to_dict() -> dict[str, Any]`

将插件转换为字典。

**返回**：
```python
{
    "plugin_id": "...",
    "name": "...",
    "version": "...",
    "status": "running",
    "plugin_path": "...",
    "config": {...},
    "created_at": "...",
    "updated_at": "...",
    "error_message": None
}
```

## 错误处理

### 标准错误响应

所有工具调用都返回标准的错误响应格式：

```python
{
    "status": "error",
    "error_type": "ToolExecutionError",
    "message": "Error description",
    "context": "execution"
}
```

### 异常类型

#### `PluginError`

基础插件错误。

#### `ConfigurationError`

配置错误。

#### `ToolExecutionError`

工具执行错误。

### 错误处理示例

```python
try:
    result = await adapter.call_tool(plugin, "my_tool", {"param": "value"})
except ConfigurationError as e:
    print(f"Configuration error: {e}")
except ToolExecutionError as e:
    print(f"Tool execution error: {e}")
except Exception as e:
    print(f"Unknown error: {e}")
```

## 工具调用

### 工具定义

工具在manifest中定义：

```json
{
    "name": "tool_name",
    "description": "Tool description",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"}
        },
        "required": ["param1"]
    }
}
```

### 工具调用流程

1. **验证工具存在**
   ```python
   tools = adapter.get_tools(plugin)
   tool_names = [t["name"] for t in tools]
   if "my_tool" not in tool_names:
       raise ValueError("Tool not found")
   ```

2. **验证输入参数**
   ```python
   # 根据input_schema验证参数
   ```

3. **调用工具**
   ```python
   result = await adapter.call_tool(plugin, "my_tool", {"param1": "value"})
   ```

4. **处理结果**
   ```python
   if result["status"] == "success":
       data = result["data"]
   else:
       error = result["message"]
   ```

## 资源访问

### 资源定义

资源在manifest中定义：

```json
{
    "uri": "resource://example/data",
    "name": "Example Resource",
    "description": "Resource description",
    "mime_type": "application/json"
}
```

### 资源访问流程

1. **获取资源列表**
   ```python
   resources = adapter.get_resources(plugin)
   ```

2. **访问资源**
   ```python
   # 通过插件的资源接口访问
   resource_data = await plugin.get_resource("resource://example/data")
   ```

## 完整示例

### 加载和使用插件

```python
import asyncio
from backend.app.core.mcp_plugin_adapter import MCPPluginAdapter

async def main():
    # 初始化适配器
    adapter = MCPPluginAdapter("/path/to/plugins")
    
    # 加载插件
    plugin = adapter.load_plugin("/path/to/github-plugin")
    
    # 验证manifest
    is_valid, errors = adapter.validate_manifest(plugin.manifest)
    if not is_valid:
        print(f"Validation errors: {errors}")
        return
    
    # 检查兼容性
    is_compatible, warnings = adapter.check_compatibility(plugin.manifest)
    if not is_compatible:
        print("Plugin is not compatible")
        return
    
    # 启动服务器
    if not adapter.start_server(plugin):
        print("Failed to start server")
        return
    
    # 调用工具
    result = await adapter.call_tool(
        plugin,
        "list_repositories",
        {"username": "torvalds", "limit": 5}
    )
    print(f"Result: {result}")
    
    # 停止服务器
    adapter.stop_server(plugin)
    
    # 卸载插件
    adapter.unload_plugin(plugin.plugin_id)

if __name__ == "__main__":
    asyncio.run(main())
```

## 相关文档

- [MCP插件Manifest规范](MCP_PLUGIN_MANIFEST_SPEC.md)
- [MCP插件开发者指南](MCP_PLUGIN_DEVELOPER_GUIDE.md)
- [MCP插件审核标准](MCP_PLUGIN_REVIEW_STANDARDS.md)
- [MCP插件示例](MCP_PLUGIN_EXAMPLES.md)
