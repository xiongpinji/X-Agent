# X-Agent Production Deployment Complete Package

## Overview

This comprehensive deployment package provides production-ready configurations for X-Agent using Docker, Docker Compose, Kubernetes, and Helm.

## Package Contents

### 1. Docker Configuration
- **Dockerfile**: Multi-stage production image with security best practices
  - Builder stage for dependencies
  - Runtime stage with minimal footprint
  - Non-root user execution
  - Health checks included

### 2. Docker Compose
- **docker-compose.yml**: Complete stack with all services
  - PostgreSQL 16 (database)
  - Redis 7 (cache & broker)
  - Qdrant (vector database)
  - Neo4j 5 (graph database)
  - X-Agent API server
  - Celery workers
  - Celery beat scheduler
  - Logging configuration
  - Health checks for all services

### 3. Kubernetes Manifests
Located in `deployment/k8s/`:
- **namespace.yaml**: Kubernetes namespace
- **configmap.yaml**: Configuration management
- **secret.yaml**: Secrets management
- **postgres-deployment.yaml**: PostgreSQL with PVC
- **redis-deployment.yaml**: Redis with PVC
- **qdrant-deployment.yaml**: Qdrant with PVC
- **neo4j-deployment.yaml**: Neo4j with PVC
- **xagent-api-deployment.yaml**: API with HPA
- **xagent-worker-deployment.yaml**: Workers with HPA
- **xagent-beat-deployment.yaml**: Scheduler
- **ingress.yaml**: Ingress configuration

### 4. Helm Chart
Located in `deployment/helm/`:
- **Chart.yaml**: Chart metadata
- **values.yaml**: Default values
- **values-production.yaml**: Production-specific values
- **templates/configmap.yaml**: ConfigMap template
- **templates/secret.yaml**: Secret template
- **templates/namespace.yaml**: Namespace template
- **templates/api-deployment.yaml**: API deployment template
- **templates/ingress.yaml**: Ingress template

### 5. Deployment Scripts
Located in `deployment/scripts/`:
- **deploy.sh**: Main deployment script
- **rollback.sh**: Rollback script
- **migrate-db.sh**: Database migration script
- **pre-deployment-checklist.sh**: Pre-deployment verification

### 6. CI/CD Integration
- **.github/workflows/deploy.yml**: GitHub Actions workflow
  - Build Docker image
  - Run tests
  - Deploy to staging
  - Deploy to production
  - Automated rollback on failure

### 7. Documentation
- **docs/DEPLOYMENT.md**: Comprehensive deployment guide
- **docs/OPERATIONS.md**: Operations manual
- **deployment/env/README.md**: Environment configuration guide

## Key Features

### High Availability
- Multi-replica deployments (3-10 for API)
- Pod anti-affinity rules
- Automatic failover
- Health checks and readiness probes
- Graceful shutdown handling

### Auto-Scaling
- Horizontal Pod Autoscaler (HPA)
- CPU-based scaling (70% threshold)
- Memory-based scaling (80% threshold)
- Min/max replica limits
- Gradual scale-up/down policies

### Zero-Downtime Deployment
- Rolling update strategy
- Graceful connection draining
- Database migration safety
- Automatic rollback on failure
- Blue-green deployment support

### Security
- Non-root container execution
- Read-only root filesystem
- Network policies
- Secret management
- TLS/SSL encryption
- RBAC configuration
- Pod security policies

### Monitoring & Observability
- Prometheus metrics
- Grafana dashboards
- Health checks
- Log aggregation
- Distributed tracing support
- Performance monitoring

### Backup & Recovery
- Automated database backups
- Point-in-time recovery
- Volume snapshots
- Disaster recovery procedures
- Backup retention policies

## Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.25+ (for K8s deployment)
- Helm 3.0+ (for Helm deployment)
- kubectl 1.25+ (for K8s deployment)

### Docker Compose Deployment

```bash
# 1. Clone repository
git clone https://github.com/xagent/xagent.git
cd xagent

# 2. Copy environment file
cp .env.example .env

# 3. Edit environment variables
nano .env

# 4. Start services
docker-compose up -d

# 5. Check status
docker-compose ps

# 6. View logs
docker-compose logs -f xagent-api

# 7. Access API
curl http://localhost:8000/health
```

### Kubernetes with Helm Deployment

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

# 3. Deploy with Helm
helm install xagent deployment/helm \
  --namespace xagent \
  --values deployment/helm/values-production.yaml

# 4. Check status
kubectl get pods -n xagent

# 5. View logs
kubectl logs -f deployment/xagent-api -n xagent

