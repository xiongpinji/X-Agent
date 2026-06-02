# X-Agent 企业级集成指南

**版本**: 1.0  
**最后更新**: 2026-05-29  
**适用范围**: 企业客户、系统集成商

---

## 目录

1. [企业部署架构](#企业部署架构)
2. [多租户配置](#多租户配置)
3. [企业认证集成](#企业认证集成)
4. [数据安全和合规](#数据安全和合规)
5. [高可用性配置](#高可用性配置)
6. [性能和扩展性](#性能和扩展性)
7. [监控和告警](#监控和告警)
8. [支持和SLA](#支持和sla)

---

## 企业部署架构

### 推荐的企业部署拓扑

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer (HA)                    │
│              (AWS ALB / Azure LB / F5)                   │
└────────────────┬────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼──┐    ┌───▼──┐    ┌───▼──┐
│ API  │    │ API  │    │ API  │
│ Pod1 │    │ Pod2 │    │ Pod3 │
└───┬──┘    └───┬──┘    └───┬──┘
    │           │           │
    └───────────┼───────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───▼──┐   ┌───▼──┐   ┌───▼──┐
│Worker│   │Worker│   │Worker│
│ Pod1 │   │ Pod2 │   │ Pod3 │
└──────┘   └──────┘   └──────┘
    │           │           │
    └───────────┼───────────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───▼──────┐ ┌─▼──────┐ ┌──▼──────┐
│PostgreSQL│ │ Qdrant │ │  Redis  │
│  Primary │ │Cluster │ │ Cluster │
└──────────┘ └────────┘ └─────────┘
    │
    └─ Backup (Standby)
```

### 部署配置示例

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-api
  namespace: xagent-prod
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
                  - xagent-api
              topologyKey: kubernetes.io/hostname
      containers:
      - name: xagent-api
        image: xagent:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: database-url
        resources:
          requests:
            cpu: "2"
            memory: "4Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
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

## 多租户配置

### 租户隔离策略

```python
# 1. 数据库级隔离
class TenantMiddleware:
    async def __call__(self, request: Request, call_next):
        # 从请求头或JWT获取租户ID
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Missing tenant ID")
        
        # 验证租户
        tenant = await verify_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=403, detail="Invalid tenant")
        
        # 存储在请求上下文
        request.state.tenant_id = tenant_id
        request.state.tenant = tenant
        
        response = await call_next(request)
        return response

# 2. 查询隔离
async def get_workflows(request: Request):
    tenant_id = request.state.tenant_id
    
    # 自动添加租户过滤
    workflows = await db.query(
        "SELECT * FROM workflows WHERE tenant_id = %s",
        [tenant_id]
    )
    return workflows

# 3. 资源配额
TENANT_QUOTAS = {
    "free": {
        "workflows": 10,
        "agents": 5,
        "api_calls_per_day": 1000,
        "storage_gb": 1
    },
    "pro": {
        "workflows": 100,
        "agents": 50,
        "api_calls_per_day": 100000,
        "storage_gb": 100
    },
    "enterprise": {
        "workflows": -1,  # 无限
        "agents": -1,
        "api_calls_per_day": -1,
        "storage_gb": -1
    }
}
```

### 租户配置示例

```yaml
# config/tenants.yaml
tenants:
  - id: "tenant_acme"
    name: "ACME Corporation"
    tier: "enterprise"
    features:
      - workflows
      - agents
      - memory_system
      - browser_automation
      - custom_tools
      - sso
      - audit_logs
    limits:
      api_calls_per_day: -1
      concurrent_workflows: 100
      storage_gb: 1000
    settings:
      data_residency: "us-east-1"
      encryption: "customer_managed_key"
      backup_retention_days: 90
      
  - id: "tenant_startup"
    name: "StartUp Inc"
    tier: "pro"
    features:
      - workflows
      - agents
      - memory_system
    limits:
      api_calls_per_day: 100000
      concurrent_workflows: 10
      storage_gb: 100
    settings:
      data_residency: "us-east-1"
      encryption: "aws_managed_key"
      backup_retention_days: 30
```

---

## 企业认证集成

### SSO集成 (SAML 2.0)

```python
# 1. SAML配置
SAML_CONFIG = {
    "sp": {
        "entityID": "https://xagent.example.com/metadata/",
        "assertionConsumerService": {
            "url": "https://xagent.example.com/auth/saml/acs",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
        },
        "singleLogoutService": {
            "url": "https://xagent.example.com/auth/saml/sls",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        }
    },
    "idp": {
        "entityID": "https://idp.example.com/metadata/",
        "singleSignOnService": {
            "url": "https://idp.example.com/sso",
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        },
        "x509cert": "..."
    }
}

# 2. SAML认证端点
@router.post("/auth/saml/acs")
async def saml_acs(request: Request):
    # 验证SAML响应
    auth = OneLogin_Saml2_Auth(request, SAML_CONFIG)
    auth.process_response()
    
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML authentication failed")
    
    # 获取用户信息
    user_email = auth.get_nameid()
    user_attributes = auth.get_attributes()
    
    # 创建或更新用户
    user = await get_or_create_user(
        email=user_email,
        attributes=user_attributes
    )
    
    # 创建会话
    token = create_jwt_token(user)
    return {"token": token}
```

### OAuth 2.0集成

```python
# 1. OAuth配置
OAUTH_PROVIDERS = {
    "azure": {
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        "authority": "https://login.microsoftonline.com/common",
        "redirect_uri": "https://xagent.example.com/auth/oauth/callback"
    },
    "okta": {
        "client_id": os.getenv("OKTA_CLIENT_ID"),
        "client_secret": os.getenv("OKTA_CLIENT_SECRET"),
        "domain": os.getenv("OKTA_DOMAIN"),
        "redirect_uri": "https://xagent.example.com/auth/oauth/callback"
    }
}

# 2. OAuth认证流程
@router.get("/auth/oauth/authorize")
async def oauth_authorize(provider: str, state: str):
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail="Unknown provider")
    
    config = OAUTH_PROVIDERS[provider]
    
    # 生成授权URL
    auth_url = f"{config['authority']}/oauth2/v2.0/authorize"
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "openid profile email",
        "state": state
    }
    
    return RedirectResponse(url=f"{auth_url}?{urlencode(params)}")

@router.get("/auth/oauth/callback")
async def oauth_callback(code: str, state: str, provider: str):
    # 交换授权码获取令牌
    config = OAUTH_PROVIDERS[provider]
    
    token_response = requests.post(
        f"{config['authority']}/oauth2/v2.0/token",
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code"
        }
    )
    
    # 获取用户信息
    user_info = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"}
    ).json()
    
    # 创建用户和会话
    user = await get_or_create_user(email=user_info["mail"])
    token = create_jwt_token(user)
    
    return RedirectResponse(url=f"https://app.example.com?token={token}")
```

---

## 数据安全和合规

### 加密配置

```python
# 1. 传输层加密 (TLS)
# nginx配置
server {
    listen 443 ssl http2;
    server_name api.xagent.example.com;
    
    ssl_certificate /etc/ssl/certs/xagent.crt;
    ssl_certificate_key /etc/ssl/private/xagent.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}

# 2. 数据库加密
# PostgreSQL配置
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/etc/ssl/certs/server.crt';
ALTER SYSTEM SET ssl_key_file = '/etc/ssl/private/server.key';

# 3. 字段级加密
from cryptography.fernet import Fernet

class EncryptedField:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

# 使用
encrypted_field = EncryptedField(os.getenv("ENCRYPTION_KEY"))

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String)
    api_key = Column(String)  # 加密存储
    
    def set_api_key(self, key: str):
        self.api_key = encrypted_field.encrypt(key)
    
    def get_api_key(self) -> str:
        return encrypted_field.decrypt(self.api_key)
```

### 审计日志

```python
# 1. 审计日志模型
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, index=True)
    user_id = Column(String, index=True)
    action = Column(String)  # create, read, update, delete
    resource_type = Column(String)  # workflow, agent, tool
    resource_id = Column(String)
    changes = Column(JSON)  # 变更详情
    ip_address = Column(String)
    user_agent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

# 2. 审计日志中间件
class AuditMiddleware:
    async def __call__(self, request: Request, call_next):
        # 记录请求
        start_time = time.time()
        response = await call_next(request)
        
        # 记录审计日志
        if should_audit(request):
            await log_audit(
                tenant_id=request.state.tenant_id,
                user_id=request.state.user_id,
                action=get_action(request),
                resource_type=get_resource_type(request),
                resource_id=get_resource_id(request),
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )
        
        return response

# 3. 审计日志查询
async def get_audit_logs(
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
    resource_type: Optional[str] = None
):
    query = db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.timestamp >= start_date,
        AuditLog.timestamp <= end_date
    )
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    return await query.all()
```

### 合规性配置

```yaml
# config/compliance.yaml
compliance:
  gdpr:
    enabled: true
    data_retention_days: 90
    right_to_be_forgotten: true
    data_portability: true
    
  hipaa:
    enabled: false
    encryption_required: true
    audit_logging_required: true
    access_controls_required: true
    
  soc2:
    enabled: true
    access_logging: true
    change_management: true
    incident_response: true
    
  pci_dss:
    enabled: false
    encryption_required: true
    access_controls_required: true
    vulnerability_scanning: true
