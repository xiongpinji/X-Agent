# X-Agent Disaster Recovery Plan

## Overview

This document outlines the disaster recovery procedures for X-Agent production environment. It covers prevention, detection, and recovery strategies for various failure scenarios.

> 2026-07-20 (P1-15/P1-17) 更新:
> - 权威部署资产为 Helm chart `deployment/helm/`(namespace: **xagent**); 旧 `deployment/kubernetes/`(namespace production)已归档至 `archive/legacy_kubernetes_manifests_2026-07-20/`, 参考用裸清单 `deployment/k8s/` 已于 2026-08-05 归档至 `archive/legacy_k8s_manifests_2026-08/`。本文所有 `kubectl` 命令已对齐到 `xagent` 命名空间。
> - Qdrant 备份/恢复改用官方快照 API(创建 `POST /collections/{name}/snapshots`; 下载 `GET /collections/{name}/snapshots/{file}`; 恢复 `POST /collections/{name}/snapshots/upload` 或 `PUT /collections/{name}/snapshots/recover`)。旧的 `/collections/backup`、`/collections/restore` 端点不存在, 已废弃。
> - 定时备份由 Helm CronJob 执行(`deployment/helm/templates/backup-cronjob.yaml`, `backup.enabled=true`), 脚本 `deployment/backup/backup.sh`。

## Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO)

> 注: 以下 RTO/RPO 为**目标值**, 尚未经过真实演练验证(首次演练后回填实测值)。

| Component | RTO | RPO |
|-----------|-----|-----|
| API Service | 15 minutes | 5 minutes |
| Worker Service | 30 minutes | 10 minutes |
| Database | 1 hour | 5 minutes |
| Redis Cache | 30 minutes | 0 (can be rebuilt) |
| Qdrant Vector DB | 2 hours | 1 hour |
| Complete System | 4 hours | 1 hour |

## Disaster Scenarios

### Scenario 1: Single Pod Failure

**Detection:**
```bash
# Pod is not running
kubectl get pods -n xagent | grep xagent-api

# Pod is in CrashLoopBackOff
kubectl describe pod <pod-name> -n xagent
```

**Recovery:**
```bash
# Kubernetes automatically restarts the pod
# Monitor recovery
kubectl get pods -n xagent -w

# If pod doesn't recover, check logs
kubectl logs <pod-name> -n xagent --previous
```

**RTO:** 2-5 minutes

### Scenario 2: Node Failure

**Detection:**
```bash
# Node is NotReady
kubectl get nodes

# Pods are pending
kubectl get pods -n xagent | grep Pending
```

**Recovery:**
```bash
# Kubernetes automatically reschedules pods to healthy nodes
kubectl get pods -n xagent -o wide

# If node doesn't recover, drain and remove it
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <node-name>

# Add new node to cluster
# (depends on your infrastructure provider)
```

**RTO:** 5-15 minutes

### Scenario 3: Database Failure

**Detection:**
```bash
# Database connection errors in logs
kubectl logs -n xagent -l app=xagent-api | grep "database"

# Health check fails
curl https://api.example.com/health
```

**Recovery:**

#### Option A: Failover to Replica

```bash
# If using RDS with Multi-AZ
# AWS automatically fails over to replica
# Monitor failover progress in AWS console

# Verify connection
kubectl exec -it <pod-name> -n xagent -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod -c "SELECT 1"
```

#### Option B: Restore from Backup

```bash
# List available backups
ls -lh /backups/

# Restore from backup
python deployment/migrations/migrate.py restore /backups/backup_20240527_020000/database.dump

# Verify restoration
python deployment/migrations/migrate.py verify
```

**RTO:** 15-60 minutes

### Scenario 4: Redis Failure

**Detection:**
```bash
# Redis connection errors
kubectl logs -n xagent -l app=xagent-api | grep "redis"

# Cache misses increasing
# (monitor in Prometheus)
```

**Recovery:**

#### Option A: Failover to Replica

```bash
# If using ElastiCache with Multi-AZ
# AWS automatically fails over to replica

# Verify connection
kubectl exec -it <pod-name> -n xagent -- \
  redis-cli -h $REDIS_HOST ping
```

#### Option B: Rebuild Cache

```bash
# Clear cache
redis-cli -h $REDIS_HOST FLUSHALL

# Rebuild cache from database
# (application will rebuild on demand)

# Monitor cache hit rate
# (should recover to normal within minutes)
```

**RTO:** 5-30 minutes

### Scenario 5: Qdrant Failure

