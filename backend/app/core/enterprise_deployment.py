"""
企业级部署指南和API集成

提供:
- 完整的部署配置
- Kubernetes部署清单
- Docker Compose配置
- 监控和告警设置
- 备份和恢复策略
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Kubernetes部署清单
# ============================================================================

KUBERNETES_DEPLOYMENT_MANIFEST = """
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
  app_mode: "production"
  log_level: "INFO"
  max_iterations: "4"
  default_token_budget: "16000"

---
apiVersion: v1
kind: Secret
metadata:
  name: xagent-secrets
  namespace: xagent
type: Opaque
stringData:
  jwt_secret: "CHANGE_ME_TO_RANDOM_64_CHAR_STRING"
  encryption_key: "CHANGE_ME_TO_32_CHAR_HEX_STRING"
  database_url: "postgresql://user:password@postgres:5432/xagent"
  redis_url: "redis://redis:6379/0"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-api
  namespace: xagent
  labels:
    app: xagent
    component: api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: xagent
      component: api
  template:
    metadata:
      labels:
        app: xagent
        component: api
    spec:
      serviceAccountName: xagent
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: xagent-api
        image: xagent:latest
        imagePullPolicy: IfNotPresent
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        env:
        - name: XAGENT_APP_MODE
          valueFrom:
            configMapKeyRef:
              name: xagent-config
              key: app_mode
        - name: XAGENT_JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: jwt_secret
        - name: XAGENT_ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: encryption_key
        - name: XAGENT_DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: database_url
        - name: XAGENT_REDIS_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis_url
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: http
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: cache
          mountPath: /app/cache
      volumes:
      - name: tmp
        emptyDir: {}
      - name: cache
        emptyDir: {}
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
                  - xagent
              topologyKey: kubernetes.io/hostname

---
apiVersion: v1
kind: Service
metadata:
  name: xagent-api
  namespace: xagent
  labels:
    app: xagent
    component: api
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 8000
    targetPort: http
    protocol: TCP
  selector:
    app: xagent
    component: api

---
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

---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: xagent-api-pdb
  namespace: xagent
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: xagent
      component: api

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: xagent
  namespace: xagent

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: xagent
  namespace: xagent
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: xagent
  namespace: xagent
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: xagent
subjects:
- kind: ServiceAccount
  name: xagent
  namespace: xagent
"""


# ============================================================================
# Docker Compose配置
# ============================================================================

DOCKER_COMPOSE_CONFIG = """
version: '3.8'

services:
  # PostgreSQL数据库
  postgres:
    image: postgres:15-alpine
    container_name: xagent-postgres
    environment:
      POSTGRES_USER: xagent
      POSTGRES_PASSWORD: xagent_password
      POSTGRES_DB: xagent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U xagent"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # Redis缓存
  redis:
    image: redis:7-alpine
    container_name: xagent-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # Qdrant向量数据库
  qdrant:
    image: qdrant/qdrant:latest
    container_name: xagent-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT_API_KEY: qdrant_api_key
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network

  # X-Agent API
  xagent-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: xagent-api
    environment:
      XAGENT_APP_MODE: production
      XAGENT_DATABASE_URL: postgresql://xagent:xagent_password@postgres:5432/xagent
      XAGENT_REDIS_URL: redis://redis:6379/0
      XAGENT_QDRANT_URL: http://qdrant:6333
      XAGENT_JWT_SECRET: change_me_to_random_64_char_string
      XAGENT_ENCRYPTION_KEY: change_me_to_32_char_hex_string
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - xagent-network
    restart: unless-stopped

  # Prometheus监控
  prometheus:
    image: prom/prometheus:latest
    container_name: xagent-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - xagent-network

  # Grafana可视化
  grafana:
    image: grafana/grafana:latest
    container_name: xagent-grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_ALLOW_SIGN_UP: 'false'
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    depends_on:
      - prometheus
    networks:
      - xagent-network

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  prometheus_data:
  grafana_data:

networks:
  xagent-network:
    driver: bridge
"""


# ============================================================================
# 监控和告警配置
# ============================================================================

PROMETHEUS_CONFIG = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'xagent-monitor'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - '/etc/prometheus/rules/*.yml'

scrape_configs:
  - job_name: 'xagent-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
"""

PROMETHEUS_ALERTS = """
groups:
  - name: xagent_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P95 latency is {{ $value }} seconds"

      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_available < 5
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"
          description: "Available connections: {{ $value }}"

      - alert: HighMemoryUsage
        expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: DiskSpaceRunningOut
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Disk space running out"
          description: "Available disk space: {{ $value | humanizePercentage }}"
"""


# ============================================================================
# 备份和恢复策略
# ============================================================================

BACKUP_STRATEGY = """
# X-Agent 备份和恢复策略

## 备份类型

### 1. 完整备份
- 频率: 每天一次（凌晨2点）
- 保留期: 30天
- 包含内容:
  - PostgreSQL数据库完整转储
  - Redis数据快照
  - Qdrant向量数据库备份
  - 配置文件和密钥

### 2. 增量备份
- 频率: 每6小时一次
- 保留期: 7天
- 包含内容:
  - 数据库变更日志
  - 审计日志

### 3. 事务日志备份
- 频率: 连续
- 保留期: 3天
- 用途: 时间点恢复

## 备份存储

### 本地存储
- 位置: /backup/xagent
- 容量: 500GB
- 冗余: RAID-6

### 远程存储
- 位置: S3/Azure Blob Storage
- 加密: AES-256
- 复制: 跨区域复制

## 恢复过程

### 完整恢复
1. 停止所有服务
2. 恢复PostgreSQL数据库
3. 恢复Redis数据
4. 恢复Qdrant数据
5. 验证数据完整性
6. 启动服务

### 增量恢复
1. 恢复最近的完整备份
2. 应用增量备份
3. 应用事务日志
4. 验证数据一致性

### 时间点恢复
1. 恢复完整备份
2. 应用事务日志到指定时间点
3. 验证恢复结果

## 恢复时间目标 (RTO)
- 完整恢复: 4小时
- 增量恢复: 1小时
- 时间点恢复: 2小时

## 恢复点目标 (RPO)
- 数据库: 1小时
- 审计日志: 15分钟
- 配置: 1天
"""


