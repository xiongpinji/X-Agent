# X-Agent 性能基准测试指南

## 概述

本指南提供了X-Agent项目的完整性能基准测试套件，包括API性能测试、数据库性能测试和负载测试。

## 文件说明

### 核心测试脚本

1. **performance_tests.py** - API性能测试
   - 测试所有关键API端点
   - 测量响应时间、吞吐量、错误率
   - 支持并发测试和压力测试
   - 生成JSON格式的性能报告

2. **database_benchmark.py** - 数据库性能测试
   - 测试INSERT、SELECT、UPDATE、DELETE操作
   - 测试复杂查询和事务性能
   - 测量数据库操作时间和吞吐量
   - 生成数据库性能报告

3. **locustfile.py** - Locust负载测试
   - 模拟真实用户行为
   - 支持并发用户模拟
   - 提供Web UI和命令行模式
   - 生成详细的负载测试报告

4. **run_performance_tests.py** - 测试运行器
   - 自动运行所有性能测试
   - 生成综合测试报告
   - 提供命令行参数控制

### 文档

- **PERFORMANCE_BENCHMARK_REPORT.md** - 性能基准报告模板
  - 详细的测试结果记录
  - 性能指标分析
  - 优化建议

## 安装依赖

### 基础依赖

```bash
# 安装项目依赖
pip install -e .

# 或安装特定的测试依赖
pip install -e ".[test]"
```

### 额外依赖

```bash
# 安装Locust（用于负载测试）
pip install locust>=2.20.0

# 安装性能监控工具
pip install psutil>=5.9.0
```

## 快速开始

### 1. 启动X-Agent服务

```bash
# 启动FastAPI服务
uvicorn backend.app.web:app --host 0.0.0.0 --port 8000 --reload

# 或使用Docker
docker-compose up -d
```

### 2. 启动PostgreSQL数据库

```bash
# 使用Docker Compose
docker-compose -f docker-compose.postgres.yml up -d

# 或本地PostgreSQL
psql -U postgres -d xagent
```

### 3. 运行性能测试

#### 方式一：运行所有测试（推荐）

```bash
# 运行API和数据库测试
python run_performance_tests.py

# 包含Locust负载测试
python run_performance_tests.py --with-locust

# 自定义Locust参数
python run_performance_tests.py --with-locust \
  --locust-users 200 \
  --locust-spawn-rate 20 \
  --locust-time 10m
```

#### 方式二：单独运行各个测试

**API性能测试**:
```bash
python performance_tests.py
```

输出文件: `performance_benchmark_report.json`

**数据库性能测试**:
```bash
python database_benchmark.py
```

输出文件: `database_benchmark_report.json`

**Locust负载测试**:

启动Web UI（推荐用于交互式测试）:
```bash
locust -f locustfile.py --host=http://localhost:8000
```

然后在浏览器中打开 http://localhost:8089

命令行模式（自动化测试）:
```bash
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --csv=locust_results
```

## 测试配置

### API性能测试配置

编辑 `performance_tests.py` 中的 `run_api_benchmarks()` 方法：

```python
# 修改请求数和并发数
await self.benchmark_endpoint(
    "GET",
    f"{self.base_url}/api/v1/workflows",
    num_requests=2000,      # 总请求数
    concurrency=20          # 并发数
)
```

### 数据库性能测试配置

编辑 `database_benchmark.py` 中的连接参数：

```python
benchmark = DatabaseBenchmark(
    host="localhost",
    port=5432,
    database="xagent",
    user="postgres",
    password="postgres"
)
```

修改操作数量：

```python
await benchmark.benchmark_insert(num_inserts=10000)
await benchmark.benchmark_select(num_selects=10000)
```

### Locust配置

编辑 `locustfile.py` 中的用户行为：

```python
class XAgentUser(HttpUser):
    wait_time = between(1, 3)  # 请求间隔
    
    @task(5)  # 任务权重
    def list_workflows(self):
        # 任务实现
        pass
```

## 性能指标解释

### API性能指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| Min | 最小响应时间 | - |
| Max | 最大响应时间 | - |
| Mean | 平均响应时间 | < 100ms |
| Median | 中位数响应时间 | < 100ms |
| P95 | 95%请求的响应时间 | < 200ms |
| P99 | 99%请求的响应时间 | < 500ms |
| Throughput | 吞吐量（RPS） | > 500 |
| Error Rate | 错误率 | < 0.1% |

### 数据库性能指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| Mean | 平均操作时间 | < 10ms |
| P95 | 95%操作的时间 | < 20ms |
| P99 | 99%操作的时间 | < 50ms |
| Throughput | 吞吐量（ops/sec） | > 1000 |
| Error Rate | 错误率 | < 0.1% |

