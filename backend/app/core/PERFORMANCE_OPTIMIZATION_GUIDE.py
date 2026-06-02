"""
性能优化集成指南和最佳实践

本文档说明如何在X-Agent中集成性能优化模块
"""

# ============================================================================
# 1. 在FastAPI应用中集成性能优化
# ============================================================================

"""
在 backend/app/main.py 或应用初始化文件中添加:

from backend.app.core.performance_optimization import (
    performance_monitor,
    ResponseCache,
    BatchLoader,
    MultiLayerCache,
    OptimizedConnectionPool,
    AdaptiveRateLimiter,
    MemoryOptimizer,
)

# 初始化性能监控
app = FastAPI()

# 添加中间件
from starlette.middleware.base import BaseHTTPMiddleware
import time

class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"
        return response

app.add_middleware(PerformanceMiddleware)
"""

# ============================================================================
# 2. API响应缓存使用示例
# ============================================================================

"""
from backend.app.core.performance_optimization import cached_response

@app.get("/api/v1/agents")
@cached_response(ttl_seconds=300)
async def list_agents():
    # 这个响应会被缓存300秒
    return await get_agents_from_db()

# 获取缓存统计
@app.get("/api/v1/metrics/cache")
async def get_cache_stats():
    return performance_monitor.response_cache.get_stats()
"""

# ============================================================================
# 3. 数据库查询优化 - 批量加载
# ============================================================================

"""
from backend.app.core.performance_optimization import BatchLoader

# 创建批量加载器
async def batch_load_agents(agent_ids: list[str]):
    # 单个查询获取所有agent
    return await db.query(Agent).filter(Agent.id.in_(agent_ids)).all()

agent_loader = BatchLoader(batch_load_agents, batch_size=100)

# 在API中使用
@app.get("/api/v1/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = await db.get_workflow(workflow_id)
    # 使用批量加载器获取agent，防止N+1查询
    agent = await agent_loader.load(workflow.agent_id)
    return {"workflow": workflow, "agent": agent}
"""

# ============================================================================
# 4. 多层缓存使用
# ============================================================================

"""
from backend.app.core.performance_optimization import MultiLayerCache
import redis.asyncio as redis

# 初始化Redis客户端
redis_client = await redis.from_url("redis://localhost:6379")

# 创建多层缓存
cache = MultiLayerCache(redis_client=redis_client, l1_max_size_mb=50)

# 使用缓存
@app.get("/api/v1/search")
async def search(q: str):
    # 先查缓存
    cached = await cache.get(f"search:{q}")
    if cached:
        return cached

    # 执行搜索
    results = await perform_search(q)

    # 缓存结果
    await cache.set(f"search:{q}", results, ttl_seconds=600)

    return results

# 获取缓存统计
@app.get("/api/v1/metrics/cache-stats")
async def get_cache_stats():
    return cache.get_stats()
"""

# ============================================================================
# 5. 连接池优化
# ============================================================================

"""
from backend.app.core.performance_optimization import OptimizedConnectionPool

# 创建数据库连接池
async def create_db_connection():
    return await asyncpg.connect("postgresql://...")

db_pool = OptimizedConnectionPool(
    factory=create_db_connection,
    min_size=10,
    max_size=50,
    timeout=30.0,
)

# 初始化
await db_pool.initialize()

# 使用连接
async def query_database():
    conn = await db_pool.acquire()
    try:
        result = await conn.fetch("SELECT * FROM agents")
        return result
    finally:
        await db_pool.release(conn)

# 获取连接池统计
@app.get("/api/v1/metrics/pool")
async def get_pool_stats():
    stats = db_pool.get_stats()
    return {
        "total_connections": stats.total_connections,
        "active_connections": stats.active_connections,
        "idle_connections": stats.idle_connections,
        "peak_active": stats.peak_active,
    }
"""

# ============================================================================
# 6. 速率限制
# ============================================================================

"""
from backend.app.core.performance_optimization import AdaptiveRateLimiter
import psutil

rate_limiter = AdaptiveRateLimiter(base_rps=1000)

@app.get("/api/v1/data")
async def get_data():
    # 获取速率限制许可
    await rate_limiter.acquire()

    # 执行操作
    return await fetch_data()

# 定期调整限制
async def adjust_rate_limit():
    while True:
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent
        rate_limiter.adjust_limit(cpu, memory)
        await asyncio.sleep(60)
"""

