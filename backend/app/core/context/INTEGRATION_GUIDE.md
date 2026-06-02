# X-Agent 上下文管理系统集成指南

## 1. 快速开始

### 1.1 安装依赖

上下文管理系统已包含在X-Agent中，无需额外安装。确保以下依赖已安装：

```bash
pip install tiktoken>=0.5.0
pip install qdrant-client>=1.11.0
```

### 1.2 基本使用

```python
from backend.app.core.context import ContextManager, SessionRecovery
from backend.app.core.context_compactor import ContextCompactor

# 初始化组件
session_recovery = SessionRecovery(storage_path="~/.xagent/sessions")
context_compactor = ContextCompactor(model="gpt-4", token_limit=128_000)

# 创建上下文管理器
context_manager = ContextManager(
    session_recovery=session_recovery,
    context_compactor=context_compactor,
    auto_compress_enabled=True,
)

# 初始化会话
await context_manager.initialize_session(
    session_id="my-session",
    agent_id="agent-1",
    tenant_id="tenant-1",
)

# 添加消息
message = await context_manager.add_message(
    role="user",
    content="What is 2+2?",
)

# 获取当前上下文
context = await context_manager.get_context()

# 保存会话
await context_manager.save_session()
```

## 2. 集成到Agent执行循环

### 2.1 在agent.py中集成

```python
from backend.app.core.context import ContextManager, SessionRecovery
from backend.app.core.context_compactor import ContextCompactor

class AgentLoop:
    def __init__(self, ...):
        # ... 其他初始化 ...
        
        # 初始化上下文管理
        self.session_recovery = SessionRecovery()
        self.context_compactor = ContextCompactor()
        self.context_manager = ContextManager(
            session_recovery=self.session_recovery,
            context_compactor=self.context_compactor,
            auto_compress_enabled=True,
        )
    
    async def run(self, context: RunContext):
        # 初始化或恢复会话
        await self.context_manager.initialize_session(
            session_id=context.session_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
        )
        
        # 启动自动保存
        await self.context_manager.start_auto_save()
        
        try:
            for iteration in range(self.max_iterations):
                # 添加用户消息
                await self.context_manager.add_message(
                    role="user",
                    content=context.user_input,
                )
                
                # 获取当前上下文用于LLM调用
                current_context = await self.context_manager.get_context()
                
                # 调用LLM
                response = await self.llm.complete(
                    messages=current_context,
                    model=context.model,
                )
                
                # 添加助手响应
                await self.context_manager.add_message(
                    role="assistant",
                    content=response.content,
                )
                
                # 执行工具调用
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        result = await self.tools.execute(tool_call)
                        
                        # 添加工具结果
                        await self.context_manager.add_message(
                            role="tool",
                            content=str(result),
                            metadata={"tool": tool_call.name},
                        )
                
                # 自动压缩会在add_message中触发
        
        finally:
            # 停止自动保存并保存最终状态
            await self.context_manager.stop_auto_save()
            await self.context_manager.save_session()
```

### 2.2 在FastAPI应用中注册API

```python
from fastapi import FastAPI
from backend.app.api import sessions

app = FastAPI()

# 创建全局上下文管理器
context_manager = ContextManager(...)

# 注册会话管理API
app.include_router(sessions.router)

# 设置全局上下文管理器
sessions.set_context_manager(context_manager)

# 应用启动时初始化
@app.on_event("startup")
async def startup():
    await context_manager.start_auto_save()

# 应用关闭时清理
@app.on_event("shutdown")
async def shutdown():
    await context_manager.cleanup()
```

## 3. API端点参考

### 3.1 会话管理

#### 初始化会话
```
POST /api/sessions/initialize
Content-Type: application/json

{
  "session_id": "my-session",
  "agent_id": "agent-1",
  "tenant_id": "tenant-1",
  "context_window": 128000
}
```

#### 添加消息
```
POST /api/sessions/messages
Content-Type: application/json

{
  "role": "user",
  "content": "What is 2+2?",
  "metadata": {"source": "api"},
  "importance": 0.8
}
```

