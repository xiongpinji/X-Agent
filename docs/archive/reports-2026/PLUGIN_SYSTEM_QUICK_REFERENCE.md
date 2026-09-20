# X-Agent 插件系统 - 快速参考

## 快速开始

### 1. 发现插件
```python
from backend.app.core.plugin_system import plugin_system

# 按能力发现
plugins = plugin_system.discover_plugins(capability="calculator")

# 搜索
results = plugin_system.search_plugins("calc")

# 列出所有
all_plugins = plugin_system.list_all_plugins()
```

### 2. 安装插件
```python
# 安装并启用
success, error = plugin_system.install_plugin(
    plugin_id="calculator",
    config={"precision": 2},
    auto_enable=True
)

if not success:
    print(f"安装失败: {error}")
```

### 3. 执行插件
```python
# 执行操作
result = plugin_system.execute_plugin_action(
    plugin_id="calculator",
    action="add",
    a=5,
    b=3
)

if result.get("success"):
    print(f"结果: {result['data']}")
else:
    print(f"错误: {result['error']}")
```

### 4. 管理插件
```python
# 启用
plugin_system.enable_plugin(plugin_id)

# 禁用
plugin_system.disable_plugin(plugin_id)

# 升级
plugin_system.upgrade_plugin(plugin_id, "2.0.0")

# 卸载
plugin_system.uninstall_plugin(plugin_id)
```

### 5. 审计和监控
```python
# 获取审计追踪
trail = plugin_system.get_plugin_audit_trail(plugin_id)

# 导出报告
report = plugin_system.export_audit_report(plugin_id)

# 验证完整性
valid, issues = plugin_system.verify_system_integrity()

# 系统状态
status = plugin_system.get_system_status()
```

## 开发新插件

### 1. 创建插件文件
```bash
cp backend/app/plugins/template_plugin.py backend/app/plugins/my_plugin.py
```

### 2. 实现插件
```python
class MyPlugin:
    PLUGIN_NAME = "my_plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Your Name"
    PLUGIN_DESCRIPTION = "What it does"
    PLUGIN_CAPABILITIES = ["capability1"]
    PLUGIN_PERMISSIONS = ["resource:action"]
    PLUGIN_RISK_LEVEL = "medium"

    def execute(self, action: str, **kwargs) -> dict:
        if action == "my_action":
            return {"success": True, "data": "result"}
        return {"success": False, "error": "Unknown action"}

plugin = MyPlugin()
```

### 3. 注册插件
```python
from backend.app.core.plugin_schema import PluginSchema
from backend.app.core.plugin_marketplace import marketplace

schema = PluginSchema(
    name="my_plugin",
    version="1.0.0",
    author="Your Name",
    description="Description",
    capabilities=["capability1"],
    permissions=["resource:action"],
    risk_level="medium",
    install_url="file:///path/to/plugin",
    documentation_url="https://docs.example.com"
)

marketplace.register_plugin(schema)
```

### 4. 安装和测试
```python
success, error = plugin_system.install_plugin(
    plugin_id=schema.plugin_id,
    auto_enable=True
)

result = plugin_system.execute_plugin_action(
    plugin_id=schema.plugin_id,
    action="my_action"
)
```

## 权限管理

### 权限格式
```
resource:action
```

### 常见权限
```
file:read          # 读文件
file:write         # 写文件
network:http       # HTTP请求
database:query     # 数据库查询
data:read          # 读数据
data:write         # 写数据
```

### 权限操作
```python
# 授予权限
plugin_system.grant_permission(plugin_id, "file:read")

# 撤销权限
plugin_system.revoke_permission(plugin_id, "file:read")

# 获取权限
perms = plugin_system.get_plugin_permissions(plugin_id)

# 设置权限
plugin_system.set_plugin_permissions(plugin_id, ["file:read", "data:write"])
```

## 插件状态

```
inactive      -> 未安装
installing    -> 安装中
active        -> 已启用
disabled      -> 已禁用
error         -> 错误
uninstalling  -> 卸载中
```

## 风险等级

```
low       -> 低风险
medium    -> 中风险
high      -> 高风险
critical  -> 严重风险
```

## 常见问题

### 插件无法加载
- 检查安装路径是否存在
- 验证 __init__.py 存在 (包)
- 检查语法错误
- 查看沙箱限制

### 权限被拒绝
- 验证权限已授予
- 检查权限名称匹配
- 查看审计日志

### 兼容性问题
- 检查依赖已安装
- 验证版本兼容性
- 查看兼容性检查结果

## 文件位置

| 组件 | 文件 |
|------|------|
| Schema | `backend/app/core/plugin_schema.py` |
| Loader | `backend/app/core/plugin_loader.py` |
| Marketplace | `backend/app/core/plugin_marketplace.py` |
| Lifecycle | `backend/app/core/plugin_lifecycle.py` |
| System | `backend/app/core/plugin_system.py` |
| Examples | `backend/app/plugins/` |
| Guide | `backend/app/plugins/PLUGIN_DEVELOPMENT_GUIDE.md` |
| Tests | `tests/test_plugin_system.py` |

## API 速查表

### 发现
- `discover_plugins(capability, risk_level)` - 发现插件
- `search_plugins(query)` - 搜索插件
- `get_plugin_info(plugin_id)` - 获取信息
- `list_installed_plugins()` - 列出已安装
- `list_all_plugins()` - 列出所有

### 安装
- `install_plugin(plugin_id, config, auto_enable)` - 安装
- `uninstall_plugin(plugin_id, force)` - 卸载
- `enable_plugin(plugin_id)` - 启用
- `disable_plugin(plugin_id)` - 禁用
- `upgrade_plugin(plugin_id, new_version)` - 升级

### 权限
- `grant_permission(plugin_id, permission)` - 授予
- `revoke_permission(plugin_id, permission)` - 撤销
- `get_plugin_permissions(plugin_id)` - 获取
- `set_plugin_permissions(plugin_id, permissions)` - 设置

### 执行
- `execute_plugin_action(plugin_id, action, **kwargs)` - 执行

### 审计
- `get_plugin_audit_trail(plugin_id)` - 审计追踪
- `get_audit_records(plugin_id, action)` - 审计记录
- `export_audit_report(plugin_id)` - 导出报告

### 状态
- `get_plugin_lifecycle(plugin_id)` - 生命周期
- `get_plugin_action_history(plugin_id)` - 操作历史
- `get_system_status()` - 系统状态
- `verify_system_integrity()` - 完整性验证

## 示例插件

### 计算器
```python
from backend.app.plugins.example_calculator import plugin

result = plugin.execute("add", a=5, b=3)
# {"result": 8, "operation": "add"}
```

### 模板
```python
# 复制 template_plugin.py 作为基础
# 实现 execute() 方法
# 定义 PLUGIN_* 元数据
```

## 最佳实践

1. **最小依赖** - 保持插件轻量
2. **清晰权限** - 只请求需要的权限
3. **错误处理** - 处理所有错误情况
4. **日志记录** - 使用日志调试
5. **文档** - 记录所有能力
6. **测试** - 部署前测试
7. **版本** - 遵循语义版本
8. **安全** - 验证所有输入

## 支持

- 开发指南: `backend/app/plugins/PLUGIN_DEVELOPMENT_GUIDE.md`
- 实现报告: `PLUGIN_SYSTEM_IMPLEMENTATION_REPORT.md`
- 交付总结: `PLUGIN_SYSTEM_DELIVERY_SUMMARY.md`
- 测试: `tests/test_plugin_system.py`
