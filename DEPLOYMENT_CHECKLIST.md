# X-Agent Production Deployment Checklist

## Deployment Overview

This document defines the complete deployment process for X-Agent production environment, including pre-deployment checks, deployment steps, monitoring metrics, and rollback procedures.

**Deployment Version**: 1.0.0  
**Release Date**: 2026-05-27  
**Estimated Deployment Time**: 1-2 hours (including verification)

---

## 1. Pre-Deployment Checklist

### 1.1 Infrastructure Checks

- [ ] **Database**
  - [ ] PostgreSQL 16+ installed and running
  - [ ] Database connection verified
  - [ ] Full backup completed
  - [ ] Backup verified and tested
  - [ ] Sufficient disk space (minimum 50GB available)
  - [ ] Backup retention policy configured

- [ ] **Cache Layer**
  - [ ] Redis 7+ installed and running
  - [ ] Redis connection verified
  - [ ] Sufficient memory (minimum 4GB)
  - [ ] Persistence enabled
  - [ ] Password configured

- [ ] **Message Queue**
  - [ ] Celery workers running normally
  - [ ] Queue connection verified
  - [ ] Pending tasks queue cleared
  - [ ] Worker concurrency configured

- [ ] **Vector Database**
  - [ ] Qdrant installed and running
  - [ ] Qdrant connection verified
  - [ ] Sufficient storage space
  - [ ] API key configured

- [ ] **Graph Database**
  - [ ] Neo4j installed and running
  - [ ] Neo4j connection verified
  - [ ] Authentication credentials correct
  - [ ] Sufficient memory allocated

### 1.2 Application Checks

- [ ] **Code Review**
  - [ ] Code reviewed and approved
  - [ ] All tests passing (unit, integration, e2e)
  - [ ] Code coverage >= 85%
  - [ ] Security scan passed
  - [ ] Linting passed (ruff, mypy)

- [ ] **Configuration**
  - [ ] All environment variables configured
  - [ ] Secrets configured and verified
  - [ ] Database migrations prepared
  - [ ] Configuration files reviewed

- [ ] **Documentation**
  - [ ] Deployment guide reviewed
  - [ ] Operations manual reviewed
  - [ ] Runbooks prepared
  - [ ] Troubleshooting guide available

### 1.3 Docker/Kubernetes Checks

- [ ] **Docker**
  - [ ] Docker installed (version 20.10+)
  - [ ] Docker daemon running
  - [ ] Sufficient disk space for images
  - [ ] Registry credentials configured

- [ ] **Kubernetes** (if applicable)
  - [ ] Kubernetes cluster accessible
  - [ ] kubectl configured correctly
  - [ ] Cluster resources sufficient
  - [ ] Namespace created
  - [ ] RBAC configured

- [ ] **Helm** (if applicable)
  - [ ] Helm installed (version 3.0+)
  - [ ] Helm chart validated
  - [ ] Values files reviewed
  - [ ] Secrets configured

### 1.4 Monitoring & Logging

- [ ] **Monitoring**
  - [ ] Prometheus configured
  - [ ] Grafana dashboards prepared
  - [ ] Alert rules configured
  - [ ] Notification channels tested

- [ ] **Logging**
  - [ ] Log aggregation configured
  - [ ] Log retention policy set
  - [ ] Log levels configured
  - [ ] Log rotation configured

### 1.5 Security Checks

- [ ] **Secrets Management**
  - [ ] All default passwords changed
  - [ ] Strong random keys generated
  - [ ] Secrets stored securely
  - [ ] Access controls configured

- [ ] **Network Security**
  - [ ] TLS/SSL certificates configured
  - [ ] Firewall rules configured
  - [ ] Network policies configured
  - [ ] Ingress configured

- [ ] **Access Control**
  - [ ] RBAC configured
  - [ ] User permissions verified
  - [ ] API keys configured
  - [ ] Authentication tested

## 2. Pre-Deployment Verification

### 2.1 Run Pre-Deployment Checklist Script