#### 获取上下文
```
GET /api/sessions/context?limit=10&include_metadata=true
```

#### 压缩上下文
```
POST /api/sessions/compress
```

#### 保存会话
```
POST /api/sessions/{session_id}/save
```

#### 恢复会话
```
POST /api/sessions/{session_id}/restore
```

#### 列出会话
```
GET /api/sessions?agent_id=agent-1&limit=100
```

#### 删除会话
```
DELETE /api/sessions/{session_id}
```

#### 获取会话统计
```
GET /api/sessions/{session_id}/stats
```

#### 获取指标
```
GET /api/sessions/metrics
```

## 4. 配置选项

### 4.1 ContextManager配置

```python
context_manager = ContextManager(
    session_recovery=session_recovery,
    context_compactor=context_compactor,
    hybrid_memory_system=None,  # 可选
    auto_save_interval_seconds=300,  # 5分钟
    auto_compress_enabled=True,
)
```

### 4.2 SessionRecovery配置

```python
session_recovery = SessionRecovery(
    storage_path="~/.xagent/sessions",  # 存储路径
    snapshot_interval_seconds=300,  # 快照间隔
    retention_days=30,  # 保留天数
)
```

### 4.3 ContextCompactor配置

```python
context_compactor = ContextCompactor(
    model="gpt-4",  # LLM模型
    token_limit=128_000,  # Token限制
    compression_threshold=0.85,  # 压缩阈值
    min_messages_to_keep=3,  # 最少保留消息数
)
```

## 5. 高级用法

### 5.1 自定义消息重要性评分

```python
# 添加消息时指定重要性
await context_manager.add_message(
    role="user",
    content="Important instruction",
    importance=0.9,  # 高重要性
)
```

### 5.2 导出和导入会话

```python
# 导出会话
await session_recovery.export_session(
    session_id="my-session",
    export_path="/path/to/export.json",
)

# 导入会话
imported_session = await session_recovery.import_session(
    import_path="/path/to/export.json",
)
```

### 5.3 会话清理

```python
# 清理旧会话
deleted_count = await session_recovery.cleanup_old_sessions()
print(f"Deleted {deleted_count} old sessions")
```

### 5.4 获取详细指标

```python
# 获取上下文指标
metrics = await context_manager.get_metrics()
print(f"Total messages: {metrics.total_messages}")
print(f"Total tokens: {metrics.total_tokens}")
print(f"Compression ratio: {metrics.compression_ratio:.2%}")
print(f"Compression count: {metrics.compression_count}")

# 获取会话统计
stats = await context_manager.get_session_stats("my-session")
print(f"Message count: {stats.message_count}")
print(f"Storage size: {stats.storage_size_mb:.2f} MB")
```

## 6. 监控和调试

### 6.1 启用日志

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("backend.app.core.context")
logger.setLevel(logging.DEBUG)
```

### 6.2 常见问题

#### 问题：压缩不工作
**解决方案：** 检查token计数是否正确，确保消息内容足够长以触发压缩阈值。

#### 问题：会话恢复失败
**解决方案：** 检查存储路径是否存在且可访问，确保会话文件未损坏。

#### 问题：内存使用过高
**解决方案：** 增加压缩阈值或减少min_messages_to_keep值。

## 7. 性能优化

### 7.1 批量操作

```python
# 批量添加消息
messages = [
    ("user", "Message 1"),
    ("assistant", "Response 1"),
    ("user", "Message 2"),
    ("assistant", "Response 2"),
]

for role, content in messages:
    await context_manager.add_message(role=role, content=content)

# 一次性保存
await context_manager.save_session()
```

### 7.2 异步操作

```python
# 并行处理多个会话
import asyncio

sessions = ["session-1", "session-2", "session-3"]
tasks = [
    context_manager.get_session_stats(sid)
    for sid in sessions
]

stats_list = await asyncio.gather(*tasks)
```

## 8. 与混合记忆系统集成

```python
from backend.app.core.hybrid_memory_system import HybridMemorySystem

