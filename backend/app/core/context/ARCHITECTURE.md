# X-Agent 上下文管理系统架构设计

## 1. 概述

X-Agent上下文管理系统是一个完整的对话历史管理和会话恢复框架，用于支持长对话、自动Token压缩和断点续传。

### 核心目标
- 自动Token压缩，防止长对话丢失上下文
- 会话状态持久化和恢复
- 混合记忆系统（热/冷/图）的统一管理
- 与Claude Code对标的用户体验

### 关键指标
- 压缩性能：<1秒
- 会话恢复时间：<2秒
- 支持100K+Token对话
- 99.9%的上下文保留率

## 2. 架构设计

### 2.1 分层架构

```
┌───────────────────────────────────────────────────────────────┐
│                   Agent Execution Loop                        │
├───────────────────────────────────────────────────────────────┤
│                   ContextManager (协调器)                      │
├───────────────┬───────────────┬───────────────┬───────────────┤
│ SessionRecov  │ ContextComp   │ Context       │ Codebase      │
│   ery         │   ressor      │ Retriever     │ Index         │
│ (会话恢复)     │ (智能压缩)     │ (智能检索)     │ (代码索引)     │
├───────────────┼───────────────┼───────────────┼───────────────┤
│ Hot Store     │ Cold Store    │ TF-IDF        │ Symbol        │
│ (Filesystem)  │ (Qdrant)      │ (内存)         │ (内存)         │
└───────────────┴───────────────┴───────────────┴───────────────┘
```

> **Phase 4 更新 (2026-05-30):** 新增 ContextCompressor、ContextRetriever、CodebaseIndex 三个模块，通过 ContextManager 统一协调。

### 2.2 核心模块

#### 2.2.1 ContextManager（上下文管理器）
**职责：**
- 协调各个子系统
- 管理上下文生命周期
- 触发压缩和恢复操作
- 提供统一的API

**关键方法：**
```python
async def add_message(message: Message) -> None
async def get_context(limit: int = None) -> List[Message]
async def compress_if_needed() -> CompactionResult
async def save_session(session_id: str) -> SessionSnapshot
async def restore_session(session_id: str) -> SessionSnapshot
async def get_session_list() -> List[SessionMetadata]
```

#### 2.2.2 SessionRecovery（会话恢复）
**职责：**
- 会话状态快照保存
- 会话状态恢复
- 会话元数据管理
- 断点续传支持

**关键方法：**
```python
async def save_snapshot(session_id: str, state: SessionState) -> str
async def load_snapshot(session_id: str) -> SessionState
async def list_sessions() -> List[SessionMetadata]
async def delete_session(session_id: str) -> bool
async def get_session_stats(session_id: str) -> SessionStats
```

#### 2.2.3 ContextCompactor（上下文压缩）
**职责：**
- Token计数（多模型支持）
- 消息重要性评分
- 智能压缩算法
- 压缩触发机制

**改进点：**
- 支持更多LLM模型
- 改进重要性评分算法
- 支持增量压缩
- 压缩历史跟踪

#### 2.2.4 HybridMemorySystem（混合记忆）
**职责：**
- 三层记忆协调
- 自动分层存储
- 混合检索
- 记忆生命周期管理

#### 2.2.5 ContextCompressor（智能上下文压缩）[Phase 4 新增]
**职责：**
- 多策略文本压缩（摘要/语义/混合）
- 关键信息提取与保留
- 增量压缩支持
- 异步压缩接口

**关键方法：**
```python
def compress(content: str, target_ratio: float = 0.5, strategy: str = "hybrid") -> CompressedContext
async def compress_async(content: str, target_ratio: float = 0.5, strategy: str = "hybrid") -> CompressedContext
def compress_incremental(chunks: Iterator[str], target_ratio: float = 0.5) -> Iterator[CompressedChunk]
def extract_key_info(content: str) -> list[KeyInfo]
```

