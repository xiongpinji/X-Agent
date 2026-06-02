# X-Agent 记忆系统V2 - 完整使用指南

## 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [API参考](#api参考)
4. [使用示例](#使用示例)
5. [最佳实践](#最佳实践)
6. [性能优化](#性能优化)
7. [故障排除](#故障排除)

## 快速开始

### 安装和初始化

```python
from backend.app.core.memory_v2_system import MemoryV2System, MemoryCategory, MemoryTier
from backend.app.core.memory_v2_skill import SkillMemoryLayer
from backend.app.core.memory_v2_nudge import NudgeMemoryLayer, NudgeConfig

# 初始化系统
memory_system = MemoryV2System(
    storage_path=".xagent_runtime/memory_v2.jsonl",
    enable_skill_generation=True,
    enable_nudge_consolidation=True,
    enable_hybrid_retrieval=True,
)

# 初始化技能层
skill_layer = SkillMemoryLayer(
    storage_path=".xagent_runtime/skills.jsonl",
    auto_generate=True,
)

# 初始化主动整理层
nudge_config = NudgeConfig(
    consolidation_enabled=True,
    consolidation_schedule="0 2 * * *",  # 每天凌晨2点
    deduplication_enabled=True,
    deduplication_schedule="0 3 * * 0",  # 每周日凌晨3点
)
nudge_layer = NudgeMemoryLayer(config=nudge_config, memory_system=memory_system)

# 启动主动整理
await nudge_layer.start()
```

### 基本操作

```python
# 存储记忆
memory_id = await memory_system.store(
    content="Python是一种高级编程语言",
    tenant_id="tenant-001",
    agent_id="agent-001",
    category=MemoryCategory.REFERENCE,
    importance=0.7,
    tags=["python", "programming"],
)

# 检索记忆
memory = await memory_system.retrieve(memory_id, tenant_id="tenant-001")
print(memory.content)

# 搜索记忆
results = await memory_system.search(
    query="Python编程",
    tenant_id="tenant-001",
    limit=10,
)
for result in results:
    print(f"相关性: {result.importance:.2f}, 内容: {result.content[:50]}")
```

## 核心概念

### 三层记忆架构

#### 第一层：程序记忆 (Skill Memory)

自动从Agent执行结果生成SKILL.md，包含：
- 技能描述和参数
- 使用示例
- 最佳实践
- 性能和安全说明

```python
# 从执行结果生成技能
skill = await skill_layer.generate_from_execution(
    agent_id="agent-001",
    execution_result={
        "description": "数据分析技能",
        "parameters": {
            "data": "输入数据",
            "method": "分析方法"
        },
        "returns": {
            "result": "分析结果"
        },
        "examples": [
            {
                "title": "基础示例",
                "input": {"data": [1, 2, 3]},
                "output": {"result": 2.0}
            }
        ],
        "best_practices": [
            "始终验证输入数据",
            "使用缓存提高性能"
        ],
        "common_pitfalls": [
            "忽略数据类型检查",
            "未处理边界情况"
        ]
    },
    skill_name="data_analysis",
    description="数据分析和统计"
)

# 导出为SKILL.md
markdown = skill_layer.export_skill_as_markdown(skill.metadata.skill_id)
with open("SKILL.md", "w") as f:
    f.write(markdown)
```

#### 第二层：主动记忆整理 (Nudge Memory)

周期性自动执行：
- 记忆整合（Consolidation）
- 去重合并（Deduplication）
- 内容压缩（Compression）
- 归档管理（Archival）
- 淘汰清理（Eviction）

```python
# 手动触发整合
result = await nudge_layer.consolidate(
    tenant_id="tenant-001",
    batch_size=50,
    min_importance=0.3,
)
print(f"整合了 {result['consolidated']} 条记忆")

# 手动触发去重
result = await nudge_layer.deduplicate(
    tenant_id="tenant-001",
    similarity_threshold=0.85,
)
print(f"去重了 {result['deduplicated']} 条记忆")

# 手动触发淘汰
result = await nudge_layer.evict(
    tenant_id="tenant-001",
    storage_limit_mb=500,
    min_importance=0.1,
    max_age_days=30,
)
print(f"淘汰了 {result['evicted']} 条记忆")
```

#### 第三层：混合检索 (Hybrid Retrieval)

结合向量、关键词和图谱检索：

```python
from backend.app.core.memory_v2_retriever import HybridRetriever, HybridRetrieverConfig

# 配置混合检索
config = HybridRetrieverConfig(
    vector_weight=0.5,      # 向量检索权重
    keyword_weight=0.3,     # 关键词检索权重
    graph_weight=0.2,       # 图谱检索权重
    top_k=10,
    enable_reranking=True,
    enable_diversity=True,
)

retriever = HybridRetriever(config=config)

# 执行混合检索
results = await retriever.search(
    query="Python机器学习",
    tenant_id="tenant-001",
    top_k=10,
    use_vector=True,
    use_keyword=True,
    use_graph=True,
)

for result in results:
    print(f"排名: {result.rank}")
    print(f"综合评分: {result.combined_score:.3f}")
    print(f"  向量评分: {result.vector_score:.3f}")
    print(f"  关键词评分: {result.keyword_score:.3f}")
    print(f"  图谱评分: {result.graph_score:.3f}")
    print(f"内容: {result.content[:100]}")
```

### 重要性评分

记忆重要性由多个维度综合计算：

```
重要性 = 
    0.25 * 访问频率 +
    0.20 * 新鲜度 +
    0.20 * 内容质量 +
    0.15 * 关系中心性 +
    0.15 * 用户标记 +
    0.05 * 执行成功率
```

示例：

```python
# 查看记忆的重要性评分详情
memory = await memory_system.retrieve(memory_id, tenant_id)
score = memory.importance_score

print(f"总分: {score.total:.2f}")
print(f"访问频率: {score.access_frequency:.2f}")
print(f"新鲜度: {score.freshness:.2f}")
print(f"内容质量: {score.content_quality:.2f}")
print(f"关系中心性: {score.relationship_centrality:.2f}")
print(f"用户标记: {score.user_mark:.2f}")
print(f"执行成功率: {score.execution_success:.2f}")
```

### 版本控制

每条记忆都支持版本管理：

```python
# 更新记忆并创建新版本
new_version = await memory_system.update_version(
    memory_id=memory_id,
    new_content="更新后的内容",
    agent_id="agent-001",
    change_summary="添加了新的示例",
)

print(f"新版本: {new_version.version}")
print(f"变更类型: {new_version.change_type}")
print(f"变更摘要: {new_version.change_summary}")

# 查看版本历史
memory = await memory_system.retrieve(memory_id, tenant_id)
for version in memory.versions:
    print(f"版本 {version.version}: {version.change_summary}")

# 回滚到历史版本
rollback_result = await memory_system.rollback_version(
    memory_id=memory_id,
    target_version=1,
)
print(f"已回滚到版本 {rollback_result.version}")
```

## API参考

### MemoryV2System

#### store()

存储新记忆。

```python
memory_id = await memory_system.store(
    content: str,                           # 记忆内容
    tenant_id: str,                         # 租户ID
    agent_id: str | None = None,            # Agent ID
    category: MemoryCategory = REFERENCE,   # 记忆类别
    tier: MemoryTier | str = "auto",        # 存储层
    importance: float | None = None,        # 重要性(0-1)
    tags: list[str] | None = None,          # 标签
    metadata: dict | None = None,           # 元数据
    related_memory_ids: list[str] | None = None,  # 相关记忆
) -> str
```

#### retrieve()

检索记忆。

```python
memory = await memory_system.retrieve(
    memory_id: str,                 # 记忆ID
    tenant_id: str | None = None,   # 租户ID(用于访问控制)
) -> MemoryV2Item | None
```

#### search()

搜索记忆。

```python
results = await memory_system.search(
    query: str,                     # 搜索查询
    tenant_id: str,                 # 租户ID
    limit: int = 10,                # 返回结果数
    tier: MemoryTier | None = None, # 限制搜索层
    category: MemoryCategory | None = None,  # 限制类别
) -> list[MemoryV2Item]
```

#### consolidate()

整合记忆。

```python
result = await memory_system.consolidate(
    tenant_id: str,                 # 租户ID
    source_tier: MemoryTier = NUDGE,  # 源层
    target_tier: MemoryTier = ARCHIVE,  # 目标层
    min_importance: float = 0.3,    # 最小重要性
    max_items: int = 50,            # 最大项数
) -> dict[str, Any]
```

#### update_version()

更新记忆并创建新版本。

```python
version = await memory_system.update_version(
    memory_id: str,                 # 记忆ID
    new_content: str,               # 新内容
    agent_id: str | None = None,    # Agent ID
    change_summary: str = "",       # 变更摘要
) -> MemoryVersion | None
```

#### rollback_version()

回滚到历史版本。

```python
version = await memory_system.rollback_version(
    memory_id: str,                 # 记忆ID
    target_version: int,            # 目标版本号
) -> MemoryVersion | None
```

### SkillMemoryLayer

#### generate_from_execution()

从执行结果生成技能。

```python
skill = await skill_layer.generate_from_execution(
    agent_id: str,                  # Agent ID
    execution_result: dict[str, Any],  # 执行结果
    skill_name: str,                # 技能名称
    description: str = "",          # 描述
) -> SkillMemory
```

#### update_skill()

更新技能。

```python
skill = await skill_layer.update_skill(
    skill_id: str,                  # 技能ID
    updates: dict[str, Any],        # 更新内容
) -> SkillMemory | None
```

#### add_example()

添加使用示例。

```python
skill = await skill_layer.add_example(
    skill_id: str,                  # 技能ID
    example: SkillExample,          # 示例
) -> SkillMemory | None
```

#### record_execution()

记录执行结果。

```python
skill = await skill_layer.record_execution(
    skill_id: str,                  # 技能ID
    success: bool,                  # 是否成功
    execution_time_ms: float | None = None,  # 执行时间
) -> SkillMemory | None
```

### NudgeMemoryLayer

#### consolidate()

整合记忆。

```python
result = await nudge_layer.consolidate(
    tenant_id: str,                 # 租户ID
    batch_size: int | None = None,  # 批大小
    min_importance: float | None = None,  # 最小重要性
) -> dict[str, Any]
```

#### deduplicate()

去重记忆。

```python
result = await nudge_layer.deduplicate(
    tenant_id: str,                 # 租户ID
    similarity_threshold: float | None = None,  # 相似度阈值
) -> dict[str, Any]
```

#### compress()

压缩记忆。

```python
result = await nudge_layer.compress(
    tenant_id: str,                 # 租户ID
    ratio_target: float | None = None,  # 压缩比目标
) -> dict[str, Any]
```

#### archive()

归档记忆。

```python
result = await nudge_layer.archive(
    tenant_id: str,                 # 租户ID
    age_days: int | None = None,    # 年龄(天)
    importance_threshold: float | None = None,  # 重要性阈值
) -> dict[str, Any]
```

#### evict()

淘汰记忆。

```python
result = await nudge_layer.evict(
    tenant_id: str,                 # 租户ID
    storage_limit_mb: int | None = None,  # 存储限制
    min_importance: float | None = None,  # 最小重要性
    max_age_days: int | None = None,  # 最大年龄
) -> dict[str, Any]
```

## 使用示例

### 示例1：Agent执行后自动生成技能

```python
async def agent_execution_with_skill_generation():
    """Agent执行并自动生成技能记忆。"""
    
    # 执行Agent任务
    execution_result = {
        "description": "数据清洗和转换",
        "parameters": {
            "input_file": "输入CSV文件路径",
            "output_file": "输出CSV文件路径",
            "transformations": "应用的转换列表"
        },
        "returns": {
            "rows_processed": "处理的行数",
            "errors": "错误列表",
            "duration_ms": "执行时间"
        },
        "examples": [
            {
                "title": "基础数据清洗",
                "input": {
                    "input_file": "raw_data.csv",
                    "transformations": ["remove_nulls", "normalize"]
                },
                "output": {
                    "rows_processed": 1000,
                    "errors": []
                }
            }
        ],
        "best_practices": [
            "始终备份原始数据",
            "验证转换结果",
            "记录所有变更"
        ],
        "common_pitfalls": [
            "忽略数据类型",
            "未处理缺失值",
            "性能问题"
        ],
        "performance_notes": "大文件建议使用流式处理",
        "security_notes": "确保文件权限正确"
    }
    
    # 生成技能
    skill = await skill_layer.generate_from_execution(
        agent_id="data-agent-001",
        execution_result=execution_result,
        skill_name="data_cleaning",
        description="数据清洗和转换技能"
    )
    
    # 导出SKILL.md
    markdown = skill_layer.export_skill_as_markdown(skill.metadata.skill_id)
    print(markdown)
    
    # 记录执行
    await skill_layer.record_execution(
        skill_id=skill.metadata.skill_id,
        success=True,
        execution_time_ms=1234.5
    )
```

### 示例2：周期性记忆整理

```python
async def periodic_memory_maintenance():
    """周期性执行记忆整理任务。"""
    
    tenant_id = "tenant-001"
    
    # 启动主动整理层
    await nudge_layer.start()
    
    # 手动触发整合
    consolidation = await nudge_layer.consolidate(
        tenant_id=tenant_id,
        batch_size=100,
        min_importance=0.3
    )
    print(f"整合: {consolidation['consolidated']} 条记忆")
    
    # 手动触发去重
    deduplication = await nudge_layer.deduplicate(
        tenant_id=tenant_id,
        similarity_threshold=0.85
    )
    print(f"去重: {deduplication['deduplicated']} 条记忆")
    
    # 手动触发压缩
    compression = await nudge_layer.compress(
        tenant_id=tenant_id,
        ratio_target=0.8
    )
    print(f"压缩: {compression['compressed']} 条记忆")
    
    # 手动触发淘汰
    eviction = await nudge_layer.evict(
        tenant_id=tenant_id,
        storage_limit_mb=500,
        min_importance=0.1,
        max_age_days=30
    )
    print(f"淘汰: {eviction['evicted']} 条记忆")
    
    # 获取统计信息
    stats = nudge_layer.get_statistics()
    print(f"任务统计: {stats}")
```

### 示例3：混合检索

```python
async def hybrid_search_example():
    """使用混合检索查找相关记忆。"""
    
    # 存储测试数据
    for i in range(100):
        await memory_system.store(
            content=f"Python {i}: 高级编程语言特性",
            tenant_id="tenant-001",
            tags=["python", "programming"],
            importance=0.5 + (i % 10) * 0.05
        )
    
    # 执行混合检索
    results = await memory_system.search(
        query="Python编程",
        tenant_id="tenant-001",
        limit=10
    )
    
    # 显示结果
    for result in results:
        print(f"重要性: {result.importance:.2f}")
        print(f"内容: {result.content}")
        print(f"标签: {result.tags}")
        print("---")
```

## 最佳实践

### 1. 合理设置重要性

```python
# 高重要性：核心技能、关键决策
await memory_system.store(
    content="关键算法实现",
    tenant_id=tenant_id,
    importance=0.9,
    tags=["critical", "algorithm"]
)

# 中等重要性：常用工具、参考资料
await memory_system.store(
    content="常用工具函数",
    tenant_id=tenant_id,
    importance=0.5,
    tags=["utility", "reference"]
)

# 低重要性：临时记录、调试信息
await memory_system.store(
    content="临时调试信息",
    tenant_id=tenant_id,
    importance=0.2,
    tags=["temporary", "debug"]
)
```

### 2. 使用标签分类

```python
# 按功能分类
await memory_system.store(
    content="...",
    tenant_id=tenant_id,
    tags=["data-processing", "etl", "python"]
)

# 按来源分类
await memory_system.store(
    content="...",
    tenant_id=tenant_id,
    tags=["agent-001", "execution-result"]
)

# 按状态分类
await memory_system.store(
    content="...",
    tenant_id=tenant_id,
    tags=["verified", "production-ready"]
)
```

### 3. 定期维护

```python
# 每天凌晨2点自动整合
nudge_config.consolidation_schedule = "0 2 * * *"

# 每周日凌晨3点自动去重
nudge_config.deduplication_schedule = "0 3 * * 0"

# 每周日凌晨4点自动归档
nudge_config.archival_schedule = "0 4 * * 0"

# 每天凌晨5点自动淘汰
nudge_config.eviction_schedule = "0 5 * * *"
```

### 4. 监控性能

```python
# 获取系统统计
stats = memory_system.get_statistics()
print(f"总记忆数: {stats['total_memories']}")
print(f"缓存大小: {stats['cache_size']}")
print(f"存储统计: {stats['tier_counts']}")

# 获取技能统计
skill_stats = skill_layer.get_statistics()
print(f"总技能数: {skill_stats['total_skills']}")
print(f"成功率: {skill_stats['success_rate']:.2%}")

# 获取任务统计
task_stats = nudge_layer.get_statistics()
print(f"完成任务: {task_stats['completed_tasks']}")
print(f"失败任务: {task_stats['failed_tasks']}")
```

## 性能优化

### 1. 缓存优化

- L1缓存（内存）：最近100条记忆，TTL 5分钟
- L2缓存（Redis）：热点记忆，TTL 1小时
- L3缓存（本地文件）：程序记忆，持久化

### 2. 索引优化

- PostgreSQL：GIN索引用于全文搜索
- Qdrant：HNSW索引用于向量搜索
- Neo4j：属性索引用于图谱查询

### 3. 批量操作

```python
# 批量存储
memory_ids = []
for i in range(1000):
    memory_id = await memory_system.store(
        content=f"Memory {i}",
        tenant_id=tenant_id
    )
    memory_ids.append(memory_id)

# 批量搜索
results = await memory_system.search(
    query="Memory",
    tenant_id=tenant_id,
    limit=100
)
```

## 故障排除

### 问题1：搜索性能下降

**症状**：搜索时间超过50ms

**解决方案**：
1. 检查缓存命中率
2. 运行去重和整合
3. 检查索引状态
4. 考虑增加缓存大小

### 问题2：存储空间不足

**症状**：存储使用率超过限制

**解决方案**：
1. 手动运行淘汰任务
2. 检查低重要性记忆
3. 启用自动压缩
4. 增加存储限制

### 问题3：重复记忆过多

**症状**：去重后仍有大量相似记忆

**解决方案**：
1. 降低相似度阈值
2. 改进记忆生成逻辑
3. 增加去重频率
4. 手动审查和合并

## 参考资源

- [架构设计文档](memory_system_v2_architecture.md)
- [性能测试报告](../tests/test_memory_v2_performance.py)
- [迁移指南](memory_v2_migration.md)
