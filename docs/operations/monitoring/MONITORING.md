# X-Agent 监控告警系统文档

## 概述

X-Agent 监控告警系统提供完整的可观测性解决方案，包括：

- **Prometheus**: 时间序列数据库和指标收集
- **Grafana**: 可视化仪表板
- **AlertManager**: 告警管理和通知
- **健康检查**: 服务健康状态监控

## 架构

```
X-Agent API
    ↓
Prometheus (指标收集)
    ↓
Grafana (可视化)
    ↓
AlertManager (告警通知)
```

## 快速开始

### 启动监控栈

```bash
docker-compose -f deployment/docker-compose.monitoring.yml up -d
```

### 访问服务

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093

## 指标说明

### HTTP 请求指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_http_requests_total` | Counter | 总HTTP请求数 |
| `xagent_http_request_duration_seconds` | Histogram | HTTP请求耗时 |

### 错误指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_errors_total` | Counter | 总错误数 |
| `xagent_error_rate` | Gauge | 当前错误率 |

### Agent 执行指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_agent_executions_total` | Counter | Agent执行总数 |
| `xagent_agent_execution_duration_seconds` | Histogram | Agent执行耗时 |
| `xagent_agent_active_executions` | Gauge | 活跃Agent执行数 |

### 工具调用指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_tool_calls_total` | Counter | 工具调用总数 |
| `xagent_tool_call_duration_seconds` | Histogram | 工具调用耗时 |

### LLM 指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_llm_calls_total` | Counter | LLM调用总数 |
| `xagent_llm_tokens_total` | Counter | LLM令牌使用总数 |
| `xagent_llm_call_duration_seconds` | Histogram | LLM调用耗时 |

### 内存指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_memory_operations_total` | Counter | 内存操作总数 |
| `xagent_memory_size_bytes` | Gauge | 内存大小 |
| `xagent_memory_retrieval_duration_seconds` | Histogram | 内存检索耗时 |

### 工作流指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_workflow_executions_total` | Counter | 工作流执行总数 |
| `xagent_workflow_execution_duration_seconds` | Histogram | 工作流执行耗时 |

### 数据库指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_db_queries_total` | Counter | 数据库查询总数 |
| `xagent_db_query_duration_seconds` | Histogram | 数据库查询耗时 |
| `xagent_db_connection_pool_size` | Gauge | 连接池大小 |
| `xagent_db_active_connections` | Gauge | 活跃连接数 |

### 缓存指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_cache_hits_total` | Counter | 缓存命中总数 |
| `xagent_cache_misses_total` | Counter | 缓存未命中总数 |
| `xagent_cache_size_bytes` | Gauge | 缓存大小 |

### 业务指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_approvals_pending` | Gauge | 待审批数 |
| `xagent_runs_total` | Gauge | 总运行数 |
| `xagent_traces_total` | Gauge | 总追踪数 |
| `xagent_memories_total` | Gauge | 总记忆数 |

### 资源指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `xagent_cpu_usage_percent` | Gauge | CPU使用率 |
| `xagent_memory_usage_bytes` | Gauge | 内存使用量 |
| `xagent_disk_usage_bytes` | Gauge | 磁盘使用量 |

## 仪表板

### 1. 系统概览 (System Overview)

显示整体系统健康状态：
- HTTP请求速率
- 错误率
- 响应时间百分位数
- CPU使用率
- 业务指标

**访问**: http://localhost:3000/d/xagent-overview

### 2. API性能 (API Performance)

监控API端点性能：
- 按方法的请求速率
- 按状态的请求速率
- 响应时间分布
- 按类型的错误率
- 按端点的请求量

**访问**: http://localhost:3000/d/xagent-api-performance

### 3. Agent执行 (Agent Execution)

监控Agent执行情况：
- 按状态的执行速率
- Agent失败率
- 执行耗时百分位数
- 活跃执行数
- 工具调用速率
- LLM调用速率

**访问**: http://localhost:3000/d/xagent-execution

### 4. 资源使用 (Resource Usage)