# 创建混合记忆系统
hybrid_memory = HybridMemorySystem(
    hot_store=hot_store,
    cold_store=cold_store,
    graph_store=graph_store,
    classifier=classifier,
    merger=merger,
)

# 集成到上下文管理器
context_manager = ContextManager(
    session_recovery=session_recovery,
    context_compactor=context_compactor,
    hybrid_memory_system=hybrid_memory,
)
```

## 9. 测试

### 9.1 运行测试

```bash
# 运行所有上下文管理测试
pytest tests/test_context_management_system.py -v

# 运行特定测试类
pytest tests/test_context_management_system.py::TestSessionInitialization -v

# 运行特定测试
pytest tests/test_context_management_system.py::TestSessionInitialization::test_initialize_new_session -v
```

### 9.2 性能测试

```bash
# 运行性能基准测试
pytest tests/test_context_management_system.py::TestLongConversation -v --benchmark
```

## 10. 故障排除

### 10.1 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 检查会话状态
session_state = await context_manager._current_session
print(f"Messages: {len(session_state.messages)}")
print(f"Total tokens: {session_state.total_tokens}")
print(f"Compressed tokens: {session_state.compressed_tokens}")

# 检查压缩历史
for compression in session_state.compression_history:
    print(f"Compression: {compression}")
```

### 10.2 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| `ValueError: No active session` | 未初始化会话 | 调用 `initialize_session()` |
| `FileNotFoundError` | 存储路径不存在 | 检查存储路径权限 |
| `asyncio.TimeoutError` | 操作超时 | 增加超时时间或检查系统资源 |
| `json.JSONDecodeError` | 会话文件损坏 | 删除损坏的会话文件 |

## 11. 最佳实践

1. **定期保存会话** - 使用自动保存功能
2. **监控Token使用** - 定期检查指标
3. **清理旧会话** - 定期运行cleanup_old_sessions()
4. **错误处理** - 总是在try-finally中调用cleanup()
5. **日志记录** - 启用日志以便调试
6. **性能监控** - 跟踪压缩性能和内存使用

## 12. 迁移指南

### 从旧系统迁移

```python
# 1. 导出旧会话
old_sessions = await old_session_manager.list_sessions()

# 2. 导入到新系统
for old_session in old_sessions:
    new_session = SessionState(
        session_id=old_session.id,
        agent_id=old_session.agent_id,
        messages=[...],  # 转换消息格式
    )
    await session_recovery.save_snapshot(new_session)
```

## 13. 支持和反馈

如有问题或建议，请提交Issue或Pull Request。

## 14. 更新日志

### v1.0.0 (2026-05-28)
- 初始版本发布
- 完整的会话管理功能
- 自动Token压缩
- REST API端点
- 集成测试

### v2.0.0 (2026-05-30)
- Phase 4 新增：智能压缩、智能检索、代码库索引
- ContextManager 集成三个新组件
- 混合检索策略支持
- 代码库符号索引和依赖分析

## 15. Phase 4 新增能力概览

Phase 4 为上下文管理系统引入了三个强大的新模块：

1. **ContextCompressor** - 智能上下文压缩，支持多种策略
2. **ContextRetriever** - 智能上下文检索，支持混合检索
3. **CodebaseIndex** - 代码库索引和搜索，支持多语言

这些模块已集成到 ContextManager 中，可通过统一入口使用。

## 16. 通过 ContextManager 统一入口使用新能力

### 16.1 端到端示例