# 6. Access API
kubectl port-forward svc/xagent-api 8000:8000 -n xagent
curl http://localhost:8000/health
```

## Environment Configuration

### Development
```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG=true
API_WORKERS=1
```

### Staging
```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO
DEBUG=false
API_WORKERS=2
```

### Production
```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
DEBUG=false
API_WORKERS=4
```

## Deployment Checklist

Before deploying to production:

- [ ] Run pre-deployment checklist
- [ ] Verify all secrets are configured
- [ ] Create database backup
- [ ] Review deployment configuration
- [ ] Test in staging environment
- [ ] Prepare rollback plan
- [ ] Notify stakeholders
- [ ] Monitor deployment progress
- [ ] Verify health checks
- [ ] Run smoke tests

## Scaling

### Horizontal Scaling

```bash
# Docker Compose
docker-compose up -d --scale xagent-api=5

# Kubernetes
kubectl scale deployment xagent-api --replicas=5 -n xagent

# Helm
helm upgrade xagent deployment/helm \
  --set api.replicas=5 -n xagent
```

### Vertical Scaling

```bash
# Update resource limits
kubectl set resources deployment xagent-api \
  --limits=cpu=1000m,memory=2Gi \
  --requests=cpu=500m,memory=1Gi \
  -n xagent
```

## Backup & Recovery

### Database Backup

```bash
# Docker Compose
docker-compose exec -T postgres pg_dump -U xagent xagent_db > backup.sql

# Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  pg_dump -U xagent xagent_db > backup.sql
```

### Database Recovery

```bash
# Docker Compose
docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql

# Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  psql -U xagent xagent_db < backup.sql
```

## Troubleshooting

### API Not Responding

```bash
# Check pod status
kubectl get pods -n xagent -l app=xagent-api

# Check logs
kubectl logs deployment/xagent-api -n xagent

# Check health
curl http://localhost:8000/health
```

### Database Connection Failed

```bash
# Check database pod
kubectl get pods -n xagent -l app=postgres

# Check database logs
kubectl logs deployment/postgres -n xagent

# Test connection
kubectl exec -it deployment/postgres -n xagent -- \
  psql -U xagent -d xagent_db -c "SELECT 1"
```

### High Memory Usage

```bash
# Check memory usage
kubectl top pods -n xagent

# Restart pod
kubectl rollout restart deployment/xagent-api -n xagent
```

## Performance Tuning

### Database Optimization
- Create indexes on frequently queried columns
- Analyze query performance with EXPLAIN
- Configure connection pooling
- Enable query caching

### Redis Optimization
- Monitor memory usage
- Configure eviction policies
- Enable persistence
- Use pipelining for batch operations

### API Optimization
- Increase API_WORKERS for higher concurrency
- Enable caching for frequently accessed data
- Use connection pooling
- Monitor and optimize slow queries

## Security Considerations

1. **Secrets Management**
   - Use Kubernetes Secrets or external vault
   - Rotate secrets regularly
   - Never commit secrets to version control

2. **Network Security**
   - Use TLS/SSL for all communications
   - Implement network policies
   - Use firewalls to restrict access

3. **Access Control**
   - Implement RBAC
   - Use strong authentication
   - Audit access logs

4. **Data Protection**
   - Enable encryption at rest
   - Enable encryption in transit
   - Regular backups

## Support & Documentation

- **Deployment Guide**: See `docs/DEPLOYMENT.md`
- **Operations Manual**: See `docs/OPERATIONS.md`
- **Environment Config**: See `deployment/env/README.md`
- **GitHub**: https://github.com/xagent/xagent
- **Issues**: https://github.com/xagent/xagent/issues

## Files Summary

### Docker
- `Dockerfile` - Production image
- `docker-compose.yml` - Complete stack

### Kubernetes (11 files)
- `deployment/k8s/namespace.yaml`
- `deployment/k8s/configmap.yaml`
- `deployment/k8s/secret.yaml`
- `deployment/k8s/postgres-deployment.yaml`
- `deployment/k8s/redis-deployment.yaml`
- `deployment/k8s/qdrant-deployment.yaml`
- `deployment/k8s/neo4j-deployment.yaml`
- `deployment/k8s/xagent-api-deployment.yaml`
- `deployment/k8s/xagent-worker-deployment.yaml`
- `deployment/k8s/xagent-beat-deployment.yaml`
- `deployment/k8s/ingress.yaml`

### Helm (8 files)
- `deployment/helm/Chart.yaml`
- `deployment/helm/values.yaml`
- `deployment/helm/values-production.yaml`
- `deployment/helm/templates/configmap.yaml`
- `deployment/helm/templates/secret.yaml`
- `deployment/helm/templates/namespace.yaml`
- `deployment/helm/templates/api-deployment.yaml`
- `deployment/helm/templates/ingress.yaml`

### Scripts (4 files)
- `deployment/scripts/deploy.sh`
- `deployment/scripts/rollback.sh`
- `deployment/scripts/migrate-db.sh`
- `deployment/scripts/pre-deployment-checklist.sh`

### CI/CD (1 file)
- `.github/workflows/deploy.yml`

### Documentation (3 files)
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`
- `deployment/env/README.md`