```bash
./deployment/scripts/pre-deployment-checklist.sh
```

Expected output:
- All system checks passed
- All configuration files present
- No default secrets found
- Sufficient resources available

### 2.2 Verify Database

```bash
# Docker Compose
docker-compose exec postgres pg_isready -U xagent

# Kubernetes
kubectl exec -it deployment/postgres -n xagent -- pg_isready -U xagent
```

### 2.3 Verify Redis

```bash
# Docker Compose
docker-compose exec redis redis-cli ping

# Kubernetes
kubectl exec -it deployment/redis -n xagent -- redis-cli ping
```

### 2.4 Verify Qdrant

```bash
# Docker Compose
curl http://localhost:6333/health

# Kubernetes
kubectl exec -it deployment/qdrant -n xagent -- curl http://localhost:6333/health
```

### 2.5 Verify Neo4j

```bash
# Docker Compose
curl http://localhost:7474

# Kubernetes
kubectl exec -it deployment/neo4j -n xagent -- curl http://localhost:7474
```

## 3. Deployment Steps

### 3.1 Docker Compose Deployment

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit environment variables
nano .env

# 3. Start services
docker-compose up -d

# 4. Check status
docker-compose ps

# 5. View logs
docker-compose logs -f xagent-api

# 6. Run migrations
docker-compose exec xagent-api alembic upgrade head

# 7. Verify health
curl http://localhost:8000/health
```

### 3.2 Kubernetes Manual Deployment

```bash
# 1. Create namespace
kubectl create namespace xagent

# 2. Create secrets
kubectl create secret generic xagent-secrets \
  --from-literal=DB_PASSWORD=secure_password \
  --from-literal=REDIS_PASSWORD=secure_password \
  --from-literal=QDRANT_API_KEY=secure_key \
  --from-literal=NEO4J_PASSWORD=secure_password \
  --from-literal=SECRET_KEY=secure_secret_key \
  -n xagent

# 3. Apply configurations
kubectl apply -f deployment/k8s/

# 4. Check status
kubectl get pods -n xagent

# 5. Run migrations
kubectl exec -it deployment/xagent-api -n xagent -- alembic upgrade head

# 6. Verify health
kubectl exec -it deployment/xagent-api -n xagent -- curl http://localhost:8000/health
```

### 3.3 Helm Deployment

```bash
# 1. Create namespace
kubectl create namespace xagent

# 2. Deploy with Helm
helm install xagent deployment/helm \
  --namespace xagent \
  --values deployment/helm/values-production.yaml

# 3. Check status
helm status xagent -n xagent

# 4. Verify pods
kubectl get pods -n xagent

# 5. Run migrations
kubectl exec -it deployment/xagent-api -n xagent -- alembic upgrade head

# 6. Verify health
kubectl exec -it deployment/xagent-api -n xagent -- curl http://localhost:8000/health
```

## 4. Post-Deployment Verification

### 4.1 Service Health Checks

- [ ] API server responding to health checks
- [ ] Database connections established
- [ ] Redis cache operational
- [ ] Qdrant vector database operational
- [ ] Neo4j graph database operational
- [ ] Celery workers processing tasks
- [ ] Celery beat scheduler running

### 4.2 Functional Tests

- [ ] API endpoints responding correctly
- [ ] Database queries working
- [ ] Cache operations working
- [ ] Background tasks processing
- [ ] Scheduled tasks running
- [ ] Error handling working

### 4.3 Performance Tests

- [ ] API response time acceptable (< 1s p95)
- [ ] Database query performance acceptable
- [ ] Memory usage within limits
- [ ] CPU usage within limits
- [ ] Disk I/O acceptable

### 4.4 Monitoring Verification

- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards displaying data
- [ ] Alerts configured and working
- [ ] Logs being collected
- [ ] Traces being recorded

## 5. Monitoring Metrics

### 5.1 Key Performance Indicators

- **API Response Time**: p95 < 1 second
- **Error Rate**: < 0.1%
- **Availability**: > 99.9%
- **Database Connections**: < 80% of max
- **Memory Usage**: < 80% of limit
- **CPU Usage**: < 70% of limit
- **Disk Usage**: < 80% of capacity

### 5.2 Alert Thresholds

- **High Error Rate**: > 5% for 5 minutes
- **High Latency**: p95 > 1 second for 5 minutes
- **Database Connection Pool Exhausted**: >= max connections
- **Redis Memory High**: > 90% of max
- **Disk Space Low**: < 10% available
- **Pod Restart**: > 3 restarts in 1 hour

### 5.3 Monitoring Commands

```bash
# Check pod status
kubectl get pods -n xagent

