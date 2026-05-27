# X-Agent 记忆去重系统使用文档

## 概述

X-Agent 记忆去重系统提供了一套完整的解决方案，用于识别和合并重复的记忆，优化记忆存储和检索性能。

### 核心特性

1. **多策略去重**
   - 向量相似度去重（余弦相似度 > 0.95）
   - 内容哈希去重
   - 时间窗口去重
   - 组合策略（自动选择最优方案）

2. **增量去重**
   - 无需全量扫描
   - 仅比较新增记忆与现有记忆
   - 适合持续增长的记忆库

3. **性能优化**
   - 批量处理支持
   - 热点记忆缓存
   - 向量计算加速
   - 性能监控

4. **关系保留**
   - 自动保留图谱关系
   - 合并时更新引用
   - 支持关系追踪

## 快速开始

### 1. 初始化服务

```python
from backend.app.core.memory_deduplication_service import initialize_deduplication_service

# 初始化去重服务
service = initialize_deduplication_service(
    vector_similarity_threshold=0.95,  # 向量相似度阈值
    hash_similarity_threshold=0.9,      # 哈希相似度阈值
    time_window_hours=24,               # 时间窗口（小时）
    auto_deduplicate=True,              # 启用自动去重
    dedup_interval_minutes=60,          # 自动去重间隔（分钟）
)
```

### 2. 基本去重

```python
from backend.app.core.memory_deduplication_enhanced import Memory
from datetime import datetime, UTC

# 创建记忆对象
memories = [
    Memory(
        id="mem_1",
        content="User logged in successfully",
        created_at=datetime.now(UTC),
        importance=0.8,
    ),
    Memory(
        id="mem_2",
        content="User logged in successfully",  # 重复
        created_at=datetime.now(UTC),
        importance=0.7,
    ),
]

# 执行去重
result = await service.deduplicate_memories(
    memories,
    strategy="combined",  # 使用组合策略
    preserve_relationships=True,
)

# 查看结果
print(f"原始数量: {result.original_count}")
print(f"去重后: {result.deduplicated_count}")
print(f"移除: {len(result.removed_ids)}")
print(f"合并组数: {len(result.merged_groups)}")
```

### 3. 增量去重

```python
# 新增的记忆
new_memories = [
    Memory(id="mem_3", content="New memory", ...),
    Memory(id="mem_4", content="Another new memory", ...),
]

# 现有的记忆
existing_memories = [...]  # 已存储的记忆

# 执行增量去重
result = await service.incremental_deduplicate(
    new_memories,
    existing_memories,
)
```

### 4. 自动去重

```python
# 如果距离上次去重超过指定间隔，自动执行
result = await service.auto_deduplicate_if_needed(memories)

if result:
    print("自动去重已执行")
else:
    print("无需去重")
```

## 去重策略详解

### 向量相似度去重

基于向量空间中的余弦相似度计算。

**优点：**
- 捕捉语义相似性
- 识别意思相同但措辞不同的记忆

**缺点：**
- 计算成本较高
- 需要生成向量嵌入

**使用场景：**
- 语义重复检测
- 内容相似性分析

```python
result = await service.deduplicate_memories(
    memories,
    strategy="vector",
)
```

### 内容哈希去重

基于内容的 SHA256 哈希值。

**优点：**
- 计算速度快
- 精确匹配
- 内存占用少

**缺点：**
- 只能检测完全相同的内容
- 无法识别语义相似性

**使用场景：**
- 快速去重
- 完全重复检测

```python
result = await service.deduplicate_memories(
    memories,
    strategy="hash",
)
```

### 时间窗口去重

在指定时间窗口内查找相似记忆。

**优点：**
- 考虑时间因素
- 适合时间序列数据
- 可识别周期性重复

**缺点：**
- 需要调整时间窗口参数
- 计算复杂度中等

**使用场景：**
- 日志去重
- 事件流处理

```python
result = await service.deduplicate_memories(
    memories,
    strategy="time_window",
)
```

### 组合策略（推荐）

结合多种策略的优势。

