# X-Agent 测试环境配置指南

**版本**: 1.0  
**日期**: 2026-05-27  
**用途**: Beta测试演示服务器部署与配置

---

## 1. 环境需求

### 1.1 硬件配置

#### 最小配置 (小规模测试)
```
CPU: 4核
内存: 8GB
存储: 200GB SSD
网络: 50Mbps
```

#### 推荐配置 (中等规模)
```
CPU: 8核
内存: 16GB
存储: 500GB SSD
网络: 100Mbps
```

#### 生产配置 (大规模)
```
CPU: 16核+
内存: 32GB+
存储: 1TB+ SSD
网络: 1Gbps+
```

### 1.2 软件依赖

```
操作系统: Ubuntu 22.04 LTS / CentOS 8+ / Debian 11+
Python: 3.11+
Node.js: 18+
PostgreSQL: 14+
Redis: 7+
Docker: 24+
Docker Compose: 2.0+
```

---

## 2. 快速部署 (Docker Compose)

### 2.1 前置准备

```bash
# 1. 克隆项目
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# 2. 创建环境文件
cp .env.example .env

# 3. 编辑环境配置
nano .env
```

### 2.2 环境文件配置 (.env)

```bash
# 基础配置
ENVIRONMENT=beta
DEBUG=false
LOG_LEVEL=INFO

# 服务配置
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_PORT=3000
ADMIN_PORT=8001

# 数据库配置
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=xagent_beta
POSTGRES_USER=xagent
POSTGRES_PASSWORD=secure_password_here
DATABASE_URL=postgresql://xagent:secure_password_here@postgres:5432/xagent_beta

# Redis配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=redis_password_here

# 向量数据库配置
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_API_KEY=qdrant_api_key_here

# 认证配置
JWT_SECRET=your_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# 邮件配置
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=noreply@x-agent.io

# 存储配置
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=xagent-beta
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_REGION=us-east-1

# 监控配置
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
LOKI_ENABLED=true

# 功能开关
FEATURE_WORKFLOW=true
FEATURE_DESKTOP_AUTOMATION=true
FEATURE_MEMORY_SYSTEM=true
FEATURE_MARKETPLACE=true
FEATURE_PLUGINS=true

# 速率限制
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=3600

# 日志配置
LOG_FORMAT=json
LOG_OUTPUT=file
LOG_FILE_PATH=/var/log/xagent/app.log
LOG_MAX_SIZE=100M
LOG_BACKUP_COUNT=10
```

### 2.3 Docker Compose 配置

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15-alpine
    container_name: xagent-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # Redis 缓存
  redis:
    image: redis:7-alpine
    container_name: xagent-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # Qdrant 向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    container_name: xagent-qdrant
    environment:
      QDRANT_API_KEY: ${QDRANT_API_KEY}
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # 后端API服务
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: xagent-backend
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - QDRANT_URL=http://qdrant:6333
      - JWT_SECRET=${JWT_SECRET}
      - ENVIRONMENT=${ENVIRONMENT}
      - LOG_LEVEL=${LOG_LEVEL}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - /app/__pycache__
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - xagent-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 前端应用
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: xagent-frontend
    environment:
      - REACT_APP_API_URL=http://localhost:8000
      - REACT_APP_WS_URL=ws://localhost:8000
    depends_on:
      - backend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm start
    networks:
      - xagent-network

  # Prometheus 监控
  prometheus:
    image: prom/prometheus:latest
    container_name: xagent-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - xagent-network

  # Grafana 可视化
  grafana:
    image: grafana/grafana:latest
    container_name: xagent-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
    networks:
      - xagent-network

  # Loki 日志聚合
  loki:
    image: grafana/loki:latest
    container_name: xagent-loki
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/local-config.yml
      - loki_data:/loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yml
    networks:
      - xagent-network

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: xagent-nginx
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
      - frontend
    networks:
      - xagent-network

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  prometheus_data:
  grafana_data:
  loki_data:

networks:
  xagent-network:
    driver: bridge
```

### 2.4 启动服务

```bash
# 1. 构建镜像
docker-compose build

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 验证服务状态
docker-compose ps

# 5. 初始化数据库
docker-compose exec backend python -m alembic upgrade head

# 6. 创建超级用户
docker-compose exec backend python -m scripts.create_admin
```

---

## 3. 手动部署 (非Docker)

### 3.1 系统准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y build-essential git curl wget

# 安装Python
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 安装Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 安装PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 安装Redis
sudo apt install -y redis-server

# 安装Docker (可选)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### 3.2 后端部署

```bash
# 1. 创建虚拟环境
cd backend
python3.11 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
nano .env

# 4. 初始化数据库
alembic upgrade head

# 5. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3.3 前端部署

```bash
# 1. 安装依赖
cd frontend
npm install

# 2. 配置环境变量
cp .env.example .env
nano .env

# 3. 构建应用
npm run build

# 4. 启动开发服务器
npm start

# 或使用生产服务器
npm install -g serve
serve -s build -l 3000
```

---

## 4. 数据库初始化

### 4.1 PostgreSQL 初始化脚本

创建 `scripts/init-db.sql`:

