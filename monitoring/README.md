# X-Agent 监控系统

完整的生产级监控解决方案，包括指标收集、日志聚合、分布式追踪和告警管理。

## 快速开始

### 1. 启动监控栈

```bash
# 创建日志目录
mkdir -p /var/log/xagent

# 启动所有监控服务
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# 验证服务状态
docker-compose -f monitoring/docker-compose.monitoring.yml ps
```

### 2. 访问监控界面

| 服务 | URL | 说明 |
|------|-----|------|
| Prometheus | http://localhost:9090 | 指标存储和查询 |
| Grafana | http://localhost:3000 | 指标可视化 |
| Kibana | http://localhost:5601 | 日志可视化 |
| Jaeger | http://localhost:16686 | 分布式追踪 |
| AlertManager | http://localhost:9093 | 告警管理 |

### 3. 集成到应用

当前应用实际挂载的指标端点是 `GET /api/v1/metrics/prometheus`
（`backend/app/api/metrics.py`，已随 `main.py` 自动挂载，无需手动添加）。
下方 `/metrics` 示例对应 `PrometheusMiddleware` 方案，需 backend 侧完成
P0-04 接线后才生效：

```python
from fastapi import FastAPI
from backend.app.services.observability.monitoring_setup import setup_monitoring

app = FastAPI()

# 设置监控
setup_monitoring(app, db_engine)

# 添加metrics端点
@app.get("/metrics")
async def metrics():
    from prometheus_client import generate_latest
    return Response(generate_latest(), media_type="text/plain; charset=utf-8")
```

## 配置收敛状态（P0-04，2026-07-19）

- **权威 Prometheus 配置仅一套**：`monitoring/prometheus.yml`（即两个
  compose 文件挂载的同一份）。根目录 `prometheus.yml` 与原
  `monitoring/prometheus/` 目录已归档至 `monitoring/archive/`。
- **抓取路径已对齐代码真实产出**：`x-agent-api` 抓取
  `/api/v1/metrics/prometheus`，输出 `xagent_{runs,traces,memories,
  workflows,...}_total` 系列 gauge。
- **告警规则**：`alert_rules.yml` 中的 `xagent:api:*` 等表达式经
  `recording_rules.yml` 挂接，但其依赖的原始指标需 backend 侧
  P0-04 接线（`PrometheusMiddleware` + `/metrics`）后才真实产出；
  接线前录制规则类告警不触发，属预期。
- **金丝雀自动回滚判据当前无效，待指标补齐**：
  `deployment/canary/deploy-canary.sh` 的回滚判据引用
  `http_requests_total{version=...}` 与
  `http_request_duration_seconds_bucket{version=...}`，代码从未产生
  这些指标（真实指标为 `xagent_api_requests_total`，且无 `version`
  标签），查询结果恒为空、错误率恒被解析为 0，即**判据恒为"通过"，
  回滚保护实际不存在**。修复需在 backend 指标接线后改写判据
  （deployment/ 不在本次修复范围）。
- **已知待办**：`monitoring/docker-compose.monitoring.yml` 尚未挂载
  `recording_rules.yml`（compose 不在本次修复范围）；生产模式下抓取需
  `x-api-key` 认证头。

## 文件结构

```
monitoring/
├── README.md                          # 本文件
├── DEPLOYMENT_CHECKLIST.md            # 部署检查清单
├── INTEGRATION_EXAMPLES.md            # 集成示例
├── docker-compose.monitoring.yml      # Docker Compose配置
├── prometheus.yml                     # Prometheus配置
├── alert_rules.yml                    # 告警规则
├── alertmanager.yml                   # AlertManager配置
├── elk/
│   └── logstash.conf                  # Logstash配置
├── grafana/
│   └── provisioning/
│       ├── datasources.yml            # Grafana数据源
│       └── dashboards.yml             # Grafana仪表板
└── archive/                           # 已归档的旧配置（P0-04 收敛，勿直接使用）
    ├── root-prometheus.yml            # 原根目录 prometheus.yml
    └── prometheus/                    # 原 monitoring/prometheus/ 目录
        ├── prometheus.yml
        └── alerts.yml
```

## 核心组件

### Prometheus (指标收集)

- **端口**: 9090
- **功能**: 收集和存储时间序列指标
- **配置**: `monitoring/prometheus.yml`
- **保留期**: 30天
- **采样间隔**: 15秒

**关键指标**:
- HTTP请求数、延迟、大小
- 数据库查询性能
- Agent执行状态
- 工具执行情况
- 系统资源使用

### Grafana (可视化)

- **端口**: 3000
- **功能**: 指标可视化和仪表板
- **默认凭证**: admin/admin
- **数据源**: Prometheus

**预配置仪表板**:
- X-Agent概览
- API性能
- 数据库性能
- Agent执行
- 系统资源

### ELK Stack (日志管理)

#### Elasticsearch
- **端口**: 9200
- **功能**: 日志存储和索引
- **索引模式**: xagent-YYYY.MM.dd

#### Logstash
- **端口**: 5000-8080
- **功能**: 日志处理和转发
- **输入**: 文件、TCP、HTTP、Syslog
- **输出**: Elasticsearch

#### Kibana
- **端口**: 5601
- **功能**: 日志可视化和分析
- **索引**: xagent-*

### Jaeger (分布式追踪)

- **端口**: 16686 (UI), 6831 (UDP), 14268 (HTTP)
- **功能**: 分布式追踪和性能分析
- **采样率**: 可配置
- **存储**: 内存 (可配置为持久化)

### AlertManager (告警管理)

