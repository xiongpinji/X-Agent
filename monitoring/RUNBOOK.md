# X-Agent 监控系统运维手册

## 目录

1. [系统概述](#系统概述)
2. [部署指南](#部署指南)
3. [配置管理](#配置管理)
4. [监控仪表板](#监控仪表板)
5. [告警管理](#告警管理)
6. [日志管理](#日志管理)
7. [分布式追踪](#分布式追踪)
8. [自动化运维](#自动化运维)
9. [故障排查](#故障排查)
10. [最佳实践](#最佳实践)

---

## 系统概述

X-Agent 监控系统是一个完整的可观测性解决方案，包括：

- **Prometheus**: 时间序列数据库和指标收集
- **Grafana**: 数据可视化和仪表板
- **AlertManager**: 告警管理和通知
- **ELK Stack**: 日志聚合和分析
- **Jaeger**: 分布式追踪
- **自动化脚本**: 自动扩缩容、重启、备份

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    X-Agent 应用                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  API Server  │  │   Worker     │  │   Services   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
           │                │                │
           ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    指标收集层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Prometheus   │  │ Node Exporter│  │ DB Exporter  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    存储和分析层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Prometheus   │  │ Elasticsearch│  │   Jaeger     │      │
│  │   Storage    │  │   Storage    │  │   Storage    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
           │                │                │
           ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    可视化和告警层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Grafana    │  │ AlertManager │  │   Kibana     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 部署指南

### 前置条件

- Docker 20.10+
- Docker Compose 2.0+
- 至少 8GB RAM
- 至少 50GB 磁盘空间

### 快速启动

```bash
# 1. 进入监控目录
cd monitoring

# 2. 启动所有监控服务
docker-compose up -d

# 3. 验证服务状态
docker-compose ps

# 4. 检查日志
docker-compose logs -f
```

### 访问地址

| 服务 | 地址 | 用户名 | 密码 |
|------|------|--------|------|
| Grafana | http://localhost:3000 | admin | admin |
| Prometheus | http://localhost:9090 | - | - |
| AlertManager | http://localhost:9093 | - | - |
| Kibana | http://localhost:5601 | - | - |
| Jaeger | http://localhost:16686 | - | - |

### 环境变量配置

创建 `.env` 文件：

```bash
# Elasticsearch
ELASTICSEARCH_HOST=elasticsearch
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=changeme

# Slack 通知
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# PagerDuty 集成
PAGERDUTY_SERVICE_KEY=your-service-key

# 邮件通知
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=alerts@xagent.com

# 告警邮箱
CRITICAL_ALERT_EMAIL=critical@example.com
WARNING_ALERT_EMAIL=warning@example.com

# 环境配置
ENVIRONMENT=production
CLUSTER_NAME=xagent-prod
```

---

## 配置管理

### Prometheus 配置

编辑 `prometheus.yml`：

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'x-agent-api'
    static_configs:
      - targets: ['localhost:8000']
    # 与 backend/app/api/metrics.py 实际挂载路径一致
    metrics_path: '/api/v1/metrics/prometheus'
    scrape_interval: 10s
```

### AlertManager 配置

编辑 `alertmanager.yml`：

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: '${SLACK_WEBHOOK_URL}'

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
```

### Grafana 数据源配置

1. 登录 Grafana (http://localhost:3000)
2. 进入 Configuration > Data Sources
3. 添加 Prometheus 数据源：
   - URL: http://prometheus:9090
   - Access: Server

---

## 监控仪表板

### 系统概览仪表板

显示整体系统健康状态：
- API 请求速率
- 错误率
- API 延迟百分位数
- 系统内存使用

**访问**: http://localhost:3000/d/xagent-overview

### 应用性能仪表板

显示应用层性能指标：
- 请求速率和延迟
- 错误率
- Agent/Tool/Workflow 成功率
- 缓存命中率

**访问**: http://localhost:3000/d/xagent-app-performance

### 数据库性能仪表板

显示数据库性能指标：
- 查询速率和延迟
- 连接池使用率
- 内存使用
- 操作速率

**访问**: http://localhost:3000/d/xagent-db-performance

### 业务指标仪表板

显示业务相关指标：
- 总运行数
- 完成的任务数
- 错误数
- 成功率

**访问**: http://localhost:3000/d/xagent-business-metrics

---

## 告警管理

### 告警规则

告警规则定义在 `alert_rules.yml` 中，包括：

| 告警名称 | 严重级别 | 阈值 | 持续时间 |
|---------|---------|------|---------|
| HighAPILatency | warning | P95 > 1s | 5m |
| CriticalAPILatency | critical | P99 > 5s | 2m |
| HighErrorRate | warning | > 5% | 5m |
| CriticalErrorRate | critical | > 10% | 2m |
| DatabaseDown | critical | 无响应 | 1m |
| HighMemoryUsage | warning | > 80% | 5m |
| CriticalMemoryUsage | critical | > 90% | 2m |

### 告警通知

告警通过以下渠道发送：

1. **Slack**: 实时通知到指定频道
2. **PagerDuty**: 关键告警触发 on-call
3. **Email**: 邮件通知
4. **OpsGenie**: 集成告警管理

### 告警响应流程

```
告警触发
    ↓
AlertManager 分组和去重
    ↓
根据严重级别路由
    ↓
发送通知 (Slack/Email/PagerDuty)
    ↓
运维人员响应
    ↓
问题解决
    ↓
告警解除
```

---

## 日志管理

### 日志收集

日志通过以下方式收集：

1. **文件输入**: `/var/log/xagent/*.log`
2. **TCP 输入**: 端口 5001
3. **HTTP 输入**: 端口 8080
4. **UDP 输入**: 端口 5002

### 日志索引

Elasticsearch 中的日志索引：

- `xagent-logs-*`: 所有应用日志
- `xagent-critical-*`: 关键错误日志
- `xagent-audit-*`: 审计日志

### 日志查询

在 Kibana 中查询日志：

```
# 查询所有错误日志
log_level: "ERROR"

# 查询特定用户的操作
user_id: "user123"

# 查询特定时间范围的日志
@timestamp: [2024-01-01 TO 2024-01-02]

# 查询特定服务的日志
service: "x-agent-api"
```

### 日志保留策略

- 应用日志: 30 天
- 关键错误日志: 90 天
- 审计日志: 1 年

---

## 分布式追踪

### Jaeger 配置

Jaeger 用于追踪分布式请求：

- **采样率**: 10% (可配置)
- **存储**: Elasticsearch
- **保留期**: 72 小时

### 查看追踪

1. 访问 Jaeger UI: http://localhost:16686
2. 选择服务: x-agent-api, x-agent-worker 等
3. 查看请求追踪和性能分析

### 追踪示例

```
请求 ID: abc123
├── x-agent-api (100ms)
│   ├── 认证 (5ms)
│   ├── 业务逻辑 (80ms)
│   │   ├── 数据库查询 (40ms)
│   │   ├── 缓存查询 (10ms)
│   │   └── 外部 API 调用 (30ms)
│   └── 响应序列化 (15ms)
└── 总耗时: 100ms
```

---

## 自动化运维

### 自动扩缩容

脚本: `scripts/autoscaling.sh`

```bash
# 启动自动扩缩容
./scripts/autoscaling.sh

# 配置参数
CPU_THRESHOLD=80          # CPU 使用率阈值
MEMORY_THRESHOLD=85       # 内存使用率阈值
MIN_REPLICAS=1            # 最小副本数
MAX_REPLICAS=5            # 最大副本数
SCALE_UP_COOLDOWN=300     # 扩容冷却时间 (秒)
SCALE_DOWN_COOLDOWN=600   # 缩容冷却时间 (秒)
```

### 自动重启

脚本: `scripts/autorestart.sh`

```bash
# 启动自动重启
./scripts/autorestart.sh

# 配置参数
CHECK_INTERVAL=30         # 检查间隔 (秒)
MAX_RETRIES=3             # 最大重试次数
RETRY_DELAY=10            # 重试延迟 (秒)
```

### 自动备份

脚本: `scripts/backup.sh`

```bash
# 执行备份
./scripts/backup.sh

# 配置参数
BACKUP_DIR=/backups/xagent    # 备份目录
RETENTION_DAYS=30             # 保留天数

# 备份内容
- PostgreSQL 数据库
- Redis 数据
- Qdrant 向量数据库
- 应用日志
- Elasticsearch 索引
```

### 定时任务

在 crontab 中配置定时任务：

```bash
# 每小时检查一次服务健康
0 * * * * /path/to/autorestart.sh

# 每天凌晨 2 点执行备份
0 2 * * * /path/to/backup.sh

# 每分钟检查一次资源使用
* * * * * /path/to/autoscaling.sh
```

---

## 故障排查

### 常见问题

#### 1. Prometheus 无法连接到目标

**症状**: Prometheus 中显示 "DOWN"

**解决方案**:
```bash
# 检查目标服务是否运行
docker-compose ps

# 检查网络连接
docker-compose exec prometheus curl http://x-agent-api:8000/api/v1/metrics/prometheus

# 查看 Prometheus 日志
docker-compose logs prometheus
```

#### 2. Grafana 仪表板无数据

**症状**: 仪表板显示 "No data"

**解决方案**:
```bash
# 检查 Prometheus 数据源
# 在 Grafana 中测试数据源连接

# 检查指标是否存在
curl http://localhost:9090/api/v1/query?query=xagent_api_requests_total

# 检查时间范围
# 确保选择的时间范围内有数据
```

#### 3. 告警未发送

**症状**: 告警触发但未收到通知

**解决方案**:
```bash
# 检查 AlertManager 状态
curl http://localhost:9093/api/v1/status

# 检查告警规则
curl http://localhost:9090/api/v1/rules

# 查看 AlertManager 日志
docker-compose logs alertmanager

# 检查通知配置 (Slack/Email)
# 验证 webhook URL 和凭证
```

#### 4. 日志未出现在 Kibana

**症状**: Kibana 中看不到日志

**解决方案**:
```bash
# 检查 Logstash 是否运行
docker-compose ps logstash

# 检查 Elasticsearch 连接
curl http://localhost:9200/_cluster/health

# 查看 Logstash 日志
docker-compose logs logstash

# 检查日志文件权限
ls -la /var/log/xagent/
```

### 性能优化

#### 1. 减少 Prometheus 存储占用

```yaml
# 在 prometheus.yml 中配置
global:
  retention: 15d  # 保留 15 天数据
```

#### 2. 优化 Elasticsearch 性能

```bash
# 调整分片数
curl -X PUT "localhost:9200/xagent-logs-*/_settings" -H 'Content-Type: application/json' -d'{
  "index": {
    "number_of_shards": 3,
    "number_of_replicas": 1
  }
}'
```

#### 3. 调整采样率

```yaml
# 在 jaeger-config.yml 中配置
sampling:
  type: "probabilistic"
  param: 0.05  # 5% 采样率
```

---

## 最佳实践

### 1. 告警配置

- ✅ 设置合理的阈值，避免告警疲劳
- ✅ 为每个告警配置 runbook
- ✅ 定期审查和调整告警规则
- ✅ 使用告警分级 (critical/warning/info)

### 2. 日志管理

- ✅ 使用结构化日志 (JSON 格式)
- ✅ 包含请求 ID 用于追踪
- ✅ 定期清理过期日志
- ✅ 设置日志级别 (DEBUG/INFO/WARN/ERROR)

### 3. 性能监控

- ✅ 监控关键业务指标
- ✅ 设置性能基线
- ✅ 定期分析性能趋势
- ✅ 及时发现性能瓶颈

### 4. 容量规划

- ✅ 监控磁盘使用率
- ✅ 监控内存使用率
- ✅ 定期评估扩容需求
- ✅ 提前规划容量增长

### 5. 安全性

- ✅ 限制 Grafana/Kibana 访问
- ✅ 使用强密码
- ✅ 启用 HTTPS
- ✅ 定期审计访问日志

---

## 联系和支持

- **文档**: https://wiki.example.com/xagent-monitoring
- **Slack**: #xagent-monitoring
- **邮件**: monitoring@example.com
- **On-Call**: 通过 PagerDuty

---

**最后更新**: 2024-01-15
**版本**: 1.0.0