**Total: 30+ production-ready files**

## Next Steps

1. **Configure Secrets**: Update all default passwords and keys
2. **Set Up Monitoring**: Deploy Prometheus and Grafana
3. **Configure Backups**: Set up automated backup procedures
4. **Test Deployment**: Deploy to staging and verify
5. **Production Deployment**: Follow deployment checklist
6. **Monitor**: Set up alerts and dashboards
7. **Document**: Update runbooks and procedures


#### `scripts/deploy_agent_v2.py`
**功能**: 自动化部署脚本
- 执行部署前检查
- 运行数据库迁移
- 执行灰度发布
- 监控关键指标
- 自动回滚

**使用方式**:
```bash
python scripts/deploy_agent_v2.py
```

**配置选项**:
```python
config = DeploymentConfig(
    api_url="http://localhost:8000",
    initial_rollout_percentage=10,
    rollout_increment=10,
    rollout_interval_seconds=300,
    error_threshold_percentage=5.0,
)
```

#### `scripts/health_check.py`
**功能**: 健康检查脚本
- 检查 API 健康状态
- 检查数据库连接
- 检查 Redis 连接
- 检查 Qdrant 连接
- 检查特性开关
- 检查指标端点

**使用方式**:
```bash
python scripts/health_check.py
```

### 3. 监控配置

#### `backend/app/core/monitoring_config.py`
**功能**: 监控指标和告警配置
- 定义执行指标
- 定义性能指标
- 定义数据库指标
- 定义缓存指标
- 定义告警规则
- 提供 Prometheus 配置模板
- 提供 Grafana 仪表板配置

**关键配置**:
- 执行指标: v1/v2 执行次数、错误次数
- 性能指标: 响应时间、内存使用、CPU 使用
- 告警规则: 错误率、响应时间、资源使用

### 4. 文档

#### `DEPLOYMENT_CHECKLIST.md`
**内容**: 完整的部署检查清单
- 部署前检查（基础设施、应用、团队）
- 部署步骤（代码部署、服务更新、特性开关）
- 灰度发布步骤
- 部署后验证
- 监控指标定义
- 回滚计划
- 部署验证清单

#### `DEPLOYMENT_GUIDE.md`
**内容**: 详细的部署指南
- 架构设计说明
- 特性开关工作原理
- 灰度发布策略
- 监控和告警配置
- 回滚流程
- 故障排查指南
- 常见问题解答

#### `DEPLOYMENT_QUICK_REFERENCE.md`
**内容**: 快速参考指南
- 常用命令
- 灰度发布时间表
- 关键指标速查表
- 故障排查快速指南
- 文件位置索引

---

## 部署流程概览

### 阶段 1: 部署前准备 (T-1 小时)

```bash
# 1. 运行健康检查
python scripts/health_check.py

# 2. 备份数据
pg_dump -h localhost -U xagent xagent > backup_$(date +%Y%m%d_%H%M%S).sql
redis-cli BGSAVE

# 3. 验证代码
git pull origin main
pytest tests/ -v
```

### 阶段 2: 自动化部署 (T 时刻)

```bash
# 运行自动化部署脚本
python scripts/deploy_agent_v2.py

# 脚本将自动执行:
# - 健康检查
# - 数据库迁移
# - 10% -> 25% -> 50% -> 75% -> 100% 灰度发布
# - 每个阶段监控 5 分钟
# - 错误率超过 5% 时自动回滚
```

### 阶段 3: 部署后验证 (T+2 小时)

```bash
# 1. 验证所有服务
python scripts/health_check.py

# 2. 检查执行指标
curl http://localhost:8000/admin/metrics/execution

# 3. 验证 Agent V2 执行
curl -X POST http://localhost:8000/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{"task": "test", "context": {}}'
```

---

## 关键指标监控

### 执行指标
| 指标 | 目标 | 告警阈值 |
|------|------|---------|
| Agent V2 错误率 | < 1% | > 5% |
| API 响应时间 (p95) | < 500ms | > 1000ms |
| 数据库连接池使用率 | < 70% | > 90% |
| Redis 内存使用率 | < 70% | > 85% |

