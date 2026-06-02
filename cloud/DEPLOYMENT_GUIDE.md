# X-Agent 云端服务部署方案

**版本：** 1.0.0  
**日期：** 2026-05-27

---

## 1. 部署架构

### 1.1 开发环境部署

```
单机部署 (Docker Compose)
├─ PostgreSQL 16
├─ Redis 7
├─ Qdrant (向量数据库)
├─ Neo4j 5 (图数据库)
└─ X-Agent API (单实例)
```

### 1.2 生产环境部署

```
Kubernetes 集群部署
├─ 主区域
│  ├─ PostgreSQL (主从复制)
│  ├─ Redis (集群模式)
│  ├─ Qdrant (集群)
│  ├─ X-Agent API (多副本)
│  ├─ Sync Worker (多副本)
│  └─ Conflict Resolver (多副本)
├─ 备用区域
│  ├─ PostgreSQL (从)
│  ├─ Redis (从)
│  ├─ Qdrant (从)
│  └─ X-Agent API (多副本)
└─ 监控与日志
   ├─ Prometheus
   ├─ Grafana
   ├─ ELK Stack
   └─ Jaeger (分布式追踪)
```

---

## 2. Docker 部署

### 2.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend ./backend
COPY cloud ./cloud

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动应用
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Docker Compose 配置

```yaml
version: '3.9'

services:
  # PostgreSQL
  postgres:
    image: postgres:16-alpine
    container_name: xagent-postgres
    environment:
      POSTGRES_USER: ${DB_USER:-xagent}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-xagent_secure_password}
      POSTGRES_DB: ${DB_NAME:-xagent_db}
    ports:
      - "${DB_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./deployment/migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-xagent}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    container_name: xagent-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-redis_secure_password}
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network
    restart: unless-stopped

  # Qdrant
  qdrant:
    image: qdrant/qdrant:latest
    container_name: xagent-qdrant
    environment:
      QDRANT_API_KEY: ${QDRANT_API_KEY:-qdrant_secure_key}
    ports:
      - "${QDRANT_PORT:-6333}:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network
    restart: unless-stopped

  # X-Agent API
  xagent-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: xagent-api
    environment:
      DATABASE_URL: postgresql://${DB_USER:-xagent}:${DB_PASSWORD:-xagent_secure_password}@postgres:5432/${DB_NAME:-xagent_db}
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis_secure_password}@redis:6379/0
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY:-qdrant_secure_key}
      ENVIRONMENT: ${ENVIRONMENT:-development}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      SECRET_KEY: ${SECRET_KEY:-change-me-in-production}
    ports:
      - "${API_PORT:-8000}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
      - ./cloud:/app/cloud
      - ./logs:/app/logs
    networks:
      - xagent-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:
  qdrant_data:

networks:
  xagent-network:
    driver: bridge
```

### 2.3 环境变量配置 (.env)

```bash
# 数据库
DB_USER=xagent
DB_PASSWORD=xagent_secure_password
DB_NAME=xagent_db
DB_PORT=5432

# Redis
REDIS_PASSWORD=redis_secure_password
REDIS_PORT=6379

# Qdrant
QDRANT_API_KEY=qdrant_secure_key
QDRANT_PORT=6333

# 应用
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=false
SECRET_KEY=your-secret-key-here
API_PORT=8000
API_WORKERS=4

# 安全
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
REQUIRE_API_KEY=true
```

---

## 3. Kubernetes 部署

### 3.1 Namespace 和 ConfigMap

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: xagent

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: xagent-config
  namespace: xagent
data:
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
  API_WORKERS: "4"
```

### 3.2 Secret 配置

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: xagent-secrets
  namespace: xagent
type: Opaque
stringData:
  db-user: xagent
  db-password: xagent_secure_password
  redis-password: redis_secure_password
  qdrant-api-key: qdrant_secure_key
  secret-key: your-secret-key-here
```

### 3.3 PostgreSQL StatefulSet

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: xagent
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: db-user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: db-password
        - name: POSTGRES_DB
          value: xagent_db
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U xagent
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - /bin/sh
            - -c
            - pg_isready -U xagent
          initialDelaySeconds: 5
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: xagent
spec:
  clusterIP: None
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

### 3.4 Redis Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: xagent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - --requirepass
        - $(REDIS_PASSWORD)
        ports:
        - containerPort: 6379
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis-password
        volumeMounts:
        - name: redis-storage
          mountPath: /data
        livenessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: redis-storage
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: xagent
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### 3.5 X-Agent API Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-api
  namespace: xagent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: xagent-api
  template:
    metadata:
      labels:
        app: xagent-api
    spec:
      containers:
      - name: xagent-api
        image: xagent:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: postgresql://$(DB_USER):$(DB_PASSWORD)@postgres:5432/xagent_db
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: db-user
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: db-password
        - name: REDIS_URL
          value: redis://:$(REDIS_PASSWORD)@redis:6379/0
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis-password
        - name: QDRANT_URL
          value: http://qdrant:6333
        - name: QDRANT_API_KEY
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: qdrant-api-key
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: secret-key
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: xagent-config
              key: LOG_LEVEL
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: xagent-config
              key: ENVIRONMENT
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
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
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: xagent-api
  namespace: xagent