# ============================================================================
# 企业级部署检查清单
# ============================================================================

DEPLOYMENT_CHECKLIST = """
# X-Agent 企业级部署检查清单

## 前置条件
- [ ] Kubernetes集群已部署（v1.24+）
- [ ] PostgreSQL 13+ 已安装
- [ ] Redis 6+ 已安装
- [ ] Qdrant 已部署
- [ ] 网络连接已验证
- [ ] DNS已配置

## 安全配置
- [ ] JWT密钥已更改（最少64字符）
- [ ] 加密密钥已更改（32字符十六进制）
- [ ] 数据库密码已更改
- [ ] CORS源已配置
- [ ] SSL/TLS证书已安装
- [ ] 防火墙规则已配置
- [ ] 网络策略已应用
- [ ] RBAC已配置

## 数据库配置
- [ ] PostgreSQL已初始化
- [ ] 数据库用户已创建
- [ ] 连接池已配置
- [ ] 备份策略已启用
- [ ] 复制已配置
- [ ] 监控已启用

## 应用配置
- [ ] 环境变量已设置
- [ ] 日志级别已配置
- [ ] 监控指标已启用
- [ ] 追踪已配置
- [ ] 告警已设置

## 监控和告警
- [ ] Prometheus已部署
- [ ] Grafana已配置
- [ ] 告警规则已加载
- [ ] 告警通知已配置
- [ ] 仪表板已创建

## 备份和恢复
- [ ] 备份策略已实施
- [ ] 备份存储已配置
- [ ] 恢复流程已测试
- [ ] 恢复文档已准备

## 高可用性
- [ ] 多副本已配置
- [ ] 负载均衡器已设置
- [ ] 故障转移已测试
- [ ] 健康检查已配置

## 性能优化
- [ ] 缓存已配置
- [ ] 连接池已优化
- [ ] 查询已优化
- [ ] 索引已创建

## 文档和培训
- [ ] 部署文档已完成
- [ ] 运维手册已准备
- [ ] 故障排除指南已准备
- [ ] 团队培训已完成

## 上线前测试
- [ ] 功能测试已通过
- [ ] 性能测试已通过
- [ ] 安全测试已通过
- [ ] 负载测试已通过
- [ ] 灾难恢复测试已通过
"""


# ============================================================================
# 部署指南生成器
# ============================================================================

class DeploymentGuideGenerator:
    """部署指南生成器"""

    @staticmethod
    def generate_kubernetes_guide() -> str:
        """生成Kubernetes部署指南"""
        return """
# X-Agent Kubernetes部署指南

## 前置条件
- Kubernetes 1.24+
- kubectl已安装
- Helm 3.0+（可选）

## 部署步骤

### 1. 创建命名空间
```bash
kubectl create namespace xagent
```

### 2. 创建密钥
```bash
kubectl create secret generic xagent-secrets \\
  --from-literal=jwt_secret='your-random-64-char-string' \\
  --from-literal=encryption_key='your-32-char-hex-string' \\
  --from-literal=database_url='postgresql://user:password@postgres:5432/xagent' \\
  -n xagent
```

### 3. 应用部署清单
```bash
kubectl apply -f kubernetes-manifest.yaml
```

### 4. 验证部署
```bash
kubectl get pods -n xagent
kubectl get svc -n xagent
```

### 5. 检查日志
```bash
kubectl logs -n xagent deployment/xagent-api
```

## 扩展和更新

### 手动扩展
```bash
kubectl scale deployment xagent-api --replicas=5 -n xagent
```

### 自动扩展
HPA已配置，将根据CPU和内存使用情况自动扩展。

### 更新镜像
```bash
kubectl set image deployment/xagent-api \\
  xagent-api=xagent:v2.0 \\
  -n xagent
```

## 监控

### 查看指标
```bash
kubectl top nodes
kubectl top pods -n xagent
```

### 访问Grafana
```bash
kubectl port-forward -n xagent svc/grafana 3000:3000
# 访问 http://localhost:3000
```
"""

    @staticmethod
    def generate_docker_compose_guide() -> str:
        """生成Docker Compose部署指南"""
        return """
# X-Agent Docker Compose部署指南

## 前置条件
- Docker 20.10+
- Docker Compose 2.0+

## 部署步骤

### 1. 克隆仓库
```bash
git clone https://github.com/xagent/xagent.git
cd xagent
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，更改密钥和密码
```

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 验证服务
```bash
docker-compose ps
docker-compose logs xagent-api
```

### 5. 初始化数据库
```bash
docker-compose exec xagent-api python -m alembic upgrade head
```

## 访问应用

- API: http://localhost:8000
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## 停止服务
```bash
docker-compose down
```

## 备份数据
```bash
docker-compose exec postgres pg_dump -U xagent xagent > backup.sql
```

## 恢复数据
```bash
docker-compose exec -T postgres psql -U xagent xagent < backup.sql
```
"""

    @staticmethod
    def generate_production_checklist() -> str:
        """生成生产环境检查清单"""
        return DEPLOYMENT_CHECKLIST


logger.info("Enterprise deployment guide module loaded")
