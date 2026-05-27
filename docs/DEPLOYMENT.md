# X-Agent Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying X-Agent to production environments using Docker, Docker Compose, and Kubernetes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Deployment](#docker-deployment)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Helm Deployment](#helm-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Database Migrations](#database-migrations)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **CPU**: Minimum 4 cores (8+ recommended for production)
- **Memory**: Minimum 8GB (16GB+ recommended for production)
- **Storage**: Minimum 50GB (100GB+ recommended for production)
- **OS**: Linux (Ubuntu 20.04+ or CentOS 8+)

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.25+ (for K8s deployment)
- Helm 3.0+ (for Helm deployment)
- kubectl 1.25+ (for K8s deployment)
- PostgreSQL client tools (for database management)

### Network Requirements

- Outbound HTTPS access for LLM API calls
- Inbound HTTP/HTTPS access for API endpoints
- Internal network connectivity between services

## Docker Deployment

### Building the Image

```bash
# Build the Docker image
docker build -t xagent:latest -f Dockerfile .

# Tag for registry
docker tag xagent:latest your-registry/xagent:latest

# Push to registry
docker push your-registry/xagent:latest
```

### Running a Container

```bash
# Create a network
docker network create xagent-network

# Run the container
docker run -d \
  --name xagent-api \
  --network xagent-network \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@postgres:5432/xagent_db" \
  -e REDIS_URL="redis://:password@redis:6379/0" \
  -e ENVIRONMENT="production" \
  xagent:latest
```

## Docker Compose Deployment

### Quick Start

```bash
# Copy environment file
cp .env.example .env

# Edit environment variables
nano .env

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f xagent-api
```

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DB_USER=xagent
DB_PASSWORD=secure_password_here
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=secure_password_here
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=secure_key_here
QDRANT_PORT=6333

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=secure_password_here
NEO4J_PORT=7687

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
SECRET_KEY=secure_secret_key_here
API_WORKERS=4
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster 1.25+
- kubectl configured to access your cluster
- Helm 3.0+ installed

### Manual Deployment

```bash
# Create namespace
kubectl create namespace xagent

# Create secrets
kubectl create secret generic xagent-secrets \
  --from-literal=DB_PASSWORD=secure_password \
  --from-literal=REDIS_PASSWORD=secure_password \
  --from-literal=QDRANT_API_KEY=secure_key \
  --from-literal=NEO4J_PASSWORD=secure_password \
  --from-literal=SECRET_KEY=secure_secret_key \
  -n xagent

# Apply configurations
kubectl apply -f deployment/k8s/namespace.yaml
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/secret.yaml

# Deploy services
kubectl apply -f deployment/k8s/postgres-deployment.yaml
kubectl apply -f deployment/k8s/redis-deployment.yaml
kubectl apply -f deployment/k8s/qdrant-deployment.yaml
kubectl apply -f deployment/k8s/neo4j-deployment.yaml

# Deploy application
kubectl apply -f deployment/k8s/xagent-api-deployment.yaml
kubectl apply -f deployment/k8s/xagent-worker-deployment.yaml
kubectl apply -f deployment/k8s/xagent-beat-deployment.yaml

# Deploy ingress
kubectl apply -f deployment/k8s/ingress.yaml

# Check deployment status
kubectl get deployments -n xagent
kubectl get pods -n xagent
kubectl get services -n xagent
```

## Helm Deployment

### Installation

```bash
# Add Helm repository (if applicable)
helm repo add xagent https://charts.xagent.dev
helm repo update

# Install release
helm install xagent deployment/helm \
  --namespace xagent \
  --create-namespace \
  --values deployment/helm/values.yaml

# Or upgrade existing release
helm upgrade --install xagent deployment/helm \
  --namespace xagent \
  --create-namespace \
  --values deployment/helm/values.yaml
```

### Custom Values

Create `values-production.yaml`:

```yaml
global:
  environment: production
  logLevel: INFO
  debug: false

api:
  replicas: 5
  autoscaling:
    enabled: true
    minReplicas: 5
    maxReplicas: 20

secrets:
  dbPassword: your-secure-password
  redisPassword: your-secure-password
  qdrantApiKey: your-secure-key
  neo4jPassword: your-secure-password
  secretKey: your-secure-secret-key
```

Deploy with custom values:

```bash
helm install xagent deployment/helm \
  --namespace xagent \
  --create-namespace \
  --values deployment/helm/values-production.yaml
```

### Helm Commands

