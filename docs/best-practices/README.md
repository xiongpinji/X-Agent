# X-Agent 最佳实践

学习如何最大化利用 X-Agent，构建高效、可靠的自动化系统。

## 目录

1. [Agent 设计最佳实践](#agent-设计最佳实践)
2. [工作流设计最佳实践](#工作流设计最佳实践)
3. [性能优化最佳实践](#性能优化最佳实践)
4. [安全最佳实践](#安全最佳实践)
5. [成本优化最佳实践](#成本优化最佳实践)

## Agent 设计最佳实践

### 1. 明确定义 Agent 的职责

```python
# 好的实践：单一职责
class DataAnalystAgent:
    """专门用于数据分析的 Agent"""
    def __init__(self):
        self.tools = [
            "query_database",
            "analyze_data",
            "generate_report"
        ]

# 不好的实践：职责过多
class UniversalAgent:
    """什么都能做的 Agent"""
    def __init__(self):
        self.tools = [
            "query_database",
            "send_email",
            "delete_files",
            "analyze_data",
            "generate_report",
            # ... 更多工具
        ]
```

### 2. 提供清晰的系统提示词

```python
# 好的实践：具体的系统提示词
system_prompt = """
你是一个专业的数据分析师。你的职责是：

1. 理解用户的数据分析需求
2. 制定分析计划
3. 执行分析
4. 生成清晰的报告

在执行分析时，请遵循以下原则：
- 数据准确性优先
- 提供详细的分析过程
- 给出明确的结论和建议
- 如果数据不足，请说明

禁止的操作：
- 不要修改原始数据
- 不要删除任何数据
- 不要访问未授权的数据源
"""

agent.set_system_prompt(system_prompt)
```

### 3. 合理配置工具

```python
# 好的实践：只添加必要的工具
agent.add_tools([
    "query_database",
    "analyze_data",
    "generate_report"
])

# 不好的实践：添加过多工具
agent.add_tools([
    "query_database",
    "analyze_data",
    "generate_report",
    "send_email",
    "delete_files",
    "modify_config",
    # ... 更多工具
])
```

### 4. 实现适当的错误处理

```python
# 好的实践：完善的错误处理
async def execute_with_error_handling(agent, task):
    try:
        result = await agent.execute(task)
        return result
    except TimeoutError:
        logger.error(f"任务超时: {task}")
        # 重试或使用备用方案
    except ValueError as e:
        logger.error(f"输入错误: {e}")
        # 返回有用的错误信息
    except Exception as e:
        logger.error(f"未知错误: {e}")
        # 记录详细信息用于调试
```

### 5. 使用记忆系统优化性能

```python
# 好的实践：利用记忆系统缓存结果
async def analyze_with_cache(agent, query):
    # 检查缓存
    cached_result = await memory.retrieve(f"analysis_{query}")
    if cached_result:
        return cached_result
    
    # 执行分析
    result = await agent.execute(f"分析: {query}")
    
    # 缓存结果
    await memory.store(
        key=f"analysis_{query}",
        value=result,
        ttl=86400  # 24 小时
    )
    
    return result
```

## 工作流设计最佳实践

### 1. 使用清晰的节点命名

```yaml
# 好的实践：清晰的节点名称
nodes:
  - id: validate_order
    name: 验证订单信息
  - id: check_inventory
    name: 检查库存可用性
  - id: create_shipment
    name: 生成发货单

# 不好的实践：模糊的节点名称
nodes:
  - id: step1
    name: 步骤 1
  - id: step2
    name: 步骤 2
  - id: step3
    name: 步骤 3
```

### 2. 合理设置超时时间

```python
# 好的实践：根据操作复杂度设置超时
nodes = [
    WorkflowNode(
        id="quick_check",
        name="快速检查",
        timeout=10  # 10 秒
    ),
    WorkflowNode(
        id="complex_analysis",
        name="复杂分析",
        timeout=300  # 5 分钟
    ),
    WorkflowNode(
        id="external_api_call",
        name="外部 API 调用",
        timeout=60  # 1 分钟
    )
]
```

### 3. 完善的错误处理和补偿

```python
# 好的实践：为每个节点配置错误处理
workflow.add_node(WorkflowNode(
    id="create_shipment",
    name="生成发货单",
    retry_count=3,
    retry_delay=5
))

# 定义补偿操作
workflow.add_compensation(
    node_id="create_shipment",
    compensation_action="cancel_shipment"
)

# 定义错误处理
workflow.add_error_handler(
    node_id="create_shipment",
    handler_action="log_error_and_notify"
)
```

### 4. 使用条件分支优化流程

```python
# 好的实践：使用条件分支处理不同情况
workflow.add_edge(
    from_node="validate_order",
    to_node="require_approval",
    condition="amount > 10000"
)

workflow.add_edge(
    from_node="validate_order",
    to_node="process_payment",
    condition="amount <= 10000"
)
```

### 5. 并行执行提高效率

```python
# 好的实践：使用并行节点提高效率
parallel_node = WorkflowNode(
    id="parallel_processing",
    name="并行处理",
    type=NodeType.PARALLEL,
    nodes=[
        "send_email",
        "update_database",
        "log_event"
    ]
)

workflow.add_node(parallel_node)
```

## 性能优化最佳实践

### 1. 使用批量操作

```python
# 不好的实践：逐个操作
for item in items:
    await memory.store(f"item_{item.id}", item)

# 好的实践：批量操作
await memory.store_batch({
    f"item_{item.id}": item
    for item in items
})
```

### 2. 缓存频繁访问的数据

```python
# 好的实践：缓存配置和参考数据
class CachedDataManager:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600
    
    async def get_config(self, key):
        if key in self.cache:
            return self.cache[key]
        
        value = await self.fetch_from_db(key)
        self.cache[key] = value
        return value
```

### 3. 使用异步操作

```python
# 不好的实践：同步操作
for url in urls:
    result = requests.get(url)
    process(result)

# 好的实践：异步操作
import asyncio

async def fetch_all(urls):
    tasks = [fetch_url(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results
```

### 4. 优化数据库查询

```python
# 不好的实践：N+1 查询
users = await db.query("SELECT * FROM users")
for user in users:
    orders = await db.query(f"SELECT * FROM orders WHERE user_id = {user.id}")

# 好的实践：使用 JOIN
users_with_orders = await db.query("""
    SELECT u.*, o.* FROM users u
    LEFT JOIN orders o ON u.id = o.user_id
""")
```

### 5. 监控和分析性能

```python
# 好的实践：监控性能指标
from backend.app.core.monitoring import PerformanceMonitor

monitor = PerformanceMonitor()

# 记录操作时间
with monitor.measure("database_query"):
    result = await db.query("SELECT * FROM users")

# 获取性能报告
report = monitor.get_report()
print(f"平均查询时间: {report.avg_query_time}ms")
print(f"最慢查询: {report.slowest_query}ms")
```

## 安全最佳实践

### 1. 输入验证和清理

```python
# 好的实践：验证和清理输入
from pydantic import BaseModel, validator

class TaskInput(BaseModel):
    query: str
    limit: int
    
    @validator('query')
    def validate_query(cls, v):
        if len(v) > 1000:
            raise ValueError("查询过长")
        return v.strip()
    
    @validator('limit')
    def validate_limit(cls, v):
        if v < 1 or v > 1000:
            raise ValueError("limit 必须在 1-1000 之间")
        return v
```

### 2. 权限控制

```python
# 好的实践：实现权限检查
async def execute_with_permission_check(agent, task, user):
    # 检查用户权限
    if not await check_permission(user, task):
        raise PermissionError(f"用户 {user} 无权执行任务 {task}")
    
    # 执行任务
    return await agent.execute(task)
```

### 3. 敏感信息保护

```python
# 好的实践：加密敏感信息
from cryptography.fernet import Fernet

class SecureMemory:
    def __init__(self):
        self.cipher = Fernet(key)
    
    async def store_sensitive(self, key, value):
        encrypted = self.cipher.encrypt(value.encode())
        await memory.store(key, encrypted)
    
    async def retrieve_sensitive(self, key):
        encrypted = await memory.retrieve(key)
        return self.cipher.decrypt(encrypted).decode()
```

### 4. 审计日志

```python
# 好的实践：记录所有重要操作
from backend.app.core.audit import AuditLogger

audit_logger = AuditLogger()

async def execute_with_audit(agent, task, user):
    # 记录操作开始
    await audit_logger.log(
        action="agent_execute",
        user=user,
        task=task,
        timestamp=datetime.now()
    )
    
    try:
        result = await agent.execute(task)
        
        # 记录操作成功
        await audit_logger.log(
            action="agent_execute_success",
            user=user,
            task=task,
            result=result
        )
        
        return result
    except Exception as e:
        # 记录操作失败
        await audit_logger.log(
            action="agent_execute_failure",
            user=user,
            task=task,
            error=str(e)
        )
        raise
```

### 5. 安全的 API 调用

```python
# 好的实践：安全的 API 调用
import httpx

async def safe_api_call(url, params=None):
    # 验证 URL
    if not url.startswith(("http://", "https://")):
        raise ValueError("无效的 URL")
    
    # 使用超时
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API 调用失败: {e}")
            raise
```

## 成本优化最佳实践

### 1. 优化 LLM 调用

```python
# 好的实践：减少不必要的 LLM 调用
async def analyze_with_cache(query):
    # 检查缓存
    cached = await memory.retrieve(f"analysis_{query}")
    if cached:
        return cached
    
    # 只在必要时调用 LLM
    result = await llm.analyze(query)
    
    # 缓存结果
    await memory.store(f"analysis_{query}", result)
    return result
```

### 2. 使用更便宜的模型

```python
# 好的实践：根据任务复杂度选择模型
from backend.app.core.llm import LLMRouter

llm_router = LLMRouter()

# 简单任务使用便宜的模型
simple_result = await llm_router.route(
    task="简单分类",
    model="gpt-3.5-turbo"
)

# 复杂任务使用高级模型
complex_result = await llm_router.route(
    task="复杂分析",
    model="gpt-4"
)
```

### 3. 批量处理

```python
# 好的实践：批量处理任务
async def process_batch(items):
    # 分批处理
    batch_size = 100
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        results = await asyncio.gather(*[
            process_item(item) for item in batch
        ])
        yield results
```

### 4. 监控成本

```python
# 好的实践：监控 LLM 成本
class CostMonitor:
    def __init__(self):
        self.total_cost = 0
        self.call_count = 0
    
    async def track_llm_call(self, model, tokens):
        cost = self.calculate_cost(model, tokens)
        self.total_cost += cost
        self.call_count += 1
        
        if self.total_cost > self.budget:
            logger.warning(f"成本超预算: {self.total_cost}")
    
    def calculate_cost(self, model, tokens):
        # 根据模型和 token 数计算成本
        rates = {
            "gpt-3.5-turbo": 0.0005,
            "gpt-4": 0.03
        }
        return tokens * rates.get(model, 0)
```

## 总结

遵循这些最佳实践可以帮助你：

- 构建更可靠的自动化系统
- 提高系统性能和效率
- 增强系统安全性
- 降低运营成本
- 改善用户体验

## 下一步

- 阅读 [故障排除](../troubleshooting/COMMON_ISSUES.md)
- 阅读 [FAQ](../faq/README.md)
- 探索 [示例代码库](../../examples/)
