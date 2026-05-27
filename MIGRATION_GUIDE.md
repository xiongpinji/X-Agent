# X-Agent 迁移指南

## 概述

本指南说明如何将现有的Agent引擎、工具系统和记忆系统逐步迁移到新的7个核心系统架构。迁移过程保持向后兼容性，支持新旧系统并行运行。

## 新架构概览

### 7个核心系统

1. **上下文管理系统** (`context_manager.py`)
   - 会话恢复：从快照恢复之前的会话状态
   - 上下文压缩：当token使用超过阈值时压缩上下文
   - 快照管理：定期保存会话快照以支持恢复
   - 内存优化：自动清理过期的快照和上下文

2. **并行工具执行器** (`parallel_tool_executor.py`)
   - 批量执行：同时执行多个工具调用
   - 超时管理：为每个工具设置超时
   - 重试机制：失败的工具自动重试
   - 依赖管理：支持工具间的依赖关系
   - 结果聚合：收集所有工具的执行结果

3. **混合记忆系统** (`hybrid_memory_system.py`)
   - 分层存储：热存储、向量存储、图存储
   - 智能检索：多维度记忆查询
   - 自动去重：消除重复记忆
   - 关系管理：维护记忆间的关系

4. **文件系统管理器** (`filesystem_manager.py`)
   - 虚拟路径映射：安全的路径隔离
   - 访问控制：基于用户的权限检查
   - 工作区管理：多用户隔离
   - 安全防护：防止路径遍历攻击

5. **兼容层** (`compatibility_layer.py`)
   - 旧工具包装：使用新架构执行旧工具
   - 数据迁移：将旧数据迁移到新系统
   - API适配：提供旧API的适配器
   - 渐进式迁移：支持新旧系统并行运行

6. **迁移适配器** (`agent_migration_adapter.py`)
   - Agent引擎集成：集成新系统到Agent引擎
   - 工具注册表适配：支持新旧工具并行
   - 记忆系统适配：支持新旧记忆并行
   - 迁移编排：协调整个迁移过程

7. **验证报告** (`migration_verification_report.py`)
   - 迁移检查点：记录迁移过程
   - 性能指标：收集迁移指标
   - 验证报告：生成迁移验证报告

## 迁移步骤

### 第1步：准备阶段

#### 1.1 备份现有系统

```bash
# 备份数据库
pg_dump xagent_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 备份配置文件
cp -r config/ config_backup_$(date +%Y%m%d_%H%M%S)/

# 备份代码
git tag migration_backup_$(date +%Y%m%d_%H%M%S)
```

#### 1.2 创建测试环境

```bash
# 创建测试分支
git checkout -b migration/test

# 创建测试数据库
createdb xagent_test
```

#### 1.3 准备回滚方案

- 记录当前系统版本
- 准备回滚脚本
- 测试回滚流程

### 第2步：上下文管理系统迁移

#### 2.1 初始化上下文管理器

```python
from backend.app.core.context_manager import ContextManager

# 创建上下文管理器
context_manager = ContextManager(
    storage_path="data/context",
    max_tokens=150000,
    compression_threshold=0.8,
    max_snapshots=10
)
```

#### 2.2 集成到Agent引擎

```python
from backend.app.core.agent import AgentLoop
from backend.app.core.agent_migration_adapter import AgentLoopMigrationAdapter

# 创建迁移适配器
adapter = AgentLoopMigrationAdapter(
    agent_loop=agent_loop,
    storage_path="data/context"
)

# 运行Agent
result = await adapter.run_with_migration(context, task)
```

#### 2.3 测试会话恢复

```python
# 创建会话
session_id = await context_manager.create_session()

# 保存上下文
await context_manager.save_snapshot(
    session_id,
    {"task": "test", "status": "in_progress"}
)

# 恢复会话
recovered = await context_manager.recover_session(session_id)
assert recovered["task"] == "test"
```

#### 2.4 测试上下文压缩

```python
# 创建大上下文
large_context = {"data": "x" * 10000}

# 保存并压缩
await context_manager.save_snapshot(session_id, large_context)

# 检查压缩
should_compress = context_manager.should_compress(session_id)
if should_compress:
    compressed = await context_manager.compress_context(session_id)
```

