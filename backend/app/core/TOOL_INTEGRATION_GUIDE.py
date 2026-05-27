"""
工具层标准化集成指南
"""

INTEGRATION_GUIDE = """
# X-Agent 工具层标准化集成指南

## 概述

本指南说明如何将统一的工具协议和注册表集成到 X-Agent 系统中。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Manager                              │
│  (初始化、管理、执行所有工具)                                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Registry│ │Executor│ │Wrapper │
   └────────┘ └────────┘ └────────┘
        │          │          │
        └──────────┼──────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   ┌─────────┐          ┌──────────┐
   │Audit Log│          │Lifecycle │
   │         │          │Events    │
   └─────────┘          └──────────┘
```

## 核心组件

### 1. Tool Schema (tool_schema.py)

定义统一的工具协议：
- ToolSchema: 工具定义
- ToolCallInput: 工具调用输入
- ToolCallOutput: 工具调用输出
- ToolAuditEntry: 审计条目
- ToolLifecycleEvent: 生命周期事件

### 2. Tool Registry (tool_registry.py)

管理工具的生命周期：
- 注册/注销工具
- 版本管理
- 权限检查
- 审计记录
- 生命周期事件

### 3. Tool Executor (tool_executor.py)

执行工具调用：
- ToolWrapper: 统一的调用接口
- ToolExecutionEngine: 执行引擎
- 参数验证
- 权限检查
- 审批检查

### 4. Tool Definitions (tool_definitions.py)

标准工具定义：
- Browser 工具 (5个)
- Desktop 工具 (3个)
- Memory 工具 (3个)
- Workflow 工具 (2个)
- Plugin 工具 (3个)

### 5. Tool Manager (tool_manager.py)

统一的工具管理接口：
- 初始化所有工具
- 执行工具
- 获取工具信息
- 审计日志
- 统计信息

### 6. Tool Documentation (tool_documentation.py)

生成工具文档：
- Markdown 文档
- JSON Schema
- OpenAPI 规范
- Python 函数签名
- 参考指南

## 集成步骤

### 步骤 1: 初始化工具管理器

```python
from backend.app.core.tool_manager import ToolManager

# 创建工具管理器
manager = ToolManager(storage_path="/path/to/tools")

# 初始化所有标准工具
manager.initialize()
```

### 步骤 2: 执行工具

```python
import asyncio

async def main():
    # 执行浏览器导航工具
    output = await manager.execute_tool(
        tool_name="browser_navigate",
        arguments={"url": "https://example.com"},
        trace_id="trace-123",
        run_id="run-456",
        tenant_id="tenant-1",
        user_id="user-1",
    )

    if output.success:
        print(f"Tool executed successfully: {output.result}")
    else:
        print(f"Tool execution failed: {output.error}")

asyncio.run(main())
```

### 步骤 3: 获取工具信息

```python
# 获取工具清单
manifest = manager.get_tool_manifest()

# 获取特定工具信息
tool_info = manager.get_tool_info("browser_navigate")

# 获取统计信息
stats = manager.get_statistics()
```

### 步骤 4: 审计和监控

```python
# 获取审计日志
audit_log = manager.get_audit_log(tool_name="browser_navigate", limit=100)

# 获取统计信息
stats = manager.get_statistics()
print(f"Total tools: {stats['total_tools']}")
print(f"Total calls: {stats['total_calls']}")
print(f"Success rate: {stats['successful_calls'] / stats['total_calls'] * 100}%")
```

### 步骤 5: 工具生命周期管理

```python
# 禁用工具
manager.disable_tool("browser_click")

# 启用工具
manager.enable_tool("browser_click")

# 弃用工具
manager.deprecate_tool("old_tool", reason="Use new_tool instead")
```

## API 参考

### ToolManager

#### 初始化

```python
manager = ToolManager(storage_path: str | Path | None = None)
manager.initialize()
```

#### 执行工具

```python
output = await manager.execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    trace_id: str | None = None,
    run_id: str | None = None,
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> ToolCallOutput
```

#### 获取信息

```python
manifest = manager.get_tool_manifest() -> list[dict]
info = manager.get_tool_info(tool_name: str) -> dict | None
stats = manager.get_statistics() -> dict
audit_log = manager.get_audit_log(tool_name: str | None, limit: int) -> list[dict]
```

#### 生命周期管理

```python
manager.enable_tool(tool_name: str) -> bool
manager.disable_tool(tool_name: str) -> bool
manager.deprecate_tool(tool_name: str, reason: str) -> bool
```

## 工具列表

### Browser 工具

1. **browser_navigate** - 导航到 URL
   - 参数: url (string), timeout (number)
   - 风险等级: LOW

2. **browser_click** - 点击页面元素
   - 参数: selector (string)
   - 风险等级: LOW

3. **browser_fill** - 填充表单字段
   - 参数: selector (string), value (string)
   - 风险等级: LOW

4. **browser_screenshot** - 截图
   - 参数: path (string, optional)
   - 风险等级: LOW

5. **browser_extract_text** - 提取文本
   - 参数: selector (string, optional)
   - 风险等级: LOW

### Desktop 工具

1. **desktop_click** - 桌面点击
   - 参数: x (number), y (number)
   - 风险等级: MEDIUM

2. **desktop_type** - 桌面输入
   - 参数: text (string)
   - 风险等级: MEDIUM

3. **desktop_screenshot** - 桌面截图
   - 参数: path (string, optional)
   - 风险等级: LOW

### Memory 工具

1. **memory_store** - 存储内存
   - 参数: content (string), layer (number), tags (array)
   - 风险等级: LOW

2. **memory_retrieve** - 检索内存
   - 参数: query (string), limit (number)
   - 风险等级: LOW

3. **memory_update** - 更新内存
   - 参数: memory_id (string), content (string)
   - 风险等级: LOW

### Workflow 工具

1. **workflow_execute** - 执行工作流
   - 参数: workflow_id (string), input (object)
   - 风险等级: MEDIUM
   - 需要审批: 是

2. **workflow_status** - 获取工作流状态
   - 参数: run_id (string)
   - 风险等级: LOW

### Plugin 工具

1. **plugin_install** - 安装插件
   - 参数: plugin_name (string), version (string)
   - 风险等级: HIGH
   - 需要审批: 是

2. **plugin_uninstall** - 卸载插件
   - 参数: plugin_id (string)
   - 风险等级: HIGH
   - 需要审批: 是

3. **plugin_execute** - 执行插件
   - 参数: plugin_id (string), action (string), params (object)
   - 风险等级: MEDIUM

## 扩展工具

### 添加新工具

1. 在 `tool_definitions.py` 中定义工具 Schema：

```python
NEW_TOOL = ToolSchema(
    name="new_tool",
    version="1.0.0",
    description="Description of the new tool",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="param1",
            type="string",
            description="Parameter description",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Return value description",
    ),
    permissions=["tool:execute"],
)
```

2. 在 `tool_manager.py` 中添加处理器：

```python
async def _handle_new_tool(self, param1: str) -> dict[str, Any]:
    # 实现工具逻辑
    return {"result": "success"}
```

3. 在 `_register_handlers()` 中注册处理器：

```python
self.engine.wrapper.register_handler("new_tool", self._handle_new_tool)
```

4. 将工具添加到 `STANDARD_TOOLS` 列表。

## 测试

运行集成测试：

```bash
python -m backend.app.core.tool_integration_tests
```

测试覆盖：
- 工具注册
- 工具执行
- 审计记录
- 统计信息
- 文档生成
- 生命周期管理
- 权限检查

## 性能考虑

1. **缓存**: 工具 Schema 被缓存在内存中
2. **异步执行**: 所有工具执行都是异步的
3. **审计日志**: 异步写入磁盘
4. **版本管理**: 支持多版本并存

## 安全考虑

1. **权限检查**: 每个工具都有权限要求
2. **审批流程**: 高风险工具需要审批
3. **审计记录**: 所有调用都被记录
4. **参数验证**: 所有参数都被验证
5. **错误处理**: 完整的错误处理和恢复

## 故障排除

### 工具未找到

```
Tool {tool_name} not found
```

解决方案: 确保工具已注册并初始化

### 权限被拒绝

```
Tool {tool_name} requires scope: {scope}
```

解决方案: 检查用户权限配置

### 参数验证失败

```
Parameter {param_name} must be {type}
```

解决方案: 检查参数类型和值

## 文件结构

```
backend/app/core/
├── tool_schema.py              # 工具 Schema 定义
├── tool_registry.py            # 工具注册表
├── tool_executor.py            # 工具执行引擎
├── tool_definitions.py         # 标准工具定义
├── tool_manager.py             # 工具管理器
├── tool_documentation.py       # 文档生成器
└── tool_integration_tests.py   # 集成测试
```

## 下一步

1. 集成到 API 层 (backend/app/api/tools.py)
2. 添加 WebSocket 支持用于实时工具执行
3. 实现工具市场和插件系统
4. 添加工具性能监控和优化
5. 实现工具版本管理和回滚

## 参考资源

- [Tool Schema Documentation](tool_schema.py)
- [Tool Registry Documentation](tool_registry.py)
- [Tool Executor Documentation](tool_executor.py)
- [Tool Definitions Documentation](tool_definitions.py)
- [Tool Manager Documentation](tool_manager.py)
"""

if __name__ == "__main__":
    print(INTEGRATION_GUIDE)
