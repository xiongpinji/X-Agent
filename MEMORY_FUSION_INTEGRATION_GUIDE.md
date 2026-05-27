"""
高级记忆融合系统集成指南。

本文档说明如何将高级记忆融合系统集成到X-Agent中。
"""

# 高级记忆融合系统集成指南

## 概述

高级记忆融合系统是X-Agent的核心记忆管理模块，提供以下功能：

1. **智能记忆合并** - 基于语义相似度的自动合并
2. **重要性评分** - 多维度的记忆重要性评估
3. **检索优化** - 混合检索和重排序
4. **图谱增强** - 自动实体识别和关系推理
5. **生命周期管理** - 记忆的状态转换和自动清理
6. **分析工具** - 质量评估和报告生成

## 快速开始

### 1. 基本使用

```python
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem

# 初始化系统
system = AdvancedMemoryFusionSystem()

# 处理记忆
memories = [
    {
        "id": "mem1",
        "content": "Python is a programming language",
        "importance": 0.8,
        "created_at": datetime.now(UTC),
    },
    # ... 更多记忆
]

result = await system.process_memories(memories)
print(f"处理了 {result['processed_count']} 条记忆")
```

### 2. 检索记忆

```python
# 执行混合检索
results = await system.retrieve_memories(
    query="Python programming",
    memories=memories,
    top_k=10
)

for result in results:
    print(f"记忆 {result['id']}: 分数 {result['score']:.2f}")
```

### 3. 生成报告

```python
# 生成分析报告
report = await system.generate_report(memories, period_days=30)

print(f"总记忆数: {report.total_memories}")
print(f"平均质量: {report.avg_quality:.2f}")
print(f"覆盖度: {report.coverage.coverage_percentage:.1f}%")
```

## 模块详解

### 记忆合并 (MemoryMerger)

合并相似的记忆以减少存储和提高检索效率。

```python
from backend.app.core.memory.merger import MemoryMerger

merger = MemoryMerger(
    similarity_threshold=0.85,  # 相似度阈值
    min_group_size=2,           # 最小合并组大小
    max_group_size=10,          # 最大合并组大小
)

merged_memories, stats = await merger.merge_memories(memories)

print(f"原始: {stats.original_count}, 合并后: {stats.merged_count}")
print(f"减少: {stats.total_reduction:.1f}%")
```

**关键参数:**
- `similarity_threshold`: 相似度阈值 (0-1)，越高越严格
- `min_group_size`: 最小合并组大小，小于此值的组不合并
- `max_group_size`: 最大合并组大小，防止过度合并
- `preserve_metadata`: 是否保留所有元数据

### 重要性评分 (MemoryImportanceScorer)

基于多个维度评估记忆的重要性。

```python
from backend.app.core.memory.importance import MemoryImportanceScorer

scorer = MemoryImportanceScorer()

scores = scorer.compute_importance(
    memory_id="mem1",
    created_at=datetime.now(UTC) - timedelta(days=1),
    access_count=10,
    association_count=5,
    user_feedback=0.5,
)

print(f"综合评分: {scores.composite_score:.2f}")
print(f"访问频率: {scores.access_frequency_score:.2f}")
print(f"时间衰减: {scores.temporal_decay_score:.2f}")
```

**评分维度:**
- `access_frequency_score`: 基于访问频率 (权重: 30%)
- `temporal_decay_score`: 基于时间衰减 (权重: 20%)
- `association_score`: 基于关联度 (权重: 30%)
- `user_feedback_score`: 基于用户反馈 (权重: 20%)

**调整权重:**
```python
scorer.adjust_weights(
    access_frequency_weight=0.4,
    temporal_decay_weight=0.2,
    association_weight=0.2,
    user_feedback_weight=0.2,
)
```

### 检索优化 (RetrieverOptimizer)

实现混合检索、查询扩展和重排序。

```python
from backend.app.core.memory.retrieval_optimizer import RetrieverOptimizer

optimizer = RetrieverOptimizer(
    vector_weight=0.6,      # 向量检索权重
    keyword_weight=0.4,     # 关键词检索权重
    cache_size=1000,        # 缓存大小
    enable_query_expansion=True,  # 启用查询扩展
    enable_reranking=True,  # 启用重排序
)

results = await optimizer.hybrid_retrieve(
    query="Python programming",
    memories=memories,
    embeddings=embeddings,
    top_k=10,
    use_cache=True,
)

# 获取统计信息
stats = optimizer.get_stats()
print(f"缓存命中率: {stats.cache_hit_rate:.1%}")
print(f"平均延迟: {stats.avg_latency*1000:.1f}ms")
```

### 图谱增强 (GraphEnhancer)

自动识别实体和推理关系。

```python
from backend.app.core.memory.graph_enhancer import GraphEnhancer

enhancer = GraphEnhancer(
    enable_entity_extraction=True,
    enable_relation_inference=True,
    enable_community_detection=True,
)

# 添加记忆到图谱
enhancer.add_memory_to_graph(
    "mem1",
    "Python is used for machine learning",
    {"importance": 0.8},
)

# 查找相关记忆
related = enhancer.find_related_memories(
    "mem1",
    depth=2,
    limit=20,
)

# 获取可视化数据
viz_data = enhancer.get_visualization_data()
```

### 生命周期管理 (MemoryLifecycleManager)

管理记忆的状态转换和自动清理。