### 第3步：工具系统迁移

#### 3.1 初始化并行执行器

```python
from backend.app.core.parallel_tool_executor import ParallelToolExecutor

# 创建并行执行器
executor = ParallelToolExecutor(
    max_parallel=5,
    timeout=30,
    max_retries=2
)
```

#### 3.2 集成到工具注册表

```python
from backend.app.core.agent_migration_adapter import ToolRegistryMigrationAdapter

# 创建工具适配器
tool_adapter = ToolRegistryMigrationAdapter(tool_registry)

# 执行工具
result = await tool_adapter.execute_tool(context, "tool_name", arguments)
```

#### 3.3 测试并行执行

```python
# 准备多个工具调用
tool_calls = [
    ("tool1", {"arg": "value1"}),
    ("tool2", {"arg": "value2"}),
    ("tool3", {"arg": "value3"}),
]

# 并行执行
results = await executor.execute_batch(tool_calls, context, executor_func)

# 验证结果
assert len(results) == 3
assert all(r.success for r in results)
```

#### 3.4 测试工具重试

```python
# 执行可能失败的工具
result = await executor._execute_with_retry(task, context, executor_func)

# 验证重试
assert result.retry_count >= 0
```

### 第4步：记忆系统迁移

#### 4.1 初始化混合记忆系统

```python
from backend.app.core.hybrid_memory_system import HybridMemorySystem

# 创建混合记忆系统
hybrid_memory = HybridMemorySystem(
    hot_storage_path="data/memory/hot",
    qdrant_client=qdrant_client,
    neo4j_client=neo4j_client
)
```

#### 4.2 迁移旧记忆数据

```python
from backend.app.core.compatibility_layer import CompatibilityLayer

# 创建兼容层
compat = CompatibilityLayer()

# 迁移旧记忆
migrated = compat.migrate_old_memory(old_memory_store)

# 验证迁移
assert migrated["metadata"]["migration_status"] == "completed"
```

#### 4.3 测试记忆存储

```python
# 存储新记忆
memory_id = await hybrid_memory.store(
    "Important information",
    importance=0.8,
    tags=["important"]
)

# 验证存储
assert memory_id is not None
```

#### 4.4 测试记忆检索

```python
# 检索记忆
results = await hybrid_memory.recall("information", limit=5)

# 验证检索
assert len(results) > 0
```

### 第5步：文件系统迁移

#### 5.1 初始化文件系统管理器

```python
from backend.app.core.filesystem_manager import FileSystemManager

# 创建文件系统管理器
fs_manager = FileSystemManager()
```

#### 5.2 配置访问控制

```python
# 配置工作区
workspace = fs_manager.workspace_manager.create_workspace(
    user_id="user123",
    workspace_type="project"
)

# 配置权限
fs_manager.access_control.grant_permission(
    user_id="user123",
    path="/project/src",
    permission="read_write"
)
```

#### 5.3 测试文件操作

```python
# 映射虚拟路径
real_path = fs_manager.path_mapper.map_virtual_to_real(
    "/project/file.txt",
    "user123"
)

# 检查权限
has_permission = fs_manager.access_control.check_read_permission(
    "user123",
    real_path
)

assert has_permission
```

### 第6步：兼容层集成

#### 6.1 创建兼容层

```python
from backend.app.core.compatibility_layer import CompatibilityLayer

# 创建兼容层
compat = CompatibilityLayer()
```

#### 6.2 包装旧工具

```python
# 定义旧工具
def old_tool(arg1, arg2):
    return f"{arg1}_{arg2}"

# 注册旧工具
compat.register_wrapped_tool("old_tool", old_tool)

# 获取包装的工具
wrapped = compat.get_wrapped_tool("old_tool")
```

#### 6.3 迁移旧记忆

```python
# 迁移旧记忆
migrated = compat.migrate_old_memory(old_memory_store)

# 验证迁移
assert migrated["metadata"]["migration_status"] == "completed"
```

#### 6.4 测试兼容性

