# X-Agent 监控系统生产部署检查清单

## 部署前检查

### 1. 基础设施准备

- [ ] 服务器资源充足
  - [ ] CPU: 至少4核
  - [ ] 内存: 至少16GB
  - [ ] 磁盘: 至少100GB (用于日志和指标存储)
  - [ ] 网络: 稳定的网络连接

- [ ] Docker和Docker Compose已安装
  - [ ] Docker版本 >= 20.10
  - [ ] Docker Compose版本 >= 2.0

- [ ] 防火墙规则配置
  - [ ] 9090 (Prometheus)
  - [ ] 3000 (Grafana)
  - [ ] 9093 (AlertManager)
  - [ ] 5601 (Kibana)
  - [ ] 16686 (Jaeger)
  - [ ] 9200 (Elasticsearch)

### 2. 配置文件准备

- [ ] Prometheus配置文件已验证
  ```bash
  promtool check config monitoring/prometheus.yml
  ```

- [ ] AlertManager配置文件已验证
  ```bash
  amtool check-config monitoring/alertmanager.yml
  ```

- [ ] Logstash配置文件已验证
  ```bash
  logstash -f monitoring/elk/logstash.conf --dry-run
  ```

- [ ] 环境变量已配置
  - [ ] SLACK_WEBHOOK_URL (可选)
  - [ ] PAGERDUTY_SERVICE_KEY (可选)
  - [ ] ELASTICSEARCH_PASSWORD
  - [ ] JAEGER_HOST
  - [ ] JAEGER_PORT

### 3. 依赖项检查

- [ ] Python依赖已安装
  ```bash
  pip install prometheus-client opentelemetry-api opentelemetry-sdk
  pip install opentelemetry-exporter-jaeger opentelemetry-instrumentation-fastapi
  ```

- [ ] 所有必需的Python包已添加到requirements.txt

### 4. 应用集成检查

- [ ] FastAPI应用已集成Prometheus中间件（P0-04 backend 接线中，当前未生效）
- [ ] 日志配置已初始化
- [ ] Jaeger追踪已配置
- [ ] /api/v1/metrics/prometheus 端点已实现（/metrics 端点待 P0-04 接线）
- [ ] /health端点已实现
- [ ] /ready端点已实现

## 部署步骤

### 1. 启动监控栈

```bash
# 创建日志目录
mkdir -p /var/log/xagent
chmod 755 /var/log/xagent

# 启动所有监控服务
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# 验证所有服务已启动
docker-compose -f monitoring/docker-compose.monitoring.yml ps

# 查看日志
docker-compose -f monitoring/docker-compose.monitoring.yml logs -f
```

### 2. 验证服务健康状态

```bash
# Prometheus
curl http://localhost:9090/-/healthy

# Grafana
curl http://localhost:3000/api/health

# AlertManager
curl http://localhost:9093/-/healthy

# Elasticsearch
curl http://localhost:9200/_cluster/health

# Jaeger
curl http://localhost:16686/

# Kibana
curl http://localhost:5601/api/status
```

### 3. 配置Grafana

- [ ] 访问 http://localhost:3000
- [ ] 使用默认凭证登录 (admin/admin)
- [ ] 修改管理员密码
- [ ] 添加Prometheus数据源
- [ ] 导入仪表板
- [ ] 配置告警通知

### 4. 配置告警

- [ ] 配置Slack集成
- [ ] 配置PagerDuty集成 (可选)
- [ ] 测试告警规则
- [ ] 验证告警通知

### 5. 启动应用

```bash
# 启动X-Agent应用
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 或使用Docker
docker run -p 8000:8000 x-agent:latest
```

## 部署后验证

### 1. 指标收集验证

```bash
# 检查Prometheus目标
curl http://localhost:9090/api/v1/targets

# 查询指标（当前真实产出为 xagent_{name}_total 系列 gauge）
curl 'http://localhost:9090/api/v1/query?query=xagent_runs_total'

# 检查应用metrics端点
curl http://localhost:8000/api/v1/metrics/prometheus
```

### 2. 日志收集验证

```bash
# 检查Elasticsearch索引
curl http://localhost:9200/_cat/indices

# 查询日志
curl -X GET "localhost:9200/xagent-*/_search?size=10"

# 在Kibana中创建索引模式
# 访问 http://localhost:5601
# 创建索引模式: xagent-*
```

### 3. 追踪收集验证

```bash
# 检查Jaeger服务
curl http://localhost:16686/api/services

# 查看追踪
# 访问 http://localhost:16686
# 选择服务: x-agent
# 查看追踪列表
```

### 4. 告警验证

