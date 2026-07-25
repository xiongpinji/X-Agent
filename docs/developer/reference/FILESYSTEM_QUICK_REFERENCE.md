"""Quick Reference Guide for Filesystem Management System

快速参考指南 - 文件系统管理系统
"""

# 文件系统管理系统 - 快速参考

## 模块导入

```python
# 工作区管理
from backend.app.core.workspace_manager import (
    WorkspaceManager,
    WorkspaceConfig,
    Workspace,
)

# 路径映射
from backend.app.core.path_mapper import PathMapper

# 挂载管理
from backend.app.core.mount_manager import (
    MountManager,
    MountPoint,
)

# 访问控制
from backend.app.core.file_access_control import FileAccessControl

# 集成管理器
from backend.app.core.filesystem_manager import (
    FileSystemManager,
    create_file_system_manager,
)
```

## 常用操作

### 初始化

```python
from pathlib import Path
from backend.app.core.filesystem_manager import create_file_system_manager

# 创建文件系统管理器
fs_manager = create_file_system_manager(
    workspace_base=Path("/workspaces"),
    user_id="user123",
    data_dir=Path("/data"),
)
```

### 工作区操作

```python
# 创建工作区
ws = fs_manager.workspace_manager.create_workspace(
    user_id="user123",
    workspace_type="project",
)

# 获取工作区
ws = fs_manager.workspace_manager.get_workspace(workspace_id)

# 列出工作区
workspaces = fs_manager.workspace_manager.list_workspaces("user123")

# 删除工作区
fs_manager.workspace_manager.delete_workspace(workspace_id)

# 获取默认工作区
ws = fs_manager.get_default_workspace()

# 创建临时工作区
temp_ws = fs_manager.create_temporary_workspace(ttl_hours=24)
```

### 路径操作

```python
# 解析虚拟路径
real_path = fs_manager.resolve_path("/test/file.txt")

# 验证读权限
allowed, reason = fs_manager.validate_read_access("/test/file.txt")

# 验证写权限
allowed, reason = fs_manager.validate_write_access("/test/file.txt", size_bytes=1024)

# 验证删除权限
allowed, reason = fs_manager.validate_delete_access("/test/file.txt")

# 规范化路径
normalized = fs_manager.path_mapper.normalize_path("/foo//bar/../baz")

# 验证路径
is_valid = fs_manager.path_mapper.validate_path("/test/file.txt", "user123")
```

### 挂载操作

```python
# 挂载目录
mount_path = fs_manager.mount_directory(
    host_path="/home/user/projects",
    mount_path="/mounts/projects",
    read_only=False,
)

# 卸载目录
fs_manager.unmount_directory("/mounts/projects")

# 列出挂载
mounts = fs_manager.list_mounts()

# 获取挂载信息
mount = fs_manager.mount_manager.get_mount(mount_id)

# 获取挂载统计
stats = fs_manager.mount_manager.get_mount_stats(mount_id)
```

### 审计操作

```python
# 记录操作
fs_manager.audit_operation(
    operation="read",
    path="/test/file.txt",
    success=True,
)

# 获取审计日志
logs = fs_manager.get_audit_logs(limit=100)

# 按用户过滤
user_logs = fs_manager.access_control.get_audit_logs(
    user_id="user123",
    limit=50,
)

# 按操作过滤
read_logs = fs_manager.access_control.get_audit_logs(
    operation="read",
    limit=50,
)
```

### 权限管理

```python
# 授予权限
fs_manager.access_control.grant_permission("user123", "write")

# 撤销权限
fs_manager.access_control.revoke_permission("user123", "write")

# 检查权限
has_write = fs_manager.access_control.has_permission("user123", "write")

# 添加禁止扩展名
fs_manager.access_control.add_forbidden_extension(".exe")

# 移除禁止扩展名
fs_manager.access_control.remove_forbidden_extension(".exe")
```

## API 端点速查

### 工作区管理