```python
from backend.app.core.memory.lifecycle import (
    MemoryLifecycleManager,
    LifecyclePolicy,
    MemoryState,
)

policy = LifecyclePolicy(
    warm_threshold_days=7,      # 转为温存储的天数
    cold_threshold_days=30,     # 转为冷存储的天数
    archive_threshold_days=90,  # 归档的天数
    delete_threshold_days=365,  # 删除的天数
)

manager = MemoryLifecycleManager(policy=policy)

# 处理记忆访问
await manager.process_memory_access("mem1")

# 手动归档
await manager.archive_memory("mem1", reason="Not needed")

# 恢复记忆
await manager.restore_memory("mem1", reason="Needed again")

# 清理过期记忆
cleanup_result = await manager.cleanup_expired_memories()

# 获取统计信息
stats = manager.compute_stats()
print(f"活跃: {stats.active_count}, 温: {stats.warm_count}, 冷: {stats.cold_count}")
```

**记忆状态:**
- `ACTIVE`: 活跃状态，存储在热存储
- `WARM`: 温存储，访问频率降低
- `COLD`: 冷存储，很少访问
- `ARCHIVED`: 已归档，不常使用
- `DELETED`: 已删除

### 分析工具 (MemoryAnalytics)

评估记忆质量和生成报告。

```python
from backend.app.core.memory.analytics import MemoryAnalytics

analytics = MemoryAnalytics()

# 评估记忆质量
metrics = analytics.assess_memory_quality(
    "mem1",
    "Comprehensive memory with details",
    access_count=10,
    importance=0.8,
)

print(f"质量评分: {metrics.overall_quality:.2f}")
print(f"完整性: {metrics.completeness:.2f}")
print(f"准确性: {metrics.accuracy:.2f}")

# 分析覆盖度
coverage = analytics.analyze_coverage(memories)
print(f"覆盖度: {coverage.coverage_percentage:.1f}%")

# 生成报告
report = analytics.generate_report(memories, period_days=30)
print(f"新增记忆: {report.new_memories}")
print(f"删除记忆: {report.deleted_memories}")
```

## 集成到现有系统

### 1. 在MemorySystem中集成

```python
# backend/app/core/memory.py

from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem

class MemorySystem:
    def __init__(self, ...):
        # ... 现有初始化代码
        self.fusion_system = AdvancedMemoryFusionSystem()
    
    async def consolidate_with_fusion(self, context: RunContext):
        """使用融合系统进行记忆整合。"""
        memories = await self.search(context, "", top_k=100)
        
        result = await self.fusion_system.process_memories(
            [m.dict() for m in memories]
        )
        
        return result
```

### 2. 在API中暴露功能

```python
# backend/app/api/memory.py

@router.post("/memories/analyze")
async def analyze_memories(
    context: RunContext,
    period_days: int = 30,
):
    """分析记忆。"""
    memories = await memory_system.search(context, "", top_k=1000)
    
    report = await memory_system.fusion_system.generate_report(
        [m.dict() for m in memories],
        period_days=period_days,
    )
    
    return report
```

### 3. 定期清理任务

```python
# backend/app/core/tasks.py

async def cleanup_memories_task():
    """定期清理过期记忆。"""
    while True:
        try:
            result = await memory_system.fusion_system.cleanup_memories()
            logger.info(f"Memory cleanup: {result}")
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
        
        # 每24小时执行一次
        await asyncio.sleep(24 * 3600)
```

## 性能优化建议

### 1. 批量处理

```python
# 批量处理记忆而不是逐个处理
memories_batch = memories[i:i+100]
result = await system.process_memories(memories_batch)
```

### 2. 缓存管理

```python
# 定期清空缓存以释放内存
system.clear_caches()

# 重置统计信息
system.reset_stats()
```

### 3. 异步操作

```python
# 使用异步操作避免阻塞
tasks = [
    system.process_memories(batch)
    for batch in batches
]
results = await asyncio.gather(*tasks)
```

### 4. 选择性启用功能

```python
# 根据需要启用/禁用功能
system = AdvancedMemoryFusionSystem(
    enable_merger=True,
    enable_importance_scoring=True,
    enable_retrieval_optimization=True,
    enable_graph_enhancement=False,  # 禁用以节省资源
    enable_lifecycle_management=True,
    enable_analytics=False,  # 禁用以节省资源
)
```

## 监控和调试

### 获取系统统计信息

```python
stats = system.get_system_stats()

print(f"操作次数: {stats['operation_count']}")
print(f"检索统计: {stats.get('retrieval_stats', {})}")
print(f"图谱统计: {stats.get('graph_stats', {})}")
print(f"生命周期统计: {stats.get('lifecycle_stats', {})}")
```

### 获取可视化数据

```python
viz_data = system.get_visualization_data()

# 用于前端可视化
# viz_data['graph']: 图谱节点和边
# viz_data['lifecycle']: 生命周期分布
# viz_data['quality']: 质量分布
```

## 常见问题

### Q: 如何调整合并阈值？
A: 创建MemoryMerger时设置similarity_threshold参数。较高的值(0.9+)更严格，较低的值(0.7-)更宽松。

### Q: 如何优化检索性能？
A: 启用缓存、使用批量检索、调整vector_weight和keyword_weight的比例。

### Q: 如何处理记忆爆炸？
A: 启用生命周期管理，设置合理的清理策略，定期运行cleanup_memories()。

### Q: 如何评估记忆质量？
A: 使用MemoryAnalytics.assess_memory_quality()，查看overall_quality分数。

## 性能指标

基于测试数据：

- **合并性能**: 1000条记忆 < 100ms
- **检索性能**: 平均延迟 < 50ms (启用缓存)
- **图谱构建**: 1000个节点 < 200ms
- **报告生成**: 1000条记忆 < 500ms

## 下一步

1. 集成到现有的MemorySystem
2. 配置生命周期策略
3. 设置定期清理任务
4. 监控性能指标
5. 根据实际使用情况调整参数
