# 视频教程 2: 记忆系统深度使用 (8-10分钟)

**视频标题**: X-Agent 记忆系统 - 让你的 Agent 记住一切

**目标受众**: 中级用户、想要构建智能系统的开发者

**学习成果**:
- 理解记忆系统架构
- 存储和检索信息
- 使用向量搜索
- 实现上下文感知

---

## 脚本

### [00:00-00:30] 开场

```
欢迎回到 X-Agent 教程！

在上一个视频中，我们创建了第一个 Agent。
但那个 Agent 没有记忆 - 每次都从零开始。

在这个视频中，我们将学习如何使用记忆系统，
让你的 Agent 记住用户偏好、历史信息和学到的知识。

这将使你的 Agent 变得更加智能和有用。
```

**视觉**:
- 记忆系统概念图
- 对比演示：有记忆 vs 无记忆

---

### [00:30-02:00] 记忆系统架构

```
首先，让我们理解记忆系统的架构。

X-Agent 的记忆系统有三个层次：

1. 短期记忆 (Short-term Memory)
   - 存储当前对话的信息
   - 快速访问
   - 自动过期

2. 长期记忆 (Long-term Memory)
   - 存储重要信息
   - 持久化存储
   - 支持向量搜索

3. 工作记忆 (Working Memory)
   - 当前任务的上下文
   - 临时存储
   - 任务完成后清空

记忆系统使用：
- PostgreSQL 存储结构化数据
- Qdrant 存储向量和进行语义搜索
- 图数据库存储关系

这样设计的好处：
- 快速检索
- 语义理解
- 关系推理
```

**视觉**:
- 记忆系统架构图
- 三层记忆的对比表
- 数据流图

---

### [02:00-03:30] 基本操作：存储信息

```
现在让我们学习如何存储信息。

首先，导入必要的模块：

from backend.app.core.memory import MemoryManager
import asyncio

async def main():
    # 初始化记忆管理器
    memory = MemoryManager()
    
    # 存储简单信息
    await memory.store(
        key="user_name",
        value="Alice",
        ttl=86400  # 24 小时
    )
    
    # 存储复杂信息
    await memory.store(
        key="user_preferences",
        value={
            "theme": "dark",
            "language": "zh-CN",
            "notifications": True
        }
    )
    
    # 存储列表
    await memory.store(
        key="recent_tasks",
        value=[
            "task_1",
            "task_2",
            "task_3"
        ]
    )

asyncio.run(main())

关键参数：
- key: 唯一标识符
- value: 要存储的数据
- ttl: 生存时间（秒），可选
- metadata: 元数据，用于搜索
```

**视觉**:
- 代码编辑器
- 代码高亮
- 参数说明

---

### [03:30-05:00] 检索和搜索

```
现在让我们学习如何检索信息。

基本检索：

async def retrieve_example():
    memory = MemoryManager()
    
    # 按 key 检索
    user_name = await memory.retrieve("user_name")
    print(f"用户名: {user_name}")
    
    # 检索复杂数据
    preferences = await memory.retrieve("user_preferences")
    print(f"用户偏好: {preferences}")

语义搜索：

async def semantic_search_example():
    memory = MemoryManager()
    
    # 搜索相似的信息
    results = await memory.search(
        query="用户喜欢什么主题？",
        limit=5,
        threshold=0.7
    )
    
    for result in results:
        print(f"匹配度: {result.score}")
        print(f"内容: {result.value}")

批量检索：

async def batch_retrieve_example():
    memory = MemoryManager()
    
    # 批量检索多个 key
    keys = ["user_name", "user_preferences", "recent_tasks"]
    results = await memory.retrieve_batch(keys)
    
    for key, value in results.items():
        print(f"{key}: {value}")

这些操作的用途：
- 按 key 检索：快速访问已知信息
- 语义搜索：找到相关信息
- 批量检索：提高效率
```

**视觉**:
- 代码示例
- 搜索结果展示
- 性能对比

---

### [05:00-06:30] 实战：构建智能助手