```python
from backend.app.core.context import ContextManager
from backend.app.core.context.compression import ContextCompressor
from backend.app.core.context.retrieval import ContextRetriever, RetrievalWeights
from backend.app.core.context.code_index import CodebaseIndex
from datetime import datetime, timedelta

# 初始化三个新组件
compressor = ContextCompressor()
retriever = ContextRetriever()
codebase_index = CodebaseIndex()

# 创建 ContextManager，注入新组件
context_manager = ContextManager(
    session_recovery=session_recovery,
    context_compactor=context_compactor,
    context_compressor=compressor,
    context_retriever=retriever,
    codebase_index=codebase_index,
    auto_compress_enabled=True,
)

# 初始化会话
await context_manager.initialize_session(
    session_id="my-session",
    agent_id="agent-1",
    tenant_id="tenant-1",
)

# 添加一些消息
await context_manager.add_message(
    role="user",
    content="如何优化数据库查询性能？",
    importance=0.8,
)

await context_manager.add_message(
    role="assistant",
    content="可以通过添加索引、使用查询优化器等方式优化...",
    importance=0.7,
)

# 1. 压缩当前上下文
compressed = await context_manager.compress_context(strategy="hybrid")
if compressed:
    print(f"原始Token数: {compressed.original_tokens}")
    print(f"压缩后Token数: {compressed.compressed_tokens}")
    print(f"压缩率: {compressed.compression_ratio:.2%}")

# 2. 检索相关上下文
query = "数据库性能优化"
retrieved_items = await context_manager.retrieve_context(
    query=query,
    limit=5,
    weights=RetrievalWeights(relevance=0.6, recency=0.2, importance=0.2)
)
for item in retrieved_items:
    print(f"[{item.role}] {item.content[:50]}... (相关性: {item.relevance_score:.2f})")

# 3. 建立代码库索引
index_stats = await context_manager.index_codebase(
    root_path="/path/to/project"
)
if index_stats:
    print(f"已索引文件数: {index_stats.indexed_files}")
    print(f"总符号数: {index_stats.total_symbols}")

# 4. 搜索代码库
code_matches = await context_manager.search_codebase(
    query="数据库连接池",
    file_types=[".py"],
    limit=10
)
for match in code_matches:
    print(f"{match.file_path}:{match.line_number} - {match.content[:40]}...")
```

### 16.2 在Agent循环中使用

```python
class EnhancedAgentLoop:
    def __init__(self, ...):
        self.context_manager = ContextManager(
            context_compressor=ContextCompressor(),
            context_retriever=ContextRetriever(),
            codebase_index=CodebaseIndex(),
            # ... 其他配置
        )
    
    async def run(self, context: RunContext):
        await self.context_manager.initialize_session(
            session_id=context.session_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
        )
        
        # 建立代码库索引（首次运行）
        if not self.context_manager.codebase_index.get_stats():
            await self.context_manager.index_codebase(context.project_root)
        
        for iteration in range(self.max_iterations):
            # 添加用户消息
            await self.context_manager.add_message(
                role="user",
                content=context.user_input,
                importance=0.8,
            )
            
            # 检索相关上下文
            relevant_context = await self.context_manager.retrieve_context(
                query=context.user_input,
                limit=10,
            )
            
            # 搜索相关代码
            code_matches = await self.context_manager.search_codebase(
                query=context.user_input,
                limit=5,
            )
            
            # 构建增强的上下文
            enhanced_messages = await self.context_manager.get_context()
            
            # 调用LLM
            response = await self.llm.complete(
                messages=enhanced_messages,
                model=context.model,
            )
            
            # 添加助手响应
            await self.context_manager.add_message(
                role="assistant",
                content=response.content,
            )
            
            # 定期压缩上下文
            if iteration % 5 == 0:
                await self.context_manager.compress_context(strategy="hybrid")
```

## 17. ContextCompressor 详细用法

### 17.1 三种压缩策略对比