# ============================================================================
# 7. 内存优化
# ============================================================================

"""
from backend.app.core.performance_optimization import MemoryOptimizer

memory_optimizer = MemoryOptimizer(target_memory_mb=500)

# 定期执行内存优化
async def periodic_memory_optimization():
    while True:
        result = memory_optimizer.optimize()
        logger.info(f"内存优化: {result}")
        await asyncio.sleep(300)  # 每5分钟执行一次

# 获取内存统计
@app.get("/api/v1/metrics/memory")
async def get_memory_stats():
    return memory_optimizer.get_stats()
"""

# ============================================================================
# 8. 性能监控和报告
# ============================================================================

"""
from backend.app.core.performance_optimization import performance_monitor, PerformanceMetrics

# 记录性能指标
@app.get("/api/v1/metrics/current")
async def get_current_metrics():
    metrics = performance_monitor.get_current_metrics()
    return metrics.dict()

# 生成性能报告
@app.get("/api/v1/metrics/report")
async def get_performance_report():
    report = performance_monitor.generate_report()
    return {"report": report}

# 定期记录指标
async def periodic_metrics_recording():
    while True:
        metrics = performance_monitor.get_current_metrics()
        performance_monitor.record_metrics(metrics)
        await asyncio.sleep(60)
"""

# ============================================================================
# 9. 查询优化示例
# ============================================================================

"""
# 不好的做法 - N+1查询
@app.get("/api/v1/workflows")
async def list_workflows():
    workflows = await db.query(Workflow).all()
    # 这会导致N+1查询
    for workflow in workflows:
        workflow.agent = await db.get_agent(workflow.agent_id)
    return workflows

# 好的做法 - 批量加载
@app.get("/api/v1/workflows")
async def list_workflows():
    workflows = await db.query(Workflow).all()
    agent_ids = [w.agent_id for w in workflows]
    # 单个查询获取所有agent
    agents = await db.query(Agent).filter(Agent.id.in_(agent_ids)).all()
    agent_map = {a.id: a for a in agents}
    for workflow in workflows:
        workflow.agent = agent_map[workflow.agent_id]
    return workflows
"""

# ============================================================================
# 10. 性能目标检查清单
# ============================================================================

"""
性能优化完成检查清单:

API响应时间优化:
  ✓ 实现请求级缓存
  ✓ 添加响应压缩
  ✓ 使用CDN缓存静态资源
  ✓ 实现请求去重
  目标: API响应时间 < 100ms (P95)

数据库查询优化:
  ✓ 消除N+1查询
  ✓ 添加数据库索引
  ✓ 使用查询批处理
  ✓ 实现查询缓存
  目标: 数据库查询 < 50ms

缓存策略优化:
  ✓ 实现多层缓存 (L1内存 + L2 Redis)
  ✓ 设置合理的TTL
  ✓ 实现缓存预热
  ✓ 监控缓存命中率
  目标: 缓存命中率 > 90%

并发处理优化:
  ✓ 优化连接池配置
  ✓ 实现自适应速率限制
  ✓ 使用异步处理
  ✓ 实现请求队列
  目标: 并发处理 > 1000 RPS

内存使用优化:
  ✓ 定期垃圾回收
  ✓ 优化数据结构
  ✓ 实现内存监控
  ✓ 设置内存限制
  目标: 内存使用 < 500MB
"""

# ============================================================================
# 11. 监控和告警
# ============================================================================

"""
# 定期检查性能指标
async def monitor_performance():
    while True:
        metrics = performance_monitor.get_current_metrics()

        # 检查是否满足目标
        if not metrics.meets_targets():
            logger.warning(f"性能指标未达成: {metrics}")
            # 发送告警
            await send_alert(f"Performance degradation: {metrics}")

        await asyncio.sleep(60)

# 生成定期报告
async def generate_periodic_report():
    while True:
        report = performance_monitor.generate_report()
        logger.info(report)
        # 保存报告
        await save_report(report)
        await asyncio.sleep(3600)  # 每小时生成一次
"""
