# X-Agent 记忆系统开发

## 描述

X-Agent 的记忆系统采用多层架构：短期记忆（会话级）、长期记忆（PostgreSQL）、语义记忆（Qdrant 向量）、图谱记忆（Neo4j）。

## 适用场景

- 新增记忆类型
- 优化检索效果
- 调试记忆冲突
- 记忆迁移和备份

## 记忆架构

```
用户输入 → 记忆路由器
    ├── 短期记忆 → session 内存
    ├── 长期记忆 → PostgreSQL (memory_postgres.py)
    ├── 语义记忆 → Qdrant 向量检索 (embeddings.py)
    └── 图谱记忆 → Neo4j 关系图 (memory_graph.py)
```

## 核心模块

| 文件 | 职责 |
|------|------|
| `memory.py` | 抽象接口，统一读写 |
| `memory_postgres.py` | SQL 记忆存储 |
| `memory_graph.py` | Neo4j 图谱操作 |
| `embeddings.py` | 向量嵌入生成 |

## 开发规范

### 1. 新增记忆类型

继承基础接口，实现 `store()` 和 `retrieve()`：

```python
# backend/app/core/memory_custom.py
from backend.app.core.memory import MemoryBackend

class CustomMemory(MemoryBackend):
    async def store(self, key: str, value: dict, ttl: int = None):
        ...

    async def retrieve(self, key: str) -> dict | None:
        ...

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        ...
```

### 2. 向量检索

使用 Qdrant 进行语义搜索：

```python
from qdrant_client import QdrantClient
from backend.app.core.embeddings import get_embedding

async def semantic_search(query: str, collection: str = "memories", limit: int = 5):
    vector = await get_embedding(query)
    results = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=limit,
        score_threshold=0.7
    )
    return [hit.payload for hit in results]
```

### 3. 图查询

Neo4j 关系查询：

```python
from neo4j import AsyncGraphDatabase

async def get_related_entities(entity_id: str):
    query = """
    MATCH (e:Entity {id: $id})-[r]-(related)
    RETURN related, type(r) as relation, r.weight as weight
    ORDER BY r.weight DESC
    LIMIT 10
    """
    async with driver.session() as session:
        result = await session.run(query, id=entity_id)
        return [record.data() async for record in result]
```

### 4. 记忆冲突处理

当多个 Agent 写入同一记忆时：

```python
async def merge_memory(key: str, new_value: dict, source_agent: str):
    existing = await memory.retrieve(key)
    if existing:
        # 版本控制 + 时间戳优先
        if new_value.get("timestamp", 0) > existing.get("timestamp", 0):
            await memory.store(key, {
                **new_value,
                "_merged_from": [existing.get("_source"), source_agent],
                "_version": existing.get("_version", 0) + 1
            })
    else:
        await memory.store(key, {**new_value, "_source": source_agent})
```

## 调试命令

```bash
# 查看 Qdrant 集合
python -c "from qdrant_client import QdrantClient; c = QdrantClient('localhost'); print(c.get_collections())"

# 查看 Neo4j 图统计
python -c "from neo4j import GraphDatabase; d = GraphDatabase.driver('bolt://localhost:7687'); print(d.execute_query('MATCH (n) RETURN count(n)'))"

# 运行记忆相关测试
pytest tests/core/test_memory*.py -v
```
