# X-Agent 性能调优指南

**版本**: 1.0  
**最后更新**: 2026-05-27  
**文档状态**: Published

---

## 目录

1. [性能概览](#性能概览)
2. [性能指标](#性能指标)
3. [配置调优](#配置调优)
4. [数据库优化](#数据库优化)
5. [缓存策略](#缓存策略)
6. [监控指标](#监控指标)
7. [故障排查](#故障排查)
8. [基准测试](#基准测试)

---

## 性能概览

X-Agent 采用多层性能优化策略：

- **异步处理** - 使用FastAPI异步框架
- **缓存机制** - Redis缓存热数据
- **数据库优化** - 索引、查询优化
- **连接池** - 数据库连接复用
- **消息队列** - 异步任务处理
- **CDN加速** - 静态资源加速

### 性能目标

| 指标 | 目标 | 说明 |
|------|------|------|
| API响应时间 | <200ms | P95延迟 |
| 吞吐量 | >1000 req/s | 单机容量 |
| 内存占用 | <500MB | 基础内存 |
| CPU使用率 | <70% | 正常负载 |
| 数据库查询 | <50ms | P95延迟 |

---

## 性能指标

### 关键性能指标(KPI)

```python
# 响应时间分布
Response Time Distribution:
- P50: 50ms
- P95: 150ms
- P99: 300ms

# 吞吐量
Throughput: 1000-2000 req/s

# 错误率
Error Rate: <0.1%

# 可用性
Availability: >99.9%
```

### 监控指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 请求计数
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# 响应时间
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# 活跃连接
active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

# 数据库查询时间
db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']
)
```

---

## 配置调优

### FastAPI配置

```python
# settings.py
class Settings(BaseSettings):
    # 工作进程数
    workers: int = 4
    
    # 线程池大小
    thread_pool_size: int = 10
    
    # 连接超时
    connection_timeout: int = 30
    
    # 请求超时
    request_timeout: int = 60
    
    # 最大请求体大小
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    
    # 启用gzip压缩
    enable_gzip: bool = True
    gzip_min_size: int = 1000
```

### Uvicorn配置

```bash
# 启动命令
uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --loop uvloop \
  --http httptools \
  --access-log \
  --log-level info
```

### 数据库连接池

```python
from sqlalchemy.pool import QueuePool

# PostgreSQL连接池配置
DATABASE_URL = "postgresql://user:password@localhost/xagent"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,           # 连接池大小
    max_overflow=40,        # 最大溢出连接
    pool_recycle=3600,      # 连接回收时间(秒)
    pool_pre_ping=True,     # 连接前检查
    echo=False              # 禁用SQL日志
)
```

---

## 数据库优化

### 索引策略

```sql
-- 创建必要的索引
CREATE INDEX idx_agents_tenant_id ON agents(tenant_id);
CREATE INDEX idx_agents_created_at ON agents(created_at DESC);
CREATE INDEX idx_runs_agent_id ON runs(agent_id);
CREATE INDEX idx_runs_status ON runs(status);
CREATE INDEX idx_runs_created_at ON runs(created_at DESC);

-- 复合索引
CREATE INDEX idx_runs_agent_status ON runs(agent_id, status);
CREATE INDEX idx_memory_tenant_type ON memory(tenant_id, type);

-- 向量索引(用于相似度搜索)
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);
```

### 查询优化

```python
# 使用select()而不是query()
from sqlalchemy import select

# 优化前
agents = db.query(Agent).filter(Agent.tenant_id == tenant_id).all()

# 优化后 - 只选择需要的列
stmt = select(Agent.id, Agent.name, Agent.status).where(
    Agent.tenant_id == tenant_id
)
agents = db.execute(stmt).fetchall()

# 使用joinedload避免N+1查询
from sqlalchemy.orm import joinedload

agents = db.query(Agent).options(
    joinedload(Agent.runs)
).filter(Agent.tenant_id == tenant_id).all()
```

### 批量操作

```python
# 批量插入
from sqlalchemy import insert

values = [
    {"name": f"agent_{i}", "tenant_id": tenant_id}
    for i in range(1000)
]
db.execute(insert(Agent).values(values))
db.commit()

# 批量更新
from sqlalchemy import update

db.execute(
    update(Agent)
    .where(Agent.status == "inactive")
    .values(status="archived")
)
db.commit()
```

---

## 缓存策略

### Redis缓存

```python
from redis import Redis
from functools import wraps
import json

redis_client = Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_keepalive=True
)

# 缓存装饰器
def cache(ttl: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # 尝试从缓存获取
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存储到缓存
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )
            
            return result
        return wrapper
    return decorator

# 使用缓存
@cache(ttl=3600)
async def get_agent(agent_id: str):
    return db.query(Agent).filter(Agent.id == agent_id).first()
```

### 缓存预热

```python
async def warm_cache():
    """启动时预热缓存"""
    # 缓存热数据
    agents = db.query(Agent).filter(Agent.active == True).all()
    for agent in agents:
        cache_key = f"agent:{agent.id}"
        redis_client.setex(
            cache_key,
            3600,
            json.dumps(agent.dict())
        )
```

### 缓存失效

```python
# 主动失效
def invalidate_cache(pattern: str):
    """失效匹配模式的缓存"""
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)

# 使用
@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, agent: AgentUpdate):
    # 更新数据库
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    # ... 更新逻辑
    
    # 失效缓存
    invalidate_cache(f"agent:{agent_id}:*")
    
    return db_agent
```

---

## 监控指标

### Prometheus指标

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# 在FastAPI中集成Prometheus
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 自定义指标
agent_count = Gauge('agent_count', 'Total agents')
run_duration = Histogram('run_duration_seconds', 'Run duration')
memory_usage = Gauge('memory_usage_bytes', 'Memory usage')
```

### Grafana仪表板

```json
{
  "dashboard": {
    "title": "X-Agent Performance",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time P95",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~'5..'}[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 故障排查

### 高CPU使用率

**症状**: CPU使用率持续>80%

**排查步骤**:
1. 检查是否有长时间运行的任务
2. 分析热点函数
3. 检查数据库查询性能
4. 增加工作进程数

```bash
# 使用py-spy分析CPU
py-spy record -o profile.svg -- python -m uvicorn backend.app.main:app

# 查看热点函数
py-spy top -- python -m uvicorn backend.app.main:app
```

### 高内存占用

**症状**: 内存使用率持续增长

**排查步骤**:
1. 检查是否有内存泄漏
2. 分析缓存大小
3. 检查连接池配置
4. 使用内存分析工具

```python
# 使用memory_profiler
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 代码
    pass
```

### 数据库连接耗尽

**症状**: "too many connections" 错误

**排查步骤**:
1. 检查连接池配置
2. 查看活跃连接数
3. 检查是否有连接泄漏
4. 增加连接池大小

```sql
-- 查看活跃连接
SELECT count(*) FROM pg_stat_activity;

-- 查看连接详情
SELECT pid, usename, application_name, state FROM pg_stat_activity;

-- 终止空闲连接
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' AND query_start < now() - interval '1 hour';
```

### 查询性能问题

**症状**: 某些查询响应缓慢

**排查步骤**:
1. 启用查询日志
2. 分析执行计划
3. 添加必要的索引
4. 优化查询逻辑

```sql
-- 启用慢查询日志
SET log_min_duration_statement = 1000;  -- 记录>1秒的查询

-- 分析执行计划
EXPLAIN ANALYZE SELECT * FROM agents WHERE tenant_id = 'xxx';

-- 查看索引使用情况
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;
```

---

## 基准测试

### 使用Apache Bench

```bash
# 基准测试
ab -n 10000 -c 100 http://localhost:8000/api/agents

# 输出示例
Requests per second:    1234.56 [#/sec]
Time per request:       81.00 [ms]
```

### 使用wrk

```bash
# 安装wrk
git clone https://github.com/wg/wrk.git
cd wrk && make

# 运行基准测试
./wrk -t4 -c100 -d30s http://localhost:8000/api/agents

# 使用Lua脚本
./wrk -t4 -c100 -d30s -s script.lua http://localhost:8000/api/agents
```

### 基准测试脚本

```python
# benchmark.py
import asyncio
import time
from httpx import AsyncClient

async def benchmark():
    async with AsyncClient() as client:
        start = time.time()
        
        tasks = [
            client.get("http://localhost:8000/api/agents")
            for _ in range(1000)
        ]
        
        results = await asyncio.gather(*tasks)
        
        duration = time.time() - start
        
        print(f"Total requests: 1000")
        print(f"Duration: {duration:.2f}s")
        print(f"Throughput: {1000/duration:.2f} req/s")
        print(f"Avg response time: {duration*1000/1000:.2f}ms")

asyncio.run(benchmark())
```

---

## 性能优化清单

- [ ] 启用异步处理
- [ ] 配置Redis缓存
- [ ] 创建必要的数据库索引
- [ ] 优化数据库查询
- [ ] 配置连接池
- [ ] 启用gzip压缩
- [ ] 配置CDN
- [ ] 设置监控告警
- [ ] 定期进行基准测试
- [ ] 分析和优化热点代码

---

## 相关资源

- [FastAPI性能优化](https://fastapi.tiangolo.com/deployment/concepts/)
- [PostgreSQL性能调优](https://www.postgresql.org/docs/current/performance-tips.html)
- [Redis最佳实践](https://redis.io/topics/optimization)
- [Python性能分析](https://docs.python.org/3/library/profile.html)

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 性能团队  
**许可证**: MIT