**Detection:**
```bash
# Vector search errors
kubectl logs -n xagent -l app=xagent-api | grep "qdrant"

# Memory retrieval failures
# (monitor in application logs)
```

**Recovery:**

#### Option A: Failover to Replica

```bash
# If using Qdrant cluster
# Failover to replica node

# Verify connection
curl http://prod-qdrant.example.com:6333/health
```

#### Option B: Restore from Snapshot

```bash
# List available backups (每个集合一个快照文件, 由 deployment/backup/backup.sh 生成)
ls -lh /backups/

# 方式 1: 上传快照文件恢复 (官方 API: POST /collections/{name}/snapshots/upload)
# priority=snapshot 表示以快照数据为准
curl -X POST "http://prod-qdrant.example.com:6333/collections/<collection>/snapshots/upload?priority=snapshot" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/backups/backup_20240527_020000/qdrant_<collection>.snapshot"

# 方式 2: 若快照文件已在 Qdrant 节点本地或可下载 URL, 用 recover 端点
# (官方 API: PUT /collections/{name}/snapshots/recover)
curl -X PUT "http://prod-qdrant.example.com:6333/collections/<collection>/snapshots/recover" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"location": "file:///qdrant/snapshots/qdrant_<collection>.snapshot", "priority": "snapshot"}'
```

**RTO:** 30-120 minutes

### Scenario 6: Complete Data Center Failure

**Detection:**
```bash
# All services down
# Network unreachable
# Multiple component failures
```

**Recovery:**

#### Step 1: Assess Situation

```bash
# Check status of all components
# - Kubernetes cluster
# - Database
# - Redis
# - Qdrant
# - Network connectivity
```

#### Step 2: Activate Disaster Recovery

```bash
# Failover to secondary data center
# (if available)

# Or restore from backups in new region
```

#### Step 3: Restore Services

```bash
# 1. Restore database from backup
python deployment/migrations/migrate.py restore /backups/latest/database.dump

# 2. Restore Redis from backup (RDB 文件放回数据目录后重启; --rdb 是备份命令)
kubectl cp /backups/latest/redis.rdb <redis-pod>:/data/dump.rdb -n xagent
kubectl delete pod <redis-pod> -n xagent

# 3. Restore Qdrant from snapshot (官方快照上传 API, 每个集合执行一次)
curl -X POST "http://new-qdrant:6333/collections/<collection>/snapshots/upload?priority=snapshot" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/backups/latest/qdrant_<collection>.snapshot"

# 4. Deploy application
helm upgrade --install xagent deployment/helm \
  --namespace xagent \
  --create-namespace \
  --values deployment/helm/values-production.yaml
```

#### Step 4: Verify and Communicate

```bash
# Run comprehensive health checks
bash disaster-recovery/scripts/health-check.sh

# Notify stakeholders
# - Incident started
# - Recovery in progress
# - Services restored
# - Status updates
```

**RTO:** 2-4 hours

## Backup and Recovery

### Backup Strategy

```bash
# Automated daily backups (K8s CronJob: deployment/k8s/backup-cronjob.yaml,
# 或 Helm backup.enabled=true, 二选一勿重复; 脚本: deployment/backup/backup.sh)
# - Database: 2 AM UTC (pg_dump custom 格式)
# - Redis: 同一任务内顺序执行 (RDB)
# - Qdrant: 同一任务内顺序执行 (官方快照 API, 每个集合一个 .snapshot 文件)

# Backup retention: 30 days (RETENTION_DAYS)
# Backup location: 本地 PVC (xagent-backup-pvc); 可选 S3 (跨区, S3_ENABLED=true,
# S3 上传需 aws cli, 请扩展 deployment/backup/Dockerfile 安装后启用)

# Backup verification: Daily
# - Restore test weekly
# - Full recovery test monthly
```

### Backup Verification

```bash
# List backups (本地 PVC; 若启用了可选 S3 上传, 用 aws s3 ls s3://$S3_BUCKET/)
ls -lhd /backups/*/

# Verify backup integrity (读取 XAGENT_DATABASE_URL, 兼容 DATABASE_URL)
python deployment/migrations/migrate.py verify

# Test restore (in staging)
python deployment/migrations/migrate.py restore /backups/latest/database.dump
```

### Restore Procedures

