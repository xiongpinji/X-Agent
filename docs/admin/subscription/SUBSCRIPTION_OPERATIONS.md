# X-Agent 订阅管理系统 运维文档

## 目录

1. [系统架构](#系统架构)
2. [部署指南](#部署指南)
3. [配置管理](#配置管理)
4. [监控告警](#监控告警)
5. [故障排查](#故障排查)
6. [性能优化](#性能优化)
7. [备份恢复](#备份恢复)
8. [安全加固](#安全加固)

## 系统架构

### 核心组件

```
┌─────────────────────────────────────────────────────────┐
│                    API Gateway                          │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Subscription │ │    Quota     │ │ Automation   │
│   Manager    │ │   Manager    │ │   Service    │
└──────────────┘ └──────────────┘ └──────────────┘
        │            │                    │
        └────────────┼────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   PostgreSQL Database   │
        │  (Subscriptions, Quota) │
        └─────────────────────────┘
```

### 数据库表

| 表名 | 说明 | 主要字段 |
|------|------|--------|
| subscriptions | 订阅信息 | id, tenant_id, user_id, status, renewal_date |
| quota_usage | 配额使用 | id, tenant_id, user_id, api_calls_used, tokens_used |
| billing_history | 计费历史 | id, tenant_id, event_type, subscription_id |
| pricing_tiers | 价格层级 | id, tier_name, monthly_price, monthly_api_calls |

## 部署指南

### 前置条件

- Python 3.10+
- PostgreSQL 13+
- Redis 6.0+
- Docker & Docker Compose (可选)

### 安装步骤

1. **克隆代码**
```bash
git clone https://github.com/xagent/xagent.git
cd xagent/backend
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **初始化数据库**
```bash
# 创建数据库
createdb xagent_billing

# 运行迁移
alembic upgrade head
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，设置数据库连接、支付提供商等
```

5. **启动服务**
```bash
# 开发环境
uvicorn app.web:app --reload --host 0.0.0.0 --port 8000

# 生产环境
gunicorn app.web:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Docker 部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "app.web:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

```bash
# 构建镜像
docker build -t xagent-billing:latest .

# 运行容器
docker run -d \
  -e DATABASE_URL=postgresql://user:pass@db:5432/xagent_billing \
  -e REDIS_URL=redis://redis:6379 \
  -p 8000:8000 \
  xagent-billing:latest
```

## 配置管理

### 环境变量

```bash
# 数据库
DATABASE_URL=postgresql://user:password@localhost:5432/xagent_billing
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# 支付提供商
STRIPE_API_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

ALIPAY_APP_ID=xxx
ALIPAY_PRIVATE_KEY=xxx

WECHAT_APP_ID=xxx
WECHAT_APP_SECRET=xxx

# 邮件通知
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=xxx@gmail.com
SMTP_PASSWORD=xxx

# 日志
LOG_LEVEL=INFO
LOG_FORMAT=json

# 自动化任务
AUTO_RENEWAL_ENABLED=true
AUTO_RENEWAL_HOUR=0
AUTO_RENEWAL_MINUTE=0

EXPIRATION_REMINDER_ENABLED=true
EXPIRATION_REMINDER_HOUR=9
EXPIRATION_REMINDER_MINUTE=0
```

### 配置文件示例

```yaml
# config/subscription.yaml
subscription:
  # 试用期配置
  trial_periods:
    - name: "7_days"
      days: 7
    - name: "14_days"
      days: 14
    - name: "30_days"
      days: 30

  # 自动续费配置
  auto_renewal:
    enabled: true
    max_retries: 3
    retry_intervals: [1, 3, 7]  # 天数

  # 配额告警配置
  quota_alerts:
    - level: 80
      severity: warning
    - level: 90
      severity: critical
    - level: 100
      severity: critical

  # 过期提醒配置
  expiration_reminders:
    - days_before: 7
    - days_before: 3
    - days_before: 1
```

## 监控告警

### 关键指标

```python
# Prometheus 指标
subscription_total{status="active"}  # 活跃订阅数
subscription_total{status="paused"}  # 暂停订阅数
subscription_total{status="expired"} # 过期订阅数

auto_renewal_success_total  # 自动续费成功数
auto_renewal_failure_total  # 自动续费失败数

quota_usage_percent{quota_type="api_calls"}  # API 调用配额使用率
quota_usage_percent{quota_type="tokens"}     # Token 配额使用率
quota_usage_percent{quota_type="storage"}    # 存储配额使用率

payment_success_total  # 支付成功数
payment_failure_total  # 支付失败数
```

### 告警规则

```yaml
# prometheus/rules.yaml
groups:
  - name: subscription
    rules:
      # 自动续费失败率过高
      - alert: HighAutoRenewalFailureRate
        expr: |
          (rate(auto_renewal_failure_total[5m]) / 
           (rate(auto_renewal_success_total[5m]) + rate(auto_renewal_failure_total[5m]))) > 0.1
        for: 5m
        annotations:
          summary: "自动续费失败率过高"
          description: "过去5分钟内自动续费失败率超过10%"

      # 配额使用率过高
      - alert: HighQuotaUsage
        expr: quota_usage_percent > 90
        for: 5m
        annotations:
          summary: "配额使用率过高"
          description: "{{ $labels.quota_type }} 配额使用率超过90%"

      # 支付失败
      - alert: PaymentFailure
        expr: rate(payment_failure_total[5m]) > 0
        for: 1m
        annotations:
          summary: "支付处理失败"
          description: "检测到支付处理失败"
```

### 日志监控

```bash
# 查看订阅相关日志
docker logs xagent-billing | grep "subscription"

# 查看自动续费日志
docker logs xagent-billing | grep "auto_renewal"

# 查看错误日志
docker logs xagent-billing | grep "ERROR"
```

## 故障排查

### 常见问题

#### 1. 自动续费失败

**症状**: 订阅未按时续费

**排查步骤**:
```bash
# 1. 检查自动续费任务是否运行
docker logs xagent-billing | grep "process_auto_renewals"

# 2. 检查数据库中的订阅状态
psql -U user -d xagent_billing -c "
  SELECT id, user_id, status, renewal_date, auto_renew 
  FROM subscriptions 
  WHERE renewal_date < NOW() AND status = 'active'
"

# 3. 检查支付提供商连接
curl -X GET https://api.stripe.com/v1/account \
  -H "Authorization: Bearer sk_test_xxx"

# 4. 查看错误日志
docker logs xagent-billing | grep "auto_renewal" | grep "ERROR"
```

**解决方案**:
- 检查支付提供商 API 密钥是否正确
- 检查网络连接是否正常
- 手动触发续费任务: `python -m app.tasks.subscription_automation process_auto_renewals`

#### 2. 配额限制不生效

**症状**: 用户超过配额仍能继续使用

**排查步骤**:
```bash
# 1. 检查配额记录
psql -U user -d xagent_billing -c "
  SELECT * FROM quota_usage 
  WHERE user_id = 'user_123'
"

# 2. 检查配额检查逻辑
grep -r "check_quota" app/core/

# 3. 查看 API 调用日志
docker logs xagent-billing | grep "quota_check"
```

**解决方案**:
- 确保在 API 调用前调用 `check_quota()`
- 检查配额初始化是否正确
- 重置配额: `python -m app.tasks.quota_manager reset_quota --user_id user_123`

#### 3. 数据库连接超时

**症状**: 频繁出现数据库连接错误

**排查步骤**:
```bash
# 1. 检查数据库连接池状态
psql -U user -d xagent_billing -c "
  SELECT count(*) FROM pg_stat_activity 
  WHERE datname = 'xagent_billing'
"

# 2. 检查连接池配置
grep -r "DATABASE_POOL_SIZE" .env

# 3. 查看慢查询
psql -U user -d xagent_billing -c "
  SELECT query, mean_time FROM pg_stat_statements 
  ORDER BY mean_time DESC LIMIT 10
"
```

**解决方案**:
- 增加连接池大小: `DATABASE_POOL_SIZE=50`
- 优化慢查询
- 添加数据库索引

## 性能优化

### 数据库优化

```sql
-- 创建索引
CREATE INDEX idx_subscription_renewal_date 
  ON subscriptions(renewal_date) 
  WHERE status = 'active';

CREATE INDEX idx_quota_usage_period 
  ON quota_usage(tenant_id, user_id, period_start, period_end);

-- 分析查询计划
EXPLAIN ANALYZE
SELECT * FROM subscriptions 
WHERE renewal_date < NOW() AND status = 'active';
```

### 缓存优化

```python
# 使用 Redis 缓存配额信息
from backend.app.core.cache import get_cache

async def get_quota_cached(tenant_id: str, user_id: str):
    cache_key = f"quota:{tenant_id}:{user_id}"
    
    # 尝试从缓存获取
    cached = await get_cache().get(cache_key)
    if cached:
        return cached
    
    # 从数据库获取
    quota = await get_quota_info(tenant_id, user_id)
    
    # 缓存 5 分钟
    await get_cache().set(cache_key, quota, ex=300)
    
    return quota
```

### 批量处理优化

```python
# 批量处理自动续费
async def process_auto_renewals_batch(batch_size: int = 100):
    offset = 0
    while True:
        subscriptions = await get_subscriptions_for_renewal(
            limit=batch_size,
            offset=offset
        )
        
        if not subscriptions:
            break
        
        # 并行处理
        tasks = [
            process_renewal(sub) 
            for sub in subscriptions
        ]
        await asyncio.gather(*tasks)
        
        offset += batch_size
```

## 备份恢复

### 数据库备份

```bash
# 全量备份
pg_dump -U user -d xagent_billing > backup_$(date +%Y%m%d_%H%M%S).sql

# 压缩备份
pg_dump -U user -d xagent_billing | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# 定时备份 (crontab)
0 2 * * * pg_dump -U user -d xagent_billing | gzip > /backups/xagent_billing_$(date +\%Y\%m\%d).sql.gz
```

### 数据恢复

```bash
# 从备份恢复
psql -U user -d xagent_billing < backup_20240101_000000.sql

# 从压缩备份恢复
gunzip -c backup_20240101_000000.sql.gz | psql -U user -d xagent_billing
```

### 增量备份

```bash
# 使用 WAL 归档进行增量备份
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /wal_archive/%f'
```

## 安全加固

### 访问控制

```python
# 实现基于角色的访问控制 (RBAC)
from backend.app.core.security import require_role

@router.post("/subscriptions")
@require_role("admin", "user")
async def create_subscription(request: CreateSubscriptionRequest):
    pass
```

### 数据加密

```python
# 加密敏感数据
from cryptography.fernet import Fernet

def encrypt_payment_method_id(payment_method_id: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.encrypt(payment_method_id.encode()).decode()

def decrypt_payment_method_id(encrypted: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted.encode()).decode()
```

### 审计日志

```python
# 记录所有关键操作
async def log_subscription_event(
    tenant_id: str,
    user_id: str,
    event_type: str,
    details: dict
):
    event = BillingHistory(
        id=str(uuid4()),
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        details=details,
    )
    session.add(event)
    await session.commit()
```

### 速率限制

```python
# 实现 API 速率限制
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/subscriptions")
@limiter.limit("100/minute")
async def create_subscription(request: CreateSubscriptionRequest):
    pass
```

## 故障恢复计划

### RTO/RPO 目标

- **RTO (恢复时间目标)**: 1 小时
- **RPO (恢复点目标)**: 15 分钟

### 灾难恢复步骤

1. **检测故障** (5 分钟)
   - 监控系统检测到异常
   - 发送告警通知

2. **初步诊断** (10 分钟)
   - 检查服务状态
   - 查看错误日志
   - 确定故障范围

3. **启动恢复** (15 分钟)
   - 切换到备用数据库
   - 重启服务
   - 验证功能

4. **验证恢复** (10 分钟)
   - 运行健康检查
   - 验证数据一致性
   - 确认服务可用

5. **事后分析** (24 小时)
   - 分析故障原因
   - 制定改进措施
   - 更新文档

## 联系方式

- **技术支持**: support@xagent.com
- **紧急热线**: +86-xxx-xxxx-xxxx
- **文档**: https://docs.xagent.com/billing