```

---

## 高可用性配置

### 数据库高可用

```yaml
# PostgreSQL HA配置 (使用Patroni)
scope: xagent-db
namespace: /xagent/db/
name: postgres-1

postgresql:
  use_pg_rewind: true
  pg_ctlcluster: /usr/lib/postgresql/14/bin/pg_ctl
  pgpass: /var/lib/postgresql/.pgpass
  parameters:
    max_connections: 1000
    shared_buffers: 256MB
    effective_cache_size: 1GB
    maintenance_work_mem: 64MB
    checkpoint_completion_target: 0.9
    wal_buffers: 16MB
    default_statistics_target: 100
    random_page_cost: 1.1
    effective_io_concurrency: 200
    work_mem: 262kB
    min_wal_size: 1GB
    max_wal_size: 4GB
    max_worker_processes: 4
    max_parallel_workers_per_gather: 2
    max_parallel_workers: 4
    max_parallel_maintenance_workers: 2

etcd:
  hosts:
  - 10.0.1.10:2379
  - 10.0.1.11:2379
  - 10.0.1.12:2379

ha:
  watchdog:
    mode: automatic
    device: /dev/watchdog
    safety_margin: 5
```

### 应用层高可用

```python
# 1. 健康检查
@router.get("/health")
async def health_check():
    checks = {
        "database": await check_database(),
        "cache": await check_cache(),
        "vector_db": await check_vector_db(),
        "external_apis": await check_external_apis()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if all_healthy else "degraded", "checks": checks}
    )

