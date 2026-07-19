# Context Management System for X-Agent

完整的上下文管理系统，支持自动压缩、持久化存储和会话恢复。

## 概述

X-Agent的上下文管理系统由三个核心模块组成：

1. **ContextCompactor** - 智能压缩对话历史
2. **MemoryPersistence** - 文件系统持久化存储
3. **SessionRecovery** - 会话快照和恢复

## 核心功能

### 1. ContextCompactor - 自动压缩

自动检测token使用率，在接近限制时触发压缩。

```python
from backend.app.core.context_compactor import ContextCompactor

# 创建压缩器
compactor = ContextCompactor(
    model="gpt-4",
    token_limit=128_000,
    compression_threshold=0.85,  # 使用率达到85%时触发
)

# 检查是否需要压缩
messages = [...]
if compactor.should_compress(messages):
    result = compactor.compress(messages)
    if result.success:
        messages = result.messages
        print(f"压缩比: {result.metrics.compression_ratio:.2%}")
```

**压缩策略：**
- 保留最近的消息（最新上下文）
- 保留高重要性消息（工具调用、错误、用户指令）
- 为删除的消息创建摘要
- 支持增量压缩

**重要性评分：**
- 工具消息 (role=tool): 0.4分
- 助手工具调用: 0.35分
- 用户消息: 0.25分
- 错误消息: +0.2分
- 系统消息: 0.15分
- 最近消息: 更高权重

### 2. MemoryPersistence - 持久化存储

类似Claude Code的memory系统，使用Markdown文件存储。

```python
from backend.app.core.memory_persistence import MemoryEntry, MemoryPersistence

# 初始化
persistence = MemoryPersistence("./memory")

# 保存记忆
entry = MemoryEntry(
    name="project_context",
    category="project",  # user, feedback, project, reference
    content="Project description and key decisions",
    tags=["important", "architecture"],
    metadata={"version": "1.0"}
)
persistence.save_memory(entry)

# 加载记忆
loaded = persistence.load_memory("project_context")
print(loaded.content)

# 搜索记忆
results = persistence.search_memories("architecture")

# 列出所有记忆
all_memories = persistence.list_memories()

# 按类别列出
project_memories = persistence.list_memories(category="project")

# 删除记忆
persistence.delete_memory("project_context")

# 获取索引
index_md = persistence.get_index_markdown()
```

**文件结构：**
```
memory/
├── MEMORY.md                 # 自动生成的索引
├── .memory_metadata.json     # 元数据
├── project_context.md        # 记忆文件
├── user_preferences.md
└── ...
```

**MEMORY.md格式：**
```markdown
# Memory Index

## project
- [project_context](project_context.md) — Project description and key decisions

## reference
- [api_docs](api_docs.md) — API documentation
```

### 3. SessionRecovery - 会话恢复

保存会话快照，支持从中断点恢复。

```python
from backend.app.core.session_recovery import SessionRecovery, SessionSnapshot

# 初始化
recovery = SessionRecovery("./sessions")

# 创建会话
session_id = recovery.create_session(metadata={"task": "code_review"})

# 保存快照
snapshot = SessionSnapshot(
    session_id=session_id,
    iteration=5,
    messages=[...],
    context={"current_file": "main.py"},
    state={"tool_calls": 3}
)
recovery.save_snapshot(snapshot)

# 加载最新快照
latest = recovery.load_latest_snapshot(session_id)
if latest:
    messages = latest.messages
    iteration = latest.iteration

# 加载特定迭代的快照
snapshot_at_5 = recovery.load_snapshot_at_iteration(session_id, 5)

# 列出所有快照
snapshots = recovery.list_snapshots(session_id)

# 更新会话状态
recovery.update_session_status(session_id, "paused")

# 列出所有会话
all_sessions = recovery.list_sessions()
active_sessions = recovery.list_sessions(status="active")

# 删除会话
recovery.delete_session(session_id)
```

**会话状态：**
- `active` - 正在进行
- `paused` - 暂停
- `completed` - 已完成
- `failed` - 失败

## 集成到AgentLoop

### 方式1：使用ContextManager

```python
from backend.app.core.context_manager import ContextManager, AgentLoopContextIntegration

# 初始化上下文管理器
context_manager = ContextManager(
    memory_dir="./memory",
    sessions_dir="./sessions",
    token_limit=128_000,
    compression_threshold=0.85,
    enable_snapshots=True,
    snapshot_interval=5,  # 每5次迭代保存一次快照
)

# 创建集成助手
integration = AgentLoopContextIntegration(context_manager)

# 在AgentLoop中使用
class AgentLoop:
    def __init__(self, ...):
        self.context_manager = context_manager
        self.integration = integration
        self.session_id = context_manager.create_session()
    
    async def run(self, context, task, ...):
        for iteration in range(self.max_iterations):
            # 迭代开始：检查压缩
            messages = self.integration.on_iteration_start(
                self.session_id,
                iteration,
                messages
            )
            
            # ... 执行迭代逻辑 ...
            
            # 工具调用时保存
            self.integration.on_tool_call(tool_name, tool_input, tool_output)
            
            # 错误时保存
            if error:
                self.integration.on_error(str(error), context)
            
            # 迭代结束：保存快照
            self.integration.on_iteration_end(
                self.session_id,
                iteration,
                messages,
                context,
                state
            )
        
        # 完成时标记
        self.integration.on_completion(self.session_id, messages, result)
```