```bash
# Database restore
python deployment/migrations/migrate.py restore <backup-file>

# Redis restore: RDB 文件放回数据目录后重启 (redis-cli --rdb 是备份命令, 不能用于恢复)
docker cp /backups/latest/redis.rdb <redis-container>:/data/dump.rdb
docker restart <redis-container>
# K8s: kubectl cp /backups/latest/redis.rdb <redis-pod>:/data/dump.rdb -n xagent && \
#      kubectl delete pod <redis-pod> -n xagent

# Qdrant restore (官方快照上传 API; <collection> 为集合名, 与备份文件名对应:
# qdrant_<collection>.snapshot)
curl -X POST "http://qdrant:6333/collections/<collection>/snapshots/upload?priority=snapshot" \
  -H "api-key: $QDRANT_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/backups/latest/qdrant_<collection>.snapshot"
```

## Monitoring and Alerting

### Critical Alerts

```yaml
# Prometheus alert rules
- alert: PodCrashLooping
  expr: rate(kube_pod_container_status_restarts_total[15m]) > 0.1
  for: 5m

- alert: DatabaseConnectionFailed
  expr: up{job="postgres"} == 0
  for: 2m

- alert: RedisConnectionFailed
  expr: up{job="redis"} == 0
  for: 2m

- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  for: 5m

- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
  for: 10m
```

### Alert Routing

```bash
# Critical alerts → PagerDuty → On-call engineer
# Warning alerts → Slack → Engineering team
# Info alerts → Logs → Monitoring dashboard
```

## Testing and Drills

### Monthly Disaster Recovery Drill

```bash
# 1. Simulate component failure
# 2. Execute recovery procedure
# 3. Verify recovery
# 4. Document results
# 5. Update procedures if needed

# Schedule: First Friday of each month
# Duration: 2 hours
# Participants: Engineering + Operations teams
```

### Annual Full Recovery Test

```bash
# 1. Restore all components from backup
# 2. Deploy application
# 3. Run full test suite
# 4. Verify data integrity
# 5. Document lessons learned

# Schedule: Q4 each year
# Duration: Full day
# Participants: All teams
```

## Communication Plan

### Incident Notification

```
Severity 1 (Critical):
- Notify: On-call engineer, Engineering manager, Operations lead
- Channel: Phone call + Slack
- Frequency: Every 15 minutes

Severity 2 (High):
- Notify: Engineering team, Operations team
- Channel: Slack + Email
- Frequency: Every 30 minutes

Severity 3 (Medium):
- Notify: Engineering team
- Channel: Slack
- Frequency: Every hour
```

### Status Updates

```
During Incident:
- Every 15 minutes: Internal status update
- Every 30 minutes: Customer notification (if applicable)

Post-Incident:
- Root cause analysis: Within 24 hours
- Incident report: Within 48 hours
- Action items: Within 1 week
```

## Documentation and Runbooks

### Runbook Locations

> P1-17 修正: 原引用的 `/deployment/runbooks/` 目录不存在, 已替换为仓库中真实存在的文档与脚本。

```
disaster-recovery/                     # 灾难恢复文档体系
├── DISASTER_RECOVERY_MANUAL.md        # 操作手册(故障诊断/转移/恢复/回切)
├── DISASTER_RECOVERY_PLAN.md          # DR 计划(RTO/RPO/场景/演练计划)
├── DRILL_REPORT_TEMPLATE.md           # 演练报告模板
├── RCA_TEMPLATE.md                    # 根因分析模板
└── scripts/
    ├── health-check.sh                # 健康检查(应用/PG/Redis/Qdrant/Neo4j/资源)
    ├── failover.sh                    # 故障转移(自动/手动, 含 dry-run)
    └── verify-recovery.sh             # 恢复验证
monitoring/RUNBOOK.md                  # 监控告警处置 runbook
deployment/backup/backup.sh            # 全量备份脚本(PG/Redis/Qdrant 快照)
deployment/k8s/backup-cronjob.yaml     # 定时备份 CronJob
```

### Runbook Updates

```bash
# Update frequency: Quarterly
# Review frequency: After each incident
# Version control: Git
# Distribution: Wiki + Slack
```

## Related Documentation

> P1-17 修正: 原引用的 PRODUCTION_DEPLOYMENT_GUIDE.md / PRODUCTION_CHECKLIST.md /
> deployment/security/security-hardening.md 在仓库中不存在, 已替换为真实路径或移除。

- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Rollback Procedure](./ROLLBACK_PROCEDURE.md)
- [Deployment Checklist](monitoring/DEPLOYMENT_CHECKLIST.md)
- [Monitoring Runbook](monitoring/RUNBOOK.md)