**压缩策略：**
- `summary`: 摘要式，按句子重要性打分保留高分句
- `semantic`: 语义式，去除填充词保留核心语义
- `hybrid`: 混合式（默认），先摘要再语义裁剪

#### 2.2.6 ContextRetriever（智能上下文检索）[Phase 4 新增]
**职责：**
- 基于相关性的语义检索（TF-IDF + 余弦相似度）
- 基于时间的范围检索
- 基于重要性的优先级检索
- 混合检索（加权组合三种策略）

**关键方法：**
```python
def retrieve_by_relevance(query: str, top_k: int = 10) -> list[ContextItem]
def retrieve_by_time(start: datetime, end: datetime, sort_order: str = "desc") -> list[ContextItem]
def retrieve_by_importance(min_priority: float = 0.5, top_k: int | None = None) -> list[ContextItem]
def retrieve_hybrid(query: str, weights: RetrievalWeights | None = None, top_k: int = 10) -> list[ContextItem]
def update_messages(messages: list[Message]) -> None
def add_message(message: Message) -> None
```

**检索权重配置：**
```python
RetrievalWeights(relevance=0.5, recency=0.3, importance=0.2)  # 自动归一化
```

#### 2.2.7 CodebaseIndex（代码库索引）[Phase 4 新增]
**职责：**
- 代码库文件扫描与索引
- 符号提取（函数/类/变量）
- 导入关系分析与依赖图构建
- 语义代码搜索
- 增量索引更新

**关键方法：**
```python
def build_index(root_path: Path | str, patterns: list[str] | None = None) -> IndexStats
def update_index(changed_files: list[Path | str]) -> IndexStats
def search(query: str, file_types: list[str] | None = None, limit: int = 20) -> list[CodeMatch]
def get_dependencies(file_path: Path | str) -> DependencyGraph
def get_dependents(file_path: Path | str) -> list[Path]
def get_stats() -> IndexStats
```

**支持的语言：**
Python, TypeScript, JavaScript, Java, Go, Rust, C/C++, C#, Ruby, PHP

## 3. 数据模型

### 3.1 Message（消息）
```python
@dataclass
class Message:
    id: str
    role: str  # user, assistant, system, tool
    content: str
    timestamp: datetime
    metadata: dict
    importance: float = 0.5
    compressed: bool = False
```

### 3.2 SessionState（会话状态）
```python
@dataclass
class SessionState:
    session_id: str
    agent_id: str
    messages: List[Message]
    context_window: int
    compression_history: List[CompactionMetrics]
    metadata: dict
    created_at: datetime
    updated_at: datetime
    last_checkpoint: datetime
```

### 3.3 SessionSnapshot（会话快照）
```python
@dataclass
class SessionSnapshot:
    snapshot_id: str
    session_id: str
    timestamp: datetime
    message_count: int
    token_count: int
    compressed_token_count: int
    compression_ratio: float
    storage_path: str
    metadata: dict
```

### 3.4 CompactionMetrics（压缩指标）
```python
@dataclass
class CompactionMetrics:
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    messages_before: int
    messages_after: int
    duration_ms: float
    timestamp: datetime
```

### 3.5 压缩相关数据模型 [Phase 4 新增]
```python
@dataclass
class KeyInfo:
    """关键信息项（压缩时保留）。"""
    text: str
    importance: float
    category: str  # error / action / entity / result
    position: int

@dataclass
class CompressedContext:
    """压缩后的上下文结果。"""
    original_tokens: int
    compressed_tokens: int
    content: str
    key_info: list[KeyInfo] = field(default_factory=list)
    compression_ratio: float = 1.0
    strategy: str = "unknown"  # summary / semantic / hybrid
    metadata: dict = field(default_factory=dict)

@dataclass
class CompressedChunk:
    """增量压缩的单个块。"""
    original_content: str
    compressed_content: str
    original_tokens: int
    compressed_tokens: int
    key_info: list[KeyInfo] = field(default_factory=list)
    chunk_index: int = 0
```