```bash
# 创建工作区
POST /api/v1/workspace/create
{
  "workspace_type": "project",
  "max_size_mb": 1000,
  "ttl_hours": null
}

# 列出工作区
GET /api/v1/workspace/list?workspace_type=project

# 删除工作区
DELETE /api/v1/workspace/{workspace_id}
```

### 挂载管理

```bash
# 挂载目录
POST /api/v1/workspace/mount
{
  "host_path": "/home/user/data",
  "mount_path": "/mounts/data",
  "read_only": false
}

# 卸载目录
DELETE /api/v1/workspace/mount/{mount_id}

# 列出挂载
GET /api/v1/workspace/mounts
```

### 路径验证

```bash
# 验证路径访问
POST /api/v1/workspace/validate-path
{
  "path": "/test/file.txt",
  "operation": "read"
}
```

### 审计

```bash
# 获取审计日志
GET /api/v1/workspace/audit-logs?limit=100
```

### 维护

```bash
# 清理过期工作区
POST /api/v1/workspace/cleanup-expired
```

## 工具集成示例

### 读文件工具

```python
async def read_file_tool(
    path: str,
    _fs_manager: FileSystemManager,
) -> str:
    """Read file with permission checking."""
    # 验证权限
    allowed, reason = _fs_manager.validate_read_access(path)
    if not allowed:
        raise PermissionError(f"Read denied: {reason}")
    
    # 解析路径
    real_path = _fs_manager.resolve_path(path)
    
    # 执行操作
    content = real_path.read_text()
    
    # 记录审计
    _fs_manager.audit_operation("read", path, True)
    
    return content
```

### 写文件工具

```python
async def write_file_tool(
    path: str,
    content: str,
    _fs_manager: FileSystemManager,
) -> dict:
    """Write file with permission checking."""
    # 验证权限
    allowed, reason = _fs_manager.validate_write_access(
        path,
        len(content),
    )
    if not allowed:
        raise PermissionError(f"Write denied: {reason}")
    
    # 解析路径
    real_path = _fs_manager.resolve_path(path)
    
    # 执行操作
    real_path.parent.mkdir(parents=True, exist_ok=True)
    real_path.write_text(content)
    
    # 记录审计
    _fs_manager.audit_operation("write", path, True)
    
    return {"success": True, "path": path}
```

### 删除文件工具

```python
async def delete_file_tool(
    path: str,
    _fs_manager: FileSystemManager,
) -> dict:
    """Delete file with permission checking."""
    # 验证权限
    allowed, reason = _fs_manager.validate_delete_access(path)
    if not allowed:
        raise PermissionError(f"Delete denied: {reason}")
    
    # 解析路径
    real_path = _fs_manager.resolve_path(path)
    
    # 执行操作
    if real_path.exists():
        real_path.unlink()
    
    # 记录审计
    _fs_manager.audit_operation("delete", path, True)
    
    return {"success": True, "path": path}
```

## 错误处理

```python
from pathlib import Path

try:
    # 尝试解析路径
    real_path = fs_manager.resolve_path(path)
except ValueError as e:
    # 路径无效
    print(f"Invalid path: {e}")
except PermissionError as e:
    # 访问被拒绝
    print(f"Access denied: {e}")

# 检查权限而不抛出异常
allowed, reason = fs_manager.validate_read_access(path)
if not allowed:
    print(f"Cannot read: {reason}")
```

## 配置

### 环境变量

```bash
# 工作区配置
export XAGENT_WORKSPACE_BASE=/workspaces
export XAGENT_WORKSPACE_MAX_SIZE_MB=1000
export XAGENT_WORKSPACE_TTL_HOURS=24

# 挂载配置
export XAGENT_MOUNT_STORAGE_PATH=/data/mounts.json

# 审计配置
export XAGENT_AUDIT_PATH=/data/audit.jsonl
```

### Python配置

```python
from pathlib import Path
from backend.app.settings import PROJECT_ROOT

# 工作区配置
WORKSPACE_BASE = PROJECT_ROOT / "workspaces"
WORKSPACE_MAX_SIZE_MB = 1000
WORKSPACE_TTL_HOURS = 24

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
MOUNT_STORAGE_PATH = DATA_DIR / "mounts.json"
AUDIT_PATH = DATA_DIR / "audit.jsonl"
```

