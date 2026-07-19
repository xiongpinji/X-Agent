# X-Agent 高级功能指南

完整的高级功能使用指南，帮助开发者构建复杂的自动化系统。

---

## 目录

1. [记忆系统深度使用](#记忆系统深度使用)
2. [自定义工作流设计](#自定义工作流设计)
3. [多 Agent 协作模式](#多-agent-协作模式)
4. [性能调优技巧](#性能调优技巧)
5. [安全最佳实践](#安全最佳实践)

---

## 记忆系统深度使用

### 1. 记忆架构详解

X-Agent 的记忆系统采用三层架构：

```
┌─────────────────────────────────────────┐
│         应用层 (Application Layer)       │
│  Agent、Workflow、Tool 使用记忆          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         记忆管理层 (Memory Manager)      │
│  存储、检索、搜索、版本控制              │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│         存储层 (Storage Layer)           │
│  PostgreSQL、Qdrant、Redis               │
└─────────────────────────────────────────┘
```

### 2. 高级存储策略

#### 分层存储

```python
from backend.app.core.memory import MemoryManager, MemoryTier

async def hierarchical_storage():
    memory = MemoryManager()
    
    # 热数据：Redis（快速访问）
    await memory.store(
        key="current_user_session",
        value=session_data,
        tier=MemoryTier.HOT,
        ttl=3600
    )
    
    # 温数据：PostgreSQL（常规访问）
    await memory.store(
        key="user_preferences",
        value=preferences,
        tier=MemoryTier.WARM,
        ttl=86400 * 30  # 30 天
    )
    
    # 冷数据：Qdrant（归档）
    await memory.store(
        key="historical_data",
        value=archive_data,
        tier=MemoryTier.COLD,
        ttl=None  # 永久存储
    )
```

#### 智能缓存

```python
class SmartCache:
    def __init__(self):
        self.memory = MemoryManager()
        self.access_count = {}
    
    async def get_with_cache(self, key, fetch_fn):
        # 尝试从缓存获取
        cached = await self.memory.retrieve(key)
        if cached:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return cached
        
        # 获取新数据
        data = await fetch_fn()
        
        # 根据访问频率决定缓存时间
        access_count = self.access_count.get(key, 0)
        if access_count > 10:
            ttl = 86400  # 24 小时
        elif access_count > 5:
            ttl = 3600   # 1 小时
        else:
            ttl = 600    # 10 分钟
        
        await self.memory.store(key, data, ttl=ttl)
        return data
```

### 3. 向量搜索优化

```python
async def advanced_vector_search():
    memory = MemoryManager()
    
    # 语义搜索
    results = await memory.search(
        query="用户喜欢什么产品？",
        limit=10,
        threshold=0.7,
        filters={
            "user_id": "user_123",
            "type": "preference"
        }
    )
    
    # 混合搜索（关键词 + 语义）
    hybrid_results = await memory.hybrid_search(
        query="AI 工具",
        keyword_weight=0.3,
        semantic_weight=0.7,
        limit=20
    )
    
    # 相似度排序
    sorted_results = sorted(
        results,
        key=lambda x: x.similarity_score,
        reverse=True
    )
    
    return sorted_results
```

### 4. 记忆关系图

```python
async def memory_relationships():
    memory = MemoryManager()
    
    # 创建关系
    await memory.create_relationship(
        from_key="user_123",
        to_key="project_456",
        relationship_type="owns",
        metadata={"created_at": "2024-01-01"}
    )
    
    # 查询关系
    owned_projects = await memory.get_related(
        key="user_123",
        relationship_type="owns",
        direction="outgoing"
    )
    
    # 路径查询
    paths = await memory.find_paths(
        from_key="user_123",
        to_key="task_789",
        max_depth=3
    )
    
    # 关系统计
    stats = await memory.relationship_stats(
        key="user_123"
    )
    print(f"关系数: {stats.total_relationships}")
    print(f"关系类型: {stats.relationship_types}")
```

### 5. 记忆版本控制

```python
async def memory_versioning():
    memory = MemoryManager()
    
    # 存储带版本的数据
    await memory.store_versioned(
        key="config",
        value={"version": "2.0", "features": ["A", "B"]},
        version="2.0",
        metadata={"author": "admin", "reason": "新功能"}
    )
    
    # 获取特定版本
    old_config = await memory.retrieve_version(
        key="config",
        version="1.0"
    )
    
    # 版本历史
    history = await memory.get_version_history(key="config")
    for version in history:
        print(f"版本 {version.version}: {version.timestamp}")
    
    # 版本对比
    diff = await memory.compare_versions(
        key="config",
        version1="1.0",
        version2="2.0"
    )
    print(f"变更: {diff}")
    
    # 回滚到特定版本
    await memory.rollback_to_version(
        key="config",
        version="1.0"
    )
```

---

## 自定义工作流设计

### 1. 工作流模式

#### 顺序模式

```python
async def sequential_workflow():
    workflow = Workflow(name="Sequential")
    
    # 节点按顺序执行
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    workflow.add_edge("step3", "step4")
```

#### 并行模式

```python
async def parallel_workflow():
    workflow = Workflow(name="Parallel")
    
    # 多个节点并行执行
    parallel_node = WorkflowNode(
        id="parallel_tasks",
        type=NodeType.PARALLEL,
        nodes=["task_a", "task_b", "task_c"]
    )
    
    workflow.add_node(parallel_node)
    workflow.add_edge("start", "parallel_tasks")
    workflow.add_edge("parallel_tasks", "end")
```

#### 条件分支模式

```python
async def conditional_workflow():
    workflow = Workflow(name="Conditional")
    
    # 根据条件选择不同路径
    workflow.add_edge(
        from_node="check_status",
        to_node="process_success",
        condition="status == 'success'"
    )
    
    workflow.add_edge(
        from_node="check_status",
        to_node="handle_error",
        condition="status == 'error'"
    )
    
    workflow.add_edge(
        from_node="check_status",
        to_node="retry",
        condition="status == 'retry'"
    )
```

#### 循环模式

```python
async def loop_workflow():
    workflow = Workflow(name="Loop")
    
    # 循环执行
    loop_node = WorkflowNode(
        id="loop_task",
        type=NodeType.LOOP,
        condition="count < 10",
        body="process_item"
    )
    
    workflow.add_node(loop_node)
```

### 2. 动态工作流

```python
class DynamicWorkflow:
    def __init__(self):
        self.workflow = Workflow(name="Dynamic")
    
    async def add_conditional_branch(self, condition, action):
        """动态添加条件分支"""
        node = WorkflowNode(
            id=f"branch_{len(self.workflow.nodes)}",
            action=action
        )
        self.workflow.add_node(node)
        
        # 添加条件边
        self.workflow.add_edge(
            from_node="decision",
            to_node=node.id,
            condition=condition
        )
    
    async def add_parallel_tasks(self, tasks):
        """动态添加并行任务"""
        parallel_node = WorkflowNode(
            id="dynamic_parallel",
            type=NodeType.PARALLEL,
            nodes=tasks
        )
        self.workflow.add_node(parallel_node)
    
    async def execute_with_context(self, context):
        """使用上下文执行工作流"""
        return await self.workflow.execute(
            input_data=context
        )
```

### 3. 工作流优化

```python
class WorkflowOptimizer:
    @staticmethod
    async def optimize_workflow(workflow):
        """优化工作流性能"""
        
        # 1. 识别可并行化的节点
        parallelizable = WorkflowOptimizer.find_parallelizable_nodes(
            workflow
        )
        
        # 2. 合并相邻节点
        merged = WorkflowOptimizer.merge_adjacent_nodes(workflow)
        
        # 3. 添加缓存
        cached = WorkflowOptimizer.add_caching(merged)
        
        # 4. 优化数据流
        optimized = WorkflowOptimizer.optimize_data_flow(cached)
        
        return optimized
    
    @staticmethod
    def find_parallelizable_nodes(workflow):
        """找出可以并行执行的节点"""
        parallelizable = []
        
        for node in workflow.nodes:
            # 检查节点是否有依赖
            dependencies = workflow.get_dependencies(node.id)
            if len(dependencies) == 0:
                parallelizable.append(node)
        
        return parallelizable
```

---

## 多 Agent 协作模式

### 1. 协作架构

```python
class CollaborationFramework:
    def __init__(self):
        self.agents = {}
        self.message_queue = asyncio.Queue()
        self.shared_memory = MemoryManager()
    
    async def register_agent(self, agent):
        """注册 Agent"""
        self.agents[agent.name] = agent
        agent.set_message_handler(self.handle_message)
    
    async def handle_message(self, message):
        """处理 Agent 间的消息"""
        await self.message_queue.put(message)
        
        # 路由消息到目标 Agent
        target_agent = self.agents.get(message.target)
        if target_agent:
            await target_agent.receive_message(message)
    
    async def execute_collaborative_task(self, task, agents):
        """执行协作任务"""
        results = {}
        
        for agent_name in agents:
            agent = self.agents[agent_name]
            result = await agent.execute(task)
            results[agent_name] = result
        
        return results
```

### 2. 任务委派

```python
class TaskDelegator:
    def __init__(self, agents):
        self.agents = agents
        self.capability_index = self.build_capability_index()
    
    def build_capability_index(self):
        """构建能力索引"""
        index = {}
        for agent in self.agents:
            for capability in agent.capabilities:
                if capability not in index:
                    index[capability] = []
                index[capability].append(agent)
        return index
    
    async def delegate_task(self, task):
        """根据能力委派任务"""
        required_capabilities = self.extract_capabilities(task)
        
        # 找出最合适的 Agent
        best_agent = self.find_best_agent(required_capabilities)
        
        if best_agent:
            return await best_agent.execute(task)
        else:
            raise ValueError("没有合适的 Agent 来执行此任务")
    
    def find_best_agent(self, capabilities):
        """找出最合适的 Agent"""
        candidates = []
        
        for capability in capabilities:
            agents = self.capability_index.get(capability, [])
            candidates.extend(agents)
        
        # 选择能力最匹配的 Agent
        best_agent = max(
            candidates,
            key=lambda a: len(set(a.capabilities) & set(capabilities))
        )
        
        return best_agent
```

### 3. 结果聚合

```python
class ResultAggregator:
    @staticmethod
    async def aggregate_results(results, strategy="merge"):
        """聚合多个 Agent 的结果"""
        
        if strategy == "merge":
            return ResultAggregator.merge_results(results)
        elif strategy == "vote":
            return ResultAggregator.vote_results(results)
        elif strategy == "consensus":
            return ResultAggregator.consensus_results(results)
        else:
            raise ValueError(f"未知的聚合策略: {strategy}")
    
    @staticmethod
    def merge_results(results):
        """合并结果"""
        merged = {}
        for agent_name, result in results.items():
            merged[agent_name] = result
        return merged
    
    @staticmethod
    def vote_results(results):
        """投票选择最佳结果"""
        from collections import Counter
        
        votes = Counter(results.values())
        best_result = votes.most_common(1)[0][0]
        return best_result
    
    @staticmethod
    def consensus_results(results):
        """达成共识"""
        # 检查所有结果是否一致
        unique_results = set(results.values())
        
        if len(unique_results) == 1:
            return list(unique_results)[0]
        else:
            # 需要进一步协商
            return None
```

---

## 性能调优技巧

### 1. 缓存策略

```python
class CacheStrategy:
    @staticmethod
    async def implement_multi_level_cache():
        """多级缓存策略"""
        
        # L1: 内存缓存（最快）
        l1_cache = {}
        
        # L2: Redis 缓存（快）
        l2_cache = RedisCache()
        
        # L3: 数据库缓存（慢）
        l3_cache = DatabaseCache()
        
        async def get_with_cache(key):
            # 尝试 L1
            if key in l1_cache:
                return l1_cache[key]
            
            # 尝试 L2
            value = await l2_cache.get(key)
            if value:
                l1_cache[key] = value
                return value
            
            # 尝试 L3
            value = await l3_cache.get(key)
            if value:
                l2_cache.set(key, value)
                l1_cache[key] = value
                return value
            
            return None
        
        return get_with_cache
```

### 2. 批量操作

```python
class BatchProcessor:
    def __init__(self, batch_size=100, timeout=5):
        self.batch_size = batch_size
        self.timeout = timeout
        self.queue = []
        self.timer = None
    
    async def add_item(self, item):
        """添加项目到批处理队列"""
        self.queue.append(item)
        
        if len(self.queue) >= self.batch_size:
            await self.process_batch()
        else:
            self.start_timer()
    
    async def process_batch(self):
        """处理批次"""
        if not self.queue:
            return
        
        batch = self.queue[:self.batch_size]
        self.queue = self.queue[self.batch_size:]
        
        # 批量处理
        results = await self.batch_operation(batch)
        return results
    
    def start_timer(self):
        """启动超时计时器"""
        if self.timer:
            self.timer.cancel()
        
        self.timer = asyncio.Timer(
            self.timeout,
            lambda: asyncio.create_task(self.process_batch())
        )
```

### 3. 异步优化

```python
class AsyncOptimizer:
    @staticmethod
    async def parallel_execution(tasks):
        """并行执行任务"""
        results = await asyncio.gather(*tasks)
        return results
    
    @staticmethod
    async def concurrent_execution(tasks, max_concurrent=10):
        """并发执行任务（限制并发数）"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_task(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(*[
            bounded_task(task) for task in tasks
        ])
        return results
    
    @staticmethod
    async def streaming_execution(tasks, chunk_size=10):
        """流式执行任务"""
        results = []
        
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            chunk_results = await asyncio.gather(*chunk)
            results.extend(chunk_results)
            
            # 允许其他任务运行
            await asyncio.sleep(0)
        
        return results
```

---

## 安全最佳实践

### 1. 输入验证

```python
from pydantic import BaseModel, validator, Field

class SecureTaskInput(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=100)
    query: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., regex=r"^[a-zA-Z0-9_-]+$")
    
    @validator('task_id')
    def validate_task_id(cls, v):
        # 检查 SQL 注入
        if any(char in v for char in [';', '--', '/*', '*/']):
            raise ValueError("无效的任务 ID")
        return v
    
    @validator('query')
    def validate_query(cls, v):
        # 检查恶意内容
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE']
        if any(keyword in v.upper() for keyword in dangerous_keywords):
            raise ValueError("查询包含危险关键字")
        return v
```

### 2. 权限控制

```python
class PermissionManager:
    def __init__(self):
        self.permissions = {}
    
    async def check_permission(self, user, action, resource):
        """检查权限"""
        user_permissions = self.permissions.get(user, {})
        
        if action not in user_permissions:
            return False
        
        allowed_resources = user_permissions[action]
        return resource in allowed_resources
    
    async def grant_permission(self, user, action, resource):
        """授予权限"""
        if user not in self.permissions:
            self.permissions[user] = {}
        
        if action not in self.permissions[user]:
            self.permissions[user][action] = set()
        
        self.permissions[user][action].add(resource)
    
    async def revoke_permission(self, user, action, resource):
        """撤销权限"""
        if user in self.permissions:
            if action in self.permissions[user]:
                self.permissions[user][action].discard(resource)
```

### 3. 审计日志

```python
class AuditLogger:
    def __init__(self):
        self.logs = []
    
    async def log_action(self, action, user, resource, result):
        """记录操作"""
        log_entry = {
            "timestamp": datetime.now(),
            "action": action,
            "user": user,
            "resource": resource,
            "result": result,
            "ip_address": get_client_ip(),
            "user_agent": get_user_agent()
        }
        
        self.logs.append(log_entry)
        
        # 持久化到数据库
        await self.persist_log(log_entry)
    
    async def get_audit_trail(self, user, start_date, end_date):
        """获取审计跟踪"""
        return [
            log for log in self.logs
            if log['user'] == user
            and start_date <= log['timestamp'] <= end_date
        ]
```

---

## 总结

这个高级功能指南涵盖了：

- 记忆系统的深度使用和优化
- 自定义工作流设计模式
- 多 Agent 协作框架
- 性能调优技巧
- 安全最佳实践

通过掌握这些高级功能，你可以构建更加强大、高效和安全的 X-Agent 系统。

---

## 下一步

- 查看 [案例研究](../case-studies/) 了解实际应用
- 阅读 [API 参考](../api/) 获取详细文档
- 加入 [社区](https://community.x-agent.dev) 获取支持