```sql
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    avatar_url VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建组织表
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建工作流表
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    definition JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'draft',
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建执行记录表
CREATE TABLE IF NOT EXISTS executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    org_id UUID NOT NULL REFERENCES organizations(id),
    status VARCHAR(50) DEFAULT 'pending',
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_organizations_owner_id ON organizations(owner_id);
CREATE INDEX idx_workflows_org_id ON workflows(org_id);
CREATE INDEX idx_executions_workflow_id ON executions(workflow_id);
CREATE INDEX idx_executions_status ON executions(status);
```

### 4.2 运行初始化

```bash
# 使用 psql
psql -U xagent -d xagent_beta -f scripts/init-db.sql

# 或使用 Alembic
alembic upgrade head
```

---

## 5. 监控与日志配置

### 5.1 Prometheus 配置

创建 `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'xagent-backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
```

### 5.2 Grafana 仪表板

访问 `http://localhost:3001`:
- 用户名: admin
- 密码: admin

导入仪表板:
1. 点击 "+" 按钮
2. 选择 "Import"
3. 输入仪表板ID或上传JSON

### 5.3 日志配置

创建 `logging.yaml`:

```yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  json:
    format: '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: /var/log/xagent/app.log
    maxBytes: 104857600
    backupCount: 10

loggers:
  xagent:
    level: INFO
    handlers: [console, file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

---

## 6. 安全配置

### 6.1 SSL/TLS 配置

```bash
# 生成自签名证书 (测试用)
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365

# 或使用 Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone -d beta.x-agent.io
```

### 6.2 Nginx 配置

创建 `nginx/nginx.conf`:

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name beta.x-agent.io;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name beta.x-agent.io;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 前端
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
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
    }
}
```

### 6.3 防火墙配置

```bash
# 允许必要的端口
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # API (内部)
sudo ufw allow 3000/tcp  # Frontend (内部)

# 启用防火墙
sudo ufw enable
```

---

## 7. 性能优化

### 7.1 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_executions_created_at ON executions(created_at DESC);
CREATE INDEX idx_workflows_status ON workflows(status);

-- 启用自动清理
ALTER TABLE executions SET (autovacuum_vacuum_scale_factor = 0.01);

-- 调整连接池
-- 在 .env 中设置
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

### 7.2 Redis 优化

```bash
# 编辑 /etc/redis/redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # 禁用RDB持久化 (如果使用AOF)
appendonly yes  # 启用AOF
```

### 7.3 应用优化

```python
# 在 backend/app/main.py 中
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend

# 启用缓存
FastAPICache2.init(RedisBackend(redis), prefix="xagent-cache")

# 启用压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://beta.x-agent.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 8. 备份与恢复

### 8.1 备份策略

```bash
#!/bin/bash
# backup.sh - 每日备份脚本

BACKUP_DIR="/backups/xagent"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份数据库
pg_dump -U xagent xagent_beta | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# 备份Redis
redis-cli --rdb $BACKUP_DIR/redis_$DATE.rdb

# 备份应用数据
tar -czf $BACKUP_DIR/app_$DATE.tar.gz /app/data

# 上传到S3
aws s3 cp $BACKUP_DIR/ s3://xagent-backups/ --recursive

# 清理旧备份 (保留7天)
find $BACKUP_DIR -mtime +7 -delete
```

### 8.2 恢复流程

```bash
# 恢复数据库
gunzip < backup.sql.gz | psql -U xagent xagent_beta

# 恢复Redis
redis-cli shutdown
cp redis_backup.rdb /var/lib/redis/dump.rdb
redis-server

# 恢复应用数据
tar -xzf app_backup.tar.gz -C /
```

---

## 9. 故障排查

### 9.1 常见问题

#### 问题: 无法连接数据库
```bash
# 检查PostgreSQL状态
sudo systemctl status postgresql

# 检查连接
psql -U xagent -d xagent_beta -c "SELECT 1"

# 查看日志
sudo tail -f /var/log/postgresql/postgresql.log
```

#### 问题: Redis连接失败
```bash
# 检查Redis状态
redis-cli ping

# 检查配置
redis-cli CONFIG GET requirepass

# 重启Redis
sudo systemctl restart redis-server
```

#### 问题: 高内存占用
```bash
# 检查进程
ps aux | grep python

# 检查内存使用
free -h

# 重启服务
docker-compose restart backend
```

### 9.2 日志查看

```bash
# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend

# 查看系统日志
journalctl -u xagent -f

# 查看Nginx日志
tail -f /var/log/nginx/error.log
```

---

## 10. 验证清单

部署完成后，请验证以下项目:

- [ ] 后端API可访问 (http://localhost:8000/health)
- [ ] 前端应用可访问 (http://localhost:3000)
- [ ] 数据库连接正常
- [ ] Redis连接正常
- [ ] 向量数据库连接正常
- [ ] 监控系统可访问 (http://localhost:3001)
- [ ] 日志系统正常工作
- [ ] SSL证书有效
- [ ] 备份系统正常
- [ ] 性能指标正常

---

## 11. 维护计划

### 11.1 日常维护

- 监控系统资源使用
- 检查错误日志
- 验证备份完成
- 监控API响应时间

### 11.2 周期维护

- 数据库优化 (VACUUM, ANALYZE)
- 日志轮转
- 性能分析
- 安全补丁更新

### 11.3 月度维护

- 容量规划
- 性能基准测试
- 灾难恢复演练
- 安全审计

---

**维护人员**: DevOps团队  
**最后更新**: 2026-05-27  
**下次审查**: 2026-06-10