### 3.6 检索相关数据模型 [Phase 4 新增]
```python
@dataclass
class ContextItem:
    """检索返回的上下文条目。"""
    content: str
    timestamp: datetime
    priority: float = 0.5
    relevance_score: float = 0.0
    message_id: str = ""
    role: str = ""
    metadata: dict = field(default_factory=dict)

@dataclass
class RetrievalWeights:
    """混合检索权重（__post_init__ 自动归一化）。"""
    relevance: float = 0.5
    recency: float = 0.3
    importance: float = 0.2
```

### 3.7 代码索引相关数据模型 [Phase 4 新增]
```python
@dataclass
class CodeMatch:
    """代码搜索命中项。"""
    file_path: Path
    line_number: int
    content: str
    relevance_score: float
    context_lines: list[str] = field(default_factory=list)

@dataclass
class FileNode:
    """索引中的单个文件节点。"""
    path: Path
    file_type: str
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    size: int = 0
    last_modified: datetime = field(default_factory=...)

@dataclass
class DependencyEdge:
    """依赖图的一条边。"""
    from_file: Path
    to_file: Path
    import_statement: str
    edge_type: str = "import"

@dataclass
class DependencyGraph:
    """文件依赖图。"""
    nodes: dict[Path, FileNode] = field(default_factory=dict)
    edges: list[DependencyEdge] = field(default_factory=list)

@dataclass
class IndexStats:
    """索引统计信息。"""
    total_files: int = 0
    indexed_files: int = 0
    total_symbols: int = 0
    index_time_seconds: float = 0.0
    last_updated: datetime = field(default_factory=...)
```

## 4. 工作流程

### 4.1 消息处理流程
```
新消息到达
    ↓
ContextManager.add_message()
    ↓
检查是否需要压缩
    ├─ 是 → ContextCompactor.compress()
    │        ↓
    │        更新HybridMemorySystem
    │        ↓
    │        保存压缩指标
    └─ 否 → 直接存储
    ↓
定期保存会话快照
```

### 4.2 会话恢复流程
```
用户恢复会话
    ↓
SessionRecovery.load_snapshot(session_id)
    ↓
从文件系统加载快照
    ↓
恢复消息历史
    ↓
恢复上下文窗口
    ↓
验证完整性
    ↓
返回SessionState
```

### 4.3 压缩触发机制
```
消息添加后
    ↓
计算当前Token数
    ↓
检查是否超过阈值（85%）
    ├─ 是 → 触发压缩
    │        ├─ 评分所有消息
    │        ├─ 保留高分消息
    │        ├─ 生成摘要
    │        └─ 更新存储
    └─ 否 → 继续
```

## 5. 存储策略

### 5.1 热存储（Filesystem）
- **位置：** `~/.xagent/sessions/{session_id}/`
- **内容：** 最近的消息历史（最近7天）
- **格式：** JSON行格式（JSONL）
- **访问模式：** 快速读写

### 5.2 冷存储（Qdrant）
- **内容：** 历史对话的向量化表示
- **索引：** 语义相似性
- **访问模式：** 语义检索

### 5.3 图存储（Neo4j）
- **内容：** 知识图谱和关系
- **索引：** 关系推理
- **访问模式：** 图查询

## 6. 配置参数

```python
# 上下文管理配置
CONTEXT_CONFIG = {
    # Token限制
    "token_limit": 128_000,
    "compression_threshold": 0.85,
    
    # 会话配置
    "session_storage_path": "~/.xagent/sessions",
    "session_snapshot_interval": 300,  # 5分钟
    "session_retention_days": 30,
    
    # 压缩配置
    "min_messages_to_keep": 3,
    "compression_strategy": "importance_based",
    "enable_incremental_compression": True,
    
    # 内存配置
    "hot_tier_max_age_days": 7,
    "hot_tier_max_size_mb": 100,
    "cold_tier_similarity_threshold": 0.7,
}
```

## 7. 集成点

