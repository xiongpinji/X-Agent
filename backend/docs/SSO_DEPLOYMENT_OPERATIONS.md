"""SSO and Enterprise Authentication Deployment and Operations Guide."""

# SSO与企业认证系统部署和运维指南

## 部署架构

### 高可用部署

```
┌─────────────────────────────────────────────────────────────┐
│                        Load Balancer                         │
│                      (Nginx/HAProxy)                         │
└────────────┬────────────────────────────────────────┬────────┘
             │                                        │
    ┌────────▼────────┐                    ┌─────────▼────────┐
    │  API Server 1   │                    │  API Server 2    │
    │  (FastAPI)      │                    │  (FastAPI)       │
    └────────┬────────┘                    └─────────┬────────┘
             │                                        │
             └────────────────┬─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Redis Cluster   │
                    │  (Session Store)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼──────────┐
                    │  PostgreSQL DB     │
                    │  (Primary/Replica) │
                    └────────────────────┘
```

### 单机部署

```
┌──────────────────────────────────┐
│      Docker Container            │
│  ┌────────────────────────────┐  │
│  │   FastAPI Application      │  │
│  │  - OAuth Manager           │  │
│  │  - MFA Manager             │  │
│  │  - Session Manager         │  │
│  │  - WebAuthn Provider       │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │   Redis (In-Memory)        │  │
│  │  - Session Storage         │  │
│  │  - Token Cache             │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │   PostgreSQL Database      │  │
│  │  - Users                   │  │
│  │  - Audit Logs              │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

## 部署步骤

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt
pip install python-ldap pysaml2 cryptography

# 创建数据库
createdb xagent_sso

# 初始化数据库
psql xagent_sso < schema.sql

# 启动Redis
redis-server --daemonize yes
```

### 2. 配置

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置
nano .env

# 验证配置
python -m backend.app.core.sso.config_validator
```

### 3. 启动服务

```bash
# 开发环境
uvicorn backend.app.web:app --reload --host 0.0.0.0 --port 8000

# 生产环境
gunicorn backend.app.web:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### 4. Docker部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["gunicorn", "backend.app.web:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

```bash
# 构建镜像
docker build -t xagent-sso:latest .

# 运行容器
docker run -d \
  --name xagent-sso \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/xagent_sso \
  -e REDIS_URL=redis://redis:6379 \
  xagent-sso:latest
```

### 5. Kubernetes部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-sso
spec:
  replicas: 3
  selector:
    matchLabels:
      app: xagent-sso
  template:
    metadata:
      labels:
        app: xagent-sso
    spec:
      containers:
      - name: xagent-sso
        image: xagent-sso:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
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
---
apiVersion: v1
kind: Service
metadata:
  name: xagent-sso
spec:
  selector:
    app: xagent-sso
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

## 运维操作

### 监控

```bash
# 查看日志
docker logs -f xagent-sso

# 查看性能指标
curl http://localhost:8000/metrics

# 查看健康状态
curl http://localhost:8000/health
```

### 备份

```bash
# 备份数据库
pg_dump xagent_sso > backup_$(date +%Y%m%d).sql

# 备份Redis
redis-cli BGSAVE

# 备份配置
tar -czf config_backup_$(date +%Y%m%d).tar.gz .env
```

### 恢复

```bash
# 恢复数据库
psql xagent_sso < backup_20260528.sql

# 恢复Redis
redis-cli SHUTDOWN
cp dump.rdb /var/lib/redis/
redis-server

# 恢复配置
tar -xzf config_backup_20260528.tar.gz
```

### 升级

```bash
# 1. 备份
pg_dump xagent_sso > backup_pre_upgrade.sql

# 2. 停止服务
docker stop xagent-sso

# 3. 更新代码
git pull origin main

# 4. 运行迁移
python -m alembic upgrade head

# 5. 启动服务
docker start xagent-sso

# 6. 验证
curl http://localhost:8000/health
```

### 故障排除

#### 数据库连接失败

```bash
# 检查数据库状态
psql -U postgres -d xagent_sso -c "SELECT 1"

# 检查连接字符串
echo $DATABASE_URL

# 查看日志
docker logs xagent-sso | grep -i database
```

#### Redis连接失败

```bash
# 检查Redis状态
redis-cli ping

# 检查连接字符串
echo $REDIS_URL

# 查看日志
docker logs xagent-sso | grep -i redis
```

#### 高CPU使用率

```bash
# 查看进程
top -p $(pgrep -f gunicorn)

# 查看线程
ps -eLf | grep gunicorn

# 分析性能
python -m cProfile -s cumulative backend/app/web.py
```

#### 高内存使用率

```bash
# 查看内存使用
docker stats xagent-sso

# 分析内存泄漏
python -m memory_profiler backend/app/web.py

# 清理缓存
redis-cli FLUSHDB
```

## 性能调优

### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);

-- 分析查询
EXPLAIN ANALYZE SELECT * FROM sessions WHERE user_id = 'user123';

-- 优化表
VACUUM ANALYZE;
```

### Redis优化

```bash
# 配置持久化
redis-cli CONFIG SET save "900 1 300 10 60 10000"

# 配置内存管理
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 监控性能
redis-cli INFO stats
```

### 应用优化

```python
# 启用连接池
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
)

# 启用缓存
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user(user_id: str):
    return user_store.get(user_id)

# 异步处理
import asyncio

async def send_mfa_code_async(email: str, code: str):
    await email_service.send(email, code)
```

## 安全加固

### 防火墙规则

```bash
# 允许HTTPS
ufw allow 443/tcp

# 允许HTTP（重定向到HTTPS）
ufw allow 80/tcp

# 允许SSH
ufw allow 22/tcp

# 拒绝其他
ufw default deny incoming
ufw default allow outgoing
```

### SSL/TLS配置

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # CSP
    add_header Content-Security-Policy "default-src 'self'" always;

    # X-Frame-Options
    add_header X-Frame-Options "SAMEORIGIN" always;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 日志审计

```bash
# 启用审计日志
auditctl -w /app -p wa -k app_changes

# 查看审计日志
ausearch -k app_changes

# 启用系统日志
journalctl -u xagent-sso -f
```

## 合规性检查清单

- [ ] HTTPS已启用
- [ ] HSTS已配置
- [ ] 审计日志已启用
- [ ] 备份已配置
- [ ] 监控已配置
- [ ] 告警已配置
- [ ] 防火墙已配置
- [ ] 日志保留已配置
- [ ] 数据加密已启用
- [ ] 访问控制已配置

## 故障恢复计划

### RTO/RPO目标
- RTO (恢复时间目标): 1小时
- RPO (恢复点目标): 15分钟

### 恢复步骤

1. **检测故障** (5分钟)
   - 监控告警触发
   - 人工确认

2. **初始响应** (10分钟)
   - 启动故障恢复流程
   - 通知相关人员

3. **恢复数据** (30分钟)
   - 从备份恢复数据库
   - 验证数据完整性

4. **恢复服务** (15分钟)
   - 启动应用服务
   - 验证服务可用性

5. **验证** (10分钟)
   - 运行健康检查
   - 验证功能正常

## 文档和培训

### 文档
- [配置指南](SSO_CONFIGURATION.md)
- [集成指南](SSO_INTEGRATION_GUIDE.md)
- [安全测试报告](SSO_SECURITY_TEST_REPORT.md)

### 培训
- 系统架构培训
- 运维操作培训
- 故障排除培训
- 安全最佳实践培训

## 联系方式

- **技术支持**: support@example.com
- **安全问题**: security@example.com
- **紧急情况**: +1-xxx-xxx-xxxx