```python
# 执行旧工具
result = await wrapped(context, arg1="hello", arg2="world")

# 验证结果
assert result.success
assert result.output == "hello_world"
```

### 第7步：测试验证

#### 7.1 运行单元测试

```bash
# 运行迁移测试
pytest tests/test_migration.py -v

# 运行兼容性测试
pytest tests/test_compatibility.py -v
```

#### 7.2 运行集成测试

```bash
# 运行集成测试
pytest tests/test_integration.py -v

# 运行端到端测试
pytest tests/test_e2e.py -v
```

#### 7.3 性能测试

```bash
# 运行性能测试
pytest tests/test_performance.py -v

# 比较性能指标
python scripts/compare_performance.py
```

#### 7.4 兼容性测试

```bash
# 运行兼容性测试
pytest tests/test_backward_compatibility.py -v
```

### 第8步：逐步迁移

#### 8.1 迁移第一批工具

```python
# 标记工具已迁移
tool_adapter.mark_tool_migrated("tool1")
tool_adapter.mark_tool_migrated("tool2")

# 获取迁移状态
status = tool_adapter.get_tool_migration_status()
print(f"Migration: {status['migration_percentage']:.1%}")
```

#### 8.2 监控性能

```python
# 收集性能指标
metrics = {
    "execution_time": 0.5,
    "memory_usage": 100,
    "success_rate": 0.99
}

# 比较性能
if metrics["execution_time"] < baseline["execution_time"]:
    print("Performance improved!")
```

#### 8.3 收集反馈

- 监控错误日志
- 收集用户反馈
- 分析性能指标

#### 8.4 迭代改进

- 修复发现的问题
- 优化性能
- 重复迁移过程

### 第9步：生产部署

#### 9.1 灰度发布

```bash
# 部署到10%的用户
kubectl set env deployment/xagent MIGRATION_PERCENTAGE=10

# 监控指标
kubectl logs -f deployment/xagent
```

#### 9.2 监控指标

- 错误率
- 响应时间
- 内存使用
- CPU使用

#### 9.3 准备回滚

```bash
# 准备回滚脚本
git checkout migration_backup_20240101_120000

# 测试回滚
./scripts/rollback.sh
```

#### 9.4 完全切换

```bash
# 部署到100%的用户
kubectl set env deployment/xagent MIGRATION_PERCENTAGE=100

# 验证部署
kubectl rollout status deployment/xagent
```

## 常见问题

### Q: 迁移期间如何保证服务可用性？

A: 使用兼容层支持新旧系统并行运行。旧工具通过包装器执行，新工具直接执行。逐步迁移工具，确保服务持续可用。

### Q: 如何处理旧数据？

A: 使用`CompatibilityLayer.migrate_old_memory()`迁移旧记忆数据。迁移过程是非破坏性的，旧数据保持不变。

### Q: 性能会受到影响吗？

A: 新系统通过以下方式提高性能：
- 并行执行工具（提高吞吐量）
- 智能缓存（减少重复计算）
- 上下文压缩（减少内存使用）
- 分层存储（优化检索速度）

### Q: 如何验证迁移成功？

A: 运行完整的测试套件，包括：
- 单元测试
- 集成测试
- 性能测试
- 兼容性测试

### Q: 如何回滚迁移？

A: 如果迁移出现问题，按以下步骤回滚：

1. 停止新系统
2. 恢复旧系统备份
3. 验证功能
4. 分析问题
5. 修复后重新迁移

## 支持

如有问题，请参考：

- 迁移测试: `tests/test_migration.py`
- 兼容性测试: `tests/test_compatibility.py`
- 性能测试: `tests/test_performance.py`
- 迁移适配器: `backend/app/core/agent_migration_adapter.py`
- 兼容层: `backend/app/core/compatibility_layer.py`

## 总结

本迁移指南提供了从现有系统到新架构的完整迁移路径。通过遵循这些步骤，可以确保平稳的迁移过程，同时保持服务可用性和数据完整性。

关键要点：
- 逐步迁移，不要一次性全部替换
- 充分测试每个迁移步骤
- 保持向后兼容性
- 监控性能指标
- 准备回滚方案