监控系统资源：
- CPU使用率
- 内存使用量
- 数据库连接池使用率
- 数据库查询耗时
- 数据库连接数
- 缓存命中率
- 缓存大小

**访问**: http://localhost:3000/d/xagent-resources

### 5. 错误监控 (Error Monitoring)

监控系统错误：
- 总体错误率
- Agent失败率
- 工具失败率
- 按类型的错误率
- 按端点的错误率
- 按Agent的失败数
- 按工具的失败数

**访问**: http://localhost:3000/d/xagent-errors

## 告警规则

### 高错误率告警 (HighErrorRate)

**条件**: 5分钟内错误率 > 5%

**严重级别**: Warning

**描述**: 系统错误率过高

### 慢响应告警 (SlowResponseTime)

**条件**: 95百分位响应时间 > 2秒

**严重级别**: Warning

**描述**: API响应时间过长

### 高CPU使用率告警 (HighCPUUsage)

**条件**: CPU使用率 > 80%

**严重级别**: Warning

**描述**: CPU使用率过高

### 高内存使用率告警 (HighMemoryUsage)

**条件**: 内存使用量 > 4GB

**严重级别**: Warning

**描述**: 内存使用量过高

### 数据库连接池耗尽告警 (DatabaseConnectionPoolExhaustion)

**条件**: 连接使用率 > 80%

**严重级别**: Warning

**描述**: 数据库连接池即将耗尽

### 慢数据库查询告警 (SlowDatabaseQueries)

**条件**: 95百分位查询时间 > 1秒

**严重级别**: Warning

**描述**: 数据库查询过慢

### 待审批过多告警 (HighPendingApprovals)

**条件**: 待审批数 > 100

**严重级别**: Warning

**描述**: 待审批任务过多

### Agent执行失败告警 (AgentExecutionFailure)

**条件**: 5分钟内失败率 > 10%

**严重级别**: Warning

**描述**: Agent执行失败率过高

### 工具调用失败告警 (ToolCallFailure)

**条件**: 5分钟内失败率 > 10%

**严重级别**: Warning

**描述**: 工具调用失败率过高

### LLM API失败告警 (LLMAPIFailure)

**条件**: 5分钟内失败率 > 5%

**严重级别**: Warning

**描述**: LLM API失败率过高

### 缓存命中率低告警 (LowCacheHitRate)

**条件**: 缓存命中率 < 50%

**严重级别**: Info

**描述**: 缓存命中率过低

### 服务不可用告警 (ServiceUnavailable)

**条件**: 服务离线 > 1分钟

**严重级别**: Critical

**描述**: X-Agent API服务不可用

### 工作流执行时间长告警 (HighWorkflowExecutionTime)

**条件**: 95百分位执行时间 > 300秒

**严重级别**: Warning

**描述**: 工作流执行时间过长

### 内存操作失败告警 (MemoryOperationFailure)

**条件**: 5分钟内失败率 > 5%

**严重级别**: Warning

**描述**: 内存操作失败率过高

### Langfuse API失败告警 (LangfuseAPIFailure)

**条件**: 5分钟内失败率 > 10%

**严重级别**: Warning

**描述**: Langfuse API失败率过高

## 健康检查端点

### Liveness Probe

```
GET /api/v1/health/live
```

返回服务是否运行中。

**响应示例**:
```json
{
  "status": "alive",
  "timestamp": "2024-01-01T12:00:00"
}
```

### Readiness Probe

```
GET /api/v1/health/ready
```

返回服务是否准备好处理请求。

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "checks": [
    {
      "name": "database",
      "status": "healthy",
      "message": "Database accessible",
      "latency_ms": 10.5
    }
  ]
}
```

### 详细健康检查

```
GET /api/v1/health/detailed
```

返回详细的健康检查信息和指标。

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "checks": [...],
  "metrics": {
    "total_checks": 4,
    "healthy_checks": 4,
    "degraded_checks": 0,
    "unhealthy_checks": 0
  }
}
```

## Prometheus指标端点

