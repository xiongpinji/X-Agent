# X-Agent 性能优化实施指南

**版本**: 1.0  
**日期**: 2026-05-27  
**作者**: X-Agent性能优化团队

---

## 目录

1. [快速开始](#快速开始)
2. [分阶段实施](#分阶段实施)
3. [集成指南](#集成指南)
4. [验证清单](#验证清单)
5. [故障排除](#故障排除)
6. [性能监控](#性能监控)

---

## 快速开始

### 前置条件

- Python 3.11+
- PostgreSQL 12+
- Redis 6.0+ (可选，用于L2缓存)
- asyncpg >= 0.29.0
- FastAPI >= 0.115.0

### 安装依赖

```bash
# 已包含在pyproject.toml中
pip install -e ".[prod]"
```

### 基本配置

```python
# backend/app/dependencies.py
from backend.app.core.cache_manager import CacheManager
from backend.app.core.performance_optimizer import PerformanceMonitor

# 初始化缓存管理器
cache_manager = CacheManager(
    redis_client=redis_client,  # 可选
    memory_cache_size=1000
)

# 初始化性能监控
performance_monitor = PerformanceMonitor(window_size=1000)
```

---

## 分阶段实施

### 第一阶段: 数据库优化 (第1-2周)

#### 1.1 应用索引

```bash
# 连接到PostgreSQL
psql -U postgres -d xagent_db -f backend/migrations/performance_indexes.sql

# 验证索引创建
psql -U postgres -d xagent_db -c "SELECT indexname FROM pg_indexes WHERE tablename='memories';"
```

#### 1.2 优化查询

修改 `backend/app/api/runs.py`:

```python
# 之前
@router.get("", response_model=list[AgentRunRecord])
async def list_runs(
    run_store: RunStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
) -> list[AgentRunRecord]:
    items = run_store.list(limit=limit)
    items = [item for item in items if item.tenant_id == principal.tenant_id]
    if status:
        items = [item for item in items if item.status.value == status]
    return items

# 之后
@router.get("", response_model=list[AgentRunRecord])
async def list_runs(
    run_store: RunStoreDependency,
    principal: PrincipalDependency,
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
) -> list[AgentRunRecord]:
    filters = {
        'tenant_id': principal.tenant_id,
        'limit': limit
    }
    if status:
        filters['status'] = status
    return await run_store.list_filtered(**filters)
```

#### 1.3 配置连接池

修改 `backend/app/dependencies.py`:

```python
import asyncpg

async def get_db_pool():
    pool = await asyncpg.create_pool(
        database_url,
        min_size=10,
        max_size=50,
        max_queries=50000,
        max_cached_statement_lifetime=300,
        max_cacheable_statement_size=15000,
        command_timeout=60,
    )
    return pool
```

#### 1.4 验证改进

```bash
# 运行性能测试
pytest tests/performance/benchmarks.py::PerformanceBenchmarks::test_database_query_time -v

# 预期结果: <50ms
```

---

### 第二阶段: 缓存系统 (第3-4周)

#### 2.1 集成缓存管理器

修改 `backend/app/dependencies.py`:

```python
from backend.app.core.cache_manager import CacheManager, CacheWarmer

# 初始化缓存
cache_manager = CacheManager(
    redis_client=redis_client,
    memory_cache_size=1000
)

# 初始化缓存预热
cache_warmer = CacheWarmer(cache_manager, memory_system)

# 应用启动时预热缓存
@app.on_event("startup")
async def startup_event():
    await cache_warmer.warm_up()
```

#### 2.2 在API中使用缓存

```python
# backend/app/api/memory.py
from backend.app.core.cache_manager import cache_key

@router.get("/search")
async def search_memory(
    query: str,
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    # 生成缓存键
    key = cache_key("memory", "search", query)
    
    # 检查缓存
    if cached := await cache_manager.get(key):
        return cached
    
    # 执行搜索
    results = await memory_system.search(query)
    
    # 缓存结果
    await cache_manager.set(key, results, ttl=3600)
    
    return results
```

#### 2.3 验证缓存性能

```bash
# 运行缓存性能测试
pytest tests/performance/benchmarks.py::PerformanceBenchmarks::test_cache_hit_performance -v

# 预期结果: <5ms (缓存命中)
```

---

### 第三阶段: LLM优化 (第5-6周)

#### 3.1 集成LLM优化器

修改 `backend/app/core/agent.py`:

```python
from backend.app.core.performance_optimizer import LLMOptimizer

class AgentLoop:
    def __init__(self, ...):
        ...
        self.llm_optimizer = LLMOptimizer(self.llm, cache_manager)
    
    async def _call_llm(self, request):
        # 优化提示词
        optimized_prompt = self.llm_optimizer.optimize_prompt(request['prompt'])
        request['prompt'] = optimized_prompt
        
        # 使用缓存调用
        return await self.llm_optimizer.call_with_cache(request)
```

#### 3.2 实现批处理

```python
# 批量处理多个LLM请求
requests = [
    {'prompt': 'Request 1', 'model': 'gpt-4'},
    {'prompt': 'Request 2', 'model': 'gpt-4'},
    {'prompt': 'Request 3', 'model': 'gpt-4'},
]

responses = await llm_optimizer.batch_requests(requests, batch_size=5)
```

#### 3.3 验证LLM优化

```bash
# 运行LLM性能测试
pytest tests/performance/benchmarks.py -k "llm" -v

# 预期结果: 缓存命中 <100ms, 新请求 <2s
```

---

### 第四阶段: 异步优化 (第7-8周)

#### 4.1 优化workflow_worker

修改 `backend/app/workflow_worker.py`:

```python
from backend.app.core.performance_optimizer import AsyncOptimizer

async def run_once(
    scheduler: WorkflowScheduler | None = None,
    audit_store: AuditStore | None = None,
    limit: int = 20,
    worker_id: str = "workflow-worker",
    lease_seconds: int = 60,
) -> list[WorkflowScheduleRecord]:
    scheduler = scheduler or get_workflow_scheduler()
    audit_store = audit_store or get_audit_store()
    
    # 并发获取和处理记录
    records = await scheduler.run_due(
        limit=limit,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
    )
    
    # 并发审计
    async_optimizer = AsyncOptimizer(max_workers=10)
    await async_optimizer.run_concurrent(
        [lambda r=record: audit_triggered_records(audit_store, [r]) for record in records],
        max_concurrent=5
    )
    
    return records
```

#### 4.2 添加超时管理

```python
from backend.app.core.performance_optimizer import AsyncOptimizer

async_optimizer = AsyncOptimizer()

# 带超时的执行
try:
    result = await async_optimizer.run_with_timeout(
        some_coroutine(),
        timeout=30.0
    )
except TimeoutError:
    logger.error("Operation timed out")
```

#### 4.3 验证异步性能

```bash
# 运行并发性能测试
pytest tests/performance/benchmarks.py::PerformanceBenchmarks::test_concurrent_requests -v

# 预期结果: >100 RPS
```

---

### 第五阶段: 监控和测试 (第9-10周)

#### 5.1 部署性能监控

修改 `backend/app/dependencies.py`:

```python
from backend.app.core.performance_optimizer import PerformanceMonitor, monitor_performance

performance_monitor = PerformanceMonitor(window_size=1000)

# 在API端点中使用装饰器
@monitor_performance(performance_monitor, "list_runs")
@router.get("/api/v1/runs")
async def list_runs(...):
    ...
```

#### 5.2 添加监控端点

```python
# backend/app/api/metrics.py
@router.get("/metrics/performance")
async def get_performance_metrics(
    performance_monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
    return performance_monitor.generate_report()

@router.get("/metrics/cache")
async def get_cache_metrics(
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    return cache_manager.get_stats()
```

#### 5.3 运行完整基准测试

```bash
# 运行所有性能测试
pytest tests/performance/benchmarks.py -v --tb=short

# 生成性能报告
pytest tests/performance/benchmarks.py --benchmark-only --benchmark-json=results.json
```

---

## 集成指南

### 依赖注入集成

```python
# backend/app/dependencies.py
from typing import Annotated
from fastapi import Depends

from backend.app.core.cache_manager import CacheManager
from backend.app.core.performance_optimizer import PerformanceMonitor

# 全局实例
_cache_manager: CacheManager | None = None
_performance_monitor: PerformanceMonitor | None = None

def get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(
            redis_client=get_redis_client(),
            memory_cache_size=1000
        )
    return _cache_manager

def get_performance_monitor() -> PerformanceMonitor:
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor(window_size=1000)
    return _performance_monitor

# 类型别名
CacheManagerDependency = Annotated[CacheManager, Depends(get_cache_manager)]
PerformanceMonitorDependency = Annotated[PerformanceMonitor, Depends(get_performance_monitor)]
```

### 在FastAPI应用中集成

```python
# backend/app/main.py
from fastapi import FastAPI
from backend.app.dependencies import get_cache_manager, get_performance_monitor

app = FastAPI()

@app.on_event("startup")
async def startup():
    # 初始化缓存
    cache_manager = get_cache_manager()
    
    # 预热缓存
    cache_warmer = CacheWarmer(cache_manager, memory_system)
    await cache_warmer.warm_up()
    
    logger.info("Performance optimization initialized")

@app.on_event("shutdown")
async def shutdown():
    # 生成性能报告
    monitor = get_performance_monitor()
    report = monitor.generate_report()
    logger.info(f"Performance report: {report}")
```

---

## 验证清单

### 第一阶段验证

- [ ] 所有索引已创建
- [ ] 数据库查询时间 <50ms
- [ ] 连接池配置正确
- [ ] 没有N+1查询问题

### 第二阶段验证

- [ ] 缓存管理器集成
- [ ] 缓存命中率 >70%
- [ ] 缓存预热工作正常
- [ ] 缓存失效策略有效

### 第三阶段验证

- [ ] LLM优化器集成
- [ ] 提示词优化工作
- [ ] 请求缓存有效
- [ ] 批处理提升性能

### 第四阶段验证

- [ ] 异步优化完成
- [ ] 并发处理能力提升
- [ ] 超时管理工作正常
- [ ] 吞吐量 >100 RPS

### 第五阶段验证

- [ ] 性能监控部署
- [ ] 基准测试通过
- [ ] 性能指标达标
- [ ] 文档完整

---

## 故障排除

### 问题1: 缓存命中率低

**症状**: 缓存命中率 <50%

**原因**:
- 缓存键生成不一致
- TTL设置过短
- 缓存大小不足

**解决方案**:
```python
# 检查缓存统计
stats = cache_manager.get_stats()
print(f"Hit rate: {stats['memory_cache']['hit_rate']}")

# 增加缓存大小
cache_manager = CacheManager(memory_cache_size=2000)

# 增加TTL
await cache_manager.set(key, value, ttl=7200)
```

### 问题2: 数据库连接耗尽

**症状**: "too many connections" 错误

**原因**:
- 连接池大小不足
- 连接泄漏

**解决方案**:
```python
# 增加连接池大小
pool = await asyncpg.create_pool(
    database_url,
    min_size=20,
    max_size=100,
)

# 检查活跃连接
SELECT count(*) FROM pg_stat_activity;
```

### 问题3: 内存使用过高

**症状**: 内存使用 >500MB

**原因**:
- 缓存条目过多
- 内存泄漏

**解决方案**:
```python
# 监控缓存大小
stats = cache_manager.get_stats()
print(f"Cache size: {stats['memory_cache']['size']}")

# 清理过期条目
await cache_manager.invalidate()

# 减少缓存大小
cache_manager = CacheManager(memory_cache_size=500)
```

### 问题4: LLM调用超时

**症状**: LLM调用 >5s

**原因**:
- 网络延迟
- LLM服务过载
- 提示词过长

**解决方案**:
```python
# 优化提示词
optimized = llm_optimizer.optimize_prompt(prompt)

# 增加超时时间
result = await async_optimizer.run_with_timeout(
    llm_call(),
    timeout=60.0
)

# 使用批处理
results = await llm_optimizer.batch_requests(requests)
```

---

## 性能监控

### 关键指标

```python
# 获取性能报告
report = performance_monitor.generate_report()

print(f"Total requests: {report['total_requests']}")
print(f"Avg response time: {report['avg_response_time_ms']}ms")
print(f"P95 response time: {report['p95_response_time_ms']}ms")
print(f"P99 response time: {report['p99_response_time_ms']}ms")
print(f"Throughput: {report['throughput_rps']} RPS")
```

### 监控端点

```bash
# 获取性能指标
curl http://localhost:8000/metrics/performance

# 获取缓存统计
curl http://localhost:8000/metrics/cache

# 获取数据库统计
curl http://localhost:8000/metrics/database
```

### 告警配置

```python
# 设置告警阈值
ALERT_THRESHOLDS = {
    'response_time_p95_ms': 350,
    'response_time_p99_ms': 600,
    'cache_hit_rate': 0.7,
    'error_rate': 0.001,
    'throughput_rps': 100,
}

# 检查告警
report = performance_monitor.generate_report()
if report['p95_response_time_ms'] > ALERT_THRESHOLDS['response_time_p95_ms']:
    logger.warning("P95 response time exceeded threshold")
```

---

## 后续优化

### 短期 (1-3个月)

- [ ] 实现查询结果分页
- [ ] 添加响应压缩
- [ ] 优化序列化性能
- [ ] 实现请求去重

### 中期 (3-6个月)

- [ ] 实现分布式缓存
- [ ] 添加CDN支持
- [ ] 优化前端资源加载
- [ ] 实现数据库读写分离

### 长期 (6-12个月)

- [ ] 实现数据库分片
- [ ] 添加自适应缓存策略
- [ ] 实现智能预加载
- [ ] 优化机器学习模型推理

---

## 参考资源

- [PostgreSQL性能优化](https://www.postgresql.org/docs/current/performance-tips.html)
- [Redis最佳实践](https://redis.io/docs/management/optimization/)
- [Python异步编程](https://docs.python.org/3/library/asyncio.html)
- [FastAPI性能](https://fastapi.tiangolo.com/deployment/concepts/)
- [asyncpg文档](https://magicstack.github.io/asyncpg/)

---

**维护人**: X-Agent性能优化团队  
**最后更新**: 2026-05-27  
**下次审查**: 2026-06-27
