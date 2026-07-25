# X-Agent 最佳实践指南

**版本**: 1.0  
**最后更新**: 2026-05-29  
**适用范围**: 所有开发者和架构师

---

## 目录

1. [Agent设计最佳实践](#agent设计最佳实践)
2. [工作流编排最佳实践](#工作流编排最佳实践)
3. [内存系统最佳实践](#内存系统最佳实践)
4. [性能优化最佳实践](#性能优化最佳实践)
5. [安全最佳实践](#安全最佳实践)
6. [可靠性最佳实践](#可靠性最佳实践)
7. [可观测性最佳实践](#可观测性最佳实践)

---

## Agent设计最佳实践

### 1. 系统提示词设计

**原则**: 清晰、具体、可验证

```python
# 好的系统提示词
SYSTEM_PROMPT = """
你是一个数据分析专家。你的职责是：
1. 分析提供的数据集
2. 识别关键趋势和异常
3. 生成可操作的见解

约束条件：
- 只使用提供的数据
- 明确说明假设
- 提供置信度评分
- 建议进一步分析

输出格式：
- 摘要 (2-3句)
- 关键发现 (3-5项)
- 建议 (2-3项)
"""

# 避免的做法
BAD_PROMPT = "分析数据"  # 太模糊
```

### 2. 工具选择和配置

```python
# 好的工具配置
agent = Agent(
    name="DataAnalyzer",
    model="claude-3-opus",
    tools=[
        "data_analyzer",      # 核心工具
        "visualizer",         # 可视化
        "database_query"      # 数据访问
    ],
    max_iterations=10,        # 合理的迭代限制
    timeout=300,              # 5分钟超时
    memory_enabled=True,      # 启用记忆
    temperature=0.7           # 平衡创意和准确性
)

# 避免的做法
# - 工具过多 (>10个)
# - 没有超时限制
# - 温度设置不当
```

### 3. 错误处理和恢复

```python
# 好的错误处理
try:
    result = agent.execute(task)
except AgentTimeoutError:
    logger.warning(f"Agent timeout for task {task.id}")
    # 降级处理
    result = fallback_handler(task)
except AgentError as e:
    logger.error(f"Agent error: {e}")
    # 记录错误并通知
    notify_admin(e)
    raise
```

### 4. Agent生命周期管理

```python
# 好的生命周期管理
async def run_agent_safely(agent, task):
    # 初始化
    agent.initialize()
    
    try:
        # 执行
        result = await agent.execute(task)
        
        # 验证
        if not validate_result(result):
            raise ValueError("Invalid result")
        
        return result
    finally:
        # 清理
        agent.cleanup()
```

---

## 工作流编排最佳实践

### 1. 工作流设计原则

```python
# 好的工作流设计
workflow = {
    "name": "DataProcessingPipeline",
    "description": "Process and analyze data",
    "steps": [
        {
            "id": "validate",
            "type": "agent",
            "config": {
                "prompt": "Validate input data",
                "tools": ["validator"]
            },
            "timeout": 60,
            "retry": {"max_attempts": 3, "backoff": "exponential"}
        },
        {
            "id": "process",
            "type": "agent",
            "depends_on": ["validate"],
            "config": {
                "prompt": "Process validated data",
                "tools": ["processor"]
            }
        },
        {
            "id": "analyze",
            "type": "agent",
            "depends_on": ["process"],
            "config": {
                "prompt": "Analyze processed data",
                "tools": ["analyzer"]
            }
        }
    ],
    "error_handling": {
        "strategy": "fail_fast",  # 或 "continue"
        "notifications": ["admin@example.com"]
    }
}

# 避免的做法
# - 步骤过多 (>20个)
# - 没有依赖关系
# - 没有超时设置
# - 没有错误处理
```

### 2. 条件分支和循环

```python
# 好的条件分支
workflow = {
    "steps": [
        {
            "id": "check_data",
            "type": "agent",
            "config": {"prompt": "Check if data is valid"}
        },
        {
            "id": "process_valid",
            "type": "agent",
            "condition": "check_data.output.is_valid == true",
            "config": {"prompt": "Process valid data"}
        },
        {
            "id": "handle_invalid",
            "type": "agent",
            "condition": "check_data.output.is_valid == false",
            "config": {"prompt": "Handle invalid data"}
        }
    ]
}

# 避免的做法
# - 深层嵌套条件
# - 复杂的条件表达式
# - 没有默认分支
```

### 3. 工作流监控和日志

```python
# 好的监控配置
workflow_config = {
    "monitoring": {
        "enabled": True,
        "metrics": [
            "execution_time",
            "success_rate",
            "error_rate"
        ],
        "alerts": [
            {
                "condition": "error_rate > 0.1",
                "action": "notify_admin"
            }
        ]
    },
    "logging": {
        "level": "INFO",
        "format": "json",
        "destinations": ["stdout", "file", "cloudwatch"]
    }
}
```

---

## 内存系统最佳实践

### 1. 内存存储策略

```python
# 好的内存存储
memory_config = {
    "structured": {
        "backend": "postgresql",
        "retention": "90d",
        "indexing": ["user_id", "timestamp"]
    },
    "vector": {
        "backend": "qdrant",
        "embedding_model": "text-embedding-3-small",
        "similarity_threshold": 0.7,
        "retention": "180d"
    },
    "cache": {
        "backend": "redis",
        "ttl": "1h",
        "max_size": "1GB"
    }
}

# 避免的做法
# - 所有数据都存储在内存中
# - 没有过期策略
# - 没有分层存储
```

### 2. 内存查询优化

```python
# 好的内存查询
async def retrieve_context(query, user_id):
    # 1. 快速缓存查询
    cached = await cache.get(f"context:{query}")
    if cached:
        return cached
    
    # 2. 结构化查询 (精确匹配)
    structured = await db.query(
        "SELECT * FROM memory WHERE user_id = %s AND type = %s",
        [user_id, "fact"]
    )
    
    # 3. 向量查询 (语义相似)
    vector_results = await vector_db.search(
        query_embedding,
        limit=5,
        filter={"user_id": user_id}
    )
    
    # 4. 合并和排序
    combined = merge_and_rank(structured, vector_results)
    
    # 5. 缓存结果
    await cache.set(f"context:{query}", combined, ttl=3600)
    
    return combined

# 避免的做法
# - 每次都进行完整扫描
# - 没有缓存
# - 没有结果排序
```

### 3. 内存去重和压缩

```python
# 好的内存管理
async def consolidate_memory():
    # 1. 识别重复
    duplicates = await find_duplicates()
    
    # 2. 合并相似内容
    for group in duplicates:
        merged = merge_memories(group)
        await memory.update(merged)
        await memory.delete_batch([m.id for m in group[1:]])
    
    # 3. 压缩旧数据
    old_memories = await memory.query(
        "SELECT * FROM memory WHERE created_at < NOW() - INTERVAL '30 days'"
    )
    for memory_item in old_memories:
        compressed = compress_memory(memory_item)
        await memory.update(compressed)
    
    # 4. 清理过期数据
    await memory.delete_batch(
        "SELECT id FROM memory WHERE created_at < NOW() - INTERVAL '180 days'"
    )
```

---

## 性能优化最佳实践

### 1. 查询优化

```python
# 好的查询优化
# 1. 使用索引
CREATE INDEX idx_user_timestamp ON memory(user_id, created_at DESC);

# 2. 分页查询
async def get_memories_paginated(user_id, page=1, limit=20):
    offset = (page - 1) * limit
    return await db.query(
        "SELECT * FROM memory WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        [user_id, limit, offset]
    )

# 3. 选择性字段
SELECT id, content, created_at FROM memory  # 不要 SELECT *

# 避免的做法
# - 没有索引的查询
# - 一次加载所有数据
# - 选择不需要的字段
```

### 2. 缓存策略

```python
# 好的缓存策略
class CacheManager:
    def __init__(self):
        self.cache = {}
        self.ttl = {}
    
    async def get_or_compute(self, key, compute_fn, ttl=3600):
        # 检查缓存
        if key in self.cache:
            if time.time() < self.ttl.get(key, 0):
                return self.cache[key]
            else:
                del self.cache[key]
        
        # 计算值
        value = await compute_fn()
        
        # 存储缓存
        self.cache[key] = value
        self.ttl[key] = time.time() + ttl
        
        return value

# 缓存策略
CACHE_STRATEGIES = {
    "hot_data": {"ttl": 300, "size": "100MB"},      # 5分钟
    "warm_data": {"ttl": 3600, "size": "500MB"},    # 1小时
    "cold_data": {"ttl": 86400, "size": "1GB"}      # 1天
}
```

### 3. 异步处理

```python
# 好的异步处理
async def process_workflow_async(workflow_id):
    # 1. 快速响应
    task = asyncio.create_task(
        execute_workflow_background(workflow_id)
    )
    
    # 2. 返回任务ID
    return {"task_id": task.id, "status": "queued"}

# 3. 后台处理
async def execute_workflow_background(workflow_id):
    try:
        result = await execute_workflow(workflow_id)
        await store_result(workflow_id, result)
    except Exception as e:
        await handle_error(workflow_id, e)

# 避免的做法
# - 同步处理长时间操作
# - 没有超时
# - 没有错误处理
```

---

## 安全最佳实践

### 1. 输入验证

```python
# 好的输入验证
from pydantic import BaseModel, validator

class WorkflowInput(BaseModel):
    name: str
    description: str
    steps: list
    
    @validator('name')
    def name_not_empty(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('steps')
    def steps_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one step required')
        return v

# 使用验证
try:
    workflow = WorkflowInput(**input_data)
except ValidationError as e:
    logger.error(f"Validation error: {e}")
    raise
```

### 2. 权限控制

```python
# 好的权限控制
from functools import wraps

def require_permission(permission):
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.has_permission(permission):
                raise PermissionDenied(f"Missing permission: {permission}")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# 使用
@require_permission("workflow.execute")
async def execute_workflow(request, workflow_id):
    # 执行工作流
    pass
```

### 3. 数据加密

```python
# 好的数据加密
from cryptography.fernet import Fernet

class EncryptedField:
    def __init__(self, key):
        self.cipher = Fernet(key)
    
    def encrypt(self, value):
        return self.cipher.encrypt(value.encode())
    
    def decrypt(self, encrypted_value):
        return self.cipher.decrypt(encrypted_value).decode()

# 使用
encrypted_field = EncryptedField(os.getenv("ENCRYPTION_KEY"))
encrypted_api_key = encrypted_field.encrypt(api_key)
```

---

## 可靠性最佳实践

### 1. 重试策略

```python
# 好的重试策略
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_external_api(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status >= 500:
                raise Exception(f"Server error: {response.status}")
            return await response.json()

# 避免的做法
# - 无限重试
# - 固定延迟
# - 没有指数退避
```

### 2. 超时管理

```python
# 好的超时管理
async def execute_with_timeout(coro, timeout=30):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout}s")
        raise

# 使用
try:
    result = await execute_with_timeout(
        agent.execute(task),
        timeout=300
    )
except asyncio.TimeoutError:
    # 处理超时
    pass
```

### 3. 熔断器模式

```python
# 好的熔断器实现
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failure_count = 0
        self.state = "closed"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
```

---

## 可观测性最佳实践

### 1. 结构化日志

```python
# 好的结构化日志
import structlog

logger = structlog.get_logger()

# 使用
logger.info(
    "workflow_executed",
    workflow_id="wf_123",
    status="completed",
    duration_ms=1234,
    steps_completed=5,
    user_id="user_456"
)

# 避免的做法
logger.info(f"Workflow {workflow_id} completed in {duration}ms")  # 非结构化
```

### 2. 分布式追踪

```python
# 好的分布式追踪
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def execute_workflow(workflow_id):
    with tracer.start_as_current_span("execute_workflow") as span:
        span.set_attribute("workflow_id", workflow_id)
        
        with tracer.start_as_current_span("validate") as validate_span:
            # 验证逻辑
            pass
        
        with tracer.start_as_current_span("execute") as execute_span:
            # 执行逻辑
            pass
```

### 3. 指标收集

```python
# 好的指标收集
from prometheus_client import Counter, Histogram

workflow_executions = Counter(
    'workflow_executions_total',
    'Total workflow executions',
    ['status']
)

workflow_duration = Histogram(
    'workflow_duration_seconds',
    'Workflow execution duration',
    buckets=[1, 5, 10, 30, 60, 300]
)

# 使用
with workflow_duration.time():
    result = await execute_workflow(workflow_id)
    workflow_executions.labels(status=result.status).inc()
```

---

## 总结

遵循这些最佳实践可以帮助你：

✓ 构建更可靠的Agent系统  
✓ 设计更高效的工作流  
✓ 优化系统性能  
✓ 增强安全性  
✓ 改进可观测性  
✓ 提高代码质量  

---

**文档版本**: 1.0  
**最后更新**: 2026-05-29  
**维护者**: X-Agent技术团队