```bash
# 检查告警规则
curl http://localhost:9090/api/v1/rules

# 检查告警状态
curl http://localhost:9090/api/v1/alerts

# 测试告警
# 停止一个服务并观察告警
docker-compose -f monitoring/docker-compose.monitoring.yml stop postgres
```

## 生产环境配置

### 1. 安全性加固

```yaml
# Elasticsearch安全配置
xpack.security.enabled: true
xpack.security.enrollment.enabled: true

# Grafana安全配置
GF_SECURITY_ADMIN_PASSWORD: <strong_password>
GF_SECURITY_COOKIE_SECURE: true
GF_SECURITY_COOKIE_HTTPONLY: true

# Prometheus认证 (使用反向代理)
# 配置nginx或其他反向代理进行认证
```

### 2. 性能优化

```yaml
# Prometheus存储优化
--storage.tsdb.retention.time=30d
--storage.tsdb.retention.size=50GB

# Elasticsearch优化
ES_JAVA_OPTS: "-Xms2g -Xmx2g"
indices.memory.index_buffer_size: 40%

# Logstash优化
LS_JAVA_OPTS: "-Xmx1g -Xms1g"
pipeline.workers: 4
pipeline.batch.size: 1000
```

### 3. 高可用性配置

```yaml
# Prometheus高可用
# 使用Thanos进行长期存储和高可用

# Elasticsearch集群
discovery.type: multi-node
cluster.name: x-agent-cluster

# Grafana高可用
# 使用外部数据库存储配置
GF_DATABASE_TYPE: postgres
GF_DATABASE_HOST: postgres:5432
```

### 4. 备份策略

```bash
# Prometheus数据备份
docker exec x-agent-prometheus tar czf /prometheus/backup.tar.gz /prometheus/wal

# Elasticsearch备份
curl -X PUT "localhost:9200/_snapshot/backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backup"
  }
}'

# Grafana配置备份
docker exec x-agent-grafana tar czf /var/lib/grafana/backup.tar.gz /var/lib/grafana
```

## 监控和维护

### 1. 日常监控

- [ ] 检查磁盘使用情况
- [ ] 监控内存使用
- [ ] 检查网络连接
- [ ] 验证告警规则
- [ ] 查看应用日志

### 2. 定期维护

- [ ] 每周检查一次系统健康状态
- [ ] 每月清理过期日志
- [ ] 每季度更新依赖包
- [ ] 每半年进行一次灾难恢复演练

### 3. 性能调优

- [ ] 分析Prometheus查询性能
- [ ] 优化Elasticsearch索引
- [ ] 调整采样率
- [ ] 优化告警规则

## 故障排查

### 常见问题

#### 1. Prometheus无法连接到应用

```bash
# 检查应用是否运行
curl http://localhost:8000/health

# 检查metrics端点
curl http://localhost:8000/api/v1/metrics/prometheus

# 检查Prometheus配置
curl http://localhost:9090/api/v1/targets

# 查看Prometheus日志
docker logs x-agent-prometheus
```

#### 2. Elasticsearch连接失败

```bash
# 检查Elasticsearch状态
curl http://localhost:9200/_cluster/health

# 检查磁盘空间
curl http://localhost:9200/_cluster/allocation/explain

# 查看Elasticsearch日志
docker logs x-agent-elasticsearch
```

#### 3. Jaeger无法接收Span

```bash
# 检查Jaeger状态
curl http://localhost:14269/

# 检查服务列表
curl http://localhost:16686/api/services

# 查看Jaeger日志
docker logs x-agent-jaeger
```

#### 4. 告警未触发

```bash
# 检查告警规则
curl http://localhost:9090/api/v1/rules

# 检查告警状态
curl http://localhost:9090/api/v1/alerts

# 验证告警条件
# 手动查询指标确认条件是否满足
curl 'http://localhost:9090/api/v1/query?query=<alert_condition>'
```

## 回滚计划

### 1. 快速回滚

```bash
# 停止监控栈
docker-compose -f monitoring/docker-compose.monitoring.yml down

# 恢复应用到之前版本
docker pull x-agent:previous-version
docker run -p 8000:8000 x-agent:previous-version
```

### 2. 数据恢复

```bash
# 恢复Prometheus数据
docker cp backup.tar.gz x-agent-prometheus:/
docker exec x-agent-prometheus tar xzf /backup.tar.gz

# 恢复Elasticsearch数据
# 使用快照恢复功能
curl -X POST "localhost:9200/_snapshot/backup/snapshot_1/_restore"
```

## 联系和支持

- 文档: 参考 MONITORING_SETUP_GUIDE.md
- 示例: 参考 monitoring/INTEGRATION_EXAMPLES.md
- 问题报告: 提交GitHub Issue
- 社区支持: 参考项目README
