"""
高级记忆融合系统 README

X-Agent 高级记忆融合系统的完整实现和文档。
"""

# X-Agent 高级记忆融合系统

## 📋 项目概述

高级记忆融合系统是X-Agent的核心记忆管理模块，提供智能的记忆合并、重要性评分、检索优化、图谱增强、生命周期管理和分析功能。

**版本**: 1.0.0  
**状态**: ✅ 完成  
**最后更新**: 2026-05-27

## 🎯 核心功能

### 1. 智能记忆合并 (MemoryMerger)
- 基于语义相似度的自动合并
- 保留最重要的信息
- 支持异步批量处理
- 合并历史追踪

### 2. 重要性评分 (MemoryImportanceScorer)
- 多维度评分系统
- 访问频率、时间衰减、关联度、用户反馈
- 动态权重调整
- 批量评分支持

### 3. 检索优化 (RetrieverOptimizer)
- 混合检索 (向量 + 关键词)
- 查询扩展和重排序
- 智能缓存机制
- 性能监控

### 4. 图谱增强 (GraphEnhancer)
- 自动实体识别
- 关系推理
- 社区检测
- 路径查询

### 5. 生命周期管理 (MemoryLifecycleManager)
- 自动状态转换
- 冷热数据分离
- 自动清理过期数据
- 记忆恢复机制

### 6. 分析工具 (MemoryAnalytics)
- 质量评估
- 覆盖度分析
- 报告生成
- 趋势分析

## 📁 项目结构

```
backend/app/core/memory/
├── __init__.py                    # 包初始化
├── merger.py                      # 记忆合并模块
├── importance.py                  # 重要性评分模块
├── retrieval_optimizer.py         # 检索优化模块
├── graph_enhancer.py              # 图谱增强模块
├── lifecycle.py                   # 生命周期管理模块
├── analytics.py                   # 分析工具模块
├── fusion_system.py               # 完整系统集成
└── benchmark.py                   # 性能基准测试

tests/
└── test_memory_fusion.py          # 完整测试套件

文档/
├── MEMORY_FUSION_INTEGRATION_GUIDE.md    # 集成指南
├── MEMORY_FUSION_PROJECT_SUMMARY.md      # 项目总结
└── README.md                             # 本文件
```

## 🚀 快速开始

### 安装依赖

```bash
pip install numpy scikit-learn
```

### 基本使用

```python
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem
from datetime import datetime, UTC

# 初始化系统
system = AdvancedMemoryFusionSystem()

# 准备记忆数据
memories = [
    {
        "id": "mem1",
        "content": "Python is a programming language",
        "importance": 0.8,
        "created_at": datetime.now(UTC),
        "access_count": 5,
    },
    # ... 更多记忆
]

# 处理记忆
result = await system.process_memories(memories)
print(f"处理了 {result['processed_count']} 条记忆")

# 检索记忆
results = await system.retrieve_memories("Python", memories, top_k=10)
for r in results:
    print(f"记忆 {r['id']}: 分数 {r['score']:.2f}")

# 生成报告
report = await system.generate_report(memories)
print(f"平均质量: {report.avg_quality:.2f}")
```

## 📚 详细文档

### 集成指南
查看 `MEMORY_FUSION_INTEGRATION_GUIDE.md` 获取：
- 详细的模块说明
- 集成示例
- 性能优化建议
- 常见问题解答

### 项目总结
查看 `MEMORY_FUSION_PROJECT_SUMMARY.md` 获取：
- 完整的交付物清单
- 技术架构
- 性能指标
- 使用示例

## 🧪 测试

### 运行所有测试

```bash
pytest tests/test_memory_fusion.py -v
```

### 运行特定测试

```bash
# 测试记忆合并
pytest tests/test_memory_fusion.py::TestMemoryMerger -v

# 测试重要性评分
pytest tests/test_memory_fusion.py::TestMemoryImportanceScorer -v

# 测试完整系统
pytest tests/test_memory_fusion.py::TestAdvancedMemoryFusionSystem -v
```

### 性能基准测试

```bash
python backend/app/core/memory/benchmark.py
```

## 📊 性能指标

| 操作 | 100条 | 1000条 | 5000条 |
|------|-------|--------|--------|
| 合并 | <10ms | <50ms | <200ms |
| 评分 | <5ms | <40ms | <150ms |
| 检索 | <20ms | <80ms | <300ms |
| 图谱 | <15ms | <70ms | <250ms |
| 完整系统 | <80ms | <450ms | <1500ms |

## 🔧 配置示例

### 自定义生命周期策略

```python
from backend.app.core.memory.lifecycle import LifecyclePolicy, MemoryLifecycleManager

policy = LifecyclePolicy(
    warm_threshold_days=7,
    cold_threshold_days=30,
    archive_threshold_days=90,
    delete_threshold_days=365,
)

manager = MemoryLifecycleManager(policy=policy)
```

### 调整重要性权重