```python
from backend.app.core.context.compression import ContextCompressor

compressor = ContextCompressor()

# 长上下文示例
long_content = """
用户问题：如何实现分布式事务？
助手回答：分布式事务是在多个数据库或服务间保证ACID特性的机制。
主要方案包括：
1. 两阶段提交（2PC）- 协调器和参与者模式
2. 事件溯源 - 基于事件日志的最终一致性
3. Saga模式 - 长事务分解为本地事务序列
4. TCC模式 - Try-Confirm-Cancel三阶段
每种方案都有权衡...
"""

# 1. Summary 策略 - 提取关键摘要
compressed_summary = compressor.compress(
    content=long_content,
    target_ratio=0.5,
    strategy="summary"
)
print(f"Summary 策略:")
print(f"  原始: {compressed_summary.original_tokens} tokens")
print(f"  压缩后: {compressed_summary.compressed_tokens} tokens")
print(f"  压缩率: {compressed_summary.compression_ratio:.2%}")
print(f"  关键信息: {[ki.text for ki in compressed_summary.key_info[:3]]}")

# 2. Semantic 策略 - 基于语义相似度
compressed_semantic = compressor.compress(
    content=long_content,
    target_ratio=0.5,
    strategy="semantic"
)
print(f"\nSemantic 策略:")
print(f"  压缩后: {compressed_semantic.compressed_tokens} tokens")
print(f"  内容: {compressed_semantic.content[:100]}...")

# 3. Hybrid 策略 - 结合摘要和语义（推荐）
compressed_hybrid = compressor.compress(
    content=long_content,
    target_ratio=0.5,
    strategy="hybrid"
)
print(f"\nHybrid 策略（推荐）:")
print(f"  压缩后: {compressed_hybrid.compressed_tokens} tokens")
print(f"  压缩率: {compressed_hybrid.compression_ratio:.2%}")
```

### 17.2 异步压缩

```python
# 异步压缩大型内容
compressed_async = await compressor.compress_async(
    content=very_large_content,
    target_ratio=0.4,
    strategy="hybrid"
)
print(f"异步压缩完成: {compressed_async.compression_ratio:.2%}")
```

### 17.3 增量压缩

```python
# 流式处理大型文档，逐块压缩
chunks = [
    "第一部分内容...",
    "第二部分内容...",
    "第三部分内容...",
]

compressed_chunks = []
for chunk in compressor.compress_incremental(
    chunks=iter(chunks),
    target_ratio=0.5
):
    compressed_chunks.append(chunk)
    print(f"已压缩块: {chunk.content[:50]}...")

print(f"总共压缩 {len(compressed_chunks)} 块")
```

### 17.4 提取关键信息

```python
# 提取内容中的关键信息
key_infos = compressor.extract_key_info(long_content)

for ki in key_infos:
    print(f"关键信息: {ki.text}")
    print(f"  重要性: {ki.importance:.2f}")
    print(f"  类别: {ki.category}")
    print(f"  位置: {ki.position}")
```

## 18. ContextRetriever 详细用法

### 18.1 四种检索策略

```python
from backend.app.core.context.retrieval import ContextRetriever, RetrievalWeights
from datetime import datetime, timedelta

# 初始化检索器，传入消息列表
messages = [
    Message(role="user", content="如何使用Docker？", timestamp=datetime.now()),
    Message(role="assistant", content="Docker是容器化平台...", timestamp=datetime.now()),
    Message(role="user", content="Docker和虚拟机的区别？", timestamp=datetime.now()),
]

retriever = ContextRetriever(messages=messages)

# 1. 相关性检索 - 基于语义相似度
print("=== 相关性检索 ===")
relevant_items = retriever.retrieve_by_relevance(
    query="容器技术",
    top_k=5
)
for item in relevant_items:
    print(f"[{item.role}] {item.content[:50]}... (相关性: {item.relevance_score:.2f})")

# 2. 时间范围检索 - 基于时间戳
print("\n=== 时间范围检索 ===")
one_hour_ago = datetime.now() - timedelta(hours=1)
now = datetime.now()
time_items = retriever.retrieve_by_time(
    start=one_hour_ago,
    end=now,
    sort_order="desc"  # 最新优先
)
for item in time_items:
    print(f"[{item.timestamp}] {item.content[:50]}...")

# 3. 重要性检索 - 基于优先级
print("\n=== 重要性检索 ===")
important_items = retriever.retrieve_by_importance(
    min_priority=0.7,
    top_k=10
)
for item in important_items:
    print(f"[优先级: {item.priority:.2f}] {item.content[:50]}...")

# 4. 混合检索 - 结合多个维度（推荐）
print("\n=== 混合检索 ===")
weights = RetrievalWeights(
    relevance=0.6,   # 60% 权重给相关性
    recency=0.2,     # 20% 权重给时间
    importance=0.2   # 20% 权重给重要性
)
hybrid_items = retriever.retrieve_hybrid(
    query="Docker最佳实践",
    weights=weights,
    top_k=10,
    time_window_hours=24,  # 仅考虑24小时内的消息
    min_priority=0.5       # 最低优先级0.5
)
for item in hybrid_items:
    print(f"[{item.role}] {item.content[:50]}...")
    print(f"  相关性: {item.relevance_score:.2f}, 优先级: {item.priority:.2f}")
```