```
现在让我们构建一个实际的智能助手。

这个助手会：
1. 记住用户信息
2. 学习用户偏好
3. 提供个性化建议

代码示例：

class SmartAssistant:
    def __init__(self):
        self.memory = MemoryManager()
        self.agent = Agent(...)
    
    async def greet_user(self, user_id):
        # 检索用户信息
        user_info = await self.memory.retrieve(
            f"user_{user_id}"
        )
        
        if user_info:
            return f"欢迎回来，{user_info['name']}！"
        else:
            return "欢迎新用户！"
    
    async def learn_preference(self, user_id, preference):
        # 存储用户偏好
        await self.memory.store(
            key=f"preference_{user_id}",
            value=preference
        )
    
    async def get_recommendation(self, user_id, query):
        # 搜索相关偏好
        preferences = await self.memory.search(
            query=query,
            metadata={"user_id": user_id}
        )
        
        # 基于偏好生成建议
        recommendation = await self.agent.execute(
            task=f"基于这些偏好生成建议: {preferences}"
        )
        
        return recommendation

# 使用示例
async def main():
    assistant = SmartAssistant()
    
    # 第一次交互
    greeting = await assistant.greet_user("user_123")
    print(greeting)
    
    # 学习偏好
    await assistant.learn_preference(
        "user_123",
        {"favorite_topic": "AI", "language": "Chinese"}
    )
    
    # 获取建议
    recommendation = await assistant.get_recommendation(
        "user_123",
        "推荐一些学习资源"
    )
    print(recommendation)

asyncio.run(main())

这个例子展示了：
- 如何存储用户信息
- 如何检索和搜索
- 如何构建上下文感知的系统
```

**视觉**:
- 完整代码示例
- 执行流程图
- 输出结果

---

### [06:30-08:00] 高级特性

```
X-Agent 记忆系统还有许多高级特性。

1. 记忆过期和清理

async def memory_lifecycle():
    memory = MemoryManager()
    
    # 设置过期时间
    await memory.store(
        key="temporary_data",
        value="some data",
        ttl=3600  # 1 小时后过期
    )
    
    # 手动删除
    await memory.delete("temporary_data")
    
    # 清理过期数据
    await memory.cleanup_expired()

2. 记忆关系和图

async def memory_relationships():
    memory = MemoryManager()
    
    # 创建关系
    await memory.create_relationship(
        from_key="user_123",
        to_key="project_456",
        relationship_type="owns"
    )
    
    # 查询关系
    related = await memory.get_related(
        key="user_123",
        relationship_type="owns"
    )

3. 记忆版本控制

async def memory_versioning():
    memory = MemoryManager()
    
    # 存储带版本的数据
    await memory.store_versioned(
        key="config",
        value={"version": "2.0"},
        version="2.0"
    )
    
    # 获取特定版本
    old_config = await memory.retrieve_version(
        key="config",
        version="1.0"
    )

4. 记忆导出和导入

async def memory_export_import():
    memory = MemoryManager()
    
    # 导出记忆
    export_data = await memory.export(
        filter={"user_id": "user_123"}
    )
    
    # 导入记忆
    await memory.import_data(export_data)

这些高级特性使你能够：
- 管理记忆生命周期
- 建立复杂的关系
- 跟踪历史变化
- 迁移和备份数据
```

**视觉**:
- 高级特性代码示例
- 功能演示
- 使用场景

---

### [08:00-09:00] 最佳实践

```
使用记忆系统的最佳实践：

1. 合理设置 TTL
   - 临时数据: 几分钟到几小时
   - 用户偏好: 几天到几个月
   - 参考数据: 永久存储

2. 使用元数据
   await memory.store(
       key="user_data",
       value=data,
       metadata={
           "user_id": "123",
           "type": "preference",
           "importance": "high"
       }
   )

3. 定期清理
   - 删除过期数据
   - 压缩存储
   - 备份重要数据

4. 监控记忆使用
   - 跟踪存储大小
   - 监控查询性能
   - 优化索引

5. 安全性考虑
   - 加密敏感数据
   - 实现访问控制
   - 审计日志
```

**视觉**:
- 最佳实践清单
- 代码示例
- 性能对比

---

### [09:00-09:45] 总结和资源

```
总结一下我们学到的内容：

✓ 记忆系统架构
✓ 基本操作（存储、检索、搜索）
✓ 实战示例
✓ 高级特性
✓ 最佳实践

记忆系统的好处：
- 让 Agent 更聪明
- 改进用户体验
- 支持复杂应用
- 提高效率

更多资源：
- 记忆系统文档: https://docs.x-agent.dev/memory
- API 参考: https://docs.x-agent.dev/api/memory
- 示例代码: https://github.com/x-agent/examples

在下一个视频中，我们将学习工具集成。
```

**视觉**:
- 学习成果检查清单
- 资源链接
- 下一个视频预告

---

## 制作建议

### 关键演示
1. 记忆系统架构图动画
2. 存储和检索的实时演示
3. 语义搜索的可视化
4. 智能助手的完整演示

### 代码高亮
- 关键代码行用不同颜色
- 参数说明用注释
- 输出结果用特殊格式

### 字幕
- 中文: 清晰的技术术语
- 英文: 准确的翻译
