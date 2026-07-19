# X-Agent 监控告警系统快速启动指南

## 概述

本指南帮助您快速启动和配置X-Agent的完整监控告警系统。

## 系统要求

- Docker & Docker Compose
- 8GB+ RAM
- 20GB+ 磁盘空间

## 快速启动

### 1. 启动监控栈

```bash
# 在项目根目录执行(compose 内挂载路径以 deployment/ 目录为基准, -f 调用时自动正确解析)
docker-compose -f deployment/docker-compose.monitoring.yml up -d
```

### 2. 验证服务

```bash
# 检查所有容器是否运行
docker-compose -f deployment/docker-compose.monitoring.yml ps

# 检查X-Agent健康状态
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
```

### 3. 访问仪表板

| 服务 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| Grafana | http://localhost:3000 | admin | admin |
| Prometheus | http://localhost:9090 | - | - |
| AlertManager | http://localhost:9093 | - | - |

## 配置告警通知

### Slack通知

1. 创建Slack Webhook:
   - 访问 https://api.slack.com/apps
   - 创建新应用
   - 启用 Incoming Webhooks
   - 复制Webhook URL

2. 配置环境变量:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
   ```

3. 重启AlertManager:
   ```bash
   docker-compose -f deployment/docker-compose.monitoring.yml restart alertmanager
   ```

### PagerDuty通知

1. 获取PagerDuty服务密钥
2. 配置环境变量:
   ```bash
   export PAGERDUTY_SERVICE_KEY="your-service-key"
   ```

## 关键指标

### 实时监控

访问Prometheus查询界面: http://localhost:9090

常用查询:

```promql
# 请求速率
rate(xagent_http_requests_total[5m])

# 错误率
increase(xagent_errors_total[5m]) / (increase(xagent_http_requests_total[5m]) + 1)

# 响应时间P95
histogram_quantile(0.95, rate(xagent_http_request_duration_seconds_bucket[5m]))

# CPU使用率
xagent_cpu_usage_percent

# 内存使用量
xagent_memory_usage_bytes
```

### 仪表板导航

1. **系统概览**: 整体系统健康状态
2. **API性能**: API端点性能分析
3. **Agent执行**: Agent和工具执行监控
4. **资源使用**: 系统资源监控
5. **错误监控**: 错误和失败监控

## 常见问题

### Q: 如何修改告警阈值?

A: 编辑 `deployment/prometheus/alerts.yml` 文件，修改相应告警规则的条件，然后重启Prometheus:

```bash
docker-compose -f deployment/docker-compose.monitoring.yml restart prometheus
```

### Q: 如何增加数据保留期?

A: 编辑 `docker-compose.monitoring.yml`，修改Prometheus命令参数:

```yaml
command:
  - '--storage.tsdb.retention.time=90d'  # 改为90天
```

### Q: 如何导出仪表板?

A: 在Grafana中:
1. 打开仪表板
2. 点击右上角菜单
3. 选择 "Share" → "Export"
4. 下载JSON文件

### Q: 如何备份Prometheus数据?

A: 使用Docker卷备份:

```bash
docker run --rm -v xagent-prometheus_prometheus_data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz -C /data .
```

## 性能优化

### 1. 减少指标基数

避免在标签中使用高基数值（如用户ID、请求ID等）。

### 2. 使用记录规则

在 `prometheus.yml` 中添加记录规则以预聚合指标:

```yaml
rule_files:
  - 'recording_rules.yml'
```

### 3. 调整抓取间隔

根据需求调整抓取间隔（默认15秒）:

```yaml
global:
  scrape_interval: 30s  # 增加到30秒
```

## 故障排查

### 检查Prometheus状态

```bash
# 查看Prometheus日志
docker logs xagent-prometheus

# 检查Prometheus配置
docker exec xagent-prometheus cat /etc/prometheus/prometheus.yml

# 检查抓取目标
curl http://localhost:9090/api/v1/targets
```

### 检查Grafana状态

```bash
# 查看Grafana日志
docker logs xagent-grafana

# 检查数据源连接
curl http://localhost:3000/api/datasources
```

### 检查AlertManager状态

```bash
# 查看AlertManager日志
docker logs xagent-alertmanager

# 检查告警规则
curl http://localhost:9090/api/v1/rules
```

## 生产部署

### 使用Kubernetes

参考 `templates/k8s-deployment.yaml` 进行Kubernetes部署。

### 使用Terraform

创建 `terraform/monitoring.tf`:

```hcl
resource "docker_container" "prometheus" {
  name  = "xagent-prometheus"
  image = "prom/prometheus:latest"
  
  ports {
    internal = 9090
    external = 9090
  }
  
  volumes {
    container_path = "/etc/prometheus"
    host_path      = "${path.module}/../deployment/prometheus"
  }
}
```

## 监控最佳实践

1. **定期检查仪表板**: 每天检查系统概览
2. **及时响应告警**: 建立告警响应流程
3. **调整告警阈值**: 根据实际情况优化
4. **保留历史数据**: 便于趋势分析
5. **定期备份**: 保护监控数据

## 获取帮助

- 查看完整文档: `docs/MONITORING.md`
- Prometheus文档: https://prometheus.io/docs/
- Grafana文档: https://grafana.com/docs/
- AlertManager文档: https://prometheus.io/docs/alerting/

## 许可证

MIT License