### 18.2 自定义检索权重

```python
# 场景1：优先最新信息（实时问题）
weights_realtime = RetrievalWeights(
    relevance=0.3,
    recency=0.6,      # 高权重给最新消息
    importance=0.1
)

# 场景2：优先重要信息（知识库查询）
weights_knowledge = RetrievalWeights(
    relevance=0.5,
    recency=0.1,
    importance=0.4    # 高权重给重要消息
)

# 场景3：均衡检索（通用场景）
weights_balanced = RetrievalWeights(
    relevance=0.5,
    recency=0.25,
    importance=0.25
)

# 使用不同权重检索
realtime_results = retriever.retrieve_hybrid(
    query="最新的系统状态",
    weights=weights_realtime
)

knowledge_results = retriever.retrieve_hybrid(
    query="系统架构设计原则",
    weights=weights_knowledge
)
```

### 18.3 动态更新消息

```python
# 添加新消息
new_message = Message(
    role="user",
    content="新的问题",
    timestamp=datetime.now(),
    importance=0.8
)
retriever.add_message(new_message)

# 批量更新消息
new_messages = [
    Message(role="user", content="问题1", timestamp=datetime.now()),
    Message(role="assistant", content="回答1", timestamp=datetime.now()),
]
retriever.update_messages(new_messages)

# 清空所有消息
retriever.clear()
```

## 19. CodebaseIndex 详细用法

### 19.1 建立和管理索引

```python
from backend.app.core.context.code_index import CodebaseIndex
from pathlib import Path

# 创建索引实例
codebase_index = CodebaseIndex()

# 1. 建立完整索引
print("=== 建立代码库索引 ===")
index_stats = codebase_index.build_index(
    root_path="/path/to/project",
    patterns=["*.py", "*.ts", "*.tsx"]  # 可选：指定文件模式
)
print(f"索引统计:")
print(f"  总文件数: {index_stats.total_files}")
print(f"  已索引文件: {index_stats.indexed_files}")
print(f"  总符号数: {index_stats.total_symbols}")
print(f"  索引耗时: {index_stats.index_time_seconds:.2f}秒")
print(f"  最后更新: {index_stats.last_updated}")

# 2. 获取索引统计
stats = codebase_index.get_stats()
print(f"\n当前索引统计: {stats}")

# 3. 获取单个文件信息
file_info = codebase_index.get_file_info("/path/to/project/main.py")
if file_info:
    print(f"\n文件信息:")
    print(f"  路径: {file_info.path}")
    print(f"  符号数: {file_info.symbol_count}")
    print(f"  行数: {file_info.line_count}")

# 4. 列出所有Python文件
py_files = codebase_index.list_files(file_type=".py")
print(f"\nPython文件数: {len(py_files)}")
```

### 19.2 搜索代码库

```python
# 1. 基础搜索
print("=== 代码库搜索 ===")
matches = codebase_index.search(
    query="数据库连接",
    file_types=[".py"],
    limit=10
)
for match in matches:
    print(f"{match.file_path}:{match.line_number}")
    print(f"  内容: {match.content}")
    print(f"  相关性: {match.relevance_score:.2f}")
    print(f"  上下文: {match.context_lines}")

# 2. 跨语言搜索
matches_multi = codebase_index.search(
    query="API端点",
    file_types=[".py", ".ts", ".tsx"],
    limit=20
)
print(f"\n跨语言搜索结果: {len(matches_multi)} 个匹配")

# 3. 不限制文件类型的搜索
all_matches = codebase_index.search(
    query="错误处理",
    limit=15
)
print(f"全局搜索结果: {len(all_matches)} 个匹配")
```

