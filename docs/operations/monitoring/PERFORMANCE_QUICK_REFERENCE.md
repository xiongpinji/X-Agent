# X-Agent 性能测试 - 快速参考

## 快速开始（5分钟）

### 1. 启动服务
```bash
# 启动所有服务（数据库、Redis、API）
docker-compose -f docker-compose.performance.yml up -d

# 验证服务状态
curl http://localhost:8000/health
```

### 2. 运行测试
```bash
# 运行所有性能测试
python run_performance_tests.py

# 包含负载测试
python run_performance_tests.py --with-locust
```

### 3. 查看结果
```bash
# API性能报告
cat performance_benchmark_report.json

# 数据库性能报告
cat database_benchmark_report.json

# Grafana可视化
# 访问 http://localhost:3000 (admin/admin)
```

---

## 常用命令

### API性能测试
```bash
# 基础测试
python performance_tests.py

# 自定义参数
python performance_tests.py --base-url http://localhost:8000 --timeout 60
```

### 数据库性能测试
```bash
# 基础测试
python database_benchmark.py

# 自定义连接
python database_benchmark.py --host localhost --port 5432 --database xagent
```

### 负载测试
```bash
# Web UI模式（推荐）
locust -f locustfile.py --host=http://localhost:8000

# 命令行模式
locust -f locustfile.py --host=http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 5m --headless

# 自定义用户类
locust -f locustfile.py --host=http://localhost:8000 \
  -u XAgentFastUser
```

### 测试运行器
```bash
# 运行所有测试
python run_performance_tests.py

# 包含Locust
python run_performance_tests.py --with-locust

# 自定义Locust参数
python run_performance_tests.py --with-locust \
  --locust-users 200 \
  --locust-spawn-rate 20 \
  --locust-time 10m
```

---

## 性能指标速查表

### API响应时间目标
| 端点 | 目标 | P95 | P99 |
|------|------|-----|-----|
| /health | < 10ms | < 20ms | < 50ms |
| /api/v1/auth/login | < 100ms | < 200ms | < 500ms |
| /api/v1/workflows | < 100ms | < 200ms | < 500ms |
| /api/v1/agents | < 100ms | < 200ms | < 500ms |

### 数据库操作目标
| 操作 | 目标 | P95 | P99 |
|------|------|-----|-----|
| SELECT | < 2ms | < 5ms | < 10ms |
| INSERT | < 5ms | < 10ms | < 20ms |
| UPDATE | < 5ms | < 10ms | < 20ms |
| DELETE | < 5ms | < 10ms | < 20ms |
| COMPLEX_QUERY | < 10ms | < 20ms | < 50ms |
| TRANSACTION | < 15ms | < 30ms | < 100ms |

### 系统吞吐量目标
| 指标 | 目标 |
|------|------|
| API吞吐量 | > 500 RPS |
| 数据库吞吐量 | > 1000 ops/sec |
| 错误率 | < 0.1% |

---

## 故障排除速查

### 问题：连接被拒绝
```bash
# 检查服务状态
curl http://localhost:8000/health

# 查看日志
docker logs xagent-api-perf

# 重启服务
docker-compose -f docker-compose.performance.yml restart xagent-api
```

### 问题：数据库连接失败
```bash
# 检查数据库状态
docker logs xagent-postgres-perf

# 检查连接
psql -h localhost -U postgres -d xagent -c "SELECT 1"

# 重启数据库
docker-compose -f docker-compose.performance.yml restart postgres
```

### 问题：Locust找不到
```bash
# 安装Locust
pip install locust>=2.20.0

# 验证安装
locust --version
```

### 问题：性能测试超时
```bash
# 增加超时时间
python performance_tests.py --timeout 120

# 减少请求数
# 编辑 performance_tests.py 中的 num_requests 参数
```

---

## 性能优化检查清单

### 数据库优化
- [ ] 添加必要的索引
- [ ] 分析慢查询
- [ ] 调整连接池大小
- [ ] 启用查询缓存

### API优化
- [ ] 实现分页
- [ ] 启用响应压缩
- [ ] 优化序列化
- [ ] 添加缓存

### 系统优化
- [ ] 部署Redis缓存
- [ ] 配置负载均衡
- [ ] 启用异步处理
- [ ] 监控系统资源

---

## 性能监控仪表板

### Grafana访问
```
URL: http://localhost:3000
用户名: admin
密码: admin
```

### 关键指标
1. **API性能**
   - 请求速率
   - 响应时间分布
   - 错误率

2. **数据库性能**
   - 查询时间
   - 连接数
   - 缓存命中率

3. **系统资源**
   - CPU使用率
   - 内存使用
   - 磁盘I/O

---

## 性能基准建立

### 第一次运行
```bash
# 建立基准
python run_performance_tests.py > baseline_$(date +%Y%m%d).txt

# 保存报告
cp performance_benchmark_report.json baseline_$(date +%Y%m%d).json
```

### 对比优化效果
```bash
# 优化后运行
python run_performance_tests.py > optimized_$(date +%Y%m%d).txt

# 对比结果
diff baseline_*.txt optimized_*.txt
```

---

## 性能测试最佳实践

1. **定期测试**
   - 每周运行一次
   - 每个发布前运行
   - 优化后验证

2. **保存历史**
   - 记录所有测试结果
   - 跟踪性能趋势
   - 识别回归

3. **隔离变量**
   - 一次只改变一个参数
   - 控制测试环境
   - 重复测试验证

4. **分析结果**
   - 关注P95/P99
   - 检查错误率
   - 识别瓶颈

5. **文档化**
   - 记录测试条件
   - 记录优化措施
   - 分享最佳实践

---

## 性能优化建议

### 立即可做（< 1天）
```python
# 1. 添加数据库索引
CREATE INDEX idx_workflows_user_id ON workflows(user_id);

# 2. 启用响应压缩
from fastapi.middleware.gzip import GZIPMiddleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# 3. 实现分页
@app.get("/api/v1/workflows")
async def list_workflows(skip: int = 0, limit: int = 20):
    return await db.fetch(
        "SELECT * FROM workflows LIMIT $1 OFFSET $2",
        limit, skip
    )
```

### 短期优化（1-2周）
- 部署Redis缓存
- 优化慢查询
- 调整连接池
- 实现异步处理

### 中期优化（2-4周）
- 配置负载均衡
- 部署监控系统
- 实施自动扩展
- 优化序列化

---

## 文件快速导航

| 文件 | 用途 |
|------|------|
| performance_tests.py | API性能测试 |
| database_benchmark.py | 数据库性能测试 |
| locustfile.py | 负载测试 |
| run_performance_tests.py | 测试运行器 |
| PERFORMANCE_TESTING_GUIDE.md | 详细指南 |
| PERFORMANCE_BENCHMARK_REPORT.md | 报告模板 |
| .env.performance | 环境配置 |
| docker-compose.performance.yml | Docker配置 |

---

## 联系和支持

- 查看详细指南: PERFORMANCE_TESTING_GUIDE.md
- 查看报告模板: PERFORMANCE_BENCHMARK_REPORT.md
- 查看项目总结: PERFORMANCE_TESTING_SUMMARY.md

---

**最后更新**: 2026-05-26
**版本**: 1.0