## 测试

### 运行所有测试

```bash
pytest tests/test_workspace_management.py -v
```

### 运行特定测试类

```bash
# 工作区管理器测试
pytest tests/test_workspace_management.py::TestWorkspaceManager -v

# 路径映射器测试
pytest tests/test_workspace_management.py::TestPathMapper -v

# 挂载管理器测试
pytest tests/test_workspace_management.py::TestMountManager -v

# 访问控制测试
pytest tests/test_workspace_management.py::TestFileAccessControl -v
```

### 运行特定测试

```bash
# 测试路径遍历防护
pytest tests/test_workspace_management.py::TestPathMapper::test_path_traversal_attack_prevention -v

# 测试符号链接防护
pytest tests/test_workspace_management.py::TestPathMapper::test_symlink_attack_prevention -v
```

## 调试

### 启用调试日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("filesystem_manager")
logger.setLevel(logging.DEBUG)
```

### 检查审计日志

```python
# 获取最近的操作
logs = fs_manager.get_audit_logs(limit=10)
for log in logs:
    print(f"{log['timestamp']} - {log['operation']} - {log['path']} - {log['success']}")
```

### 验证工作区

```python
# 检查工作区大小
ws = fs_manager.workspace_manager.get_workspace(workspace_id)
print(f"Size: {ws.get_size_mb()}MB / {ws.max_size_mb}MB")
print(f"Over quota: {ws.is_over_quota()}")
print(f"Expired: {ws.is_expired()}")
```

## 性能优化

### 缓存路径解析

```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def resolve_path_cached(path: str, user_id: str) -> Path:
    return fs_manager.resolve_path(path)
```

### 批量操作

```python
# 批量验证多个路径
paths = ["/file1.txt", "/file2.txt", "/file3.txt"]
results = [
    fs_manager.validate_read_access(p)
    for p in paths
]
```

### 异步操作

```python
import asyncio

async def process_files(paths: list[str]):
    tasks = [
        read_file_tool(path, fs_manager)
        for path in paths
    ]
    results = await asyncio.gather(*tasks)
    return results
```

## 常见问题

### Q: 如何处理Windows路径?
```python
# 自动转换
windows_path = "C:\\Users\\data"
posix_path = fs_manager.path_mapper.convert_windows_to_posix(windows_path)
```

### Q: 如何限制文件大小?
```python
# 在验证时检查
allowed, reason = fs_manager.validate_write_access(
    path,
    size_bytes=100*1024*1024,  # 100MB
)
```

### Q: 如何禁止特定文件类型?
```python
# 添加禁止扩展名
fs_manager.access_control.add_forbidden_extension(".exe")
fs_manager.access_control.add_forbidden_extension(".dll")
```

### Q: 如何获取工作区统计?
```python
# 获取工作区信息
ws = fs_manager.workspace_manager.get_workspace(workspace_id)
print(f"Type: {ws.workspace_type}")
print(f"Size: {ws.get_size_mb()}MB")
print(f"Created: {ws.created_at}")
```

## 相关文件

- `backend/app/core/workspace_manager.py` - 工作区管理
- `backend/app/core/path_mapper.py` - 路径映射
- `backend/app/core/mount_manager.py` - 挂载管理
- `backend/app/core/file_access_control.py` - 访问控制
- `backend/app/core/filesystem_manager.py` - 集成管理器
- `backend/app/api/workspace.py` - API端点
- `tests/test_workspace_management.py` - 测试套件
- `FILESYSTEM_INTEGRATION_GUIDE.md` - 集成指南
- `FILESYSTEM_COMPLETION_REPORT.md` - 完成报告

## 更多信息

详见:
- FILESYSTEM_INTEGRATION_GUIDE.md - 完整集成指南
- FILESYSTEM_COMPLETION_REPORT.md - 项目完成报告
- 各模块的docstring - 详细API文档
