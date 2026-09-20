# X-Agent Disaster Recovery Plan

## Overview

This document outlines the disaster recovery procedures for X-Agent production environment. It covers prevention, detection, and recovery strategies for various failure scenarios.

## Recovery Time Objectives (RTO) and Recovery Point Objectives (RPO)

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
kubectl get pods -n production | grep xagent-api

# Pod is in CrashLoopBackOff
kubectl describe pod <pod-name> -n production
```

**Recovery:**
```bash
# Kubernetes automatically restarts the pod
# Monitor recovery
kubectl get pods -n production -w

# If pod doesn't recover, check logs
kubectl logs <pod-name> -n production --previous
```

**RTO:** 2-5 minutes

### Scenario 2: Node Failure

**Detection:**
```bash
# Node is NotReady
kubectl get nodes

# Pods are pending
kubectl get pods -n production | grep Pending
```

**Recovery:**
```bash
# Kubernetes automatically reschedules pods to healthy nodes
kubectl get pods -n production -o wide

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
kubectl logs -n production -l app=xagent-api | grep "database"

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
kubectl exec -it <pod-name> -n production -- \
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
kubectl logs -n production -l app=xagent-api | grep "redis"

# Cache misses increasing
# (monitor in Prometheus)
```

**Recovery:**

#### Option A: Failover to Replica

```bash
# If using ElastiCache with Multi-AZ
# AWS automatically fails over to replica

# Verify connection
kubectl exec -it <pod-name> -n production -- \
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
kubectl logs -n production -l app=xagent-api | grep "qdrant"

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

#### Option B: Restore from Backup

```bash
# List available backups
ls -lh /backups/

# Restore Qdrant backup
curl -X POST "http://prod-qdrant.example.com:6333/collections/restore" \
  -H "Content-Type: application/json" \
  -d @/backups/backup_20240527_020000/qdrant.backup
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

# 2. Restore Redis from backup
redis-cli --rdb /backups/latest/redis.rdb

# 3. Restore Qdrant from backup
curl -X POST "http://new-qdrant:6333/collections/restore" \
  -H "Content-Type: application/json" \
  -d @/backups/latest/qdrant.backup

# 4. Deploy application
helm install xagent xagent/xagent \
  --namespace production \
  --values deployment/helm/values-production.yaml
```

#### Step 4: Verify and Communicate

```bash
# Run comprehensive health checks
bash deployment/health-check.sh

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
# Automated daily backups
# - Database: 2 AM UTC
# - Redis: 2:15 AM UTC
# - Qdrant: 2:30 AM UTC

# Backup retention: 30 days
# Backup location: S3 (cross-region)

# Backup verification: Daily
# - Restore test weekly
# - Full recovery test monthly
```

### Backup Verification

```bash
# List backups
aws s3 ls s3://xagent-backups/

# Verify backup integrity
python deployment/migrations/migrate.py verify

# Test restore (in staging)
python deployment/migrations/migrate.py restore /backups/latest/database.dump
```

### Restore Procedures

```bash
# Database restore
python deployment/migrations/migrate.py restore <backup-file>

# Redis restore
redis-cli --rdb <backup-file>

# Qdrant restore
curl -X POST "http://qdrant:6333/collections/restore" \
  -d @<backup-file>
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

```
/deployment/runbooks/
├── pod-failure.md
├── node-failure.md
├── database-failure.md
├── redis-failure.md
├── qdrant-failure.md
└── complete-failure.md
```

### Runbook Updates

```bash
# Update frequency: Quarterly
# Review frequency: After each incident
# Version control: Git
# Distribution: Wiki + Slack
```

## Related Documentation

- [Production Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Rollback Procedure](ROLLBACK_PROCEDURE.md)
- [Production Checklist](PRODUCTION_CHECKLIST.md)
- [Security Hardening](deployment/security/security-hardening.md)