### 19.3 依赖分析

```python
# 1. 获取文件的依赖关系
print("=== 依赖分析 ===")
dep_graph = codebase_index.get_dependencies(
    file_path="/path/to/project/services/user_service.py"
)
print(f"依赖关系图:")
print(f"  直接依赖: {dep_graph.direct_dependencies}")
print(f"  间接依赖: {dep_graph.transitive_dependencies}")
print(f"  循环依赖: {dep_graph.circular_dependencies}")

# 2. 获取依赖该文件的其他文件
dependents = codebase_index.get_dependents(
    file_path="/path/to/project/utils/helpers.py"
)
print(f"\n依赖此文件的模块:")
for dep_file in dependents:
    print(f"  - {dep_file}")
```

### 19.4 增量更新

```python
# 当代码库发生变化时，增量更新索引
changed_files = [
    "/path/to/project/main.py",
    "/path/to/project/services/new_service.py",
]

print("=== 增量更新索引 ===")
update_stats = codebase_index.update_index(changed_files)
print(f"更新统计:")
print(f"  已更新文件: {update_stats.indexed_files}")
print(f"  总符号数: {update_stats.total_symbols}")
print(f"  更新耗时: {update_stats.index_time_seconds:.2f}秒")
```

### 19.5 模块级单例使用

```python
from backend.app.core.context.code_index import (
    get_codebase_index,
    set_codebase_index
)

# 全局获取索引实例
global_index = get_codebase_index()

# 如果不存在，创建并设置
if global_index is None:
    new_index = CodebaseIndex()
    new_index.build_index("/path/to/project")
    set_codebase_index(new_index)
    global_index = get_codebase_index()

# 使用全局索引
results = global_index.search("关键字", limit=10)
```

### 19.6 支持的语言

CodebaseIndex 支持以下编程语言：

| 语言 | 文件后缀 |
|------|--------|
| Python | .py |
| TypeScript | .ts |
| TypeScript React | .tsx |
| JavaScript | .js |
| JavaScript React | .jsx |
| Java | .java |
| Go | .go |
| Rust | .rs |
| C++ | .cpp |
| C | .c |
| C Header | .h |
| C# | .cs |
| Ruby | .rb |
| PHP | .php |

## 20. 最佳实践补充

### 20.1 集成新能力的最佳实践

1. **初始化顺序** - 先建立代码库索引，再初始化检索器
2. **权重调优** - 根据场景选择合适的检索权重
3. **压缩策略** - 长对话使用 hybrid，短对话使用 summary
4. **缓存管理** - 定期更新代码库索引以保持同步
5. **性能监控** - 监控压缩率和检索延迟

### 20.2 常见集成模式

```python
# 模式1：知识库问答
async def qa_with_codebase(question: str):
    # 搜索相关代码
    code_matches = await context_manager.search_codebase(question)
    # 检索相关历史
    history = await context_manager.retrieve_context(question)
    # 构建提示词
    prompt = f"问题: {question}\n相关代码: {code_matches}\n历史: {history}"
    return await llm.complete(prompt)

# 模式2：长对话优化
async def long_conversation_handler():
    # 定期压缩
    if message_count % 10 == 0:
        await context_manager.compress_context(strategy="hybrid")
    # 检索关键信息
    key_context = await context_manager.retrieve_context(
        query=current_query,
        weights=RetrievalWeights(importance=0.5)
    )
    return key_context

# 模式3：代码审查助手
async def code_review_assistant(file_path: str):
    # 获取文件依赖
    deps = await context_manager.codebase_index.get_dependencies(file_path)
    # 搜索相关代码模式
    patterns = await context_manager.search_codebase("最佳实践")
    # 生成审查建议
    return await llm.complete(f"审查 {file_path}，依赖: {deps}，模式: {patterns}")
```