```
GET /api/v1/metrics/prometheus
```

返回Prometheus格式的指标。

## 告警处理

### 接收告警通知

告警通过以下渠道发送：

1. **Slack**: 配置 `SLACK_WEBHOOK_URL` 环境变量
2. **PagerDuty**: 配置 `PAGERDUTY_SERVICE_KEY` 环境变量

### 告警路由

告警根据严重级别和组件路由到不同的接收者：

- **Critical**: #xagent-critical + PagerDuty
- **Warning**: #xagent-warnings
- **API**: #api-team
- **Database**: #database-team
- **Agent**: #agent-team

### 告警抑制

系统实现了告警抑制规则：

- Critical告警会抑制同一实例的Warning告警
- Warning和Info告警会抑制同一实例的Info告警

## 配置

### 环境变量

```bash
# Slack通知
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# PagerDuty通知
PAGERDUTY_SERVICE_KEY=...

# Prometheus配置
PROMETHEUS_RETENTION=30d
PROMETHEUS_SCRAPE_INTERVAL=15s
```

### Prometheus配置

编辑 `deployment/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'xagent-api'
    static_configs:
      - targets: ['localhost:8000']
```

### Grafana配置

编辑 `deployment/grafana/provisioning/datasources.yml`:

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
```

## 故障排查

### Prometheus无法连接到X-Agent

1. 检查X-Agent是否运行: `curl http://localhost:8000/health/live`
2. 检查Prometheus配置: `cat deployment/prometheus/prometheus.yml`
3. 查看Prometheus日志: `docker logs xagent-prometheus`

### Grafana无法显示数据

1. 检查Prometheus数据源: Grafana → Configuration → Data Sources
2. 检查仪表板查询: 编辑仪表板 → 检查每个面板的查询
3. 查看Grafana日志: `docker logs xagent-grafana`

### 告警未发送

1. 检查AlertManager配置: `cat deployment/alertmanager/alertmanager.yml`
2. 检查Slack Webhook URL: `echo $SLACK_WEBHOOK_URL`
3. 查看AlertManager日志: `docker logs xagent-alertmanager`

### 指标缺失

1. 检查指标是否被记录: 在代码中搜索 `metrics_collector.record_*`
2. 检查Prometheus抓取: http://localhost:9090/targets
3. 检查指标名称: http://localhost:9090/api/v1/label/__name__/values

## 最佳实践

### 1. 定期检查仪表板

- 每天检查系统概览仪表板
- 关注错误率和响应时间趋势
- 及时响应告警

### 2. 调整告警阈值

- 根据实际情况调整告警阈值
- 避免过多的误报
- 定期审查告警规则

### 3. 保留历史数据

- 配置Prometheus数据保留期: 30天
- 定期备份Prometheus数据
- 分析历史趋势

### 4. 监控关键指标

- 错误率
- 响应时间
- 资源使用率
- 业务指标

### 5. 建立告警响应流程

- 定义告警严重级别
- 分配告警所有者
- 建立升级流程
- 记录告警处理过程

## 集成Langfuse

X-Agent监控系统与Langfuse集成，提供：

- 追踪事件记录
- 成本追踪
- 自定义指标

### 配置Langfuse

```python
from backend.app.services.observability.langfuse_client import langfuse_client

# 记录事件
langfuse_client.log("agent_execution", agent_id="agent-1", status="success")

# 记录指标
metrics_collector.record_langfuse_event("agent_execution")
```

## 性能优化

### 1. 减少指标基数

- 避免使用高基数标签
- 限制标签值的数量
- 使用标签聚合

### 2. 优化查询

- 使用预聚合指标
- 避免复杂的PromQL查询
- 使用记录规则

### 3. 管理存储

- 配置合适的保留期
- 使用数据压缩
- 定期清理过期数据

## 参考资源

- [Prometheus文档](https://prometheus.io/docs/)
- [Grafana文档](https://grafana.com/docs/)
- [AlertManager文档](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [PromQL查询语言](https://prometheus.io/docs/prometheus/latest/querying/basics/)
