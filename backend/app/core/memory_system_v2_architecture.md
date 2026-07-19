# X-Agent 记忆系统代际升级 (V2) - 完整架构设计

## 1. 概述

X-Agent 记忆系统V2是一个三层混合架构，借鉴Hermes Agent的设计理念，实现程序记忆、主动记忆整理和混合检索的完整体系。

### 核心目标
- 支持Agent执行后自动生成/优化SKILL.md（程序记忆层）
- 周期性自整理记忆（主动记忆整理层）
- 混合检索策略优化（向量+关键词+图谱）
- 检索性能<50ms
- 完全兼容现有auto-memory系统

## 2. 三层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层 (Application)                      │
│  Agent执行 → 记忆路由 → 存储/检索 → 决策反馈                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              第一层：程序记忆 (Skill Memory)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ • 自动生成SKILL.md（Agent执行后）                    │   │
│  │ • 结构化知识存储（JSON/YAML）                        │   │
│  │ • 版本控制和演进追踪                                 │   │
│  │ • 快速访问（内存/本地文件）                          │   │
│  │ • 生命周期：持久化，手动更新                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           第二层：主动记忆整理 (Nudge Memory)                │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ • 周期性自整理（每天/每周）                          │   │
│  │ • 记忆去重和合并                                     │   │
│  │ • 重要性评分和自动淘汰                               │   │
│  │ • 记忆压缩和归档                                     │   │
│  │ • 生命周期：定时触发，自动维护                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         第三层：混合检索 (Hybrid Retrieval)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 向量检索 (Qdrant)                                    │   │
│  │ ├─ 语义相似性搜索                                    │   │
│  │ ├─ 向量维度：1536 (OpenAI)                           │   │
│  │ └─ 相似度阈值：0.7                                   │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 关键词检索 (PostgreSQL/Elasticsearch)                │   │
│  │ ├─ 精确匹配和模糊匹配                                │   │
│  │ ├─ 倒排索引加速                                      │   │
│  │ └─ 权重计算（TF-IDF）                                │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 图谱检索 (Neo4j)                                     │   │
│  │ ├─ 实体关系查询                                      │   │
│  │ ├─ 路径查询和中心性分析                              │   │
│  │ └─ 关系权重传播                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 3. 记忆重要性评分算法

### 3.1 评分维度

```
重要性评分 = 
    w1 * 访问频率 +
    w2 * 访问新鲜度 +
    w3 * 内容质量 +
    w4 * 关系中心性 +
    w5 * 用户标记 +
    w6 * 执行成功率

其中：
- w1 = 0.25 (访问频率权重)
- w2 = 0.20 (新鲜度权重)
- w3 = 0.20 (内容质量权重)
- w4 = 0.15 (关系中心性权重)
- w5 = 0.15 (用户标记权重)
- w6 = 0.05 (执行成功率权重)
```

### 3.2 评分计算

```python
# 访问频率 (0-1)
access_frequency = min(access_count / 100, 1.0)

# 新鲜度 (0-1)
days_old = (now - last_accessed).days
freshness = 1.0 / (1.0 + days_old / 7)

# 内容质量 (0-1)
quality = len(content) / 1000 * 0.5 + has_examples * 0.3 + has_tests * 0.2

# 关系中心性 (0-1)
centrality = min(relationship_count / 10, 1.0)

# 用户标记 (0-1)
user_mark = 1.0 if starred else 0.0

# 执行成功率 (0-1)
success_rate = successful_executions / total_executions if total_executions > 0 else 0.5
```

## 4. 自动淘汰机制

### 4.1 淘汰策略

```
淘汰条件：
1. 重要性评分 < 0.2 且 未访问超过30天
2. 重要性评分 < 0.1 且 未访问超过7天
3. 内容重复度 > 0.95 且 重要性较低
4. 存储大小超过限制 且 重要性最低的记忆

淘汰流程：
1. 计算所有记忆的重要性评分
2. 识别淘汰候选
3. 备份到冷存储（Qdrant）
4. 删除本地记忆
5. 更新索引
```

### 4.2 淘汰配置

```yaml
eviction:
  enabled: true
  schedule: "0 2 * * *"  # 每天凌晨2点
  batch_size: 100
  min_importance: 0.2
  max_age_days: 30
  storage_limit_mb: 500
  backup_before_delete: true
```

## 5. 记忆去重和合并

### 5.1 去重算法

```
相似度计算：
similarity = 
    0.4 * vector_similarity +
    0.3 * keyword_similarity +
    0.3 * semantic_similarity

去重条件：
- similarity > 0.85 → 合并
- similarity > 0.70 → 标记为相关
- similarity < 0.70 → 保留独立
```

### 5.2 合并策略

```
合并规则：
1. 保留重要性最高的记忆作为主记忆
2. 其他记忆作为版本历史保存
3. 合并标签和元数据
4. 更新关系图
5. 记录合并日志
```

## 6. 记忆版本控制

### 6.1 版本管理

```
版本结构：
{
  "memory_id": "mem-001",
  "current_version": 3,
  "versions": [
    {
      "version": 1,
      "content": "...",
      "timestamp": "2024-01-01T10:00:00Z",
      "author": "agent-001",
      "change_type": "create",
      "change_summary": "Initial creation"
    },
    {
      "version": 2,
      "content": "...",
      "timestamp": "2024-01-02T10:00:00Z",
      "author": "agent-002",
      "change_type": "update",
      "change_summary": "Added examples"
    }
  ]
}
```

### 6.2 版本操作

```
操作：
- create: 创建新版本
- update: 更新内容
- rollback: 回滚到历史版本
- diff: 查看版本差异
- merge: 合并版本
```

## 7. 混合检索策略

### 7.1 检索流程