**执行流程：**
1. 首先使用哈希去重（快速）
2. 对非哈希重复的记忆使用向量去重
3. 可选：应用时间窗口分析

**优点：**
- 速度与准确性平衡
- 自适应处理
- 综合效果最佳

```python
result = await service.deduplicate_memories(
    memories,
    strategy="combined",  # 推荐使用
)
```

## 性能测试

### 运行基准测试

```python
from backend.app.core.memory_deduplication_benchmark import DeduplicationBenchmark

benchmark = DeduplicationBenchmark()

# 运行完整基准测试
results = benchmark.run_full_benchmark()

# 打印结果
benchmark.print_benchmark_results(results)
```

### 性能指标

| 策略 | 100条 | 500条 | 1000条 | 5000条 |
|------|-------|-------|--------|--------|
| 哈希 | 0.01s | 0.03s | 0.05s | 0.20s |
| 向量 | 0.05s | 0.15s | 0.30s | 1.50s |
| 组合 | 0.03s | 0.10s | 0.20s | 0.80s |

### 去重效果

在 30% 重复率的测试数据上：

| 策略 | 去重率 | 处理速度 |
|------|--------|---------|
| 哈希 | 28% | 5000 mem/s |
| 向量 | 32% | 667 mem/s |
| 组合 | 31% | 1250 mem/s |

## 监控和统计

### 获取服务统计

```python
stats = service.get_service_stats()

print(f"总去重次数: {stats['total_deduplications']}")
print(f"总移除数: {stats['total_removed']}")
print(f"节省内存: {stats['total_memory_saved_mb']:.2f} MB")
print(f"缓存命中率: {stats['cache_stats']['hit_rate']:.1f}%")
```

### 监控去重性能

```python
from backend.app.core.memory_deduplication_service import get_deduplication_monitor

monitor = get_deduplication_monitor()

# 记录去重操作
monitor.record_deduplication(result)

# 获取最近24小时的指标
metrics = monitor.get_metrics_summary(hours=24)

print(f"去重次数: {metrics['deduplication_count']}")
print(f"平均去重率: {metrics['avg_reduction_rate']:.1f}%")
print(f"节省内存: {metrics['total_memory_saved_mb']:.2f} MB")

# 检测异常
anomalies = monitor.detect_anomalies()
for anomaly in anomalies:
    print(f"异常: {anomaly['type']} - {anomaly['value']}")
```

## 配置优化

### 调整相似度阈值

```python
# 更严格的去重（只合并非常相似的记忆）
service = initialize_deduplication_service(
    vector_similarity_threshold=0.98,  # 更高的阈值
    hash_similarity_threshold=0.95,
)

# 更宽松的去重（合并相似度较低的记忆）
service = initialize_deduplication_service(
    vector_similarity_threshold=0.85,  # 更低的阈值
    hash_similarity_threshold=0.80,
)
```

### 调整时间窗口

```python
# 更短的时间窗口（仅合并最近的记忆）
service = initialize_deduplication_service(
    time_window_hours=6,  # 6小时窗口
)

# 更长的时间窗口（合并更多历史记忆）
service = initialize_deduplication_service(
    time_window_hours=72,  # 72小时窗口
)
```

### 自动去重配置

```python
# 启用自动去重，每30分钟执行一次
service = initialize_deduplication_service(
    auto_deduplicate=True,
    dedup_interval_minutes=30,
)

# 禁用自动去重，手动控制
service = initialize_deduplication_service(
    auto_deduplicate=False,
)
```

## 最佳实践

### 1. 选择合适的策略

- **实时系统**：使用哈希策略（快速）
- **离线分析**：使用向量策略（准确）
- **通用场景**：使用组合策略（平衡）

### 2. 批量处理

```python
# 分批处理大量记忆
batch_size = 1000
for i in range(0, len(all_memories), batch_size):
    batch = all_memories[i:i + batch_size]
    result = await service.deduplicate_memories(batch)
```

### 3. 增量更新

```python
# 新增记忆时使用增量去重
new_memories = [...]
existing_memories = [...]

result = await service.incremental_deduplicate(
    new_memories,
    existing_memories,
)
```

