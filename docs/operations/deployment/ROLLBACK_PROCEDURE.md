# X-Agent Rollback Procedure

## Overview

This document describes the procedures for rolling back X-Agent deployments in case of issues or failures.

## Quick Rollback

### Automatic Rollback

The CI/CD pipeline automatically rolls back on deployment failure:

```bash
# Triggered automatically when:
# - Tests fail
# - Security scans fail
# - Deployment health checks fail
# - Smoke tests fail
```

### Manual Rollback

```bash
# Roll back the Helm release to its previous audited revision.
NAMESPACE=production RELEASE_NAME=xagent \
  bash deployment/scripts/rollback.sh
```

The rollback script never downgrades the database. A specific image or schema
recovery requires a separately reviewed operator procedure and verified backup.

## Rollback Scenarios

### Scenario 1: API Deployment Issue

```bash
# Symptoms:
# - High error rate (>1%)
# - Service unavailable
# - Pod crashes

# Rollback steps:
kubectl rollout undo deployment/xagent-api -n production
kubectl rollout status deployment/xagent-api -n production --timeout=5m

# Verify
curl https://api.example.com/health
```

### Scenario 2: Worker Deployment Issue

```bash
# Symptoms:
# - Tasks not processing
# - Queue backlog increasing
# - Worker pods crashing

# Rollback steps:
kubectl rollout undo deployment/xagent-worker -n production
kubectl rollout status deployment/xagent-worker -n production --timeout=5m

# Verify
kubectl logs -n production -l app=xagent-worker --tail=50
```

### Scenario 3: Database Schema Issue

```bash
# Symptoms:
# - Database connection errors
# - Schema validation failures
# - Migration errors

# Application rollback only. Migration 0002 is forward-only and must never be
# downgraded automatically.
bash deployment/scripts/rollback.sh

# If schema recovery is approved, stop writes and restore a verified backup:
export XAGENT_RESTORE_CONFIRMATION="$XAGENT_DATABASE_NAME"
bash deployment/scripts/restore-database.sh \
  /backups/backup_20240527_020000/database.dump
```

### Scenario 4: Complete System Failure

```bash
# Symptoms:
# - Multiple component failures
# - Cascading errors
# - System unresponsive

# Rollback application workloads to the previous audited Helm revision:
bash deployment/scripts/rollback.sh

# This will:
# 1. Roll back the complete Helm release to its previous revision
# 2. Wait for the Helm rollback to finish
# 3. Leave the database schema unchanged
# 4. Require the operator to run the verification steps below
```

## Rollback Verification

### Health Checks

```bash
# API health
curl -f https://api.example.com/health

# Database connectivity
kubectl exec -it <pod-name> -n production -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod -c "SELECT 1"

# Redis connectivity
kubectl exec -it <pod-name> -n production -- \
  redis-cli -h $REDIS_HOST ping

# Worker status
kubectl get pods -n production -l app=xagent-worker
```

### Metrics Verification

```bash
# Check error rate
# In Prometheus: rate(http_requests_total{status=~"5.."}[5m])

# Check latency
# In Prometheus: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Check queue length
# In Prometheus: celery_queue_length
```

### Log Analysis

```bash
# Check for errors
kubectl logs -n production -l app=xagent-api --tail=100 | grep ERROR

# Check for warnings
kubectl logs -n production -l app=xagent-api --tail=100 | grep WARN

# Check application logs
kubectl logs -n production -l app=xagent-api --tail=50
```

## Rollback Decision Tree

```
Issue Detected
    |
    +-- API Error Rate High?
    |   |
    |   +-- YES --> Rollback API deployment
    |   |
    |   +-- NO --> Continue
    |
    +-- Worker Queue Backlog?
    |   |
    |   +-- YES --> Rollback Worker deployment
    |   |
    |   +-- NO --> Continue
    |
    +-- Database Errors?
    |   |
    |   +-- YES --> Rollback Database schema
    |   |
    |   +-- NO --> Continue
    |
    +-- Multiple Failures?
        |
        +-- YES --> Full system rollback
        |
        +-- NO --> Investigate specific component
```

## Post-Rollback Actions

### 1. Incident Investigation

```bash
# Collect logs
kubectl logs -n production -l app=xagent-api > api-logs.txt
kubectl logs -n production -l app=xagent-worker > worker-logs.txt

# Export metrics
# From Prometheus: Export relevant metrics for analysis

# Review traces
# From Jaeger: Export traces around failure time
```

### 2. Root Cause Analysis

```bash
# Questions to answer:
# - What changed in the failed version?
# - What tests were missed?
# - What monitoring gaps exist?
# - What process improvements are needed?

# Document findings in incident report
```

### 3. Communication

```bash
# Notify stakeholders
# - Engineering team
# - Operations team
# - Product team
# - Customers (if applicable)

# Include:
# - What happened
# - When it was detected
# - What was rolled back
# - Current status
# - Next steps
```

### 4. Prevention

```bash
# Implement improvements:
# - Add missing tests
# - Improve monitoring
# - Update runbooks
# - Enhance CI/CD checks
# - Increase canary duration
```

## Rollback Limitations

### Cannot Rollback

- Data deletions (must restore from backup)
- Configuration changes (must revert manually)
- Third-party service changes (must coordinate with providers)

### Partial Rollback

```bash
# Rollback only API, keep worker on new version
kubectl rollout undo deployment/xagent-api -n production

# Rollback only worker, keep API on new version
kubectl rollout undo deployment/xagent-worker -n production
```

## Emergency Contacts

- On-call Engineer: ops-oncall@example.com
- Engineering Manager: eng-manager@example.com
- Operations Lead: ops-lead@example.com

## Related Documentation

- [Production Deployment Guide](PRODUCTION_DEPLOYMENT_GUIDE.md)
- [Disaster Recovery Plan](./DISASTER_RECOVERY.md)
- [Production Checklist](PRODUCTION_CHECKLIST.md)
