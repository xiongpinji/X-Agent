# X-Agent Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying X-Agent to production environments. It covers infrastructure setup, deployment procedures, monitoring, and disaster recovery.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Deployment Process](#deployment-process)
4. [Monitoring and Observability](#monitoring-and-observability)
5. [Scaling and Performance](#scaling-and-performance)
6. [Security Hardening](#security-hardening)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- Kubernetes 1.24+ cluster
- kubectl 1.24+
- Helm 3.0+
- Docker 20.10+
- PostgreSQL 14+
- Redis 7.0+
- Qdrant 1.0+
- Neo4j 5.0+

### AWS Resources (if using AWS)

- EKS cluster
- RDS PostgreSQL instance
- ElastiCache Redis cluster
- S3 bucket for backups
- ECR registry for Docker images

### Credentials and Secrets

Ensure the following secrets are configured:

```bash
# Database credentials
export DB_HOST=prod-db.example.com
export DB_USER=xagent
export DB_PASSWORD=<strong-password>

# Redis credentials
export REDIS_HOST=prod-redis.example.com
export REDIS_PASSWORD=<strong-password>

# Application secrets
export SECRET_KEY=<generate-with-openssl-rand-hex-32>
export SENTRY_DSN=<your-sentry-dsn>
```

## Infrastructure Setup

### 1. Kubernetes Cluster Setup

```bash
# Create namespace
kubectl create namespace production

# Create service account
kubectl apply -f deployment/kubernetes/namespace.yaml

# Create secrets
kubectl create secret generic xagent-secrets \
  --from-literal=database-url="postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:5432/xagent_prod" \
  --from-literal=redis-url="redis://:$REDIS_PASSWORD@$REDIS_HOST:6379/0" \
  --from-literal=qdrant-url="http://prod-qdrant.example.com:6333" \
  --from-literal=neo4j-uri="bolt://prod-neo4j.example.com:7687" \
  --from-literal=secret-key="$SECRET_KEY" \
  --from-literal=sentry-dsn="$SENTRY_DSN" \
  -n production
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb -h $DB_HOST -U $DB_USER xagent_prod

# Run migrations
python deployment/migrations/migrate.py migrate

# Verify schema
python deployment/migrations/migrate.py verify
```

### 3. Redis Setup

```bash
# Configure Redis for production
redis-cli -h $REDIS_HOST CONFIG SET maxmemory 10gb
redis-cli -h $REDIS_HOST CONFIG SET maxmemory-policy allkeys-lru
redis-cli -h $REDIS_HOST CONFIG SET appendonly yes
```

### 4. Qdrant Setup

```bash
# Create collections
curl -X PUT "http://prod-qdrant.example.com:6333/collections/embeddings" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    }
  }'
```

## Deployment Process

### Using Helm (Recommended)

```bash
# Add Helm repository
helm repo add xagent https://charts.example.com
helm repo update

# Deploy to production
helm install xagent xagent/xagent \
  --namespace production \
  --values deployment/helm/values-production.yaml \
  --set image.tag=v1.0.0 \
  --set secrets.secretKey="$SECRET_KEY" \
  --set secrets.dbPassword="$DB_PASSWORD" \
  --set secrets.redisPassword="$REDIS_PASSWORD"

# Verify deployment
kubectl rollout status deployment/xagent-api -n production
kubectl rollout status deployment/xagent-worker -n production
```

### Using kubectl

```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/kubernetes/deployment.yaml
kubectl apply -f deployment/kubernetes/service.yaml
kubectl apply -f deployment/kubernetes/ingress.yaml

# Verify deployment
kubectl get pods -n production
kubectl get svc -n production
kubectl get ingress -n production
```

### CI/CD Pipeline

The project includes GitHub Actions workflow for automated deployment:

```bash
# Tag a release
git tag v1.0.0
git push origin v1.0.0

# This triggers the deploy-production.yml workflow which:
# 1. Runs tests and security scans
# 2. Builds Docker image
# 3. Pushes to registry
# 4. Deploys to production
# 5. Runs smoke tests
# 6. Notifies team
```

## Monitoring and Observability

### Prometheus Metrics

```bash
# Access Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Key metrics to monitor
- http_requests_total
- http_request_duration_seconds
- database_connection_pool_size
- redis_commands_total
- task_queue_length
```

### Grafana Dashboards

```bash
# Access Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000

# Default credentials
# Username: admin
# Password: (check secret)

# Available dashboards:
# - X-Agent Overview
# - API Performance
# - Database Performance
# - Worker Status
# - Error Rates
```

### Jaeger Tracing

```bash
# Access Jaeger UI
kubectl port-forward -n monitoring svc/jaeger-query 16686:16686

# View traces for debugging
# - API request traces
# - Worker task traces
# - Database query traces
```

### Sentry Error Tracking

```bash
# Configure Sentry
export SENTRY_DSN=https://key@sentry.io/project-id

# Monitor errors in real-time
# - Exception tracking
# - Performance monitoring
# - Release tracking
```

## Scaling and Performance

### Horizontal Pod Autoscaling

```bash
# Check HPA status
kubectl get hpa -n production

# Manual scaling
kubectl scale deployment/xagent-api --replicas=10 -n production

# HPA configuration (in values-production.yaml)
api:
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
```

### Database Connection Pooling

```yaml
# In config.yaml
database:
  pool_size: 20
  max_overflow: 10
  connection_timeout: 30
```

### Redis Optimization

```bash
# Monitor Redis performance
redis-cli -h $REDIS_HOST INFO stats

# Configure for production
redis-cli -h $REDIS_HOST CONFIG SET tcp-keepalive 300
redis-cli -h $REDIS_HOST CONFIG SET timeout 0
```

## Security Hardening

### Network Security

```bash
# Apply network policies
kubectl apply -f deployment/kubernetes/network-policy.yaml

# Configure firewall rules
# - Restrict ingress to API port only
# - Restrict database access to application pods
# - Restrict Redis access to application pods
```

### Secret Management

```bash
# Use external secret management
# - AWS Secrets Manager
# - HashiCorp Vault
# - Kubernetes Secrets (with encryption at rest)

# Rotate secrets regularly
kubectl create secret generic xagent-secrets-new \
  --from-literal=secret-key="<new-key>" \
  -n production

# Update deployment to use new secret
kubectl patch deployment xagent-api -n production \
  -p '{"spec":{"template":{"metadata":{"annotations":{"secret-version":"2"}}}}}'
```

### SSL/TLS Configuration

```bash
# Certificate management with cert-manager
kubectl apply -f deployment/kubernetes/ingress.yaml

# Verify certificate
kubectl get certificate -n production
kubectl describe certificate xagent-cert -n production
```

## Troubleshooting

### Pod Issues

```bash
# Check pod status
kubectl describe pod <pod-name> -n production

# View logs
kubectl logs <pod-name> -n production
kubectl logs <pod-name> -n production --previous

# Execute commands in pod
kubectl exec -it <pod-name> -n production -- /bin/bash
```

### Database Issues

```bash
# Check database connectivity
kubectl exec -it <pod-name> -n production -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod -c "SELECT 1"

# Check connection pool
kubectl exec -it <pod-name> -n production -- \
  curl http://localhost:8000/metrics | grep database_pool
```

### Performance Issues

```bash
# Check resource usage
kubectl top nodes
kubectl top pods -n production

# Check slow queries
kubectl exec -it <pod-name> -n production -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod \
  -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10"
```

### Deployment Rollback

```bash
# Automatic rollback on failure
# (handled by CI/CD pipeline)

# Manual rollback
bash deployment/rollback.sh -v v0.9.0

# Rollback with database schema
bash deployment/rollback.sh -v v0.9.0 -d
```

## Maintenance

### Regular Backups

```bash
# Manual backup
bash deployment/backup/backup.sh

# Automated backups (via CronJob)
kubectl apply -f deployment/kubernetes/backup-cronjob.yaml

# Verify backups
ls -lh /backups/
```

### Database Maintenance

```bash
# Vacuum and analyze
kubectl exec -it <pod-name> -n production -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod \
  -c "VACUUM ANALYZE"

# Check table sizes
kubectl exec -it <pod-name> -n production -- \
  psql -h $DB_HOST -U $DB_USER -d xagent_prod \
  -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"
```

### Log Rotation

```bash
# Configure log rotation
cat > /etc/logrotate.d/xagent << EOF
/var/log/xagent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 xagent xagent
    sharedscripts
    postrotate
        systemctl reload xagent > /dev/null 2>&1 || true
    endscript
}
EOF
```

## Support and Escalation

For issues or questions:

1. Check logs: `kubectl logs -n production`
2. Check metrics: Prometheus/Grafana dashboards
3. Check traces: Jaeger UI
4. Review documentation: This guide
5. Contact: ops-team@example.com

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