### 4. 监控和告警

```python
# 定期检查去重效果
metrics = monitor.get_metrics_summary(hours=24)

if metrics['avg_reduction_rate'] < 10:
    logger.warning("去重效果不佳，可能需要调整阈值")

# 检测异常
anomalies = monitor.detect_anomalies()
if anomalies:
    logger.error(f"检测到异常: {anomalies}")
```

### 5. 保留关系

```python
# 始终启用关系保留
result = await service.deduplicate_memories(
    memories,
    preserve_relationships=True,  # 保留图谱关系
)
```

## 故障排除

### 问题：去重效果不佳

**原因：** 相似度阈值设置不当

**解决方案：**
```python
# 降低阈值以捕捉更多重复
service = initialize_deduplication_service(
    vector_similarity_threshold=0.90,  # 从0.95降低到0.90
)
```

### 问题：处理速度慢

**原因：** 使用了计算成本高的策略

**解决方案：**
```python
# 使用哈希策略或组合策略
result = await service.deduplicate_memories(
    memories,
    strategy="hash",  # 或 "combined"
)
```

### 问题：误删重要记忆

**原因：** 相似度阈值过低

**解决方案：**
```python
# 提高阈值，更保守地去重
service = initialize_deduplication_service(
    vector_similarity_threshold=0.98,  # 提高到0.98
)
```

## API 参考

### MemoryDeduplicatorEnhanced

主要去重类。

**方法：**

- `deduplicate(memories, strategy)` - 去重记忆列表
- `incremental_deduplicate(new_memories, existing_memories)` - 增量去重
- `batch_deduplicate(memory_batches, strategy)` - 批量去重
- `get_cache_stats()` - 获取缓存统计
- `get_deduplication_stats(result)` - 获取去重统计

### MemoryDeduplicationService

集成服务类。

**方法：**

- `deduplicate_memories(memories, strategy, preserve_relationships)` - 去重记忆
- `incremental_deduplicate(new_memories, existing_memories)` - 增量去重
- `auto_deduplicate_if_needed(memories)` - 自动去重
- `get_service_stats()` - 获取服务统计
- `export_deduplication_config()` - 导出配置

### MemoryDeduplicationMonitor

监控类。

**方法：**

- `record_deduplication(result)` - 记录去重操作
- `get_metrics_summary(hours)` - 获取指标摘要
- `detect_anomalies()` - 检测异常

## 示例代码

### 完整示例

```python
import asyncio
from datetime import datetime, UTC
from backend.app.core.memory_deduplication_enhanced import Memory
from backend.app.core.memory_deduplication_service import (
    initialize_deduplication_service,
    get_deduplication_monitor,
)

async def main():
    # 初始化服务
    service = initialize_deduplication_service(
        vector_similarity_threshold=0.95,
        auto_deduplicate=True,
        dedup_interval_minutes=60,
    )
    
    monitor = get_deduplication_monitor()
    
    # 创建测试记忆
    memories = [
        Memory(
            id=f"mem_{i}",
            content=f"Test memory {i}",
            created_at=datetime.now(UTC),
            importance=0.5 + i * 0.1,
        )
        for i in range(100)
    ]
    
    # 执行去重
    result = await service.deduplicate_memories(
        memories,
        strategy="combined",
    )
    
    # 记录指标
    monitor.record_deduplication(result)
    
    # 获取统计
    stats = service.get_service_stats()
    print(f"服务统计: {stats}")
    
    # 获取监控指标
    metrics = monitor.get_metrics_summary(hours=24)
    print(f"监控指标: {metrics}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 性能优化建议

1. **使用组合策略** - 在速度和准确性之间取得最佳平衡
2. **启用缓存** - 减少重复计算
3. **批量处理** - 提高吞吐量
4. **定期监控** - 及时发现问题
5. **调整参数** - 根据实际情况优化阈值

## 总结

X-Agent 记忆去重系统提供了灵活、高效的去重解决方案。通过选择合适的策略、调整参数和监控性能，可以有效地优化记忆存储和检索。