### 监控命令
```bash
# 实时监控执行统计
watch -n 5 'curl -s http://localhost:8000/admin/metrics/execution | jq'

# 查看日志
docker-compose logs -f backend | grep "Agent V2"

# 检查错误
docker-compose logs backend | grep ERROR
```

---

## 回滚流程

### 自动回滚触发条件
- 错误率 > 5% 持续 5 分钟
- 响应时间 p95 > 1000ms 持续 5 分钟
- 数据库连接池使用率 > 90%
- 健康检查失败 3 次

### 手动回滚
```bash
# 立即禁用 Agent V2
curl -X POST http://localhost:8000/admin/feature-flags/use_agent_v2 \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "rollout_percentage": 0}'

# 验证回滚
curl http://localhost:8000/admin/metrics/execution
```

---

## 文件位置速查

| 文件 | 位置 | 说明 |
|------|------|------|
| 特性开关 | `backend/app/core/feature_flags.py` | 特性开关实现 |
| 兼容层 | `backend/app/core/agent_compat.py` | V1/V2 路由 |
| 部署脚本 | `scripts/deploy_agent_v2.py` | 自动化部署 |
| 健康检查 | `scripts/health_check.py` | 健康检查 |
| 监控配置 | `backend/app/core/monitoring_config.py` | 监控指标 |
| 部署清单 | `DEPLOYMENT_CHECKLIST.md` | 检查清单 |
| 部署指南 | `DEPLOYMENT_GUIDE.md` | 详细指南 |
| 快速参考 | `DEPLOYMENT_QUICK_REFERENCE.md` | 快速参考 |

---

## 集成步骤

### 1. 集成特性开关到 API

在 FastAPI 应用中集成特性开关：

```python
from fastapi import FastAPI
from backend.app.core.feature_flags import get_feature_flag_manager

app = FastAPI()

@app.post("/admin/feature-flags/use_agent_v2")
async def update_agent_v2_flag(
    enabled: bool,
    rollout_percentage: int = 0,
):
    manager = get_feature_flag_manager()
    manager.set_flag(
        FeatureFlag.USE_AGENT_V2,
        enabled=enabled,
        rollout_percentage=rollout_percentage,
    )
    return {"status": "updated"}

@app.get("/admin/feature-flags/use_agent_v2")
async def get_agent_v2_flag():
    manager = get_feature_flag_manager()
    config = manager.get_flag_config(FeatureFlag.USE_AGENT_V2)
    return asdict(config)
```

### 2. 集成兼容层到执行流程

在 Agent 执行流程中使用兼容层：

```python
from backend.app.core.agent_compat import get_compatibility_layer

async def execute_agent(context, task, tenant_id=None, user_id=None):
    layer = get_compatibility_layer()
    response = await layer.execute(
        context,
        task,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    return response
```

### 3. 集成监控指标

在应用中集成 Prometheus 指标：

```python
from prometheus_client import Counter, Histogram
from backend.app.core.monitoring_config import MonitoringConfig

# 创建指标
v2_executions = Counter(
    "agent_v2_executions_total",
    "Total Agent V2 executions",
    ["tenant_id", "status"],
)

execution_duration = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration",
    ["agent_version"],
)

# 记录指标
v2_executions.labels(tenant_id="tenant1", status="success").inc()
execution_duration.labels(agent_version="v2").observe(0.5)
```

---

## 部署前检查清单

- [ ] 所有代码已审查
- [ ] 所有测试通过
- [ ] 数据库备份完成
- [ ] Redis 备份完成
- [ ] 环境变量已配置
- [ ] 特性开关已配置
- [ ] 监控告警已配置
- [ ] 团队已通知
- [ ] 回滚计划已准备
- [ ] 支持团队已待命

---

## 部署后验证清单

- [ ] 所有服务运行正常
- [ ] Agent V2 能够执行任务
- [ ] 错误率在预期范围内
- [ ] 性能指标正常
- [ ] 日志记录正确
- [ ] 监控告警正常工作
- [ ] 用户反馈正面
- [ ] 没有安全问题

---

## 支持和联系

- **部署负责人**: [姓名] ([邮箱])
- **技术支持**: [邮箱] / [电话]
- **运维团队**: [Slack 频道]
- **紧急情况**: [24/7 热线]

---

## 相关资源

- [Agent V2 架构设计](docs/architecture.md)
- [API 文档](docs/api.md)
- [故障排查指南](docs/troubleshooting.md)
- [性能优化指南](docs/performance.md)

---

**文档版本**: 1.0  
**创建日期**: 2026-05-26  
**最后更新**: 2026-05-26  
**维护者**: X-Agent 团队