- **端口**: 9093
- **功能**: 告警路由和管理
- **通知**: Slack, PagerDuty, Email
- **配置**: `monitoring/alertmanager.yml`

## 关键指标

> 说明：以下为代码中已定义、待 P0-04 backend 接线（PrometheusMiddleware +
> /metrics）后产出的指标；当前已接线端点 /api/v1/metrics/prometheus 实际产出
> `xagent_{runs,traces,trace_events,memories,workflows,workflow_runs,
> workflow_schedules,audit_logs,api_keys,active_api_keys,approvals,
> pending_approvals}_total` 系列 gauge。

### API指标（待接线后产出）
```
xagent_api_requests_total{method, endpoint, status}
xagent_api_request_duration_seconds{method, endpoint}
xagent_api_request_size_bytes{method, endpoint}
xagent_api_response_size_bytes{method, endpoint}
```

### 错误指标（待接线后产出）
```
xagent_errors_total{error_type, severity}
xagent_agent_errors_total{error_type}
```

### 业务指标（待接线后产出）
```
xagent_agent_runs_total{status}
xagent_agent_run_duration_seconds
xagent_workflow_runs_total{status}
xagent_tool_executions_total{tool_name, status}
```

### 系统指标
```
xagent_db_query_duration_seconds{query_type, table}
xagent_db_connections_active
xagent_cache_hits_total{cache_name}
xagent_system_memory_usage_bytes
xagent_system_cpu_usage_percent
```

## 告警规则

### 关键告警

| 告警 | 条件 | 严重性 | 动作 |
|------|------|--------|------|
| HighAPILatency | P95 > 1s | Warning | Slack |
| CriticalAPILatency | P99 > 5s | Critical | Slack + PagerDuty |
| HighErrorRate | > 0.05 err/s | Warning | Slack |
| CriticalErrorRate | > 0.1 err/s | Critical | Slack + PagerDuty |
| DatabasePoolExhausted | > 90% | Critical | Slack + PagerDuty |
| HighAgentFailureRate | > 10% | Warning | Slack |
| HighMemoryUsage | > 8GB | Warning | Slack |
| CriticalMemoryUsage | > 15GB | Critical | Slack + PagerDuty |

## 日志配置

### 日志级别

- **DEBUG**: 详细调试信息
- **INFO**: 一般信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

### 日志文件

- **主日志**: `/var/log/xagent/xagent.log` (100MB, 10个备份)
- **错误日志**: `/var/log/xagent/xagent-errors.log` (50MB, 5个备份)
- **格式**: JSON

### 日志字段

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "xagent.api",
  "module": "workflows",
  "function": "create_workflow",
  "line": 42,
  "message": "Workflow created",
  "request_id": "req-123",
  "user_id": "user-456",
  "tenant_id": "tenant-789",
  "trace_id": "trace-abc",
  "span_id": "span-def"
}
```

## 分布式追踪

### 采样策略

```python
# 生产环境: 10%采样
sampler_config = {
    "type": "probabilistic",
    "param": 0.1,
}

# 开发环境: 100%采样
sampler_config = {
    "type": "const",
    "param": 1,
}
```

### 自定义Span

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("process_workflow") as span:
    span.set_attribute("workflow_id", workflow_id)
    span.set_attribute("user_id", user_id)
    # 处理逻辑
```

## 性能优化

### Prometheus优化

```yaml
# 增加scrape间隔
scrape_interval: 30s

# 配置远程存储
remote_write:
  - url: "http://remote-storage:9009/api/v1/push"
```

### Elasticsearch优化

```yaml
# 索引生命周期管理
PUT _ilm/policy/xagent-policy
{
  "phases": {
    "hot": {"min_age": "0d"},
    "delete": {"min_age": "30d"}
  }
}
```

### Jaeger优化

```python
# 远程采样
sampler_config = {
    "type": "remote",
    "samplingServerURL": "http://jaeger-agent:5778"
}
```

## 故障排查

### 常见问题

#### Prometheus无法连接应用
```bash
curl http://localhost:8000/api/v1/metrics/prometheus
curl http://localhost:9090/api/v1/targets
```

#### Elasticsearch连接失败
```bash
curl http://localhost:9200/_cluster/health
docker logs x-agent-elasticsearch
```

#### Jaeger无法接收Span
```bash
curl http://localhost:16686/api/services
docker logs x-agent-jaeger
```

#### 告警未触发
```bash
curl http://localhost:9090/api/v1/rules
curl http://localhost:9090/api/v1/alerts
```

## 生产部署

### 安全性

- [ ] 启用Elasticsearch认证
- [ ] 配置Grafana密码策略
- [ ] 启用HTTPS/TLS
- [ ] 配置网络隔离
- [ ] 设置防火墙规则

### 可靠性

- [ ] 配置备份策略
- [ ] 设置告警通知
- [ ] 配置高可用性
- [ ] 测试故障转移

### 合规性

- [ ] 配置日志保留期
- [ ] 启用审计追踪
- [ ] 配置数据加密
- [ ] 定期安全审查

## 参考资源

- [完整设置指南](MONITORING_SETUP_GUIDE.md)
- [部署检查清单](DEPLOYMENT_CHECKLIST.md)
- [集成示例](INTEGRATION_EXAMPLES.md)
- [Prometheus文档](https://prometheus.io/docs/)
- [Grafana文档](https://grafana.com/docs/)
- [Elasticsearch文档](https://www.elastic.co/guide/en/elasticsearch/reference/)
- [Jaeger文档](https://www.jaegertracing.io/docs/)

## 许可证

MIT License

## 支持

如有问题或建议，请提交GitHub Issue或联系开发团队。