# Check resource usage
kubectl top pods -n xagent
kubectl top nodes

# Check logs
kubectl logs -f deployment/xagent-api -n xagent

# Check events
kubectl get events -n xagent

# Check HPA status
kubectl get hpa -n xagent
```

## 6. Rollback Procedures

### 6.1 Immediate Rollback (if critical issues)

```bash
# Docker Compose
docker-compose down
# Restore from backup
docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql
docker-compose up -d

# Kubernetes
helm rollback xagent -n xagent

# Verify
kubectl get pods -n xagent
```

### 6.2 Gradual Rollback (if issues detected)

```bash
# Check current revision
helm history xagent -n xagent

# Rollback to previous version
helm rollback xagent 1 -n xagent

# Verify
kubectl rollout status deployment/xagent-api -n xagent
```

### 6.3 Database Rollback

```bash
# Restore from backup
docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql

# Or using Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  psql -U xagent xagent_db < backup.sql

# Verify
docker-compose exec postgres pg_isready -U xagent
```

## 7. Post-Deployment Tasks

### 7.1 Documentation

- [ ] Update deployment documentation
- [ ] Document any configuration changes
- [ ] Update runbooks
- [ ] Update troubleshooting guide

### 7.2 Communication

- [ ] Notify stakeholders of successful deployment
- [ ] Update status page
- [ ] Send deployment summary
- [ ] Schedule post-deployment review

### 7.3 Monitoring

- [ ] Monitor metrics for 24 hours
- [ ] Check for any anomalies
- [ ] Review logs for errors
- [ ] Verify backup completion

### 7.4 Optimization

- [ ] Review performance metrics
- [ ] Identify optimization opportunities
- [ ] Plan capacity upgrades if needed
- [ ] Schedule performance review

## 8. Troubleshooting

### 8.1 API Not Responding

```bash
# Check pod status
kubectl get pods -n xagent -l app=xagent-api

# Check logs
kubectl logs deployment/xagent-api -n xagent

# Check health
kubectl exec -it deployment/xagent-api -n xagent -- curl http://localhost:8000/health

# Restart pod
kubectl rollout restart deployment/xagent-api -n xagent
```

### 8.2 Database Connection Failed

```bash
# Check database pod
kubectl get pods -n xagent -l app=postgres

# Check database logs
kubectl logs deployment/postgres -n xagent

# Test connection
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -d xagent_db -c "SELECT 1"

# Check connection pool
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -c "SELECT count(*) FROM pg_stat_activity"
```

### 8.3 High Memory Usage

```bash
# Check memory usage
kubectl top pods -n xagent

# Check pod details
kubectl describe pod <pod-name> -n xagent

# Check resource limits
kubectl get deployment xagent-api -n xagent -o yaml | grep -A 5 resources

# Restart pod
kubectl rollout restart deployment/xagent-api -n xagent
```

### 8.4 Slow Queries

```bash
# Check slow query log
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -c "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10"

# Analyze query
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -c "EXPLAIN ANALYZE SELECT ..."

