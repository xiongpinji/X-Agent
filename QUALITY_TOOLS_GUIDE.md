# X-Agent 质量提升工具指南

本指南说明如何使用第四阶段实施的质量提升工具和流程。

## 目录

1. [CI/CD工作流](#cicd工作流)
2. [测试和覆盖率](#测试和覆盖率)
3. [性能测试](#性能测试)
4. [API文档](#api文档)
5. [监控告警](#监控告警)
6. [快速开始](#快速开始)

---

## CI/CD工作流

### 工作流文件

项目包含三个GitHub Actions工作流:

#### 1. 测试工作流 (`.github/workflows/test.yml`)

**触发条件**:
- Push到main或develop分支
- 创建PR到main或develop分支

**执行步骤**:
1. 在Python 3.11和3.12上运行测试
2. 启动PostgreSQL、Redis、Qdrant服务
3. 运行linting、类型检查、安全检查
4. 执行测试并生成覆盖率报告
5. 上传覆盖率到Codecov
6. 保存覆盖率HTML报告

**查看结果**:
- GitHub Actions标签页
- Codecov集成
- 下载覆盖率报告

#### 2. 代码质量工作流 (`.github/workflows/quality.yml`)

**触发条件**:
- Push到main或develop分支
- 创建PR到main或develop分支

**执行步骤**:
1. Ruff linting和格式检查
2. MyPy类型检查
3. Bandit安全检查
4. Pylint代码分析
5. Pre-commit hooks检查
6. PR评论中显示质量报告

**查看结果**:
- GitHub Actions标签页
- PR评论中的质量报告
- 质量报告工件

#### 3. 部署工作流 (`.github/workflows/deploy.yml`)

**触发条件**:
- Push到main或develop分支
- 推送标签 (v*)

**执行步骤**:
1. 构建Docker镜像
2. 推送到容器仓库
3. 部署到staging (develop分支)
4. 部署到production (标签)
5. 创建Release

**配置**:
需要设置以下secrets:
- `STAGING_DEPLOY_KEY`: Staging部署密钥
- `PRODUCTION_DEPLOY_KEY`: Production部署密钥

---

## 测试和覆盖率

### 运行测试

#### 本地运行所有测试
```bash
pytest tests/ -v
```

#### 运行特定测试文件
```bash
pytest tests/test_api.py -v
```

#### 运行特定测试
```bash
pytest tests/test_api.py::test_health -v
```

#### 运行测试并生成覆盖率报告
```bash
pytest tests/ --cov=backend --cov-report=html --cov-report=term-missing
```

### 覆盖率分析

#### 运行覆盖率分析脚本
```bash
python scripts/analyze_coverage.py
```

这将:
1. 运行pytest并生成覆盖率数据
2. 分析覆盖率缺口
3. 生成Markdown格式的覆盖率报告 (`COVERAGE_REPORT.md`)
4. 列出低覆盖率文件
5. 提供改进建议

#### 查看覆盖率报告
```bash
# 生成HTML报告
pytest tests/ --cov=backend --cov-report=html

# 在浏览器中打开
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### 覆盖率目标

关键模块的覆盖率目标:

| 模块 | 目标 | 优先级 |
|------|------|--------|
| backend/app/core/security.py | 100% | Critical |
| backend/app/api/auth.py | 100% | Critical |
| backend/app/core/audit.py | 95% | High |
| backend/app/core/llm.py | 90% | High |
| backend/app/core/memory_postgres.py | 90% | High |
| backend/app/api/agents.py | 85% | Medium |
| backend/app/api/workflows.py | 85% | Medium |
| backend/app/services/browser/automation.py | 85% | Medium |

---

## 性能测试

### 运行性能测试

#### 运行所有性能测试
```bash
pytest tests/test_performance.py -v
```

#### 运行特定性能测试
```bash
pytest tests/test_performance.py::TestAPIPerformance::test_health_endpoint_performance -v
```

#### 运行性能测试并显示详细输出
```bash
pytest tests/test_performance.py -v -s
```

### 性能指标

性能测试收集以下指标:

- **最小值 (Min)**: 最快的响应时间
- **最大值 (Max)**: 最慢的响应时间
- **平均值 (Mean)**: 平均响应时间
- **中位数 (Median)**: 50%百分位数
- **P95**: 95%百分位数 (95%的请求快于此时间)
- **P99**: 99%百分位数 (99%的请求快于此时间)

### 性能基准

当前性能基准:

| 端点 | 平均 | P95 | P99 |
|------|------|-----|-----|
| GET /health | <10ms | <50ms | <100ms |
| POST /api/v1/agents/run | <5000ms | <8000ms | <10000ms |
| GET /api/v1/memory/search | <1000ms | <1500ms | <2000ms |
| GET /api/v1/workflows | <500ms | <800ms | <1000ms |

### 性能优化建议

1. **数据库优化**
   - 分析慢查询日志
   - 添加必要的索引
   - 优化查询语句
   - 实现查询缓存

2. **API优化**
   - 减少数据库查询次数
   - 实现响应缓存
   - 优化JSON序列化
   - 实现分页

3. **资源优化**
   - 优化内存使用
   - 实现连接池
   - 优化并发处理
   - 减少GC压力

---

## API文档

### 生成API文档

#### 运行文档生成脚本
```bash
python scripts/generate_api_docs.py
```

这将生成:
1. `docs/openapi.json` - OpenAPI 3.0规范
2. `docs/API.md` - Markdown格式的API文档

### 访问交互式文档

启动应用后，访问:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API文档内容

生成的文档包括:

- 所有API端点的完整列表
- 请求和响应示例
- 参数说明和验证规则
- 错误码和处理指南
- 认证和授权说明
- 速率限制说明
- 分页使用说明

### 文档更新

API文档会自动从代码中生成。更新API时:

1. 更新FastAPI路由和模型
2. 运行 `python scripts/generate_api_docs.py`
3. 提交更新的文档文件

---

## 监控告警

### 启动监控栈

#### 使用Docker Compose启动
```bash
cd monitoring
docker-compose up -d
```

#### 查看日志
```bash
docker-compose logs -f
```

#### 停止监控栈
```bash
docker-compose down
```

### 访问监控工具

启动后，访问:

| 工具 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| Prometheus | http://localhost:9090 | - | - |
| Grafana | http://localhost:3000 | admin | admin |
| AlertManager | http://localhost:9093 | - | - |

### Prometheus

**功能**:
- 指标存储和查询
- 时间序列数据库
- 告警规则评估

**常用查询**:
```promql
# API请求速率
rate(xagent_api_requests_total[5m])

# API P95延迟
histogram_quantile(0.95, rate(xagent_api_request_duration_seconds_bucket[5m]))

# 错误率
rate(xagent_errors_total[5m])

# 缓存命中率
rate(xagent_cache_hits_total[5m]) / (rate(xagent_cache_hits_total[5m]) + rate(xagent_cache_misses_total[5m]))
```

### Grafana

**功能**:
- 指标可视化
- 仪表板创建
- 告警配置

**预配置仪表板**:
- X-Agent Monitoring Dashboard
  - API请求速率
  - API P95延迟
  - Agent运行速率
  - 错误率
  - 活跃数据库连接数
  - 缓存命中率

**创建自定义仪表板**:
1. 登录Grafana (admin/admin)
2. 创建新仪表板
3. 添加面板
4. 选择Prometheus数据源
5. 编写PromQL查询
6. 保存仪表板

### AlertManager

**功能**:
- 告警分组和去重
- 告警路由
- 告警通知

**配置通知**:

编辑 `monitoring/alertmanager.yml`:

```yaml
global:
  slack_api_url: 'YOUR_SLACK_WEBHOOK_URL'
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'
```

设置环境变量:
```bash
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'
export PAGERDUTY_SERVICE_KEY='...'
```

重启AlertManager:
```bash
docker-compose restart alertmanager
```

### 告警规则

定义在 `monitoring/alert_rules.yml`

关键告警:

| 告警 | 条件 | 严重级别 |
|------|------|---------|
| HighAPILatency | P95 > 1000ms | Warning |
| CriticalAPILatency | P99 > 5000ms | Critical |
| HighErrorRate | > 0.05 errors/sec | Warning |
| CriticalErrorRate | > 0.1 errors/sec | Critical |
| DatabaseConnectionPoolExhausted | > 90% | Critical |
| HighMemoryUsage | > 8GB | Warning |
| CriticalMemoryUsage | > 15GB | Critical |

### 添加自定义指标

在应用代码中:

```python
from backend.app.services.observability.prometheus_metrics import (
    api_requests_total,
    api_request_duration_seconds,
)

# 记录请求
api_requests_total.labels(method="GET", endpoint="/api/v1/agents", status=200).inc()

# 记录耗时
with api_request_duration_seconds.labels(method="GET", endpoint="/api/v1/agents").time():
    # 执行操作
    pass
```

---

## 快速开始

### 1. 本地开发设置

```bash
# 克隆仓库
git clone <repository>
cd X-Agent

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev,test]"

# 安装pre-commit hooks
pre-commit install
```

### 2. 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行测试并生成覆盖率报告
pytest tests/ --cov=backend --cov-report=html

# 运行性能测试
pytest tests/test_performance.py -v
```

### 3. 生成文档

```bash
# 生成API文档
python scripts/generate_api_docs.py

# 分析覆盖率
python scripts/analyze_coverage.py
```

### 4. 启动监控

```bash
# 启动监控栈
cd monitoring
docker-compose up -d

# 访问Grafana
open http://localhost:3000
```

### 5. 提交代码

```bash
# Pre-commit hooks会自动运行
git add .
git commit -m "Your commit message"

# 推送到远程仓库
git push origin feature-branch
```

---

## 故障排除

### 测试失败

**问题**: 测试连接到数据库失败

**解决**:
```bash
# 检查环境变量
echo $DATABASE_URL

# 启动PostgreSQL
docker run -d -e POSTGRES_PASSWORD=xagent -p 5432:5432 postgres:16

# 运行测试
pytest tests/ -v
```

### 覆盖率报告为空

**问题**: 覆盖率报告没有生成

**解决**:
```bash
# 确保pytest-cov已安装
pip install pytest-cov

# 运行覆盖率分析
python scripts/analyze_coverage.py
```

### 监控栈无法启动

**问题**: Docker Compose启动失败

**解决**:
```bash
# 检查Docker是否运行
docker ps

# 查看日志
docker-compose logs

# 清理并重新启动
docker-compose down -v
docker-compose up -d
```

### Grafana无法连接到Prometheus

**问题**: Grafana中的Prometheus数据源显示红色

**解决**:
```bash
# 检查Prometheus是否运行
curl http://localhost:9090/-/healthy

# 检查网络连接
docker network ls
docker network inspect monitoring_x-agent-network

# 重启Prometheus
docker-compose restart prometheus
```

---

## 最佳实践

### 测试

1. 为每个新功能编写测试
2. 保持测试简单和独立
3. 使用有意义的测试名称
4. 定期运行覆盖率报告
5. 优先覆盖关键路径

### 性能

1. 定期运行性能测试
2. 监控关键指标
3. 在优化前建立基准
4. 使用APM工具识别瓶颈
5. 文档化性能改进

### 监控

1. 定期审查告警规则
2. 调整告警阈值以减少误报
3. 建立告警响应流程
4. 定期审查仪表板
5. 记录关键事件

### CI/CD

1. 保持工作流简单
2. 定期审查工作流日志
3. 优化构建时间
4. 使用缓存加速构建
5. 文档化部署流程

---

## 参考资源

- [GitHub Actions文档](https://docs.github.com/en/actions)
- [Prometheus文档](https://prometheus.io/docs/)
- [Grafana文档](https://grafana.com/docs/)
- [pytest文档](https://docs.pytest.org/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [Docker文档](https://docs.docker.com/)

---

**最后更新**: 2026-05-26