```bash
# List releases
helm list -n xagent

# Get release values
helm get values xagent -n xagent

# Get release manifest
helm get manifest xagent -n xagent

# Upgrade release
helm upgrade xagent deployment/helm -n xagent

# Rollback release
helm rollback xagent -n xagent

# Delete release
helm uninstall xagent -n xagent
```

## Environment Configuration

### Development Environment

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
DEBUG=true
API_WORKERS=1
```

### Staging Environment

```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO
DEBUG=false
API_WORKERS=2
```

### Production Environment

```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
DEBUG=false
API_WORKERS=4
```

## Database Migrations

### Running Migrations

```bash
# Using Docker Compose
docker-compose exec xagent-api alembic upgrade head

# Using Kubernetes
kubectl exec -it deployment/xagent-api -n xagent -- alembic upgrade head

# Using Helm
helm run-migrations xagent -n xagent
```

### Creating Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "Add new table"

# Review migration file
cat alembic/versions/xxx_add_new_table.py

# Apply migration
alembic upgrade head
```

### Rollback Migrations

```bash
# Rollback one version
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123def456
```

## Monitoring and Logging

### Prometheus Metrics

Access Prometheus at `http://localhost:9090`

Key metrics:
- `xagent_api_requests_total` - Total API requests
- `xagent_api_request_duration_seconds` - Request duration
- `xagent_database_connections` - Database connections
- `xagent_redis_operations` - Redis operations

### Grafana Dashboards

Access Grafana at `http://localhost:3000`

Default credentials:
- Username: admin
- Password: admin

### Logs

```bash
# Docker Compose logs
docker-compose logs -f xagent-api

# Kubernetes logs
kubectl logs -f deployment/xagent-api -n xagent

# Tail last 100 lines
kubectl logs --tail=100 deployment/xagent-api -n xagent

# Follow logs from all pods
kubectl logs -f -l app=xagent-api -n xagent
```

## Backup and Recovery

### Database Backup

```bash
# Using Docker Compose
docker-compose exec postgres pg_dump -U xagent xagent_db > backup.sql

# Using Kubernetes
kubectl exec -it deployment/postgres -n xagent -- \
  pg_dump -U xagent xagent_db > backup.sql
```

### Database Restore

```bash
# Using Docker Compose
docker-compose exec -T postgres psql -U xagent xagent_db < backup.sql

# Using Kubernetes
kubectl exec -i deployment/postgres -n xagent -- \
  psql -U xagent xagent_db < backup.sql
```

### Redis Backup

```bash
# Using Docker Compose
docker-compose exec redis redis-cli BGSAVE

# Using Kubernetes
kubectl exec deployment/redis -n xagent -- redis-cli BGSAVE
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

```bash
# Check database service
docker-compose ps postgres
kubectl get pods -n xagent -l app=postgres

# Check database logs
docker-compose logs postgres
kubectl logs deployment/postgres -n xagent

# Test connection
docker-compose exec xagent-api psql -h postgres -U xagent -d xagent_db
```

#### 2. Redis Connection Failed

```bash
# Check Redis service
docker-compose ps redis
kubectl get pods -n xagent -l app=redis

# Test connection
docker-compose exec xagent-api redis-cli -h redis ping
```

#### 3. API Not Responding

```bash
# Check API logs
docker-compose logs xagent-api
kubectl logs deployment/xagent-api -n xagent

# Check API health
curl http://localhost:8000/health

# Check resource usage
docker stats xagent-api
kubectl top pods -n xagent
```

#### 4. High Memory Usage

```bash
# Check memory usage
docker stats
kubectl top nodes
kubectl top pods -n xagent

# Restart service
docker-compose restart xagent-api
kubectl rollout restart deployment/xagent-api -n xagent
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready -U xagent

# Redis health
docker-compose exec redis redis-cli ping

# Qdrant health
curl http://localhost:6333/health

# Neo4j health
curl http://localhost:7474
```

## Performance Tuning

### Database Optimization

```sql
-- Create indexes
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_runs_created_at ON runs(created_at);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM workflows WHERE status = 'active';
```

### Redis Optimization

```bash
# Monitor Redis
redis-cli MONITOR

# Check memory usage
redis-cli INFO memory

# Optimize memory
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### API Optimization

- Increase `API_WORKERS` for higher concurrency
- Enable caching for frequently accessed data
- Use connection pooling for database connections
- Monitor and optimize slow queries

## Security Considerations

1. **Secrets Management**
   - Use Kubernetes Secrets or external secret management
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

## Support and Documentation

For more information, visit:
- GitHub: https://github.com/xagent/xagent
- Documentation: https://docs.xagent.dev
- Issues: https://github.com/xagent/xagent/issues