# Create index if needed
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -c "CREATE INDEX idx_name ON table(column)"
```

## 9. Sign-Off

### 9.1 Deployment Team

- [ ] Deployment Engineer: _________________ Date: _______
- [ ] QA Lead: _________________ Date: _______
- [ ] Operations Lead: _________________ Date: _______

### 9.2 Stakeholders

- [ ] Product Manager: _________________ Date: _______
- [ ] Engineering Lead: _________________ Date: _______
- [ ] DevOps Lead: _________________ Date: _______

## 10. Appendix

### 10.1 Useful Commands

```bash
# Docker Compose
docker-compose ps                    # Check service status
docker-compose logs -f               # View logs
docker-compose exec <service> bash   # Access container
docker-compose restart <service>     # Restart service
docker-compose down                  # Stop all services

# Kubernetes
kubectl get pods -n xagent           # List pods
kubectl logs deployment/xagent-api   # View logs
kubectl exec -it pod-name bash       # Access pod
kubectl rollout restart deployment   # Restart deployment
kubectl delete pod pod-name          # Delete pod

# Helm
helm list -n xagent                  # List releases
helm status xagent -n xagent         # Check status
helm upgrade xagent ...              # Upgrade release
helm rollback xagent                 # Rollback release
helm uninstall xagent -n xagent      # Uninstall release
```

### 10.2 Important Files

- Deployment Guide: `docs/DEPLOYMENT.md`
- Operations Manual: `docs/OPERATIONS.md`
- Environment Config: `deployment/env/README.md`
- Deployment Summary: `DEPLOYMENT_SUMMARY.md`

### 10.3 Contact Information

- **On-Call**: [Contact Information]
- **Escalation**: [Escalation Procedure]
- **Support**: [Support Channels]

---

**Last Updated**: 2026-05-27
**Version**: 1.0.0
**Status**: Ready for Production Deployment

  - [ ] 安全审查完成
  - [ ] 性能基准测试完成

- [ ] **依赖检查**
  - [ ] 所有依赖已更新
  - [ ] 依赖安全审计通过
  - [ ] 许可证合规性检查通过
  - [ ] 版本兼容性验证完成

- [ ] **配置检查**
  - [ ] 环境变量已配置
  - [ ] 特性开关已配置
  - [ ] 日志级别已设置
  - [ ] 监控告警已配置

### 1.3 团队准备

- [ ] **人员**
  - [ ] 部署负责人已确认
  - [ ] 技术支持团队已待命
  - [ ] 运维团队已准备
  - [ ] 产品团队已通知

- [ ] **文档**
  - [ ] 部署指南已准备
  - [ ] 回滚流程已文档化
  - [ ] 故障排查指南已准备
  - [ ] 监控仪表板已配置

- [ ] **沟通**
  - [ ] 用户已通知维护窗口
  - [ ] 内部团队已通知
  - [ ] 客户支持已准备
  - [ ] 状态页面已更新

---

## 2. 部署步骤

### 2.1 部署前准备（T-1 小时）

```bash
# 1. 创建部署快照
./scripts/create_deployment_snapshot.sh

# 2. 验证所有服务健康状态
./scripts/health_check.sh

# 3. 备份数据库
pg_dump -h localhost -U xagent xagent > backup_$(date +%Y%m%d_%H%M%S).sql

# 4. 备份 Redis
redis-cli BGSAVE

# 5. 备份 Qdrant
# 通过 Qdrant API 导出快照
curl -X POST http://localhost:6333/snapshots
```

### 2.2 部署执行（T 时刻）

#### 阶段 1: 代码部署

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行数据库迁移
alembic upgrade head

# 4. 构建 Docker 镜像
docker build -t xagent:v2 .

# 5. 推送镜像到仓库
docker push xagent:v2
```

#### 阶段 2: 服务更新

```bash
# 1. 更新后端服务
docker-compose up -d backend

# 2. 等待服务启动
sleep 30

# 3. 验证服务健康
curl http://localhost:8000/health

# 4. 检查日志
docker-compose logs -f backend
```

#### 阶段 3: 特性开关启用

```bash
# 1. 启用 Agent V2 特性开关（初始 10% 灰度）
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rollout_percentage": 10
  }'

# 2. 验证特性开关状态
curl http://localhost:8000/admin/feature-flags/use_agent_v2
```