## 性能优化建议

### 1. 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_workflows_user_id ON workflows(user_id);
CREATE INDEX idx_agents_status ON agents(status);

-- 分析查询计划
EXPLAIN ANALYZE SELECT * FROM workflows WHERE user_id = 1;

-- 调整连接池
-- 在 settings.py 中修改
DATABASE_POOL_MIN_SIZE = 10
DATABASE_POOL_MAX_SIZE = 20
```

### 2. 缓存优化

```python
# 使用Redis缓存
from redis import Redis

redis_client = Redis(host='localhost', port=6379)

# 缓存热点数据
@app.get("/api/v1/workflows")
async def list_workflows():
    cache_key = "workflows:list"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 获取数据
    data = await db.fetch("SELECT * FROM workflows")
    
    # 缓存结果
    redis_client.setex(cache_key, 3600, json.dumps(data))
    return data
```

### 3. API优化

```python
# 实现分页
@app.get("/api/v1/workflows")
async def list_workflows(skip: int = 0, limit: int = 20):
    return await db.fetch(
        "SELECT * FROM workflows LIMIT $1 OFFSET $2",
        limit, skip
    )

# 启用响应压缩
from fastapi.middleware.gzip import GZIPMiddleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# 异步处理
@app.post("/api/v1/workflows/{id}/execute")
async def execute_workflow(id: str):
    # 异步执行
    asyncio.create_task(execute_workflow_async(id))
    return {"status": "queued"}
```

## 性能监控

### 实时监控

```bash
# 监控系统资源
watch -n 1 'ps aux | grep python'

# 监控数据库连接
psql -U postgres -d xagent -c "SELECT count(*) FROM pg_stat_activity;"

# 监控Redis
redis-cli INFO stats
```

### 性能指标收集

```python
# 使用Prometheus
from prometheus_client import Counter, Histogram

request_count = Counter('requests_total', 'Total requests')
request_duration = Histogram('request_duration_seconds', 'Request duration')

@app.middleware("http")
async def add_metrics(request, call_next):
    request_count.inc()
    with request_duration.time():
        response = await call_next(request)
    return response
```

## 故障排除

### 问题1：连接被拒绝

```
Error: Connection refused
```

**解决方案**:
- 检查服务是否运行: `curl http://localhost:8000/health`
- 检查端口是否正确
- 检查防火墙设置

### 问题2：数据库连接失败

```
Error: could not connect to server
```

**解决方案**:
- 检查PostgreSQL是否运行
- 检查数据库凭证
- 检查数据库是否存在

### 问题3：Locust找不到

```
Error: locust command not found
```

**解决方案**:
```bash
pip install locust
```

### 问题4：性能测试超时

**解决方案**:
- 增加超时时间
- 减少请求数
- 检查系统资源

## 性能基准对比

### 建立基准

首次运行时建立性能基准：

```bash
python run_performance_tests.py > baseline_results.txt
```

### 对比优化效果

优化后运行测试并对比：

```bash
python run_performance_tests.py > optimized_results.txt

# 对比结果
diff baseline_results.txt optimized_results.txt
```

## 持续集成

### GitHub Actions示例

```yaml
name: Performance Tests

on: [push, pull_request]

jobs:
  performance:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_DB: xagent
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      
      - name: Run performance tests
        run: python run_performance_tests.py
      
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: performance-reports
          path: |
            performance_benchmark_report.json
            database_benchmark_report.json
```

## 最佳实践

1. **定期运行测试**
   - 每周运行一次完整测试
   - 每个发布前运行测试
   - 在性能优化后运行测试

2. **保存历史数据**
   - 保存所有测试报告
   - 跟踪性能趋势
   - 识别性能回归

3. **建立性能基准**
   - 为每个版本建立基准
   - 设置性能目标
   - 监控目标达成情况

4. **分析瓶颈**
   - 使用性能分析工具
   - 识别热点代码
   - 优先优化高影响项

5. **文档化结果**
   - 记录测试条件
   - 记录优化措施
   - 分享最佳实践

## 参考资源

- [FastAPI性能优化](https://fastapi.tiangolo.com/deployment/concepts/)
- [PostgreSQL性能调优](https://www.postgresql.org/docs/current/performance-tips.html)
- [Locust文档](https://docs.locust.io/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [Redis性能优化](https://redis.io/topics/optimization)

## 支持

如有问题或建议，请提交Issue或Pull Request。

---

**最后更新**: 2026-05-26
**版本**: 1.0
