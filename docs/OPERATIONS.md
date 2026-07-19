# X-Agent Operations Manual

## Overview

This manual provides operational procedures for managing X-Agent in production environments.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Scaling](#scaling)
3. [Backup and Recovery](#backup-and-recovery)
4. [Monitoring](#monitoring)
5. [Incident Response](#incident-response)
6. [Maintenance](#maintenance)

## Daily Operations

### Health Checks

Perform these checks daily:

```bash
# Check all services are running
docker-compose ps
# or
kubectl get pods -n xagent

# Check API health
curl http://localhost:8000/health

# Check database connections
docker-compose exec postgres pg_isready -U xagent

# Check Redis
docker-compose exec redis redis-cli ping

# Check disk space
df -h

# Check memory usage
free -h
```

### Log Review

```bash
# Review API logs for errors
docker-compose logs xagent-api | grep ERROR

# Review database logs
docker-compose logs postgres | grep ERROR

# Review worker logs
docker-compose logs xagent-worker | grep ERROR
```

### Performance Monitoring

```bash
# Check CPU usage
top -b -n 1 | head -20

# Check memory usage
free -h

# Check disk I/O
iostat -x 1 5

# Check network
netstat -i
```

## Scaling

### Horizontal Scaling (Add More Instances)

#### Docker Compose

```bash
# Scale API servers
docker-compose up -d --scale xagent-api=5

# Scale workers
docker-compose up -d --scale xagent-worker=4
```

#### Kubernetes

```bash
# Scale API deployment
kubectl scale deployment xagent-api --replicas=5 -n xagent

# Scale worker deployment
kubectl scale deployment xagent-worker --replicas=4 -n xagent

# Check scaling status
kubectl get deployment -n xagent
```

#### Helm

```bash
# Update values
helm upgrade xagent deployment/helm \
  --set api.replicas=5 \
  --set worker.replicas=4 \
  -n xagent
```

### Vertical Scaling (Increase Resources)

```bash
# Update resource limits in deployment
kubectl set resources deployment xagent-api \
  --limits=cpu=1000m,memory=2Gi \
  --requests=cpu=500m,memory=1Gi \
  -n xagent
```

### Auto-Scaling

```bash
# Check HPA status
kubectl get hpa -n xagent

# View HPA details
kubectl describe hpa xagent-api-hpa -n xagent

# Update HPA
kubectl patch hpa xagent-api-hpa -n xagent -p \
  '{"spec":{"maxReplicas":20}}'
```

## Backup and Recovery

### Database Backup

#### Automated Backup

```bash
# Create backup script
cat > /usr/local/bin/backup-xagent.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/xagent"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/xagent_db_$DATE.sql"

mkdir -p "$BACKUP_DIR"

docker-compose exec -T postgres pg_dump -U xagent xagent_db > "$BACKUP_FILE"

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
EOF

chmod +x /usr/local/bin/backup-xagent.sh

# Schedule with cron
0 2 * * * /usr/local/bin/backup-xagent.sh
```

#### Manual Backup

```bash
# Docker Compose
docker-compose exec -T postgres pg_dump -U xagent xagent_db > backup_$(date +%Y%m%d).sql

# Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  pg_dump -U xagent xagent_db > backup_$(date +%Y%m%d).sql
```

### Database Recovery

```bash
# Docker Compose
docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql

# Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  psql -U xagent xagent_db < backup.sql
```

### Redis Backup

```bash
# Create backup
docker-compose exec redis redis-cli BGSAVE

# Copy backup file
docker cp xagent-redis:/data/dump.rdb ./redis_backup.rdb

# Restore backup
docker cp ./redis_backup.rdb xagent-redis:/data/dump.rdb
docker-compose restart redis
```

### Volume Backup

```bash
# Backup PostgreSQL volume
docker run --rm -v xagent_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_volume.tar.gz -C /data .

# Backup Redis volume
docker run --rm -v xagent_redis_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/redis_volume.tar.gz -C /data .
```

## Monitoring

### Prometheus Queries

```promql
# API request rate
rate(xagent_api_requests_total[5m])

# API error rate
rate(xagent_api_errors_total[5m])

# API response time (p95)
histogram_quantile(0.95, xagent_api_request_duration_seconds)

# Database connection pool usage
xagent_database_connections_active / xagent_database_connections_max

# Redis memory usage
redis_memory_used_bytes / redis_memory_max_bytes
```

### Grafana Dashboards

Key dashboards to monitor:
1. **API Performance** - Request rate, latency, errors
2. **Database** - Connections, query performance, replication
3. **Redis** - Memory usage, operations, evictions
4. **Infrastructure** - CPU, memory, disk, network

### Alerting Rules

```yaml
groups:
- name: xagent
  rules:
  - alert: HighErrorRate
    expr: rate(xagent_api_errors_total[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"

  - alert: HighLatency
    expr: histogram_quantile(0.95, xagent_api_request_duration_seconds) > 1
    for: 5m
    annotations:
      summary: "High API latency detected"

  - alert: DatabaseConnectionPoolExhausted
    expr: xagent_database_connections_active >= xagent_database_connections_max
    for: 1m
    annotations:
      summary: "Database connection pool exhausted"

  - alert: RedisMemoryHigh
    expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
    for: 5m
    annotations:
      summary: "Redis memory usage high"
```

## Incident Response

### API Outage

```bash
# 1. Check service status
docker-compose ps xagent-api
kubectl get pods -n xagent -l app=xagent-api

# 2. Check logs
docker-compose logs xagent-api
kubectl logs deployment/xagent-api -n xagent

# 3. Check resources
docker stats xagent-api
kubectl top pods -n xagent

# 4. Restart service
docker-compose restart xagent-api
kubectl rollout restart deployment/xagent-api -n xagent

# 5. Verify recovery
curl http://localhost:8000/health
```

### Database Issues

```bash
# 1. Check database status
docker-compose exec postgres pg_isready -U xagent
kubectl exec deployment/postgres -n xagent -- pg_isready -U xagent

# 2. Check connections
docker-compose exec postgres psql -U xagent -c "SELECT count(*) FROM pg_stat_activity;"

# 3. Check disk space
docker exec xagent-postgres df -h

# 4. Kill idle connections
docker-compose exec postgres psql -U xagent -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';"

# 5. Restart database
docker-compose restart postgres
kubectl rollout restart deployment/postgres -n xagent
```

### High Memory Usage

```bash
# 1. Identify process
docker stats
kubectl top pods -n xagent

# 2. Check memory leaks
docker-compose exec xagent-api ps aux

# 3. Restart service
docker-compose restart xagent-api
kubectl rollout restart deployment/xagent-api -n xagent

# 4. Monitor memory
watch -n 1 'docker stats --no-stream'
```

### Disk Space Issues

```bash
# 1. Check disk usage
df -h

# 2. Find large files
du -sh /* | sort -rh

# 3. Clean up logs
docker-compose exec postgres rm -f /var/log/postgresql/*.log

# 4. Clean up Docker
docker system prune -a

# 5. Expand volume
# For Docker: resize volume or add new volume
# For Kubernetes: resize PVC
kubectl patch pvc postgres-pvc -n xagent -p \
  '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

## Maintenance

### Regular Maintenance Tasks

#### Weekly

- Review error logs
- Check backup status
- Monitor performance metrics
- Review security logs

#### Monthly

- Update dependencies
- Review and optimize slow queries
- Clean up old logs
- Test backup recovery

#### Quarterly

- Security audit
- Performance optimization
- Capacity planning
- Disaster recovery drill

### Updating X-Agent

```bash
# 1. Create backup
docker-compose exec -T postgres pg_dump -U xagent xagent_db > backup.sql

# 2. Pull new image
docker pull xagent:latest

# 3. Update docker-compose.yml
# Update image tag to new version

# 4. Restart services
docker-compose up -d

# 5. Run migrations
docker-compose exec xagent-api alembic upgrade head

# 6. Verify
curl http://localhost:8000/health
```

### Database Maintenance

```bash
# Vacuum database
docker-compose exec postgres vacuumdb -U xagent xagent_db

# Analyze tables
docker-compose exec postgres analyzedb -U xagent xagent_db

# Reindex
docker-compose exec postgres reindexdb -U xagent xagent_db
```

### Log Rotation

```bash
# Configure logrotate
cat > /etc/logrotate.d/xagent << 'EOF'
/var/log/xagent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 xagent xagent
    sharedscripts
    postrotate
        docker-compose -f /opt/xagent/docker-compose.yml kill -s HUP xagent-api
    endscript
}
EOF
```

## Runbooks

### Runbook: Deploy New Version

1. Create backup: `docker-compose exec -T postgres pg_dump -U xagent xagent_db > backup.sql`
2. Pull new image: `docker pull xagent:latest`
3. Update docker-compose.yml
4. Restart services: `docker-compose up -d`
5. Run migrations: `docker-compose exec xagent-api alembic upgrade head`
6. Verify: `curl http://localhost:8000/health`
7. Monitor logs: `docker-compose logs -f xagent-api`

### Runbook: Scale Up

1. Check current load: `docker stats`
2. Update docker-compose.yml or Helm values
3. Scale services: `docker-compose up -d --scale xagent-api=5`
4. Verify: `docker-compose ps`
5. Monitor: `docker stats`

### Runbook: Recover from Backup

1. Stop services: `docker-compose down`
2. Restore database: `docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql`
3. Start services: `docker-compose up -d`
4. Verify: `curl http://localhost:8000/health`

## Contact and Escalation

- **On-Call**: [Contact Information]
- **Escalation**: [Escalation Procedure]
- **Documentation**: [Documentation Links]
- **Support**: [Support Channels]