### 2.3 灰度发布（T+5 分钟 到 T+2 小时）

使用自动化部署脚本进行灰度发布：

```bash
# 运行自动化部署脚本
python scripts/deploy_agent_v2.py

# 脚本将自动执行：
# - 健康检查
# - 数据库迁移
# - 10% -> 25% -> 50% -> 75% -> 100% 灰度发布
# - 每个阶段监控 5 分钟
# - 错误率超过 5% 时自动回滚
```

### 2.4 部署后验证（T+2 小时）

```bash
# 1. 验证所有服务运行正常
./scripts/health_check.sh

# 2. 检查错误日志
docker-compose logs backend | grep ERROR

# 3. 验证数据库连接
psql -h localhost -U xagent -d xagent -c "SELECT version();"

# 4. 验证 Agent V2 执行
curl -X POST http://localhost:8000/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "test task",
    "context": {}
  }'

# 5. 检查执行指标
curl http://localhost:8000/admin/metrics/execution
```

---

## 3. 监控指标

### 3.1 关键性能指标（KPI）

| 指标 | 目标 | 告警阈值 |
|------|------|---------|
| API 响应时间 (p95) | < 500ms | > 1000ms |
| Agent V2 错误率 | < 1% | > 5% |
| 数据库连接池使用率 | < 70% | > 90% |
| Redis 内存使用率 | < 70% | > 85% |
| 消息队列延迟 | < 1s | > 5s |
| 向量数据库查询时间 | < 100ms | > 500ms |

### 3.2 监控指标定义

#### 执行指标
- `v1_executions`: Agent V1 执行次数
- `v2_executions`: Agent V2 执行次数
- `v1_errors`: Agent V1 错误次数
- `v2_errors`: Agent V2 错误次数
- `error_rate_v2`: Agent V2 错误率 (%)

#### 性能指标
- `execution_time_p50`: 执行时间中位数
- `execution_time_p95`: 执行时间 95 分位数
- `execution_time_p99`: 执行时间 99 分位数
- `memory_usage`: 内存使用量
- `cpu_usage`: CPU 使用率

#### 业务指标
- `successful_tasks`: 成功任务数
- `failed_tasks`: 失败任务数
- `avg_task_duration`: 平均任务耗时
- `user_satisfaction`: 用户满意度

### 3.3 告警规则

```yaml
# Prometheus 告警规则示例
groups:
  - name: agent_v2_deployment
    rules:
      - alert: AgentV2ErrorRateHigh
        expr: rate(agent_v2_errors[5m]) / rate(agent_v2_executions[5m]) > 0.05
        for: 5m
        annotations:
          summary: "Agent V2 错误率过高"
          description: "Agent V2 错误率: {{ $value | humanizePercentage }}"

      - alert: APIResponseTimeHigh
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "API 响应时间过长"
          description: "P95 响应时间: {{ $value }}s"

      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_usage > 0.9
        for: 5m
        annotations:
          summary: "数据库连接池即将耗尽"
          description: "连接池使用率: {{ $value | humanizePercentage }}"
```

### 3.4 日志记录配置

```python
# 日志级别配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "logs/agent_v2.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
        },
    },
    "loggers": {
        "backend.app.core.agent_v2": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
        "backend.app.core.feature_flags": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
    },
}
```

---

## 4. 回滚计划

### 4.1 自动回滚触发条件

以下任何条件满足时，系统将自动回滚到 Agent V1：

1. **错误率过高**: Agent V2 错误率 > 5% 持续 5 分钟
2. **性能下降**: API 响应时间 p95 > 1000ms 持续 5 分钟
3. **资源耗尽**: 数据库连接池使用率 > 90%
4. **服务不可用**: 健康检查失败 3 次连续失败

### 4.2 手动回滚步骤

#### 步骤 1: 禁用 Agent V2

```bash
# 立即禁用 Agent V2 特性开关
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false,
    "rollout_percentage": 0
  }'

# 验证特性开关已禁用
curl http://localhost:8000/admin/feature-flags/use_agent_v2
```

