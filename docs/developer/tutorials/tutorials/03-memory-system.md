# 记忆系统教程

学习如何使用 X-Agent 的高级记忆系统进行信息存储、检索和管理。

## 目录

1. [记忆系统概述](#记忆系统概述)
2. [记忆类型](#记忆类型)
3. [存储和检索](#存储和检索)
4. [向量搜索](#向量搜索)
5. [图谱记忆](#图谱记忆)
6. [记忆管理](#记忆管理)

## 记忆系统概述

### 记忆系统的特点

- **多层次**：支持短期、长期、图谱、向量等多种记忆
- **高效检索**：支持关键词搜索、语义搜索、图谱查询
- **自动去重**：智能去重和融合相似信息
- **可扩展**：支持多种存储后端

### 记忆系统的应用

- 保存用户偏好和历史交互
- 存储知识库和参考资料
- 记录执行历史和决策过程
- 支持上下文感知的对话

## 记忆类型

### 1. 短期记忆

当前对话的上下文信息：

```python
from backend.app.core.memory import MemoryManager, MemoryType

memory = MemoryManager()

# 存储短期记忆
await memory.store(
    key="current_task",
    value={
        "task_id": "task-001",
        "description": "分析销售数据",
        "status": "in_progress"
    },
    memory_type=MemoryType.SHORT_TERM,
    ttl=3600  # 1 小时过期
)

# 检索短期记忆
task = await memory.retrieve("current_task")
print(task)
```

### 2. 长期记忆

持久化存储的知识和经验：

```python
# 存储长期记忆
await memory.store(
    key="user_preferences",
    value={
        "theme": "dark",
        "language": "zh",
        "timezone": "Asia/Shanghai"
    },
    memory_type=MemoryType.LONG_TERM
)

# 长期记忆不会自动过期
preferences = await memory.retrieve("user_preferences")
```

### 3. 向量记忆

支持语义相似性搜索：

```python
# 存储向量记忆
await memory.store(
    key="product_description",
    value="这是一个高性能的数据分析工具，支持实时处理和可视化",
    memory_type=MemoryType.VECTOR,
    embedding_model="text-embedding-3-small"
)

# 语义搜索
results = await memory.search(
    query="数据分析工具",
    memory_type=MemoryType.VECTOR,
    top_k=5
)

for result in results:
    print(f"相似度: {result.similarity}")
    print(f"内容: {result.value}")
```

### 4. 图谱记忆

实体和关系的结构化存储：

```python
# 创建实体
await memory.create_entity(
    entity_id="user-001",
    entity_type="User",
    properties={
        "name": "张三",
        "email": "zhangsan@example.com",
        "department": "销售部"
    }
)

# 创建关系
await memory.create_relationship(
    from_entity="user-001",
    to_entity="dept-001",
    relationship_type="belongs_to",
    properties={"since": "2023-01-01"}
)

# 查询关系
relationships = await memory.query_relationships(
    from_entity="user-001",
    relationship_type="belongs_to"
)
```

## 存储和检索

### 基础存储

```python
# 存储简单数据
await memory.store(
    key="api_key",
    value="sk-1234567890",
    memory_type=MemoryType.LONG_TERM
)

# 存储复杂数据
await memory.store(
    key="user_profile",
    value={
        "id": "user-001",
        "name": "张三",
        "email": "zhangsan@example.com",
        "preferences": {
            "notifications": True,
            "theme": "dark"
        }
    },
    memory_type=MemoryType.LONG_TERM
)

# 存储列表数据
await memory.store(
    key="recent_searches",
    value=["Python", "机器学习", "数据分析"],
    memory_type=MemoryType.SHORT_TERM,
    ttl=86400  # 24 小时
)
```

### 基础检索

```python
# 检索数据
api_key = await memory.retrieve("api_key")

# 检索不存在的数据（返回 None）
missing = await memory.retrieve("non_existent_key")

# 检索数据并提供默认值
theme = await memory.retrieve(
    "user_theme",
    default="light"
)
```

### 批量操作

```python
# 批量存储
await memory.store_batch({
    "key1": "value1",
    "key2": "value2",
    "key3": "value3"
})

# 批量检索
keys = ["key1", "key2", "key3"]
values = await memory.retrieve_batch(keys)

# 批量删除
await memory.delete_batch(keys)
```

### 更新和删除

```python
# 更新数据
await memory.update(
    key="user_profile",
    value={
        "name": "张三",
        "email": "newemail@example.com"
    }
)

# 删除数据
await memory.delete("user_profile")

# 清空所有短期记忆
await memory.clear(memory_type=MemoryType.SHORT_TERM)
```

## 向量搜索

### 基础向量搜索

```python
# 存储多个文档
documents = [
    "Python 是一种高级编程语言",
    "机器学习是人工智能的一个分支",
    "数据分析用于从数据中提取有用信息",
    "深度学习是机器学习的一个子领域"
]

for i, doc in enumerate(documents):
    await memory.store(
        key=f"doc_{i}",
        value=doc,
        memory_type=MemoryType.VECTOR
    )

# 搜索相似文档
results = await memory.search(
    query="编程语言",
    memory_type=MemoryType.VECTOR,
    top_k=3
)

for result in results:
    print(f"相似度: {result.similarity:.2f}")
    print(f"内容: {result.value}")
```

### 高级搜索选项

```python
# 使用过滤条件搜索
results = await memory.search(
    query="机器学习",
    memory_type=MemoryType.VECTOR,
    top_k=5,
    filters={
        "created_after": "2024-01-01",
        "category": "AI"
    },
    threshold=0.7  # 相似度阈值
)

# 混合搜索（关键词 + 向量）
results = await memory.hybrid_search(
    query="Python 编程",
    keyword_weight=0.3,
    vector_weight=0.7,
    top_k=10
)
```

### 自定义嵌入模型

```python
# 使用自定义嵌入模型
await memory.set_embedding_model("text-embedding-3-large")

# 或使用本地模型
await memory.set_embedding_model(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# 重新索引现有数据
await memory.reindex_vectors()
```

## 图谱记忆

### 创建和管理实体

```python
# 创建实体
await memory.create_entity(
    entity_id="company-001",
    entity_type="Company",
    properties={
        "name": "ABC 公司",
        "industry": "科技",
        "founded": "2020-01-01",
        "employees": 100
    }
)

# 更新实体
await memory.update_entity(
    entity_id="company-001",
    properties={
        "employees": 150
    }
)

# 查询实体
entity = await memory.get_entity("company-001")
print(entity.properties)

# 删除实体
await memory.delete_entity("company-001")
```

### 创建和管理关系

```python
# 创建关系
await memory.create_relationship(
    from_entity="user-001",
    to_entity="company-001",
    relationship_type="works_at",
    properties={
        "position": "数据分析师",
        "start_date": "2023-01-01"
    }
)

# 查询关系
relationships = await memory.query_relationships(
    from_entity="user-001",
    relationship_type="works_at"
)

# 查询所有关系
all_relationships = await memory.get_entity_relationships("user-001")

# 删除关系
await memory.delete_relationship(
    from_entity="user-001",
    to_entity="company-001",
    relationship_type="works_at"
)
```

### 图谱查询

```python
# 查询路径
paths = await memory.find_paths(
    from_entity="user-001",
    to_entity="project-001",
    max_depth=3
)

# 查询相邻节点
neighbors = await memory.get_neighbors(
    entity_id="user-001",
    relationship_type="works_at"
)

# 图谱分析
analysis = await memory.analyze_graph(
    entity_id="company-001",
    analysis_type="centrality"
)
```

## 记忆管理

### 记忆统计

```python
# 获取记忆统计信息
stats = await memory.get_statistics()

print(f"总记忆数: {stats.total_memories}")
print(f"短期记忆: {stats.short_term_count}")
print(f"长期记忆: {stats.long_term_count}")
print(f"向量记忆: {stats.vector_count}")
print(f"图谱实体: {stats.entity_count}")
print(f"图谱关系: {stats.relationship_count}")
print(f"存储大小: {stats.storage_size} MB")
```

### 记忆去重

```python
# 自动去重
await memory.deduplicate(
    similarity_threshold=0.9,
    merge_strategy="keep_latest"
)

# 手动去重
duplicates = await memory.find_duplicates(
    similarity_threshold=0.85
)

for group in duplicates:
    print(f"重复组: {group}")
    # 合并重复项
    await memory.merge_memories(group)
```

### 记忆导出和导入

```python
# 导出记忆
export_data = await memory.export(
    memory_type=MemoryType.LONG_TERM,
    format="json"
)

# 保存到文件
with open("memory_backup.json", "w") as f:
    json.dump(export_data, f)

# 导入记忆
with open("memory_backup.json", "r") as f:
    import_data = json.load(f)

await memory.import_data(import_data)
```

### 记忆清理

```python
# 清理过期记忆
cleaned = await memory.cleanup_expired()
print(f"清理了 {cleaned} 条过期记忆")

# 清理特定类型的记忆
await memory.clear(memory_type=MemoryType.SHORT_TERM)

# 清理所有记忆
await memory.clear_all()
```

## 最佳实践

1. **合理选择记忆类型**：根据数据特点选择合适的记忆类型
2. **设置合理的 TTL**：为短期记忆设置合理的过期时间
3. **定期清理**：定期清理过期和重复的记忆
4. **性能优化**：使用批量操作提高性能
5. **安全存储**：对敏感信息进行加密存储
6. **监控使用**：监控记忆系统的使用情况和性能

## 下一步

- 阅读 [浏览器自动化教程](./04-browser-automation.md)
- 阅读 [最佳实践](../../best-practices/best-practices/README.md)
- 探索 [示例代码库](../../examples/)
