"""
# X-Agent 工具并行调用 - 集成指南

## 集成步骤

### 1. 注册API路由

在 `backend/app/web.py` 中添加：

```python
from backend.app.api.tools_batch import router as batch_router

# 在FastAPI应用中注册路由
app.include_router(batch_router)
```

### 2. 启用LLM提示

在LLM初始化代码中添加：

```python
from backend.app.core.parallel_tool_prompt import ParallelToolPrompt

# 获取系统提示
system_prompt = ParallelToolPrompt.system_prompt()

# 添加到LLM系统提示
llm_config = {
    "system_prompt": system_prompt,
    # ... 其他配置
}
```

### 3. 在工具注册中集成

现有的 `ToolRegistry` 已自动支持批量执行：

```python
# 创建工具注册表
registry = build_default_tool_registry(
    policy_engine=policy_engine,
    approval_store=approval_store,
    execution_store=execution_store,
)

# 现在支持批量执行
context = RunContext(...)
tool_calls = [
    {"name": "read_file", "arguments": {"path": "file1.txt"}},
    {"name": "read_file", "arguments": {"path": "file2.txt"}},
]

records = await registry.execute_batch(context, tool_calls)
```

## 配置选项

### ParallelToolExecutor 配置

```python
from backend.app.core.parallel_tool_executor import ParallelToolExecutor
from backend.app.core.tool_result_cache import ToolResultCache

# 创建缓存
cache = ToolResultCache(
    max_size=1000,      # 最大缓存条目数
    default_ttl=300,    # 默认TTL（秒）
)

# 创建执行器
executor = ParallelToolExecutor(
    tool_registry=registry,
    cache=cache,
    max_concurrent=10,      # 最大并发数
    default_timeout=30.0,   # 默认超时（秒）
)
```

### ToolResultCache 配置

```python
cache = ToolResultCache(
    max_size=1000,      # 缓存大小
    default_ttl=300,    # 默认TTL
)

# 自定义TTL
await cache.set(
    "read_file",
    {"path": "file.txt"},
    "content",
    ttl=600  # 10分钟
)
```

### ToolCallBatcher 配置

```python
from backend.app.core.tool_call_batcher import ToolCallBatcher

batcher = ToolCallBatcher(
    max_batch_size=50  # 每个批次最多50个调用
)

# 批处理
batches = batcher.batch_tool_calls(tool_calls)

# 优化
optimized = batcher.optimize_batches(batches)
```

## 环境变量

在 `.env` 文件中配置：

```bash
# 并行执行配置
PARALLEL_TOOLS_MAX_CONCURRENT=10
PARALLEL_TOOLS_DEFAULT_TIMEOUT=30
PARALLEL_TOOLS_BATCH_SIZE=50

# 缓存配置
TOOL_CACHE_MAX_SIZE=1000
TOOL_CACHE_DEFAULT_TTL=300
TOOL_CACHE_ENABLE_PERSISTENCE=false
TOOL_CACHE_PERSISTENCE_PATH=/var/cache/x-agent/tools
```

## 监控和日志

### 启用详细日志

```python
import logging

# 设置日志级别
logging.getLogger("backend.app.core.parallel_tool_executor").setLevel(logging.DEBUG)
logging.getLogger("backend.app.core.tool_dependency_analyzer").setLevel(logging.DEBUG)
logging.getLogger("backend.app.core.tool_result_cache").setLevel(logging.DEBUG)
```

### 监控指标

```python
# 获取执行统计
stats = executor.get_stats()
print(f"总调用: {stats.total_calls}")
print(f"成功: {stats.successful_calls}")
print(f"失败: {stats.failed_calls}")
print(f"缓存命中: {stats.cached_calls}")
print(f"总耗时: {stats.total_latency_ms}ms")
print(f"并行度: {stats.parallelism_factor}x")

# 获取缓存统计
cache_stats = cache.get_stats()
print(f"缓存命中率: {cache_stats.hit_rate:.2%}")
print(f"缓存大小: {cache_stats.current_size}/{cache_stats.max_size}")
```

## 与现有系统的兼容性

### 向后兼容性

所有现有的工具执行代码继续工作：

```python
# 旧方式（仍然支持）
record = await registry.execute(context, "read_file", {"path": "file.txt"})

# 新方式（并行）
records = await registry.execute_batch(
    context,
    [{"name": "read_file", "arguments": {"path": "file.txt"}}]
)
```

### 与审批系统的集成

批量执行尊重现有的审批策略：

```python
# 高风险工具仍然需要审批
calls = [
    {"name": "write_file", "arguments": {"path": "file.txt", "content": "data"}},
    {"name": "read_file", "arguments": {"path": "config.txt"}},
]

# write_file 可能需要审批，read_file 不需要
records = await registry.execute_batch(context, calls)

# 检查审批状态
for record in records:
    if not record.success and "Approval request" in record.error:
        print(f"需要审批: {record.error}")
```

### 与追踪系统的集成

所有批量执行都被追踪：

```python
# 每个调用都有独立的追踪记录
records = await registry.execute_batch(context, calls)

# 可以通过trace_id查询
for record in records:
    print(f"Trace ID: {record.trace_id}")
    print(f"Request ID: {record.request_id}")
```

## 故障恢复

### 部分失败处理

```python
# 允许部分失败
results = await executor.execute_batch(
    calls,
    context,
    allow_partial_failure=True
)

# 检查失败
failed = [r for r in results if not r.success]
if failed:
    # 处理失败
    for result in failed:
        logger.error(f"Tool {result.tool_name} failed: {result.error}")
```

### 重试机制

```python
# 配置重试
call = ToolCall(
    tool_name="read_file",
    arguments={"path": "file.txt"},
    retry_count=3,  # 失败时重试3次
    timeout_seconds=60.0,
)

result = await executor._execute_single(call, context)
print(f"重试次数: {result.retry_attempt}")
```

### 超时处理

```python
# 配置超时
call = ToolCall(
    tool_name="long_operation",
    arguments={"data": "large_dataset"},
    timeout_seconds=120.0,  # 2分钟超时
)

try:
    result = await executor._execute_single(call, context)
except asyncio.TimeoutError:
    logger.error("Tool execution timed out")
```

## 性能优化

### 1. 调整并发限制

```python
# 对于I/O密集型操作，增加并发
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=20,  # 增加到20
)

# 对于CPU密集型操作，减少并发
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=4,  # 减少到4
)
```

### 2. 优化缓存

```python
# 增加缓存大小以提高命中率
cache = ToolResultCache(
    max_size=5000,      # 增加到5000
    default_ttl=600,    # 增加TTL到10分钟
)

# 监控缓存效率
stats = cache.get_stats()
if stats.hit_rate < 0.5:
    print("缓存命中率低，考虑增加大小或TTL")
```

### 3. 批大小优化

```python
# 对于小操作，使用较小的批
batcher = ToolCallBatcher(max_batch_size=10)

# 对于大操作，使用较大的批
batcher = ToolCallBatcher(max_batch_size=100)
```

## 测试

### 单元测试

```bash
# 运行所有并行工具测试
pytest tests/test_parallel_tools.py -v

# 运行特定测试
pytest tests/test_parallel_tools.py::TestParallelToolExecutor::test_execute_batch_simple -v
```

### 性能基准测试

```bash
# 运行性能基准测试
python tests/benchmark_parallel_tools.py
```

### 集成测试

```bash
# 运行集成测试
pytest tests/test_parallel_tools.py -v -m integration
```

## 故障排除

### 问题1：循环依赖错误

```
ValueError: Circular dependencies detected
```

**原因**：工具调用之间存在循环依赖

**解决方案**：
```python
# 检查依赖关系
analyzer = ToolDependencyAnalyzer()
graph = analyzer.analyze_dependencies(calls)
cycles = analyzer.detect_cycles(graph)
print(f"循环: {cycles}")

# 重新组织调用以消除循环
```

### 问题2：缓存不一致

```
CacheError: Cache entry expired
```

**原因**：缓存条目过期或被淘汰

**解决方案**：
```python
# 增加TTL
await cache.set(tool_name, args, result, ttl=600)

# 或增加缓存大小
cache = ToolResultCache(max_size=5000)

# 或禁用缓存
executor = ParallelToolExecutor(
    tool_registry=registry,
    cache=None,  # 禁用缓存
)
```

### 问题3：超时错误

```
asyncio.TimeoutError: Tool execution timeout
```

**原因**：工具执行超过超时时间

**解决方案**：
```python
# 增加超时时间
call = ToolCall(
    tool_name="slow_tool",
    arguments={...},
    timeout_seconds=120.0,  # 增加到2分钟
)

# 或减少并发以给每个工具更多资源
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=5,  # 减少并发
)
```

### 问题4：内存使用过高

```
MemoryError: Unable to allocate memory
```

**原因**：缓存或执行队列过大

**解决方案**：
```python
# 减少缓存大小
cache = ToolResultCache(max_size=500)

# 减少并发
executor = ParallelToolExecutor(
    tool_registry=registry,
    max_concurrent=5,
)

# 定期清理缓存
await cache.invalidate()
```

## 最佳实践总结

1. **识别独立操作**：只并行执行真正独立的操作
2. **使用有意义的ID**：为每个调用使用清晰的call_id
3. **监控性能**：定期检查执行统计和缓存效率
4. **处理失败**：实现适当的错误处理和重试逻辑
5. **优化配置**：根据工作负载调整并发和缓存设置
6. **测试充分**：在生产前进行充分的性能测试

## 支持和反馈

如有问题或建议，请提交Issue或联系开发团队。
"""