# 2. 优雅关闭
@app.on_event("shutdown")
async def shutdown_event():
    # 等待现有请求完成
    await wait_for_pending_requests(timeout=30)
    
    # 关闭数据库连接
    await db.close()
    
    # 关闭缓存连接
    await cache.close()
    
    logger.info("Application shutdown complete")

# 3. 断路器
from pybreaker import CircuitBreaker

external_api_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[
        lambda cb: logger.warning(f"Circuit breaker {cb.name} opened")
    ]
)

@external_api_breaker
async def call_external_api(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            return await response.json()
```

---

## 性能和扩展性

### 性能基准

```
API响应时间:
- 创建工作流: < 100ms
- 列表工作流: < 200ms (20项)
- 执行工作流: < 500ms (启动)
- 查询内存: < 100ms

吞吐量:
- API: 1000+ RPS
- 并发工作流: 100+
- 内存查询: 10000+ QPS

资源使用:
- CPU: < 70% 正常负载
- 内存: < 80% 正常负载
- 磁盘: < 85% 容量
```

### 扩展性配置

```yaml
# kubernetes/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xagent-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: xagent-api
  minReplicas: 3
  maxReplicas: 20
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
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 2
        periodSeconds: 30
      selectPolicy: Max
```

---

## 监控和告警

### 监控指标

```python
# Prometheus指标
from prometheus_client import Counter, Gauge, Histogram

# 请求指标
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 5]
)

# 业务指标
workflows_total = Counter(
    'workflows_total',
    'Total workflows created',
    ['tenant_id', 'status']
)

workflow_duration = Histogram(
    'workflow_duration_seconds',
    'Workflow execution duration',
    ['tenant_id'],
    buckets=[1, 5, 10, 30, 60, 300]
)

# 系统指标
database_connections = Gauge(
    'database_connections',
    'Active database connections'
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate'
)
```

### 告警规则

```yaml
# prometheus/alerts.yaml
groups:
- name: xagent
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate detected"
      
  - alert: HighLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
    for: 5m
    annotations:
      summary: "High API latency detected"
      
  - alert: DatabaseConnectionPoolExhausted
    expr: database_connections > 90
    for: 2m
    annotations:
      summary: "Database connection pool nearly exhausted"
      
  - alert: LowCacheHitRate
    expr: cache_hit_rate < 0.7
    for: 10m
    annotations:
      summary: "Cache hit rate is low"
```

---

## 支持和SLA

### SLA承诺

```
可用性: 99.9%
- 月度停机时间: < 43.2分钟
- 响应时间: < 100ms (p95)
- 错误率: < 0.1%

支持级别:
- 关键问题: 1小时响应
- 高优先级: 4小时响应
- 中优先级: 8小时响应
- 低优先级: 24小时响应

维护窗口:
- 计划维护: 每月第二个周日 02:00-04:00 UTC
- 紧急维护: 根据需要，提前24小时通知
```

### 支持流程

```python
# 支持工单系统
class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    title = Column(String)
    description = Column(String)
    priority = Column(String)  # critical, high, medium, low
    status = Column(String)  # open, in_progress, resolved, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    assigned_to = Column(String)  # 支持工程师
    
    # SLA跟踪
    response_deadline = Column(DateTime)
    resolution_deadline = Column(DateTime)
    response_time_minutes = Column(Integer)
    resolution_time_minutes = Column(Integer)
```

---

## 总结

企业级部署需要考虑:

✓ 高可用性和容错能力  
✓ 多租户隔离和安全  
✓ 企业认证集成  
✓ 数据安全和合规  
✓ 性能和可扩展性  
✓ 监控和告警  
✓ 专业支持  

---

**文档版本**: 1.0  
**最后更新**: 2026-05-29  
**维护者**: X-Agent企业支持团队