spec:
  type: LoadBalancer
  selector:
    app: xagent-api
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
```

### 3.6 Ingress 配置

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: xagent-ingress
  namespace: xagent
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.x-agent.io
    secretName: xagent-tls
  rules:
  - host: api.x-agent.io
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: xagent-api
            port:
              number: 80
```

---

## 4. 监控与日志

### 4.1 Prometheus 配置

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'xagent-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:6379']
```

### 4.2 Grafana 仪表板

关键指标：
- 同步操作吞吐量
- 冲突检测率
- 平均同步延迟
- 成功率
- 错误率
- 数据库连接数
- Redis内存使用
- API响应时间

### 4.3 ELK Stack 配置

```yaml
# Filebeat 配置
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /app/logs/*.log

output.elasticsearch:
  hosts: ["elasticsearch:9200"]

# Logstash 配置
input {
  beats {
    port => 5000
  }
}

filter {
  grok {
    match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:level} %{DATA:logger} %{GREEDYDATA:message}" }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "xagent-%{+YYYY.MM.dd}"
  }
}
```

---

## 5. 备份与恢复

### 5.1 PostgreSQL 备份

```bash
#!/bin/bash

# 完整备份
pg_dump -h postgres -U xagent -d xagent_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# 上传到S3
aws s3 cp backup_*.sql.gz s3://xagent-backups/

# 保留最近30天的备份
find . -name "backup_*.sql.gz" -mtime +30 -delete
```

### 5.2 恢复流程

```bash
#!/bin/bash

# 从S3下载备份
aws s3 cp s3://xagent-backups/backup_latest.sql.gz .

# 解压
gunzip backup_latest.sql.gz

# 恢复
psql -h postgres -U xagent -d xagent_db < backup_latest.sql
```

---

## 6. 安全加固

### 6.1 网络安全

```yaml
# NetworkPolicy - 限制入站流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: xagent-network-policy
  namespace: xagent
spec:
  podSelector:
    matchLabels:
      app: xagent-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

### 6.2 RBAC 配置

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: xagent-role
  namespace: xagent
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: xagent-rolebinding
  namespace: xagent
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: xagent-role
subjects:
- kind: ServiceAccount
  name: xagent
  namespace: xagent
```

### 6.3 Pod 安全策略

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: xagent-psp
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
  - ALL
  volumes:
  - 'configMap'
  - 'emptyDir'
  - 'projected'
  - 'secret'
  - 'downwardAPI'
  - 'persistentVolumeClaim'
  hostNetwork: false
  hostIPC: false
  hostPID: false
  runAsUser:
    rule: 'MustRunAsNonRoot'
  seLinux:
    rule: 'MustRunAs'
    seLinuxOptions:
      level: "s0:c123,c456"
  fsGroup:
    rule: 'MustRunAs'
    ranges:
    - min: 1000
      max: 65535
  readOnlyRootFilesystem: false
```

---

## 7. 性能优化

### 7.1 资源限制

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### 7.2 自动扩展

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xagent-api-hpa
  namespace: xagent
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
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 8. 故障恢复

### 8.1 健康检查

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### 8.2 Pod 重启策略

```yaml
restartPolicy: Always
terminationGracePeriodSeconds: 30
```

---

## 9. 部署检查清单

- [ ] 环境变量配置正确
- [ ] 数据库初始化完成
- [ ] 密钥和证书已配置
- [ ] 网络策略已应用
- [ ] RBAC已配置
- [ ] 监控和日志已启用
- [ ] 备份策略已配置
- [ ] SSL/TLS已启用
- [ ] 速率限制已配置
- [ ] 健康检查已验证

---

## 10. 故障排查

### 10.1 常见问题

**问题**：API无法连接到数据库
```bash
# 检查数据库连接
kubectl exec -it xagent-api-0 -n xagent -- \
  psql -h postgres -U xagent -d xagent_db -c "SELECT 1"
```

**问题**：Redis连接失败
```bash
# 检查Redis连接
kubectl exec -it xagent-api-0 -n xagent -- \
  redis-cli -h redis -a $REDIS_PASSWORD ping
```

**问题**：高内存使用
```bash
# 检查内存使用
kubectl top pods -n xagent
kubectl describe pod xagent-api-0 -n xagent
```

---

## 总结

本部署方案提供了完整的开发、测试和生产环境部署指南，包括Docker、Kubernetes、监控、备份和安全加固等方面。
