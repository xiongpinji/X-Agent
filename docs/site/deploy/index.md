# Deployment Guide

This guide covers deploying X-Agent to production environments. Choose your deployment platform below.

## Quick Start

The fastest way to get X-Agent running:

```bash
# Clone the repository
git clone https://github.com/xiongpinji/X-Agent.git
cd X-Agent

# Start with Docker Compose
docker compose up -d

# Verify it's running
curl http://localhost:8000/health
```

Access the dashboard at `http://localhost:3000`

## Deployment Options

### Development
- **Local**: Run on your machine using `docker compose up`
- **Quick**: Great for testing and development
- **Data**: SQLite (not suitable for production)

### Staging
- **Docker Compose**: Multi-container setup on a single server
- **Good for**: Testing before production
- **Data**: PostgreSQL recommended

### Production
- **Kubernetes**: Recommended for scale and reliability
- **AWS ECS/EKS**: AWS-managed container services
- **Cloud Platforms**: GCP, Azure, DigitalOcean support

## Platform-Specific Guides

### Docker
Self-contained containerized deployment.

```bash
# Build image
docker build -t xagent:latest .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  xagent:latest
```

[Full Docker guide →](/deploy/docker)

### Docker Compose
Multi-container orchestration on a single host.

```bash
docker compose up -d
docker compose ps
docker compose logs -f backend
```

[Full Docker Compose guide →](/deploy/docker-compose)

### Kubernetes
Orchestration for production at scale.

```bash
# Deploy with Helm
helm repo add xagent https://charts.xagent.dev
helm install xagent xagent/xagent \
  --namespace xagent \
  --create-namespace
```

[Full Kubernetes guide →](/deploy/kubernetes)

### Cloud Platforms

#### AWS
- **ECS**: Elastic Container Service
- **EKS**: Elastic Kubernetes Service
- **RDS**: Managed PostgreSQL
- **ElastiCache**: Managed Redis

[AWS deployment guide →](/deploy/aws-ecs)

#### Google Cloud
- **Cloud Run**: Serverless containers
- **GKE**: Google Kubernetes Engine
- **Cloud SQL**: Managed PostgreSQL
- **Memorystore**: Managed Redis

[GCP deployment guide →](/deploy/google-cloud)

#### Azure
- **Container Instances**: Managed containers
- **AKS**: Azure Kubernetes Service
- **Azure Database**: Managed PostgreSQL
- **Azure Cache**: Managed Redis

[Azure deployment guide →](/deploy/azure)

#### Self-Hosted
Deploy on your own infrastructure with full control.

[Self-hosted guide →](/deploy/self-hosted)

## Architecture

### Components

```
┌─────────────────────────────────────┐
│        Load Balancer / Ingress      │
└────────────────┬────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼──┐    ┌───▼──┐    ┌───▼──┐
│ API  │    │ API  │    │ API  │  (replicated)
│ Pod  │    │ Pod  │    │ Pod  │
└───┬──┘    └───┬──┘    └───┬──┘
    │           │           │
    └───────────┼───────────┘
                │
        ┌───────┴────────┐
        │                │
    ┌───▼──┐      ┌─────▼──┐
    │ DB   │      │ Cache  │
    │ Pod  │      │ Pod    │
    └──────┘      └────────┘
```

### High Availability

- **Multiple replicas**: Each service runs in multiple pods
- **Load balancing**: Traffic distributed across replicas
- **Health checks**: Automatic restarts of failed pods
- **Persistent storage**: Database runs in HA mode
- **Auto-scaling**: Pods scale based on CPU/memory

## Prerequisites

Before deploying, ensure you have:

1. **Docker** (20.10+)
2. **Kubernetes cluster** (if using K8s) - 1.24+
3. **PostgreSQL** (14+) or managed database
4. **Redis** (6.2+) or managed cache
5. **Secrets manager** - AWS Secrets Manager, Azure Keyvault, etc.

## Configuration

### Environment Variables

```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database
DATABASE_URL=postgresql://user:pass@host:5432/xagent
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://host:6379/0
CACHE_TTL=3600

# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Observability
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
PROMETHEUS_ENABLED=true
```

[Full configuration reference →](/guide/configuration)

### Secrets Management

Store sensitive data securely:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name xagent/api-key \
  --secret-string "YOUR_API_KEY"

# Kubernetes Secrets
kubectl create secret generic xagent-secrets \
  --from-literal=database-url="..." \
  --from-literal=redis-url="..."
```

## Monitoring & Observability

### Metrics
- CPU / Memory usage
- Request latency (p50, p95, p99)
- Error rate
- Active agents
- Tool execution time

### Logging
- Structured JSON logs
- Log aggregation (Loki recommended)
- Log retention policy

### Tracing
- Distributed traces via Langfuse
- Agent decision traces
- Tool call traces

[Observability guide →](/deploy/monitoring)

## Networking

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| API Server | 8000 | HTTP API |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboard |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |

### TLS/SSL

Enable HTTPS for security:

```bash
# Let's Encrypt (recommended)
certbot certonly --standalone -d api.xagent.dev

# Self-signed certificate
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem -out cert.pem -days 365
```

[TLS configuration →](/deploy/tls)

## Database

### Setup PostgreSQL

```bash
# Docker
docker run -d \
  -e POSTGRES_DB=xagent \
  -e POSTGRES_PASSWORD=secure \
  -v pgdata:/var/lib/postgresql/data \
  postgres:14

# Or use managed service (AWS RDS, GCP Cloud SQL)
```

### Run Migrations

```bash
docker exec xagent-backend \
  alembic upgrade head
```

[Database guide →](/deploy/database)

## Scaling

### Vertical Scaling
- Increase CPU/memory per pod
- Increase database connection pool
- Increase Redis memory

### Horizontal Scaling
- Increase number of API replicas
- Use load balancer
- Configure auto-scaling rules

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xagent-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: xagent-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

[Scaling guide →](/deploy/scaling)

## Backup & Disaster Recovery

### Database Backups

```bash
# PostgreSQL backup
pg_dump xagent > backup.sql

# Restore
psql xagent < backup.sql
```

### Automated Backups

- Daily full backups
- Continuous replication
- Point-in-time recovery (PITR)
- Cross-region backups

[Backup guide →](/deploy/backup)

## Support

- **[Docker Guide](/deploy/docker)** - Containerization details
- **[Kubernetes Guide](/deploy/kubernetes)** - K8s specifics
- **[Monitoring](/deploy/monitoring)** - Observability setup
- **[Troubleshooting](/troubleshooting)** - Common issues
- **[Discord](https://discord.gg/xagent)** - Community support