```
用户查询
    ↓
┌─────────────────────────────────────────┐
│ 1. 查询分析                             │
│    - 提取关键词                         │
│    - 识别查询意图                       │
│    - 确定查询类型                       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 2. 并行检索                             │
│    ├─ 向量检索 (Qdrant)                 │
│    ├─ 关键词检索 (PostgreSQL)           │
│    └─ 图谱检索 (Neo4j)                  │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 3. 结果融合                             │
│    - 标准化评分                         │
│    - 加权融合                           │
│    - 去重                               │
│    - 排序                               │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 4. 结果重排                             │
│    - 多样性优化                         │
│    - 相关性调整                         │
│    - 新鲜度加权                         │
└─────────────────────────────────────────┘
    ↓
返回Top-K结果
```

### 7.2 检索权重配置

```yaml
retrieval:
  vector_weight: 0.5
  keyword_weight: 0.3
  graph_weight: 0.2
  
  # 动态权重调整
  dynamic_weights:
    enabled: true
    query_type_weights:
      semantic: {vector: 0.6, keyword: 0.2, graph: 0.2}
      keyword: {vector: 0.3, keyword: 0.5, graph: 0.2}
      relationship: {vector: 0.2, keyword: 0.2, graph: 0.6}
```

## 8. 性能优化

### 8.1 缓存策略

```
L1缓存（内存）：
- 最近访问的100条记忆
- TTL: 5分钟
- 命中率目标: >80%

L2缓存（Redis）：
- 热点记忆（访问频率>10/天）
- TTL: 1小时
- 容量: 10000条

L3缓存（本地文件）：
- 程序记忆（SKILL.md）
- 持久化存储
```

### 8.2 索引优化

```
PostgreSQL索引：
- idx_memories_tenant_layer_created
- idx_memories_content_trgm (GIN)
- idx_memories_importance_created

Qdrant索引：
- HNSW (Hierarchical Navigable Small World)
- ef_construct: 200
- ef_search: 100

Neo4j索引：
- 实体类型索引
- 关系类型索引
- 属性索引
```

### 8.3 性能目标

```
检索性能：
- 向量检索: <20ms (top-10)
- 关键词检索: <10ms (top-10)
- 图谱检索: <15ms (top-10)
- 混合检索: <50ms (top-10)

存储性能：
- 单条记忆存储: <5ms
- 批量存储(100条): <100ms
- 去重处理: <100ms/1000条

内存占用：
- 缓存: <500MB
- 索引: <1GB
```

## 9. 与现有系统的兼容性

### 9.1 向后兼容

```
现有系统 → V2系统的映射：

MemoryItem (L1-L10) → MemoryV2
├─ L1-L3 → 程序记忆 (Skill Memory)
├─ L4-L7 → 主动记忆 (Nudge Memory)
└─ L8-L10 → 长期记忆 (Archive Memory)

MemorySystem.search() → HybridRetriever.search()
MemorySystem.store() → MemoryV2System.store()
```

### 9.2 迁移路径

```
阶段1：并行运行
- V1和V2同时运行
- 新记忆写入V2
- 旧记忆保持在V1

阶段2：逐步迁移
- 定期将V1记忆迁移到V2
- 更新检索路由

阶段3：完全切换
- 所有查询使用V2
- V1作为备份
```

## 10. 交付物清单

### 10.1 代码文件

```
backend/app/core/
├── memory_v2_system.py          # 核心系统
├── memory_v2_skill.py           # 程序记忆层
├── memory_v2_nudge.py           # 主动记忆层
├── memory_v2_retriever.py       # 混合检索
├── memory_v2_importance.py      # 重要性评分
├── memory_v2_deduplication.py   # 去重合并
├── memory_v2_versioning.py      # 版本控制
└── memory_v2_cache.py           # 缓存管理

backend/app/services/memory/
├── memory_v2_indexer.py         # 索引管理
├── memory_v2_optimizer.py       # 性能优化
└── memory_v2_monitor.py         # 监控指标
```

### 10.2 文档文件

```
docs/
├── memory-v2-architecture.md    # 架构设计
├── memory-v2-api.md             # API文档
├── memory-v2-examples.md        # 使用示例
├── memory-v2-performance.md     # 性能报告
└── memory-v2-migration.md       # 迁移指南
```

### 10.3 测试文件

```
tests/
├── test_memory_v2_system.py
├── test_memory_v2_skill.py
├── test_memory_v2_nudge.py
├── test_memory_v2_retriever.py
├── test_memory_v2_importance.py
├── test_memory_v2_deduplication.py
├── test_memory_v2_performance.py
└── test_memory_v2_integration.py
```

## 11. 实现时间表

```
第1周：核心系统设计和基础实现
- 记忆V2系统框架
- 程序记忆层
- 基础存储接口

第2周：高级功能实现
- 主动记忆整理
- 重要性评分算法
- 去重和合并

第3周：检索优化
- 混合检索实现
- 缓存管理
- 索引优化

第4周：测试和文档
- 单元测试
- 集成测试
- 性能测试
- 完整文档
```

## 12. 风险和缓解

### 12.1 风险

```
1. 性能下降
   - 缓解：充分的缓存和索引优化

2. 数据一致性
   - 缓解：版本控制和事务管理

3. 存储成本
   - 缓解：自动淘汰和压缩

4. 迁移复杂性
   - 缓解：并行运行和逐步迁移
```

### 12.2 监控指标

```
关键指标：
- 检索延迟 (p50, p95, p99)
- 缓存命中率
- 去重成功率
- 存储使用率
- 错误率
```

## 13. 参考资源

- Hermes Agent: https://github.com/anthropics/anthropic-sdk-python
- Qdrant: https://qdrant.tech/
- Neo4j: https://neo4j.com/
- PostgreSQL: https://www.postgresql.org/
