# X-Agent 部署运维手册

**版本**: 1.0.0  
**最后更新**: 2026-05-27  
**语言**: 中文 | [English](DEPLOYMENT_GUIDE_EN.md)

---

## 目录

1. [部署架构](#部署架构)
2. [环境要求](#环境要求)
3. [安装步骤](#安装步骤)
4. [配置说明](#配置说明)
5. [数据库迁移](#数据库迁移)
6. [备份和恢复](#备份和恢复)
7. [扩容方案](#扩容方案)
8. [高可用配置](#高可用配置)
9. [安全加固](#安全加固)
10. [性能调优](#性能调优)

---

## 部署架构

### 生产环境架构

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                 │
│                  (SSL/TLS Termination)                   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              API Servers (Kubernetes)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Pod 1       │  │  Pod 2       │  │  Pod 3       │   │
│  │ (FastAPI)    │  │ (FastAPI)    │  │ (FastAPI)    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Data Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ PostgreSQL   │  │ Qdrant       │  │ Redis Cache  │   │
│  │ (Primary)    │  │ (Vector DB)  │  │ (Session)    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Message Queue & Monitoring                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ RabbitMQ     │  │ Prometheus   │  │ Grafana      │   │
│  │ (Tasks)      │  │ (Metrics)    │  │ (Dashboard)  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 环境要求

### 硬件要求

| 组件 | 最小配置 | 推荐配置 | 企业配置 |
|------|---------|---------|---------|
| CPU | 2 核 | 8 核 | 16 核+ |
| 内存 | 4GB | 16GB | 32GB+ |
| 磁盘 | 50GB | 200GB | 1TB+ |
| 网络 | 100Mbps | 1Gbps | 10Gbps |

### 软件要求

- **操作系统**: Ubuntu 20.04 LTS / CentOS 8 / RHEL 8
- **Python**: 3.11+
- **PostgreSQL**: 14+
- **Docker**: 20.10+
- **Kubernetes**: 1.24+ (可选)
- **Node.js**: 18+ (前端)

### 网络要求

- 开放端口 80 (HTTP)
- 开放端口 443 (HTTPS)
- 开放端口 5432 (PostgreSQL, 内部)
- 开放端口 6333 (Qdrant, 内部)
- 开放端口 5672 (RabbitMQ, 内部)

---

## 安装步骤

### 1. Docker 部署（推荐用于开发）

#### 前置条件

```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 启动服务

```bash
# 克隆项目
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

# 配置环境变量
cp .env.example .env.production
# 编辑 .env.production

# 启动所有服务
docker-compose -f docker-compose.prod.yml up -d

# 验证服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f backend
```

### 2. Kubernetes 部署（推荐用于生产）

#### 前置条件

```bash
# 安装 kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# 安装 Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 部署应用

```bash
# 添加 Helm 仓库
helm repo add x-agent https://charts.x-agent.dev
helm repo update

# 创建命名空间
kubectl create namespace x-agent

# 部署应用
helm install x-agent x-agent/x-agent-core \
  --namespace x-agent \
  --values values.yaml

# 验证部署
kubectl get pods -n x-agent
kubectl get svc -n x-agent

# 查看日志
kubectl logs -n x-agent -l app=x-agent-backend -f
```

#### Helm Values 配置

```yaml
# values.yaml
replicaCount: 3

image:
  repository: x-agent/x-agent-core
  tag: "1.0.0"
  pullPolicy: IfNotPresent

service:
  type: LoadBalancer
  port: 80
  targetPort: 8000

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.x-agent.dev
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 1000m
    memory: 1Gi

postgresql:
  enabled: true
  auth:
    username: xagent
    password: secure_password
  primary:
    persistence:
      size: 100Gi

qdrant:
  enabled: true
  persistence:
    size: 50Gi
```

### 3. 传统部署（Linux 服务器）

#### 系统准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装依赖
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
  postgresql postgresql-contrib postgresql-client \
  nginx supervisor git curl wget

# 创建应用用户
sudo useradd -m -s /bin/bash xagent
sudo su - xagent
```

#### 应用部署

```bash
# 克隆项目
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e ".[prod]"

# 初始化数据库
python -m backend.app.core.migration init

# 收集静态文件
python manage.py collectstatic --noinput
```

#### Supervisor 配置

```ini
# /etc/supervisor/conf.d/x-agent.conf
[program:x-agent-backend]
command=/home/xagent/x-agent-core/venv/bin/uvicorn backend.app.web:app --host 0.0.0.0 --port 8000
directory=/home/xagent/x-agent-core
user=xagent
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/x-agent/backend.log

[program:x-agent-worker]
command=/home/xagent/x-agent-core/venv/bin/xagent-workflow-worker
directory=/home/xagent/x-agent-core
user=xagent
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/x-agent/worker.log
```

#### Nginx 配置

```nginx
# /etc/nginx/sites-available/x-agent
upstream x_agent_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.x-agent.dev;
    
    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.x-agent.dev;
    
    ssl_certificate /etc/letsencrypt/live/api.x-agent.dev/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.x-agent.dev/privkey.pem;
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://x_agent_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /static/ {
        alias /home/xagent/x-agent-core/static/;
    }
}
```

---

## 配置说明

### 环境变量

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/xagent
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Qdrant 配置
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_api_key

# LLM 配置
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
LLM_DEFAULT_MODEL=gpt-4

# 认证配置
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# 应用配置
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production

# 监控配置
PROMETHEUS_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_key

# 邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email
SMTP_PASSWORD=your_password
```

### 配置文件

```yaml
# config/production.yaml
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  timeout: 300

database:
  pool_size: 20
  max_overflow: 40
  echo: false

cache:
  backend: redis
  url: redis://localhost:6379/0
  ttl: 3600

logging:
  level: INFO
  format: json
  handlers:
    - console
    - file

security:
  cors_origins:
    - https://app.x-agent.dev
  allowed_hosts:
    - api.x-agent.dev
  rate_limit: 1000/minute
```

---

## 数据库迁移

### 初始化

```bash
# 创建数据库
createdb xagent

# 运行迁移
python -m backend.app.core.migration init

# 验证迁移
python -m backend.app.core.migration status
```

### 升级

```bash
# 查看待执行迁移
python -m backend.app.core.migration pending

# 执行迁移
python -m backend.app.core.migration upgrade

# 回滚迁移
python -m backend.app.core.migration downgrade
```

---

## 备份和恢复

### PostgreSQL 备份

```bash
# 完整备份
pg_dump -U postgres xagent > backup_$(date +%Y%m%d_%H%M%S).sql

# 压缩备份
pg_dump -U postgres xagent | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# 恢复备份
psql -U postgres xagent < backup.sql

# 从压缩备份恢复
gunzip -c backup.sql.gz | psql -U postgres xagent
```

### Qdrant 备份

```bash
# 创建快照
curl -X POST http://localhost:6333/snapshots

# 列出快照
curl http://localhost:6333/snapshots

# 恢复快照
curl -X POST http://localhost:6333/snapshots/recover
```

### 自动备份脚本

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/x-agent"
RETENTION_DAYS=30

# 创建备份目录
mkdir -p $BACKUP_DIR

# PostgreSQL 备份
pg_dump -U postgres xagent | gzip > $BACKUP_DIR/postgres_$(date +%Y%m%d_%H%M%S).sql.gz

# Qdrant 备份
curl -X POST http://localhost:6333/snapshots

# 清理旧备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

# 上传到 S3
aws s3 sync $BACKUP_DIR s3://x-agent-backups/
```

---

## 扩容方案

### 水平扩容

```bash
# Kubernetes 自动扩容
kubectl autoscale deployment x-agent-backend \
  --min=3 --max=10 \
  -n x-agent

# 手动扩容
kubectl scale deployment x-agent-backend \
  --replicas=5 \
  -n x-agent
```

### 垂直扩容

```yaml
# 增加资源限制
resources:
  limits:
    cpu: 4000m
    memory: 4Gi
  requests:
    cpu: 2000m
    memory: 2Gi
```

### 数据库扩容

```bash
# PostgreSQL 主从复制
# 在从服务器上执行
pg_basebackup -h primary_host -D /var/lib/postgresql/data -U replication

# 配置流复制
# recovery.conf
standby_mode = 'on'
primary_conninfo = 'host=primary_host port=5432 user=replication'
```

---

## 高可用配置

### PostgreSQL 高可用

```bash
# 使用 Patroni 实现自动故障转移
# patroni.yml
scope: xagent
namespace: /xagent/
name: postgresql-1

postgresql:
  data_dir: /var/lib/postgresql/data
  parameters:
    max_connections: 200
    shared_buffers: 256MB

ha:
  watchdog:
    mode: automatic
    device: /dev/watchdog
```

### 应用层高可用

```yaml
# Kubernetes 部署配置
apiVersion: apps/v1
kind: Deployment
metadata:
  name: x-agent-backend
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
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
                  - x-agent-backend
              topologyKey: kubernetes.io/hostname
      
      containers:
      - name: backend
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

---

## 安全加固

### SSL/TLS 配置

```bash
# 使用 Let's Encrypt 获取证书
sudo certbot certonly --standalone -d api.x-agent.dev

# 自动续期
sudo certbot renew --quiet --no-eff-email
```

### 防火墙配置

```bash
# UFW 防火墙
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 5432/tcp  # 仅允许内部访问
```

### 安全头配置

```nginx
# Nginx 安全头
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

---

## 性能调优

### PostgreSQL 调优

```sql
-- 调整共享缓冲区
ALTER SYSTEM SET shared_buffers = '256MB';

-- 调整工作内存
ALTER SYSTEM SET work_mem = '16MB';

-- 启用并行查询
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;

-- 应用更改
SELECT pg_reload_conf();
```

### 应用层调优

```python
# 连接池优化
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600
)

# 缓存优化
from functools import lru_cache

@lru_cache(maxsize=1024)
def get_agent_config(agent_id: str):
    return load_config(agent_id)
```

---

**X-Agent 部署运维手册** - 生产环境部署指南