### 方式2：直接使用各模块

```python
from backend.app.core.context_compactor import ContextCompactor
from backend.app.core.memory_persistence import MemoryPersistence
from backend.app.core.session_recovery import SessionRecovery

# 在AgentLoop.__init__中
self.compactor = ContextCompactor()
self.memory = MemoryPersistence("./memory")
self.recovery = SessionRecovery("./sessions")

# 在run方法中
async def run(self, context, task, ...):
    session_id = self.recovery.create_session()
    
    for iteration in range(self.max_iterations):
        # 压缩检查
        if self.compactor.should_compress(messages):
            result = self.compactor.compress(messages)
            messages = result.messages
        
        # ... 执行逻辑 ...
        
        # 定期保存快照
        if iteration % 5 == 0:
            snapshot = SessionSnapshot(
                session_id=session_id,
                iteration=iteration,
                messages=messages,
                context=context,
                state=state
            )
            self.recovery.save_snapshot(snapshot)
```

## 配置选项

### ContextCompactor

```python
ContextCompactor(
    model="gpt-4",                    # LLM模型名称
    token_limit=128_000,              # 最大token数
    compression_threshold=0.85,       # 压缩触发阈值
    min_messages_to_keep=3,           # 最少保留消息数
)
```

### MemoryPersistence

```python
MemoryPersistence(
    memory_dir="./memory"             # 存储目录
)
```

### SessionRecovery

```python
SessionRecovery(
    sessions_dir="./sessions"         # 会话目录
)
```

### ContextManager

```python
ContextManager(
    memory_dir="./memory",            # 记忆目录
    sessions_dir="./sessions",        # 会话目录
    token_limit=128_000,              # Token限制
    compression_threshold=0.85,       # 压缩阈值
    enable_snapshots=True,            # 启用快照
    snapshot_interval=5,              # 快照间隔
)
```

## 性能考虑

### Token计数

- 使用tiktoken库进行精确计数（如果可用）
- 回退到估算方法（1 token ≈ 4字符）
- 消息结构开销：每条消息+4 tokens

### 压缩性能

- 消息评分：O(n)
- 压缩执行：O(n log n)
- 摘要生成：O(m)，其中m是删除的消息数

### 存储性能

- 内存索引：快速查询
- 文件I/O：异步操作建议
- 搜索：线性扫描（可优化为全文索引）

## 最佳实践

### 1. 记忆管理

```python
# 定期清理过期记忆
old_memories = persistence.list_memories()
for memory in old_memories:
    if is_outdated(memory):
        persistence.delete_memory(memory.name)

# 使用有意义的名称和标签
entry = MemoryEntry(
    name="user_preferences_v2",
    tags=["user", "preferences", "v2"],
    metadata={"version": "2.0", "updated_by": "user_id"}
)
```

### 2. 会话管理

```python
# 定期检查会话状态
sessions = recovery.list_sessions(status="active")
for session in sessions:
    if is_stale(session):
        recovery.update_session_status(session.session_id, "paused")

# 保存关键快照
if critical_decision_made:
    recovery.save_snapshot(snapshot)
```

### 3. 压缩策略

```python
# 监控压缩指标
result = compactor.compress(messages)
if result.metrics.compression_ratio < 0.5:
    logger.warning("Aggressive compression detected")

# 保留关键信息
# - 工具调用和结果
# - 用户指令
# - 错误和恢复步骤
```

## 测试

运行完整的测试套件：

```bash
pytest tests/test_context_management.py -v
```

测试覆盖：
- Token计数准确性
- 压缩后信息保留
- 会话恢复完整性
- 记忆持久化
- 索引生成
- 搜索功能

## 故障排除

### 压缩失败

```python
result = compactor.compress(messages)
if not result.success:
    logger.error(f"Compression failed: {result.error}")
    # 使用原始消息
    messages = result.messages
```

### 记忆加载失败

```python
entry = persistence.load_memory("name")
if entry is None:
    logger.warning("Memory not found")
    # 搜索相似记忆
    results = persistence.search_memories("keyword")
```

### 会话恢复失败

```python
snapshot = recovery.load_latest_snapshot(session_id)
if snapshot is None:
    logger.warning("No snapshot found, starting fresh")
    # 创建新会话
    session_id = recovery.create_session()
```

## 扩展性

### 添加自定义压缩策略

```python
class CustomCompactor(ContextCompactor):
    def _score_message_importance(self, msg, index, total):
        score = super()._score_message_importance(msg, index, total)
        # 自定义评分逻辑
        if msg.get("role") == "user" and "important" in msg.get("content", ""):
            score += 0.3
        return min(score, 1.0)
```

### 添加自定义存储后端

```python
class DatabaseMemoryPersistence(MemoryPersistence):
    def save_memory(self, entry):
        # 保存到数据库而不是文件系统
        db.insert("memories", entry.model_dump())
```

## 与现有系统的兼容性

- 与Qdrant向量记忆共存（混合架构）
- 与现有的MemorySystem兼容
- 不修改AgentLoop的核心逻辑
- 可选集成，不强制使用

## 许可证

MIT
