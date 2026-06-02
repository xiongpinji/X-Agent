# X-Agent 监控系统快速参考

## 快速启动

### 1. 部署监控系统

```bash
cd monitoring
bash deploy-monitoring.sh
```

### 2. 验证部署

```bash
bash verify-monitoring.sh
```

## 访问地址

| 服务 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| Prometheus | http://localhost:9090 | - | - |
| Grafana | http://localhost:3000 | admin | admin |
| Kibana | http://localhost:5601 | - | - |
| Jaeger | http://localhost:16686 | - | - |
| AlertManager | http://localhost:9093 | - | - |

## 常用命令

### 查看服务状态

```bash
docker-compose -f monitoring/docker-compose.monitoring.yml ps
```

### 查看日志

```bash
# 所有服务
docker-compose -f monitoring/docker-compose.monitoring.yml logs -f

# 特定服务
docker-compose -f monitoring/docker-compose.monitoring.yml logs -f prometheus
```

### 停止/启动服务

```bash
# 停止
docker-compose -f monitoring/docker-compose.monitoring.yml down

# 启动
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# 重启特定服务
docker-compose -f monitoring/docker-compose.monitoring.yml restart prometheus
```

## 关键指标

### API 指标

- `xagent_api_requests_total` - 总请求数
- `xagent_api_request_duration_seconds` - 请求延迟
- `xagent_errors_total` - 总错误数

### Agent 指标

- `xagent_agent_runs_total` - Agent 运行总数
- `xagent_agent_run_duration_seconds` - Agent 运行时长

### 数据库指标

- `xagent_db_query_duration_seconds` - 查询延迟
- `xagent_db_connections_active` - 活跃连接数

### 缓存指标

- `xagent_cache_hits_total` - 缓存命中数
- `xagent_cache_misses_total` - 缓存未命中数

## 告警规则

### 关键告警

| 告警 | 条件 | 严重级别 |
|------|------|---------|
| HighAPILatency | P95 > 1000ms | warning |
| CriticalAPILatency | P99 > 5000ms | critical |
| HighErrorRate | 错误率 > 5% | warning |
| CriticalErrorRate | 错误率 > 10% | critical |
| HighMemoryUsage | 内存 > 8GB | warning |
| CriticalMemoryUsage | 内存 > 15GB | critical |

## 应用集成

### 基础集成

```python
from backend.app.monitoring_integration import setup_monitoring

# 初始化
metrics, tracing, health_checker = setup_monitoring(app)

# 添加端点
@app.get("/metrics")
async def prometheus_metrics():
    return Response(metrics.get_metrics(), media_type="text/plain")

@app.get("/health")
async def health():
    return await health_checker.check_health()
```

### 记录指标

```python
from backend.app.monitoring_integration import record_metric

# 计数器
record_metric(metrics.agent_runs_total, labels={"status": "success"})

# 直方图
record_metric(metrics.agent_run_duration_seconds, value=duration)

# 仪表
record_metric(metrics.db_connections_active, value=count)
```

### 分布式追踪

```python
tracer = tracing.get_tracer()

with tracer.start_as_current_span("operation_name") as span:
    span.set_attribute("key", "value")
    # 执行操作
```

## 故障排查

### 服务无法启动

```bash
# 查看日志
docker logs x-agent-prometheus

# 检查配置
docker-compose -f monitoring/docker-compose.monitoring.yml config

# 检查端口
netstat -tuln | grep LISTEN
```

### Prometheus 无法连接目标

```bash
# 检查应用
curl http://localhost:8000/metrics

# 检查网络
docker exec x-agent-prometheus curl http://x-agent-api:8000/metrics

# 查看目标状态
curl http://localhost:9090/api/v1/targets
```

### Elasticsearch 磁盘满

```bash
# 检查磁盘
df -h

# 删除旧索引
curl -X DELETE http://localhost:9200/xagent-2026.05.01

# 清理日志
docker exec x-agent-elasticsearch curl -X PUT http://localhost:9200/_all/_settings \
  -H 'Content-Type: application/json' \
  -d '{"index.blocks.read_only_allow_delete": null}'
```

## 性能优化

### 减少指标开销

```python
# 采样指标
import random
if random.random() < 0.1:  # 10% 采样率
    record_metric(metrics.api_request_duration_seconds, value=duration)
```

### 调整保留期

```yaml
# prometheus.yml
--storage.tsdb.retention.time=7d  # 改为 7 天
```

## 备份

### 备份数据

```bash
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Prometheus
docker run --rm -v x-agent-prometheus_data:/data -v $BACKUP_DIR:/backup \
  busybox tar czf /backup/prometheus-$TIMESTAMP.tar.gz -C /data .

# Elasticsearch
docker run --rm -v x-agent-elasticsearch_data:/data -v $BACKUP_DIR:/backup \
  busybox tar czf /backup/elasticsearch-$TIMESTAMP.tar.gz -C /data .
```

### 恢复数据

```bash
#!/bin/bash
BACKUP_FILE=$1

# 停止服务
docker-compose -f monitoring/docker-compose.monitoring.yml down

# 恢复
docker run --rm -v x-agent-prometheus_data:/data -v /backups:/backup \
  busybox tar xzf /backup/$BACKUP_FILE -C /data

# 启动
docker-compose -f monitoring/docker-compose.monitoring.yml up -d
```

## 安全建议

### 更改默认密码

```bash
# Grafana
curl -X PUT http://localhost:3000/api/admin/users/1/password \
  -H 'Content-Type: application/json' \
  -d '{"password":"new-password"}'
```

### 启用 HTTPS

```yaml
# docker-compose.monitoring.yml
environment:
  - GF_SERVER_PROTOCOL=https
  - GF_SERVER_CERT_FILE=/etc/grafana/certs/cert.pem
  - GF_SERVER_CERT_KEY=/etc/grafana/certs/key.pem
```

### 限制网络访问

```bash
# 仅本地访问
docker run -p 127.0.0.1:9090:9090 prom/prometheus
```

## 文档链接

- [完整部署指南](./MONITORING_DEPLOYMENT_COMPLETE.md)
- [集成示例](./INTEGRATION_EXAMPLES.md)
- [Prometheus 文档](https://prometheus.io/docs/)
- [Grafana 文档](https://grafana.com/docs/)
- [Elasticsearch 文档](https://www.elastic.co/guide/)
- [Jaeger 文档](https://www.jaegertracing.io/docs/)

## 获取帮助

遇到问题？查看以下资源：

1. 查看服务日志：`docker-compose logs -f <service>`
2. 检查配置文件：`monitoring/*.yml`
3. 查看完整部署指南：`MONITORING_DEPLOYMENT_COMPLETE.md`
4. 查看集成示例：`INTEGRATION_EXAMPLES.md`

---

**最后更新**: 2026-05-27