#### 步骤 2: 验证回滚

```bash
# 检查所有请求都路由到 Agent V1
curl http://localhost:8000/admin/metrics/execution

# 验证错误率下降
curl http://localhost:8000/admin/metrics/errors
```

#### 步骤 3: 恢复数据（如需要）

```bash
# 如果数据被破坏，从备份恢复
psql -h localhost -U xagent xagent < backup_YYYYMMDD_HHMMSS.sql

# 重启 Redis
redis-cli FLUSHALL
redis-cli BGSAVE
```

#### 步骤 4: 验证系统恢复

```bash
# 运行完整的健康检查
./scripts/health_check.sh

# 验证所有服务正常
docker-compose ps

# 检查日志中是否有错误
docker-compose logs backend | grep ERROR
```

### 4.3 回滚后分析

1. **收集日志和指标**
   ```bash
   # 导出部署期间的日志
   docker-compose logs backend > deployment_logs.txt
   
   # 导出指标数据
   curl http://localhost:8000/admin/metrics/all > metrics.json
   ```

2. **根本原因分析**
   - 分析错误日志
   - 检查性能指标
   - 审查代码变更
   - 识别问题根源

3. **修复和重新部署**
   - 修复识别的问题
   - 运行完整的测试套件
   - 计划新的部署

---

## 5. 部署验证清单

### 5.1 功能验证

- [ ] Agent V2 能够执行基本任务
- [ ] Agent V2 能够处理错误
- [ ] Agent V2 能够访问所有必需的工具
- [ ] Agent V2 能够正确记录执行跟踪
- [ ] Agent V2 能够正确存储执行结果

### 5.2 性能验证

- [ ] 执行时间在预期范围内
- [ ] 内存使用在预期范围内
- [ ] CPU 使用在预期范围内
- [ ] 数据库查询性能正常
- [ ] 缓存命中率正常

### 5.3 兼容性验证

- [ ] Agent V1 和 V2 可以共存
- [ ] 特性开关正确路由请求
- [ ] 灰度发布按预期工作
- [ ] 回滚机制正常工作

### 5.4 安全验证

- [ ] 认证和授权正常工作
- [ ] 敏感数据已加密
- [ ] 审计日志正确记录
- [ ] 没有安全漏洞

---

## 6. 部署后支持

### 6.1 监控和告警

- 部署后 24 小时内持续监控
- 设置告警通知（邮件、Slack、钉钉）
- 每小时检查一次关键指标
- 准备应急响应团队

### 6.2 用户沟通

- 发送部署完成通知
- 提供新功能文档
- 收集用户反馈
- 解决用户问题

### 6.3 文档更新

- 更新运维文档
- 更新故障排查指南
- 更新监控仪表板
- 记录部署经验

---

## 7. 附录

### 7.1 环境变量

```bash
# Agent V2 特定环境变量
AGENT_V2_ENABLED=true
AGENT_V2_ROLLOUT_PERCENTAGE=10
AGENT_V2_MAX_ITERATIONS=4
AGENT_V2_TIMEOUT_SECONDS=300

# 特性开关
USE_AGENT_V2=true
ENABLE_MEMORY_GRAPH=true
ENABLE_ADVANCED_PLANNING=false
ENABLE_AUTO_RECOVERY=false
```

### 7.2 有用的命令

```bash
# 查看部署状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 进入容器
docker-compose exec backend bash

# 运行数据库迁移
docker-compose exec backend alembic upgrade head

# 运行测试
docker-compose exec backend pytest tests/

# 性能测试
docker-compose exec backend pytest tests/ -v --benchmark
```

### 7.3 联系方式

- **部署负责人**: [姓名] ([邮箱])
- **技术支持**: [邮箱] / [电话]
- **运维团队**: [Slack 频道]
- **产品团队**: [邮箱]

---

**文档版本**: 1.0  
**最后更新**: 2026-05-26  
**下次审查**: 2026-06-26