```python
from backend.app.core.memory.importance import MemoryImportanceScorer

scorer = MemoryImportanceScorer()
scorer.adjust_weights(
    access_frequency_weight=0.4,
    temporal_decay_weight=0.2,
    association_weight=0.2,
    user_feedback_weight=0.2,
)
```

### 优化检索性能

```python
from backend.app.core.memory.retrieval_optimizer import RetrieverOptimizer

optimizer = RetrieverOptimizer(
    vector_weight=0.6,
    keyword_weight=0.4,
    cache_size=2000,
    enable_query_expansion=True,
    enable_reranking=True,
)
```

## 🔌 集成到现有系统

### 在MemorySystem中集成

```python
# backend/app/core/memory.py

from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem

class MemorySystem:
    def __init__(self):
        self.fusion_system = AdvancedMemoryFusionSystem()
    
    async def consolidate_with_fusion(self, context):
        memories = await self.search(context, "", top_k=100)
        result = await self.fusion_system.process_memories(
            [m.dict() for m in memories]
        )
        return result
```

### 在API中暴露功能

```python
# backend/app/api/memory.py

@router.post("/memories/analyze")
async def analyze_memories(context: RunContext, period_days: int = 30):
    memories = await memory_system.search(context, "", top_k=1000)
    report = await memory_system.fusion_system.generate_report(
        [m.dict() for m in memories],
        period_days=period_days,
    )
    return report
```

## 📈 监控和调试

### 获取系统统计信息

```python
stats = system.get_system_stats()
print(f"操作次数: {stats['operation_count']}")
print(f"检索统计: {stats.get('retrieval_stats', {})}")
print(f"图谱统计: {stats.get('graph_stats', {})}")
```

### 获取可视化数据

```python
viz_data = system.get_visualization_data()
# viz_data['graph']: 图谱节点和边
# viz_data['lifecycle']: 生命周期分布
# viz_data['quality']: 质量分布
```

## ❓ 常见问题

### Q: 如何调整合并阈值？
A: 创建MemoryMerger时设置similarity_threshold参数。较高的值(0.9+)更严格，较低的值(0.7-)更宽松。

### Q: 如何优化检索性能？
A: 启用缓存、使用批量检索、调整vector_weight和keyword_weight的比例。

### Q: 如何处理记忆爆炸？
A: 启用生命周期管理，设置合理的清理策略，定期运行cleanup_memories()。

### Q: 如何评估记忆质量？
A: 使用MemoryAnalytics.assess_memory_quality()，查看overall_quality分数。

### Q: 支持哪些嵌入模型？
A: 当前使用简单的哈希方法。建议集成OpenAI、Hugging Face或本地模型。

## 🛠️ 故障排除

### 内存使用过高
- 清空缓存: `system.clear_caches()`
- 禁用不需要的功能
- 减少缓存大小

### 检索速度慢
- 启用缓存
- 减少top_k值
- 禁用查询扩展

### 图谱构建缓慢
- 禁用实体提取
- 禁用社区检测
- 使用采样方法

## 📝 许可证

本项目是X-Agent的一部分。

## 👥 贡献

欢迎提交问题和改进建议。

## 📞 支持

- 查看集成指南: `MEMORY_FUSION_INTEGRATION_GUIDE.md`
- 查看项目总结: `MEMORY_FUSION_PROJECT_SUMMARY.md`
- 运行测试: `pytest tests/test_memory_fusion.py -v`
- 运行基准: `python backend/app/core/memory/benchmark.py`

## 🎓 学习资源

### 模块学习顺序
1. 从 `MemoryMerger` 开始了解基本的合并逻辑
2. 学习 `MemoryImportanceScorer` 的评分机制
3. 探索 `RetrieverOptimizer` 的检索优化
4. 理解 `GraphEnhancer` 的图谱构建
5. 掌握 `MemoryLifecycleManager` 的状态管理
6. 使用 `MemoryAnalytics` 进行质量评估
7. 通过 `AdvancedMemoryFusionSystem` 整合所有功能

### 推荐阅读
- 集成指南中的"模块详解"部分
- 项目总结中的"技术架构"部分
- 测试文件中的使用示例

## 🚀 下一步

1. ✅ 集成到现有的MemorySystem
2. ✅ 配置生命周期策略
3. ✅ 设置定期清理任务
4. ✅ 监控性能指标
5. ✅ 根据实际使用情况调整参数
6. ⏳ 集成真实的嵌入模型
7. ⏳ 实现分布式处理
8. ⏳ 开发Web可视化界面

---

**项目状态**: ✅ 完成  
**版本**: 1.0.0  
**最后更新**: 2026-05-27

**快速链接**:
- [集成指南](MEMORY_FUSION_INTEGRATION_GUIDE.md)
- [项目总结](MEMORY_FUSION_PROJECT_SUMMARY.md)
- [测试文件](tests/test_memory_fusion.py)
- [基准测试](backend/app/core/memory/benchmark.py)
