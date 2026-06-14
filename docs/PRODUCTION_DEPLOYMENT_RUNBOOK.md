# X-Agent Production Deployment Runbook

**Version**: 2.0.0  
**Last Updated**: 2026-06-14  
**Status**: Production-Ready  
**Audience**: DevOps, SRE, Platform Engineering Teams

---

## Table of Contents

1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Deployment Options](#2-deployment-options)
3. [Option A: Docker Compose (Single Server)](#3-option-a-docker-compose-single-server)
4. [Option B: Kubernetes (Multi-Zone HA)](#4-option-b-kubernetes-multi-zone-ha)
5. [Option C: Lite Mode (Development/Demo)](#5-option-c-lite-mode-developmentdemo)
6. [Post-Deployment Verification](#6-post-deployment-verification)
7. [Monitoring & Observability](#7-monitoring--observability)
8. [Rollback Procedures](#8-rollback-procedures)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Scaling Guide](#10-scaling-guide)
11. [Maintenance Windows](#11-maintenance-windows)
12. [Disaster Recovery](#12-disaster-recovery)

---

## 1. Pre-Deployment Checklist

### Infrastructure Requirements

#### Compute
- [ ] Target environment provisioned (VM, EC2, GCP Compute Engine, etc.)
- [ ] Minimum specs verified:
  - [ ] CPU: 4+ cores (8+ for high-volume production)
  - [ ] RAM: 16GB+ (32GB+ for production)
  - [ ] Storage: 100GB+ SSD (depends on data volume)
  - [ ] Network: 1Gbps+ connectivity
- [ ] Firewall rules configured for inbound/outbound traffic
- [ ] SSH/RDP access confirmed by operations team

#### Database & Cache
- [ ] PostgreSQL 14+ database ready
  - [ ] Admin credentials secured in password manager
  - [ ] Backup job configured (daily backups, 30-day retention)
  - [ ] Connection pooling enabled (pgBouncer recommended)
  - [ ] Replication set up (for HA; optional but recommended)
  - [ ] Monitoring probes configured (alert on replication lag >5s)
- [ ] Redis 7+ cache (optional but recommended)
  - [ ] Persistence enabled (RDB snapshots or AOF)
  - [ ] Replication/Sentinel configured for HA
  - [ ] Memory limits set conservatively (80% of available RAM)
- [ ] Qdrant 1.0+ vector database (if using vector search)
  - [ ] Storage path on high-performance SSD
  - [ ] Snapshots scheduled (daily to cloud storage)

#### Secrets & Credentials
- [ ] Master encryption key generated and stored securely
  - [ ] In HashiCorp Vault, AWS Secrets Manager, or equivalent
  - [ ] Access restricted to deployment automation + on-call team
  - [ ] Rotation policy set (quarterly at minimum)
- [ ] API keys generated for integrations:
  - [ ] OpenAI / Anthropic / Ollama (if using as LLM provider)
  - [ ] GitHub (for issue-to-PR automation)
  - [ ] Feishu / Slack / email service (for notifications)
- [ ] Database credentials rotated if reusing infrastructure
- [ ] SSL/TLS certificates provisioned (self-signed for dev, real certs for prod)

#### Networking & DNS
- [ ] DNS entry created pointing to deployment (e.g., `xagent.example.com`)
- [ ] SSL/TLS certificate installed and tested
- [ ] Load balancer configured (if multi-instance)
- [ ] API rate limiting configured upstream (CDN/WAF)
- [ ] VPN/Bastion access configured for team

#### Monitoring & Observability
- [ ] Prometheus set up (or Datadog/New Relic agent installed)
- [ ] Logging aggregation configured (ELK, Splunk, or Datadog)
- [ ] Tracing enabled (optional; Langfuse integration ready)
- [ ] Alerting rules loaded into AlertManager
- [ ] PagerDuty / Opsgenie integration configured for escalation
- [ ] Dashboard templates imported (Grafana or cloud provider native)

#### Documentation & Runbooks
- [ ] Runbook team trained on escalation procedures
- [ ] SSH keys distributed to on-call engineers
- [ ] Emergency contact list circulated
- [ ] Rollback plan documented and reviewed
- [ ] Change log ready (for post-deployment communication)

### Deployment Artifacts
- [ ] Docker images built and pushed to registry
  - [ ] Backend image: `x-agent/backend:2.0.0-final`
  - [ ] Frontend image: `x-agent/frontend:2.0.0-final`
  - [ ] Images scanned for vulnerabilities (Trivy / Snyk)
  - [ ] Image signatures verified (if using Docker Content Trust)
- [ ] Kubernetes manifests validated (if using K8s)
  - [ ] `kubeval` or similar tool run: `kubeval manifests/*.yaml`
  - [ ] Resource quotas reviewed (no infinite requests)
  - [ ] Security policies applied (Pod Security Policy, Network Policy)
- [ ] Database migrations prepared
  - [ ] Alembic migration files reviewed by DB team
  - [ ] Test run against staging database confirmed
  - [ ] Rollback migration written and tested
- [ ] Configuration files prepared
  - [ ] `docker-compose.yml` reviewed for sensitive data (none present)
  - [ ] Environment files (`backend.env`, `frontend.env`) prepared
  - [ ] Secrets injected via Vault/Secrets Manager (not hardcoded)

### Approval & Sign-Off
- [ ] Technical lead reviewed deployment plan
- [ ] Security team approved infrastructure & permissions
- [ ] Database team approved migrations
- [ ] On-call team acknowledged escalation chain
- [ ] Change advisory board (CAB) approval obtained (enterprise only)

---

## 2. Deployment Options

| Option | Best For | Complexity | Cost | HA Support |
|--------|----------|-----------|------|-----------|
| **Docker Compose** | Single-server, dev, small production | Low | $100-500/mo | Manual failover |
| **Kubernetes** | Multi-zone, enterprise, high-load | High | $500-5k+/mo | Built-in HA |
| **Lite Mode** | Demos, prototyping, learning | Very Low | $0 (local) | None |

---

## 3. Option A: Docker Compose (Single Server)

### 3.1 Prerequisites

```bash
# Verify Docker installation
docker --version
# Expected: Docker version 25.0+

# Verify Docker Compose
docker-compose --version
# Expected: Docker Compose version v2.20+

# Verify disk space
df -h /
# Expected: At least 100GB free

# Create non-root deployment user
sudo useradd -m -s /bin/bash xagent
sudo usermod -aG docker xagent
```

### 3.2 Environment Setup

```bash
# Clone repository and switch to deployment branch
cd /opt/x-agent || sudo mkdir -p /opt/x-agent && cd /opt/x-agent
git clone https://github.com/x-agent/x-agent.git .
git checkout v2.0.0

# Create data directories
sudo mkdir -p /data/x-agent/{postgres,redis,qdrant,logs}
sudo chown -R xagent:xagent /data/x-agent
chmod 700 /data/x-agent/*

# Create secrets directory
sudo mkdir -p /etc/x-agent/secrets
sudo chown xagent:xagent /etc/x-agent/secrets
chmod 700 /etc/x-agent/secrets
```

### 3.3 Configuration Files

Create `backend.env`:
```bash
# X-Agent Backend Configuration
APP_ENV=production
DEBUG=false
LOG_LEVEL=info

# Database
DB_URL=postgresql://xagent:${DB_PASSWORD}@postgres:5432/xagent
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant (vector search)
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=${QDRANT_KEY}

# LLM Providers
OPENAI_API_KEY=${OPENAI_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_KEY}
OLLAMA_BASE_URL=http://ollama:11434

# Authentication
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRATION=86400

# Email / Notifications
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASS}
NOTIFICATION_EMAIL=noreply@example.com

# Integrations
GITHUB_TOKEN=${GITHUB_TOKEN}
FEISHU_BOT_TOKEN=${FEISHU_TOKEN}
SLACK_BOT_TOKEN=${SLACK_TOKEN}

# Observability
LANGFUSE_API_KEY=${LANGFUSE_KEY}
PROMETHEUS_SCRAPE_INTERVAL=15s

# Security
HMAC_SECRET=${HMAC_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
CORS_ORIGINS=https://xagent.example.com

# Rate limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600
```

Create `frontend.env`:
```bash
# X-Agent Frontend Configuration
VITE_API_URL=https://xagent.example.com/api
VITE_WS_URL=wss://xagent.example.com/ws
VITE_LOG_LEVEL=info
VITE_SENTRY_DSN=https://... (if using error tracking)
```

### 3.4 Docker Compose File

Create `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: xagent-postgres
    environment:
      POSTGRES_DB: xagent
      POSTGRES_USER: xagent
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - /data/x-agent/postgres:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"  # Localhost only for security
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U xagent"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: xagent-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - /data/x-agent/redis:/data
    ports:
      - "127.0.0.1:6379:6379"  # Localhost only
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Qdrant Vector Database (optional)
  qdrant:
    image: qdrant/qdrant:latest
    container_name: xagent-qdrant
    environment:
      QDRANT_API_KEY: ${QDRANT_KEY}
    volumes:
      - /data/x-agent/qdrant:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"  # Localhost only
    restart: unless-stopped

  # X-Agent Backend
  backend:
    image: x-agent/backend:2.0.0-final
    container_name: xagent-backend
    env_file:
      - backend.env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - /data/x-agent/logs:/app/logs
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  # X-Agent Frontend
  frontend:
    image: x-agent/frontend:2.0.0-final
    container_name: xagent-frontend
    env_file:
      - frontend.env
    ports:
      - "3000:3000"
    depends_on:
      - backend
    healthcheck:
      test: ["CMD", "wget", "-q", "-O-", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Nginx Reverse Proxy / Load Balancer
  nginx:
    image: nginx:alpine
    container_name: xagent-nginx
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/x-agent/secrets/tls:/etc/nginx/tls:ro
      - /data/x-agent/logs/nginx:/var/log/nginx
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:

networks:
  default:
    name: xagent-network
    driver: bridge
```

### 3.5 Nginx Configuration

Create `nginx.conf`:
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
    use epoll;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 20M;

    # Gzip compression
    gzip on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/javascript application/json application/javascript;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=1000r/s;

    # Upstream backends
    upstream frontend {
        server frontend:3000;
    }

    upstream backend {
        server backend:8000;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name xagent.example.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl http2;
        server_name xagent.example.com;

        # TLS configuration
        ssl_certificate /etc/nginx/tls/cert.pem;
        ssl_certificate_key /etc/nginx/tls/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Backend API
        location /api/ {
            limit_req zone=api_limit burst=200 nodelay;
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_buffering off;
            proxy_request_buffering off;
        }

        # WebSocket
        location /ws/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check endpoint
        location /health {
            access_log off;
            proxy_pass http://backend;
        }
    }
}
```

### 3.6 Database Migration

```bash
# Run Alembic migrations
docker-compose exec backend alembic upgrade head

# Verify migration applied
docker-compose exec backend alembic current
# Expected: (head) sha1234567 -> Upgrade message

# If migration fails, rollback:
docker-compose exec backend alembic downgrade -1
```

### 3.7 Start Services

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Verify services are running
docker-compose ps
# Expected: All containers showing "Up (healthy)"

# Monitor logs in real-time
docker-compose logs -f backend

# Check for errors
docker-compose logs | grep -i error
```

### 3.8 Verify Deployment

```bash
# Test HTTP redirect
curl -i http://localhost/
# Expected: 301 redirect to HTTPS

# Test API health
curl -k https://localhost/health
# Expected: {"status": "ok"}

# Test frontend
curl -k https://localhost/
# Expected: HTML response

# Check database connectivity
docker-compose exec backend curl -s http://localhost:8000/api/v1/health | jq .db_status
# Expected: "ok"
```

---

## 4. Option B: Kubernetes (Multi-Zone HA)

### 4.1 Cluster Prerequisites

```bash
# Verify kubectl installation
kubectl version --client
# Expected: v1.27+

# Verify cluster access
kubectl cluster-info
# Expected: Kubernetes master is running at https://...

# Verify node resources
kubectl top nodes
# Expected: Sufficient CPU/memory across nodes

# Create namespace
kubectl create namespace xagent-prod
kubectl config set-context --current --namespace=xagent-prod
```

### 4.2 Create ConfigMaps & Secrets

```bash
# Create backend configuration
kubectl create configmap backend-config \
  --from-literal=APP_ENV=production \
  --from-literal=LOG_LEVEL=info \
  --from-literal=WORKERS=4 \
  -n xagent-prod

# Create secrets (use Vault or sealed-secrets in production)
kubectl create secret generic backend-secrets \
  --from-literal=DB_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=REDIS_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=JWT_SECRET=$(openssl rand -base64 64) \
  --from-literal=HMAC_SECRET=$(openssl rand -base64 64) \
  --from-literal=ENCRYPTION_KEY=$(openssl rand -base64 32) \
  -n xagent-prod

# Create TLS secret
kubectl create secret tls xagent-tls \
  --cert=/path/to/cert.pem \
  --key=/path/to/key.pem \
  -n xagent-prod
```

### 4.3 Deploy PostgreSQL (Helm + StatefulSet)

```bash
# Add PostgreSQL Helm chart
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Install PostgreSQL
helm install postgres bitnami/postgresql \
  --namespace xagent-prod \
  --values - <<EOF
auth:
  postgresPassword: $(kubectl get secret backend-secrets -o jsonpath='{.data.DB_PASSWORD}' | base64 -d)
  username: xagent
  password: $(kubectl get secret backend-secrets -o jsonpath='{.data.DB_PASSWORD}' | base64 -d)
  database: xagent

primary:
  persistence:
    size: 100Gi
    storageClassName: fast-ssd

replica:
  replicaCount: 2
  persistence:
    size: 100Gi
    storageClassName: fast-ssd

metrics:
  enabled: true
  serviceMonitor:
    enabled: true
EOF

# Verify PostgreSQL is running
kubectl rollout status statefulset/postgres-postgresql -n xagent-prod
```

### 4.4 Deploy Redis (Helm)

```bash
# Install Redis with Sentinel
helm install redis bitnami/redis \
  --namespace xagent-prod \
  --values - <<EOF
auth:
  password: $(kubectl get secret backend-secrets -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d)

master:
  persistence:
    size: 50Gi
    storageClassName: fast-ssd

replica:
  replicaCount: 2
  persistence:
    size: 50Gi

sentinel:
  enabled: true
  quorum: 2

metrics:
  enabled: true
EOF

# Verify Redis is running
kubectl rollout status statefulset/redis-master -n xagent-prod
```

### 4.5 Deploy Backend (Deployment)

Create `backend-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-backend
  namespace: xagent-prod
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: xagent-backend
  template:
    metadata:
      labels:
        app: xagent-backend
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - xagent-backend
              topologyKey: kubernetes.io/hostname
      containers:
      - name: backend
        image: x-agent/backend:2.0.0-final
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: http
        envFrom:
        - configMapRef:
            name: backend-config
        - secretRef:
            name: backend-secrets
        env:
        - name: DB_URL
          value: postgresql://xagent:$(DB_PASSWORD)@postgres-postgresql:5432/xagent
        - name: REDIS_URL
          value: redis://:$(REDIS_PASSWORD)@redis-master:6379
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi
      serviceAccountName: xagent-backend
---
apiVersion: v1
kind: Service
metadata:
  name: xagent-backend-svc
  namespace: xagent-prod
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  selector:
    app: xagent-backend
```

Apply deployment:
```bash
kubectl apply -f backend-deployment.yaml
kubectl rollout status deployment/xagent-backend -n xagent-prod
```

### 4.6 Deploy Frontend (Deployment)

Create `frontend-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-frontend
  namespace: xagent-prod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: xagent-frontend
  template:
    metadata:
      labels:
        app: xagent-frontend
    spec:
      containers:
      - name: frontend
        image: x-agent/frontend:2.0.0-final
        ports:
        - containerPort: 3000
        env:
        - name: VITE_API_URL
          value: https://xagent.example.com/api
        livenessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 3000
          initialDelaySeconds: 5
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: xagent-frontend-svc
  namespace: xagent-prod
spec:
  type: ClusterIP
  ports:
  - port: 3000
    targetPort: 3000
  selector:
    app: xagent-frontend
```

Apply deployment:
```bash
kubectl apply -f frontend-deployment.yaml
```

### 4.7 Configure Ingress (TLS termination)

Create `ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: xagent-ingress
  namespace: xagent-prod
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "1000"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - xagent.example.com
    secretName: xagent-tls
  rules:
  - host: xagent.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: xagent-backend-svc
            port:
              number: 8000
      - path: /ws
        pathType: Prefix
        backend:
          service:
            name: xagent-backend-svc
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: xagent-frontend-svc
            port:
              number: 3000
```

Apply ingress:
```bash
kubectl apply -f ingress.yaml
```

### 4.8 Deploy Monitoring

```bash
# Install Prometheus + Grafana
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace xagent-prod

# Install logging (ELK or Loki)
helm install loki grafana/loki-stack \
  --namespace xagent-prod
```

---

## 5. Option C: Lite Mode (Development/Demo)

Lite mode runs X-Agent with SQLite (no external database) and in-memory cache.

### 5.1 Install & Run

```bash
# Clone repository
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# Install Python dependencies
pip install -e ".[lite]"

# Set environment for lite mode
export XAGENT_MODE=lite
export DB_URL=sqlite:///./xagent.db
export LOG_LEVEL=debug

# Run backend (development server)
python -m xagent.main

# In another terminal, run frontend
cd frontend
npm install
npm run dev
```

Frontend accessible at `http://localhost:5173`  
Backend API at `http://localhost:8000`  
API docs at `http://localhost:8000/docs`

---

## 6. Post-Deployment Verification

### 6.1 Health Checks

```bash
# Backend health
curl https://xagent.example.com/health
# Expected JSON:
# {
#   "status": "ok",
#   "version": "2.0.0",
#   "db_status": "ok",
#   "cache_status": "ok",
#   "uptime_seconds": 123
# }

# Frontend health
curl -L https://xagent.example.com/
# Expected: HTML document

# Database connectivity
curl https://xagent.example.com/api/v1/system/db-status
# Expected: {"status": "connected", "pool_connections": 18/20}

# Cache connectivity
curl https://xagent.example.com/api/v1/system/cache-status
# Expected: {"status": "connected", "memory_mb": 256}
```

### 6.2 Functional Tests

```bash
# Create test session
curl -X POST https://xagent.example.com/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}' \
  -H "Authorization: Bearer $API_TOKEN"

# List sessions
curl https://xagent.example.com/api/v1/sessions \
  -H "Authorization: Bearer $API_TOKEN"

# Test agent execution
curl -X POST https://xagent.example.com/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{
    "prompt": "Hello, world!",
    "session_id": "<session_id>"
  }'
```

### 6.3 Performance Validation

```bash
# Load test (using Apache Bench)
ab -n 1000 -c 10 https://xagent.example.com/health

# Expected: 
# - Requests per second: > 100
# - Failed requests: 0
# - Time per request: < 100ms

# Memory usage check
free -h  # Or: docker stats (for Docker Compose)
# Expected: Memory usage < 50% of available

# Disk usage check
df -h /data/x-agent
# Expected: Usage < 70% of allocated
```

---

## 7. Monitoring & Observability

### 7.1 Prometheus Metrics Scraping

```bash
# Verify metrics endpoint
curl https://xagent.example.com/metrics

# Expected: Prometheus-format metrics
# TYPE xagent_http_requests_total counter
# TYPE xagent_http_request_duration_seconds histogram
# TYPE xagent_db_query_duration_seconds histogram
```

### 7.2 Log Aggregation

Direct logs to centralized logging system:

```yaml
# fluent-bit configuration
[SERVICE]
  Flush        5
  Daemon       Off
  Log_Level    info

[INPUT]
  Name              systemd
  Tag               xagent.*
  Path              /var/log/journal
  Read_From_Tail    On

[OUTPUT]
  Name   stdout
  Match  *
```

### 7.3 Alerting Rules

Create `alerts.yaml` for AlertManager:
```yaml
groups:
- name: xagent
  interval: 30s
  rules:
  - alert: XAgentBackendDown
    expr: up{job="xagent-backend"} == 0
    for: 5m
    annotations:
      summary: "X-Agent backend is down"

  - alert: HighErrorRate
    expr: rate(xagent_http_errors_total[5m]) > 0.05
    annotations:
      summary: "Error rate exceeds 5%"

  - alert: DatabaseConnectionPoolExhausted
    expr: xagent_db_pool_utilization > 0.95
    annotations:
      summary: "Database connection pool near capacity"

  - alert: CacheMemoryHigh
    expr: xagent_cache_memory_bytes / xagent_cache_max_memory_bytes > 0.9
    annotations:
      summary: "Cache memory usage above 90%"
```

---

## 8. Rollback Procedures

### 8.1 Immediate Rollback (within 30 minutes)

```bash
# Docker Compose rollback
docker-compose -f docker-compose.prod.yml down
git checkout v2.0.0-previous
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Verify rollback successful
docker-compose ps
curl https://xagent.example.com/health
```

### 8.2 Database Rollback

```bash
# If migration caused issues
docker-compose exec backend alembic downgrade -1

# Verify rollback
docker-compose exec backend alembic current
```

### 8.3 Kubernetes Rollback

```bash
# Automatic rollback to previous deployment
kubectl rollout undo deployment/xagent-backend -n xagent-prod
kubectl rollout status deployment/xagent-backend -n xagent-prod

# Or rollback to specific revision
kubectl rollout history deployment/xagent-backend -n xagent-prod
kubectl rollout undo deployment/xagent-backend --to-revision=3 -n xagent-prod
```

---

## 9. Troubleshooting Guide

### Issue: "Backend container crashes on startup"

**Symptoms:**
```
xagent-backend exited with code 1
```

**Diagnosis:**
```bash
# Check backend logs
docker-compose logs backend -n 100
# Look for: "Connection refused", "Permission denied", etc.
```

**Solutions:**
1. Verify database is running: `docker-compose exec postgres pg_isready`
2. Check database credentials in `backend.env`
3. Ensure `/data/x-agent` has correct ownership: `ls -l /data/x-agent`
4. Verify network connectivity: `docker-compose exec backend ping postgres`

### Issue: "API returning 500 errors"

**Diagnosis:**
```bash
# Check backend error logs
docker-compose logs backend | grep -i error | tail -20

# Check database query logs
docker-compose exec postgres psql -U xagent -d xagent -c "SELECT NOW();"
```

**Solutions:**
1. Check database connection pool: `curl https://xagent.example.com/api/v1/system/db-status`
2. Review recent code changes: `git log --oneline -n 10`
3. Check disk space: `df -h`
4. Restart backend: `docker-compose restart backend`

### Issue: "Slow API responses"

**Diagnosis:**
```bash
# Check server load
top -b -n 1 | head -15

# Check database query performance
docker-compose exec backend curl -s http://localhost:8000/metrics | grep db_query_duration
```

**Solutions:**
1. Increase resource limits in `docker-compose.yml`
2. Scale horizontally (add more backend replicas in Kubernetes)
3. Add caching layer (Redis is already included)
4. Analyze slow queries: `docker-compose exec postgres psql ... -c "EXPLAIN ANALYZE ..."`

### Issue: "Certificate/SSL errors"

**Diagnosis:**
```bash
# Check certificate validity
openssl x509 -in /etc/x-agent/secrets/tls/cert.pem -text -noout

# Verify certificate chain
openssl verify /etc/x-agent/secrets/tls/cert.pem
```

**Solutions:**
1. Regenerate certificate: `certbot renew --force-renewal`
2. Update Nginx secret: `kubectl delete secret xagent-tls && kubectl create secret tls xagent-tls ...`
3. Reload Nginx: `docker-compose exec nginx nginx -s reload` or `kubectl rollout restart deployment/nginx`

---

## 10. Scaling Guide

### 10.1 Vertical Scaling (increase resource per instance)

```yaml
# Update in docker-compose.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '8'  # Was 4
          memory: 16G  # Was 8G
```

Then:
```bash
docker-compose up -d backend  # Restart with new limits
```

### 10.2 Horizontal Scaling (add more instances)

For Docker Compose, use multiple backend services:
```yaml
services:
  backend-1:
    image: x-agent/backend:2.0.0-final
    container_name: xagent-backend-1
    # ... config ...

  backend-2:
    image: x-agent/backend:2.0.0-final
    container_name: xagent-backend-2
    # ... config ...

  # Update nginx to load-balance across both
```

For Kubernetes:
```bash
# Scale to 5 replicas
kubectl scale deployment xagent-backend --replicas=5 -n xagent-prod

# Monitor scaling progress
kubectl get deployment xagent-backend -n xagent-prod -w
```

### 10.3 Database Scaling

```bash
# Increase connection pool size
# In backend.env:
DB_POOL_SIZE=50  # Was 20
DB_MAX_OVERFLOW=20  # Was 10

# Increase read replicas (Kubernetes only)
helm upgrade postgres bitnami/postgresql \
  --set replica.replicaCount=5 \
  --namespace xagent-prod
```

---

## 11. Maintenance Windows

### 11.1 Scheduled Maintenance (zero-downtime)

```bash
# 1. Create new deployment with updated version
git checkout v2.1.0-rc1
docker build -t x-agent/backend:2.1.0-rc1 -f backend/Dockerfile .
docker push x-agent/backend:2.1.0-rc1

# 2. Apply database migrations in staging first
docker-compose -f docker-compose.staging.yml exec backend alembic upgrade head

# 3. Update production deployment (rolling update)
kubectl set image deployment/xagent-backend \
  xagent-backend=x-agent/backend:2.1.0-rc1 \
  -n xagent-prod

# 4. Monitor rollout
kubectl rollout status deployment/xagent-backend -n xagent-prod

# 5. Verify new version
curl https://xagent.example.com/api/v1/system/version
# Expected: {"version": "2.1.0"}
```

### 11.2 Emergency Maintenance (with downtime)

```bash
# 1. Notify users
# Send maintenance window notification via email/chat

# 2. Gracefully shut down
docker-compose down
# or: kubectl scale deployment/xagent-backend --replicas=0 -n xagent-prod

# 3. Perform maintenance (e.g., data cleanup)
docker-compose exec postgres psql -U xagent -d xagent -c "VACUUM FULL;"

# 4. Restart services
docker-compose up -d
# or: kubectl scale deployment/xagent-backend --replicas=3 -n xagent-prod

# 5. Verify health
curl https://xagent.example.com/health
```

---

## 12. Disaster Recovery

### 12.1 Backup & Restore

**Daily Backups:**
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/x-agent"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Backup PostgreSQL
docker-compose exec -T postgres pg_dump -U xagent xagent | \
  gzip > $BACKUP_DIR/postgres-$TIMESTAMP.sql.gz

# Backup data directories
tar -czf $BACKUP_DIR/data-$TIMESTAMP.tar.gz /data/x-agent

# Upload to S3/cloud storage
aws s3 cp $BACKUP_DIR/ s3://x-agent-backups/ --recursive
```

**Schedule with cron:**
```bash
0 2 * * * /opt/x-agent/backup.sh  # Run daily at 2 AM
```

**Restore from backup:**
```bash
# Restore PostgreSQL
gunzip < /backups/x-agent/postgres-20260614.sql.gz | \
  docker-compose exec -T postgres psql -U xagent xagent

# Restore data
tar -xzf /backups/x-agent/data-20260614.tar.gz -C /
```

### 12.2 Failover Procedure (to standby instance)

```bash
# 1. Update DNS to point to standby
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123 \
  --change-batch file://failover.json

# 2. Promote standby to primary
# (Database-specific, see your DB provider docs)

# 3. Monitor new primary
kubectl logs deployment/xagent-backend -n xagent-prod -f

# 4. Once stable, provision new standby
# (Follow original deployment procedure)
```

### 12.3 Disaster Recovery Plan (RTO/RPO)

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single container crash | 5 min | 0 min | Auto-restart via health checks |
| Database failure | 30 min | 5 min | Restore from latest backup |
| Zone failure | 15 min | 0 min | Failover to standby (multi-AZ) |
| Complete loss | 4 hours | 1 hour | Restore from cloud backup + rebuild |

---

## Final Checklist

- [ ] All pre-deployment checks passed
- [ ] Secrets securely managed (not in Git/logs)
- [ ] Monitoring & alerting configured
- [ ] Backup scheduled and tested
- [ ] Rollback procedure documented and tested
- [ ] Team trained on deployment & troubleshooting
- [ ] Post-deployment validation completed
- [ ] Deployment documented with timestamps
- [ ] Status communicated to stakeholders
- [ ] Runbook updated with deployment details

---

**Document Owner**: DevOps/SRE Team  
**Last Updated**: 2026-06-14  
**Next Review**: 2026-07-14  
**Emergency Contact**: on-call@x-agent.dev