### 7.1 Agent执行循环集成
```python
# 在agent.py中
async def run(self, context: RunContext):
    # 初始化上下文管理器
    context_manager = ContextManager(...)
    
    # 恢复之前的会话（如果存在）
    if context.session_id:
        session_state = await context_manager.restore_session(context.session_id)
        messages = session_state.messages
    
    # 主循环
    for iteration in range(self.max_iterations):
        # 添加新消息
        await context_manager.add_message(new_message)
        
        # 自动压缩（如果需要）
        await context_manager.compress_if_needed()
        
        # 获取当前上下文
        current_context = await context_manager.get_context()
        
        # 执行agent逻辑
        ...
    
    # 保存会话
    await context_manager.save_session(context.session_id)
```

### 7.2 API端点集成
```python
# 在api/sessions.py中
@router.post("/sessions/{session_id}/save")
async def save_session(session_id: str):
    """保存会话"""
    
@router.get("/sessions/{session_id}/restore")
async def restore_session(session_id: str):
    """恢复会话"""
    
@router.get("/sessions")
async def list_sessions():
    """列出所有会话"""
    
@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    
@router.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """获取会话统计"""
```

### 7.3 Phase 4 统一入口集成 [新增]
ContextManager 现已作为压缩 / 检索 / 代码索引三大能力的统一协调入口，对外暴露 4 个异步方法：
```python
# 在 context_manager.py 中（构造时注入 context_compressor /
# context_retriever / codebase_index 三个子系统）

async def compress_context(
    self, strategy: str = "hybrid"
) -> CompressedContext | None:
    """压缩当前上下文窗口，返回压缩结果（含 key_info 与压缩率）。"""

async def retrieve_context(
    self, query: str, limit: int = 10,
    weights: RetrievalWeights | None = None,
) -> list[ContextItem]:
    """按相关性/时间/重要性混合检索历史消息。"""

async def search_codebase(
    self, query: str, file_types: list[str] | None = None,
    limit: int = 20,
) -> list[CodeMatch]:
    """在已索引代码库中进行语义检索。"""

async def index_codebase(
    self, root_path: Path | str
) -> IndexStats | None:
    """构建/重建代码库索引，返回索引统计。"""
```
> 上述方法均内置 try/except 容错：子系统未注入或执行失败时返回 `None`（或空列表）并记录日志，不会中断 Agent 主循环。

## 8. 性能优化

### 8.1 缓存策略
- 消息缓存（LRU，最多1000条）
- 会话元数据缓存
- 压缩结果缓存

### 8.2 异步操作
- 异步保存会话快照
- 异步压缩操作
- 异步向量化

### 8.3 批处理
- 批量保存消息
- 批量向量化
- 批量图更新

## 9. 监控和指标

### 9.1 关键指标
- 平均压缩时间
- 压缩率分布
- 会话恢复时间
- 内存使用量
- Token节省率

### 9.2 日志记录
- 压缩操作日志
- 会话保存/恢复日志
- 错误和异常日志

## 10. 错误处理

### 10.1 压缩失败
- 回退到原始消息
- 记录错误
- 触发告警

### 10.2 会话恢复失败
- 创建新会话
- 记录错误
- 通知用户

### 10.3 存储失败
- 重试机制
- 降级处理
- 错误恢复

## 11. 安全考虑

- 会话数据加密存储
- 访问控制（租户隔离）
- 审计日志
- 数据清理策略

## 12. 测试策略

### 12.1 单元测试
- ContextCompactor测试
- SessionRecovery测试
- Message处理测试

### 12.2 集成测试
- 长对话测试
- 压缩恢复测试
- 多会话并发测试

### 12.3 性能测试
- 压缩性能基准
- 恢复性能基准
- 内存使用基准

## 13. 迁移计划

### 13.1 向后兼容性
- 支持旧会话格式
- 渐进式迁移
- 兼容性层

### 13.2 数据迁移
- 批量导入历史会话
- 格式转换
- 验证完整性

## 14. 未来扩展

- 分布式会话管理
- 跨设备会话同步
- 高级压缩算法
- 多模型支持
- 实时协作支持
