# X-Agent 插件系统完整文档

## 目录

1. [系统架构](#系统架构)
2. [核心组件](#核心组件)
3. [插件生命周期](#插件生命周期)
4. [安全机制](#安全机制)
5. [插件市场](#插件市场)
6. [开发指南](#开发指南)
7. [API参考](#api参考)
8. [最佳实践](#最佳实践)

## 系统架构

### 整体设计

X-Agent插件系统采用模块化、可扩展的架构，支持：

- **动态加载/卸载**：无需重启即可安装、更新、卸载插件
- **沙箱隔离**：每个插件在隔离的执行环境中运行
- **权限管理**：细粒度的权限控制和访问管理
- **版本管理**：支持多版本并存和灰度升级
- **依赖解析**：自动解析和验证插件依赖
- **审核流程**：完整的安全审核和合规检查

### 核心模块

```
plugin_system_v2.py          # 主系统管理器
├── PluginSystemV2           # 系统入口
├── PluginLoader             # 动态加载器
├── PermissionManager        # 权限管理
├── DependencyResolver       # 依赖解析
├── PluginRegistry           # 插件注册表
└── AuditLogger              # 审计日志

plugin_sandbox.py            # 沙箱隔离
├── PluginSandbox            # 基础沙箱
├── ResourceLimiter          # 资源限制
├── FileSystemAccessControl  # 文件系统控制
├── NetworkAccessControl     # 网络控制
└── SandboxManager           # 沙箱管理

plugin_review.py             # 审核系统
├── SecurityScanner          # 安全扫描
├── ComplianceChecker        # 合规检查
├── CodeQualityAnalyzer      # 代码质量分析
└── PluginReviewManager      # 审核管理

plugin_update.py             # 更新管理
├── VersionComparator        # 版本比较
├── PluginVersionRegistry    # 版本注册表
└── PluginUpdateManager      # 更新管理

plugin_marketplace.py        # 市场API
├── 插件搜索和发现
├── 安装和卸载
├── 评分和评论
└── 下载统计
```

## 核心组件

### 1. 插件系统管理器 (PluginSystemV2)

主要职责：
- 协调所有插件操作
- 管理插件生命周期
- 处理权限和审计

```python
from backend.app.core.plugin_system_v2 import plugin_system_v2

# 安装插件
request = PluginInstallRequest(
    plugin_id="my-plugin",
    source_url="https://...",
    config={"key": "value"},
    auto_enable=True
)
success, error = plugin_system_v2.install_plugin(request, actor_id="user123")

# 执行插件
exec_request = PluginExecutionRequest(
    plugin_id="my-plugin",
    action="process",
    parameters={"data": [1, 2, 3]}
)
result = plugin_system_v2.execute_plugin_action(exec_request)

# 获取系统状态
status = plugin_system_v2.get_system_status()
```

### 2. 沙箱系统 (PluginSandbox)

隔离执行环境，限制资源和访问：

```python
from backend.app.core.plugin_sandbox import SandboxPolicyBuilder

# 创建沙箱策略
policy = (SandboxPolicyBuilder("my-plugin")
    .with_allowed_modules(["json", "requests"])
    .with_allowed_path("/data/plugins/my-plugin")
    .with_memory_limit(256, 512)  # 256MB soft, 512MB hard
    .with_cpu_limit(30, 60)       # 30s soft, 60s hard
    .with_timeout(30)
    .allow_network()
    .build())

# 创建沙箱
sandbox = sandbox_manager.create_sandbox(policy)

# 在沙箱中执行
with sandbox.execution_context():
    result = plugin_module.execute("action")
```

### 3. 权限管理 (PermissionManager)

细粒度的权限控制：

```python
from backend.app.core.plugin_system_v2 import plugin_system_v2

# 授予权限
plugin_system_v2.permissions.grant_permission(
    "my-plugin",
    "file:read"
)

# 检查权限
has_perm = plugin_system_v2.permissions.has_permission(
    "my-plugin",
    "file:read"
)

# 设置权限集合
plugin_system_v2.permissions.set_permissions(
    "my-plugin",
    ["file:read", "file:write", "network:http"]
)
```

### 4. 依赖解析 (DependencyResolver)

自动解析和验证依赖：

```python
# 检查依赖兼容性
compatible, issues, warnings = plugin_system_v2.dependency_resolver.resolve_dependencies(
    "my-plugin",
    installed_plugins
)

if not compatible:
    print(f"Dependency issues: {issues}")
```

### 5. 审核系统 (PluginReview)

安全审核和合规检查：

```python
from backend.app.core.plugin_review import review_manager

# 创建审核
review = review_manager.create_review(
    plugin_id="my-plugin",
    plugin_version="1.0.0",
    plugin_path=Path("/path/to/plugin")
)

# 添加代码审查评论
review_manager.add_code_review_comment(
    review.review_id,
    reviewer_id="reviewer1",
    file_path="plugin.py",
    comment="Consider using async for this operation",
    line_number=42,
    severity="info"
)

# 批准审核
review_manager.approve_review(review.review_id, "approver1")
```

### 6. 更新管理 (PluginUpdateManager)

版本管理和更新机制：

```python
from backend.app.core.plugin_update import update_manager

# 检查更新
updates = update_manager.check_updates("my-plugin", "1.0.0")

# 创建更新
update = update_manager.create_update(
    plugin_id="my-plugin",
    from_version="1.0.0",
    to_version="1.1.0",
    download_url="https://...",
    file_hash="sha256...",
    file_size=1024000,
    changelog="Bug fixes and improvements"
)

# 执行更新
update_manager.start_update(update.update_id)
update_manager.update_download_progress(update.update_id, 50)
update_manager.complete_update(update.update_id)
```

## 插件生命周期

### 1. 发现阶段

```
用户搜索 → 市场查询 → 返回结果
```

### 2. 审核阶段

```
提交审核 → 安全扫描 → 代码审查 → 合规检查 → 批准/拒绝
```

### 3. 安装阶段

```
下载 → 验证 → 依赖检查 → 加载 → 初始化 → 启用
```

### 4. 运行阶段

```
接收请求 → 权限检查 → 沙箱执行 → 返回结果 → 审计记录
```

### 5. 更新阶段

```
检查更新 → 下载 → 备份 → 安装 → 验证 → 回滚(如需)
```

### 6. 卸载阶段

```
禁用 → 清理资源 → 删除文件 → 记录审计
```

## 安全机制

### 1. 沙箱隔离

- **内存限制**：防止内存溢出
- **CPU限制**：防止CPU耗尽
- **文件系统限制**：只允许访问指定目录
- **网络限制**：只允许连接到白名单主机
- **系统调用限制**：禁止危险操作

### 2. 权限管理

权限格式：`resource:action:scope`

```
file:read:workspace      # 读取工作区文件
file:write:workspace     # 写入工作区文件
network:http:external    # HTTP外部请求
system:exec:none         # 禁止系统执行
```

### 3. 代码审查

自动检查：
- 危险函数使用（eval, exec, __import__）
- 文件操作
- 网络操作
- 系统调用

### 4. 审计日志

记录所有操作：
- 安装/卸载
- 启用/禁用
- 执行操作
- 权限变更
- 错误事件

## 插件市场

### 市场功能

1. **发现和搜索**
   - 按类别浏览
   - 全文搜索
   - 按评分排序
   - 按下载量排序

2. **安装和管理**
   - 一键安装
   - 版本选择
   - 配置管理
   - 启用/禁用

3. **评分和评论**
   - 用户评分（1-5星）
   - 用户评论
   - 下载统计
   - 安装统计

4. **更新管理**
   - 自动检查更新
   - 灰度升级
   - 版本回滚
   - 更新日志

### API端点

```
GET    /api/v1/plugins/categories              # 获取分类
GET    /api/v1/plugins/search                  # 搜索插件
GET    /api/v1/plugins/{plugin_id}             # 获取详情
GET    /api/v1/plugins/{plugin_id}/rating      # 获取评分
POST   /api/v1/plugins/{plugin_id}/rating      # 提交评分
GET    /api/v1/plugins/{plugin_id}/updates     # 检查更新
POST   /api/v1/plugins/install                 # 安装插件
POST   /api/v1/plugins/uninstall               # 卸载插件
POST   /api/v1/plugins/{plugin_id}/enable      # 启用插件
POST   /api/v1/plugins/{plugin_id}/disable     # 禁用插件
POST   /api/v1/plugins/{plugin_id}/update      # 更新插件
GET    /api/v1/plugins/installed               # 列出已安装
GET    /api/v1/plugins/status                  # 系统状态
```

## 开发指南

### 创建插件

```bash
# 使用脚手架创建
x-agent plugin create my-plugin --author "Your Name" --description "Plugin description"
```

### 插件结构

```
my-plugin/
├── manifest.json          # 插件清单
├── plugin.py              # 主程序
├── README.md              # 文档
├── requirements.txt       # 依赖
└── tests/
    └── test_plugin.py     # 测试
```

### manifest.json

```json
{
  "metadata": {
    "name": "My Plugin",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "Plugin description",
    "license": "MIT"
  },
  "capabilities": [
    {
      "name": "process_data",
      "description": "Process data",
      "parameters": {
        "data": "array"
      }
    }
  ],
  "permissions": [
    {
      "resource": "file",
      "action": "read",
      "scope": "workspace"
    }
  ],
  "dependencies": [],
  "entry_point": "plugin",
  "risk_level": "medium",
  "sandbox_enabled": true
}
```

### 实现插件

```python
"""My Plugin"""

from typing import Any, Dict, Optional


class Plugin:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def initialize(self) -> bool:
        """Initialize plugin"""
        return True

    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute action"""
        if action == "process_data":
            data = kwargs.get("data", [])
            result = [x * 2 for x in data]
            return {"success": True, "result": result}
        return {"success": False, "error": "Unknown action"}

    def shutdown(self) -> bool:
        """Shutdown plugin"""
        return True


# Global instance
plugin = Plugin()


def initialize(config: Optional[Dict[str, Any]] = None) -> bool:
    global plugin
    plugin = Plugin(config)
    return plugin.initialize()


def execute(action: str, **kwargs) -> Dict[str, Any]:
    return plugin.execute(action, **kwargs)


def shutdown() -> bool:
    return plugin.shutdown()
```

### 测试插件

```python
"""Test plugin"""

import pytest
from plugin import Plugin


@pytest.fixture
def plugin():
    return Plugin()


def test_initialization(plugin):
    assert plugin.initialize()


def test_execute(plugin):
    result = plugin.execute("process_data", data=[1, 2, 3])
    assert result["success"]
    assert result["result"] == [2, 4, 6]


def test_shutdown(plugin):
    assert plugin.shutdown()
```

### 发布插件

```bash
# 验证插件
x-agent plugin validate

# 提交审核
x-agent plugin submit

# 等待批准
# 批准后自动发布到市场
```

## API参考

### PluginSystemV2

```python
# 安装
install_plugin(request: PluginInstallRequest, actor_id: str) -> tuple[bool, Optional[str]]

# 卸载
uninstall_plugin(plugin_id: str, actor_id: str) -> tuple[bool, Optional[str]]

# 启用
enable_plugin(plugin_id: str, actor_id: str) -> tuple[bool, Optional[str]]

# 禁用
disable_plugin(plugin_id: str, actor_id: str) -> tuple[bool, Optional[str]]

# 执行
execute_plugin_action(request: PluginExecutionRequest, actor_id: str) -> dict

# 获取状态
get_system_status() -> dict
```

### PluginRegistry

```python
# 注册
register_plugin(manifest: PluginManifest) -> None

# 获取
get_plugin(plugin_id: str) -> Optional[PluginManifest]

# 列表
list_plugins() -> list[PluginManifest]

# 搜索
search_plugins(query: str) -> list[PluginManifest]
```

### PluginUpdateManager

```python
# 检查更新
check_updates(plugin_id: str, current_version: str) -> list[PluginVersion]

# 创建更新
create_update(...) -> UpdateRecord

# 开始更新
start_update(update_id: str) -> Optional[UpdateRecord]

# 完成更新
complete_update(update_id: str) -> Optional[UpdateRecord]

# 回滚
rollback_update(plugin_id: str, plugin_path: Path, backup_path: Path) -> bool
```

## 最佳实践

### 1. 安全性

- 不使用 `eval()` 或 `exec()`
- 避免动态导入
- 验证所有输入
- 使用安全的库

### 2. 性能

- 保持操作快速
- 使用异步处理长操作
- 缓存结果
- 避免阻塞

### 3. 可靠性

- 处理所有异常
- 返回有意义的错误
- 记录重要事件
- 实现重试逻辑

### 4. 可维护性

- 编写清晰的代码
- 添加文档
- 编写测试
- 使用语义版本

### 5. 用户体验

- 提供清晰的文档
- 支持配置
- 给出有用的错误消息
- 提供示例

## 故障排除

### 插件无法加载

检查：
1. 插件路径是否正确
2. manifest.json是否有效
3. 依赖是否已安装
4. 权限是否足够

### 执行失败

检查：
1. 插件是否已启用
2. 权限是否足够
3. 参数是否正确
4. 查看审计日志

### 性能问题

检查：
1. 资源限制是否合理
2. 是否有内存泄漏
3. 是否有无限循环
4. 是否需要优化

## 总结

X-Agent插件系统提供了一个完整、安全、可扩展的插件生态。通过模块化设计、沙箱隔离、权限管理和审核流程，确保了系统的安全性和稳定性。开发者可以轻松创建、测试和发布插件，用户可以安全地安装和使用插件。
